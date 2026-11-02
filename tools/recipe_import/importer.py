"""Incremental importing; report uncertain matches without inventing facts."""
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

from .extract import extract
from .model import apply_extraction, effective_data, new_record, refresh_quality, validate_catalog
from .urls import clean_url


def due(record, now, force=False):
    if force:
        return True
    date = record["check"]["next_attempt"]
    return date is None or datetime.fromisoformat(date) <= now


def merge_redirect(catalog, record, final_url):
    other = next((r for r in catalog["recipes"] if r is not record and final_url in r["urls"]), None)
    if other is None:
        if final_url not in record["urls"]:
            record["urls"].append(final_url)
        return record
    # Preserve both curated records if human edits disagree; don't silently drop them.
    if (record["manual"] and record["manual"] != other["manual"]) or (record["experience"] != "unrated" and record["experience"] != other["experience"]):
        record["quality"]["issues"] = sorted(set(record["quality"]["issues"] + ["redirect_merge_conflict"]))
        record["reviewed_for_planning"] = False
        return record
    other["urls"] = sorted(set(other["urls"] + record["urls"]))
    if record["manual"]:
        other["manual"] = record["manual"]
    if record["experience"] != "unrated":
        other["experience"] = record["experience"]
    for key, value in record["data"].items():
        if not other["data"][key] and value:
            other["data"][key] = value
            if key in record["provenance"]:
                other["provenance"][key] = record["provenance"][key]
    other["reviewed_for_planning"] = False
    catalog["recipes"].remove(record)
    return other


def duplicate_candidates(catalog):
    candidates = []
    recipes = catalog["recipes"]
    for i, a in enumerate(recipes):
        da = effective_data(a)
        for b in recipes[i + 1:]:
            db = effective_data(b)
            titles = [" ".join((d["title"] or "").casefold().split()) for d in (da, db)]
            ingredients = [set(x.casefold() for x in d["ingredients"]) for d in (da, db)]
            similar_title = all(titles) and SequenceMatcher(None, *titles).ratio() >= .88
            same_ingredients = len(ingredients[0]) >= 3 and ingredients[0] == ingredients[1]
            if similar_title or same_ingredients:
                candidates.append({"ids": [a["id"], b["id"]], "reason": "similar_title" if similar_title else "same_ingredients"})
    return candidates


def run_import(catalog, rows, fetcher=None, now=None, force=False, limit=1000):
    validate_catalog(catalog)
    now = now or datetime.now(timezone.utc)
    stamp = now.isoformat(timespec="seconds")
    report = {"added": 0, "input_duplicates": 0, "checked": 0, "skipped": 0, "results": [], "duplicate_candidates": []}
    for row in rows:
        url, title = row["url"], row["title"]
        candidate = new_record(url, title)
        existing = next((r for r in catalog["recipes"] if (url and url in r["urls"]) or (not url and r["id"] == candidate["id"])), None)
        if existing:
            report["input_duplicates"] += 1
        else:
            catalog["recipes"].append(candidate)
            report["added"] += 1
    for record in list(catalog["recipes"]):
        if record not in catalog["recipes"]:
            continue
        if not record["urls"] or fetcher is None or not due(record, now, force) or report["checked"] >= limit:
            report["skipped"] += 1
            continue
        url = record["urls"][0]
        check = record["check"]
        conditional = {}
        if check["last_success"] and check["status"] == "ok" and check["validator_url"] == url:
            if check["etag"]:
                conditional["If-None-Match"] = check["etag"]
            if check["last_modified"]:
                conditional["If-Modified-Since"] = check["last_modified"]
        result = fetcher.fetch(url, conditional)
        report["checked"] += 1
        if result.status == "not_modified" and not conditional:
            result.status, result.error = "http_error", "unexpected_not_modified"
        if result.status in {"ok", "not_modified"}:
            record = merge_redirect(catalog, record, clean_url(result.url))
            check = record["check"]
        check.update(last_attempt=stamp, http_status=result.http_status, error=result.error)
        check["status"] = "ok" if result.status == "not_modified" else result.status
        retry = result.retry_seconds
        if result.status == "ok":
            extracted = extract(result.html, result.url)
            source_url = result.url
            # Follow at most one explicit public recipe link, one level deep.
            if len(set(extracted["links"])) == 1:
                linked_url = extracted["links"][0]
                linked = fetcher.fetch(linked_url)
                if linked.status == "ok":
                    linked_data = extract(linked.html, linked.url)
                    if linked_data["data"]["ingredients"] and linked_data["method"] in {"jsonld", "microdata", "rdfa", "house_html"}:
                        extracted, source_url = linked_data, clean_url(linked.url)
                        # Keep social and recipe URLs as aliases of one recipe.
                        record = merge_redirect(catalog, record, source_url)
                        check = record["check"]
                        check.update(last_attempt=stamp, http_status=result.http_status, error=None, status="ok")
                    else:
                        extracted["issues"].append("linked_recipe_incomplete")
                else:
                    extracted["issues"].append("linked_recipe_unavailable")
            elif len(set(extracted["links"])) > 1:
                extracted["issues"].append("multiple_recipe_links")
            apply_extraction(record, extracted, source_url)
            if "access_page" in extracted["issues"]:
                check.update(status="blocked", error="access_page")
            else:
                check["last_success"] = stamp
            # Validators must refer to the primary URL, not its linked recipe.
            check["etag"] = result.headers.get("etag")
            check["last_modified"] = result.headers.get("last-modified")
            check["validator_url"] = url if result.url == url else None
        elif result.status == "not_modified":
            check["last_success"] = stamp
        if retry is None:
            retry = 30 * 86400 if check["status"] == "ok" and record["quality"]["completeness"] == "complete" else 7 * 86400
        try:
            next_attempt = now + timedelta(seconds=max(1, retry))
        except OverflowError:
            next_attempt = datetime.max.replace(tzinfo=timezone.utc)
        check["next_attempt"] = next_attempt.isoformat(timespec="seconds")
        refresh_quality(record)
        report["results"].append({"id": record["id"], "status": check["status"], "completeness": record["quality"]["completeness"], "issues": record["quality"]["issues"]})
    for record in catalog["recipes"]:
        refresh_quality(record)
    report["duplicate_candidates"] = duplicate_candidates(catalog)
    validate_catalog(catalog)
    return report
