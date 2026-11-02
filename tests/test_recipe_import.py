from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import socket

import httpx
import pytest
from jsonschema.exceptions import ValidationError

from tools.recipe_import.__main__ import main
from tools.recipe_import.extract import extract, minutes, servings
from tools.recipe_import.importer import run_import
from tools.recipe_import.inputs import load_input
from tools.recipe_import.model import apply_extraction, effective_data, new_record, refresh_quality, validate_catalog, validate_preferences
from tools.recipe_import.network import Fetcher, FetchResult, retry_delay
from tools.recipe_import.storage import atomic_json, locked
from tools.recipe_import.urls import clean_url, public_url, UnsafeURL

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"
HTML = (FIXTURES / "recipe.html").read_text()
URL = "https://recipes.example/linsen"
NOW = datetime(2026, 11, 2, tzinfo=timezone.utc)


def catalog():
    return {"schema_version": 1, "recipes": []}


class FakeFetcher:
    def __init__(self, *results):
        self.results = iter(results)
        self.calls = []

    def fetch(self, url, conditional=None):
        self.calls.append((url, conditional))
        return next(self.results)


def success(url=URL, html=HTML):
    return FetchResult("ok", url, html, 200, headers={"etag": '"v1"'})


def test_jsonld_graph_and_no_fabricated_time():
    result = extract(HTML, URL)
    assert result["method"] == "jsonld"
    assert result["data"]["servings"] == 3
    assert result["data"]["total_minutes"] == 30
    assert result["data"]["ingredients"] == ["200 g Linsen", "150 g Reis", "1 Zwiebel"]
    assert len(result["data"]["instructions"]) == 2
    assert "https://schema.org/VeganDiet" in result["data"]["tags"]
    assert extract(HTML.replace('"totalTime":"PT30M",', ""), URL)["data"]["total_minutes"] is None


@pytest.mark.parametrize("kind,markup", [
    ("microdata", '<div itemscope itemtype="https://schema.org/Recipe"><b itemprop="name">Suppe</b><span itemprop="recipeIngredient">1 l Wasser</span><span itemprop="recipeYield">3 Portionen</span></div>'),
    ("rdfa", '<div vocab="https://schema.org/" typeof="Recipe"><b property="name">Suppe</b><span property="recipeIngredient">1 l Wasser</span><span property="recipeYield">3 Portionen</span></div>'),
])
def test_other_structured_formats(kind, markup):
    result = extract(markup, URL)
    assert result["method"] == kind
    assert result["data"]["title"] == "Suppe"
    assert result["data"]["ingredients"] == ["1 l Wasser"]


@pytest.mark.parametrize("value,expected", [("PT1H15M", 75), ("P1DT2H", 1560), ("PT30S", .5), ("PT", None), ("30 Minuten", None), (None, None)])
def test_durations(value, expected):
    assert minutes(value) == expected


@pytest.mark.parametrize("value,expected", [("3 Portionen", 3), (["4"], 4), ("2–4 Portionen", None), ("12 cookies", None), ("0", None)])
def test_yield_ambiguity(value, expected):
    assert servings(value) == expected


def test_metadata_invalid_jsonld_multiple_recipes_and_access_pages():
    assert extract('<title>Nur ein Titel</title><script type="application/ld+json">{</script>', URL)["data"]["ingredients"] == []
    ambiguous = HTML + '<script type="application/ld+json">{"@type":"Recipe","name":"Anderes Rezept"}</script>'
    assert extract(ambiguous, URL)["issues"] == ["multiple_recipes"]
    assert extract('<title>Log in | Instagram</title>', URL)["issues"] == ["access_page"]
    assert extract('<form><input type="password"></form>', URL)["data"]["title"] is None


@pytest.mark.parametrize("url", ["https://www.instagram.com/reel/ABC/", "https://www.tiktok.com/@cook/video/123"])
def test_social_public_caption_and_missing_video_data(url):
    result = extract((FIXTURES / "social.html").read_text(), url)
    assert result["data"]["ingredients"] == ["200 g Linsen", "1 Zwiebel"]
    assert result["data"]["total_minutes"] is None
    assert result["data"]["servings"] == 3
    assert "caption_requires_review" in result["issues"]
    assert extract('<title>TikTok</title><video></video>', url)["data"]["ingredients"] == []


def test_tiktok_json_caption():
    caption = "Zutaten:\n1 Ei\nZubereitung:\nEi kochen."
    html = '<script type="application/json">' + json.dumps({"item": {"desc": caption}}) + '</script>'
    assert extract(html, "https://www.tiktok.com/@a/video/1")["data"]["ingredients"] == ["1 Ei"]


def test_house_and_weekly_recipe_exclusion():
    house = ROOT / "recipes/ofenlachs-kartoffelpueree-karotten.html"
    data = extract(house.read_text(), "https://rauchmat.github.io/mealplan/recipes/" + house.name)
    assert data["data"]["servings"] == 3
    assert len(data["data"]["ingredients"]) == 8
    assert data["data"]["total_minutes"] == 30
    bring = extract((ROOT / "bring/2026-W45-3.html").read_text(), "https://rauchmat.github.io/mealplan/bring/2026-W45-3.html")
    assert bring["issues"] == ["weekly_shopping_list"]
    assert bring["data"]["ingredients"] == []


@pytest.mark.parametrize("url", ["file:///etc/passwd", "http://127.0.0.1/x", "http://[::1]/", "http://169.254.169.254/", "https://localhost/", "https://a.internal/", "https://user:secret@example.com/", "https://example.com:8443/", "https://example.com/?token=secret", "https://example.com/?x=a%40b.com", "https://example.com/\nsecret"])
def test_reject_unsafe_urls(url):
    with pytest.raises(UnsafeURL):
        clean_url(url)


def test_dns_private_mixed_and_url_identity():
    resolve = lambda *a, **kw: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
    with pytest.raises(UnsafeURL):
        public_url(URL, resolve)
    assert clean_url("https://example.com/p?utm_source=chat&q=soup#x") == "https://example.com/p?q=soup"
    assert clean_url("https://instagram.com/reel/ABC?igsh=tracking") == "https://www.instagram.com/reel/ABC/"


def make_network(handler, check=clean_url):
    clock = [0.0]
    sleeps = []
    def sleep(seconds):
        sleeps.append(seconds)
        clock[0] += seconds
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return Fetcher(client, check, sleep, lambda: clock[0]), sleeps


def test_network_redirect_robots_cookies_and_conditional():
    calls = []
    def handler(req):
        calls.append(req)
        assert "cookie" not in req.headers
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        if req.url.path == "/start":
            return httpx.Response(302, headers={"location": "/end", "set-cookie": "session=private"})
        assert "if-none-match" not in req.headers
        return httpx.Response(200, text=HTML, headers={"content-type": "text/html"})
    fetcher, sleeps = make_network(handler)
    result = fetcher.fetch("https://example.com/start", {"If-None-Match": "wrong-for-target"})
    assert result.status == "ok" and result.url.endswith("/end")
    assert [r.url.path for r in calls] == ["/robots.txt", "/start", "/end"]
    assert sleeps == [2, 2]


def test_private_redirect_never_requested():
    seen = []
    def handler(req):
        seen.append(str(req.url))
        return httpx.Response(404) if req.url.path == "/robots.txt" else httpx.Response(302, headers={"location": "http://127.0.0.1/secret"})
    fetcher, _ = make_network(handler)
    result = fetcher.fetch(URL)
    assert result.status == "unsafe_url" and result.url == URL
    assert all("127.0.0.1" not in u for u in seen)


@pytest.mark.parametrize("status,expected", [(403, "blocked"), (404, "not_found"), (429, "rate_limited"), (503, "server_error")])
def test_http_statuses_and_bounded_retries(status, expected):
    seen = []
    def handler(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        seen.append(req)
        return httpx.Response(status, headers={"retry-after": "120"})
    fetcher, _ = make_network(handler)
    result = fetcher.fetch(URL)
    assert result.status == expected
    assert len(seen) == (3 if status == 503 else 1)
    if status == 429:
        assert result.retry_seconds == 120
        assert fetcher.fetch(URL).status == "rate_limited"
        assert len(seen) == 1


def test_robots_denial_and_large_crawl_delay():
    def handler(req):
        assert req.url.path == "/robots.txt"
        return httpx.Response(200, text="User-agent: *\nDisallow: /linsen\n")
    fetcher, _ = make_network(handler)
    assert fetcher.fetch(URL).status == "robots_denied"
    fetcher, _ = make_network(lambda req: httpx.Response(200, text="User-agent: *\nCrawl-delay: 120\n"))
    result = fetcher.fetch(URL)
    assert result.status == "crawl_delay" and result.retry_seconds == 120


def test_stream_limit_and_timeouts():
    def handler(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, content=b"x" * 2_000_001, headers={"content-type": "text/html"})
    fetcher, _ = make_network(handler)
    assert fetcher.fetch(URL).status == "response_too_large"
    attempts = []
    def timeout(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        attempts.append(1)
        raise httpx.ReadTimeout("secret body", request=req)
    fetcher, _ = make_network(timeout)
    assert fetcher.fetch(URL).error == "network_error"
    assert len(attempts) == 3


def test_retry_date():
    assert retry_delay("Mon, 02 Nov 2026 00:02:00 GMT", NOW) == 120
    assert retry_delay("invalid", NOW) == 3600
    assert retry_delay("Infinity", NOW) == 3600


def test_extreme_retry_after_does_not_crash_or_retry_early():
    c = catalog()
    result = FetchResult("rate_limited", URL, http_status=429, retry_seconds=1e100)
    run_import(c, [{"url": URL, "title": None}], FakeFetcher(result), NOW)
    assert c["recipes"][0]["check"]["next_attempt"].startswith("9999-")


def test_incremental_import_manual_override_and_failure_preserves_data():
    c = catalog()
    f = FakeFetcher(success())
    rows = [{"url": URL, "title": "Importlabel"}, {"url": URL, "title": None}, {"url": None, "title": "Knödel"}]
    report = run_import(c, rows, f, NOW)
    assert report["added"] == 2 and report["input_duplicates"] == 1
    record = c["recipes"][0]
    assert not record["quality"]["planning_ready"] and record["experience"] == "unrated"
    record["manual"]["title"] = "Unser Titel"
    record["reviewed_for_planning"] = True
    refresh_quality(record)
    assert record["quality"]["planning_ready"]
    run_import(c, [], f, NOW + timedelta(days=1))
    assert len(f.calls) == 1
    not_modified = FakeFetcher(FetchResult("not_modified", URL, http_status=304))
    run_import(c, [], not_modified, NOW + timedelta(days=31))
    assert not_modified.calls[0][1] == {"If-None-Match": '"v1"'}
    assert record["quality"]["planning_ready"]
    last_success = record["check"]["last_success"]
    run_import(c, [], FakeFetcher(FetchResult("blocked", URL, http_status=403)), NOW + timedelta(days=62))
    assert record["data"]["ingredients"] and effective_data(record)["title"] == "Unser Titel"
    assert record["check"]["last_success"] == last_success
    assert not record["quality"]["planning_ready"]


def test_changes_invalidate_review_and_absent_fields_keep_old_data():
    r = new_record(URL)
    apply_extraction(r, extract(HTML, URL), URL)
    r["reviewed_for_planning"] = True
    apply_extraction(r, extract(HTML.replace("200 g Linsen", "250 g Linsen"), URL), URL)
    assert not r["reviewed_for_planning"] and "conflicting_fields" in r["quality"]["issues"]
    apply_extraction(r, extract("<title>Ein Rezept</title>", URL), URL)
    assert r["data"]["ingredients"]
    assert "source_now_incomplete" in r["quality"]["issues"]


def test_merge_redirect_and_fuzzy_titles_only_reported():
    c = catalog()
    short = "https://short.example/abc"
    report = run_import(c, [{"url": URL, "title": None}, {"url": short, "title": None}], FakeFetcher(success(), success()), NOW)
    assert len(c["recipes"]) == 1 and set(c["recipes"][0]["urls"]) == {URL, short}
    report = run_import(c, [{"url": None, "title": "Linsen mit Reis"}], now=NOW)
    assert len(c["recipes"]) == 2 and report["duplicate_candidates"]


def test_social_recipe_link_follows_one_level_with_provenance():
    social = "https://www.instagram.com/reel/ABC/"
    html = '<meta name="description" content="Rezept: https://recipes.example/linsen">'
    c = catalog()
    run_import(c, [{"url": social, "title": None}], FakeFetcher(success(social, html), success()), NOW)
    r = c["recipes"][0]
    assert URL in r["urls"] and r["provenance"]["ingredients"]["url"] == URL
    assert r["check"]["validator_url"] == social


def test_input_formats_reject_raw_chat_fields_and_redact_rejected_urls(tmp_path):
    path = tmp_path / "clean.json"
    path.write_text(json.dumps({"links": [URL, URL + "?token=secret"], "dishes": ["Knödel"]}))
    rows, rejected = load_input(path)
    assert len(rows) == 2 and rejected == [{"row": 2, "reason": "sensitive_query"}]
    assert "secret" not in json.dumps(rejected)
    path.write_text('[{"sender":"Alice", "message":"Hallo"}]')
    with pytest.raises(ValueError, match="unsupported_input_fields"):
        load_input(path)
    path = tmp_path / "clean.csv"
    path.write_text("url;title\n" + URL + ";Linsen\n;Knödel\n")
    assert len(load_input(path)[0]) == 2


def test_atomic_write_conflicts_lock_and_validation(tmp_path):
    path = tmp_path / "recipes.json"
    atomic_json(path, catalog(), validator=validate_catalog)
    original = path.read_bytes()
    with pytest.raises(ValueError, match="concurrent_file_change"):
        atomic_json(path, catalog(), b"outdated")
    with locked(path):
        with pytest.raises(FileExistsError):
            atomic_json(path, catalog(), original)
    with pytest.raises(ValidationError):
        atomic_json(path, {"schema_version": 2}, original, validate_catalog)
    assert path.read_bytes() == original


def test_cli_offline_dry_run_rejection_and_repeat(tmp_path):
    cat = tmp_path / "recipes.json"
    inp = tmp_path / "clean.json"
    report = tmp_path / "report.json"
    inp.write_text(json.dumps([URL, "Knödel"]))
    args = ["--input", str(inp), "--catalog", str(cat), "--preferences", str(ROOT / "data/preferences.json"), "--report", str(report), "--offline"]
    assert main(args + ["--dry-run"]) == 0 and not cat.exists()
    assert main(args) == 0
    original = cat.read_bytes()
    assert main(args) == 0 and cat.read_bytes() == original
    inp.write_text('["https://example.com/?token=secret"]')
    assert main(args) == 2 and cat.read_bytes() == original
    assert "secret" not in report.read_text()


def test_catalog_and_preferences_validation():
    c = json.loads((ROOT / "data/recipes.json").read_text())
    validate_catalog(c)
    prefs = json.loads((ROOT / "data/preferences.json").read_text())
    validate_preferences(prefs, c)
    prefs["inferred"] = [{"signal": "Vegan", "recipe_ids": ["unknown"], "confirmed": False}]
    with pytest.raises(ValueError, match="unknown_preference_evidence"):
        validate_preferences(prefs, c)


def test_internal_jsonld_references_and_no_remote_context_fetch(monkeypatch):
    def forbidden(*a, **kw):
        raise AssertionError("parser must not request remote data")
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    html = '<script type="application/ld+json">' + json.dumps({
        "@context": "https://untrusted.example/context",
        "@graph": [{"@type": "Recipe", "name": "Suppe", "recipeInstructions": [{"@id": "#step"}]},
                   {"@id": "#step", "@type": "HowToStep", "text": "Kochen."}]
    }) + '</script>'
    result = extract(html, URL)
    assert result["data"]["instructions"] == ["Kochen."]


def test_redirect_conflict_preserves_both_human_edits():
    a, b = new_record(URL), new_record("https://short.example/abc")
    a["manual"]["title"], b["manual"]["title"] = "Titel A", "Titel B"
    for r in (a, b):
        refresh_quality(r)
    c = {"schema_version": 1, "recipes": [a, b]}
    run_import(c, [], FakeFetcher(success(), success()), NOW)
    assert len(c["recipes"]) == 2
    assert b["manual"]["title"] == "Titel B"
    assert "redirect_merge_conflict" in b["quality"]["issues"]
    assert not b["quality"]["planning_ready"]


def test_generic_title_does_not_overwrite_known_title():
    r = new_record(URL, "Unser Gericht")
    apply_extraction(r, extract("<title>Instagram</title>", URL), URL)
    assert r["data"]["title"] == "Unser Gericht"


def test_unexpected_304_does_not_verify_unknown_recipe():
    c = catalog()
    run_import(c, [{"url": URL, "title": None}], FakeFetcher(FetchResult("not_modified", URL, http_status=304)), NOW)
    assert c["recipes"][0]["check"]["status"] == "http_error"
    assert c["recipes"][0]["check"]["last_success"] is None


def test_validate_rejects_stale_persisted_quality(tmp_path):
    c = catalog()
    r = new_record(URL)
    r["quality"]["planning_ready"] = True
    c["recipes"].append(r)
    path = tmp_path / "recipes.json"
    path.write_text(json.dumps(c))
    assert main(["--validate", "--catalog", str(path), "--preferences", str(ROOT / "data/preferences.json")]) == 2


def test_malformed_input_rows_and_whitespace_names(tmp_path):
    path = tmp_path / "input.json"
    path.write_text('[{"url": 42, "title": "Ein Gericht"}, "   "]')
    rows, rejected = load_input(path)
    assert rows == [] and [r["reason"] for r in rejected] == ["invalid_url", "empty_row"]
