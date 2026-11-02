"""Versioned validation, provenance and conservative planning eligibility."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib

from jsonschema import Draft202012Validator

from .extract import empty_data, FIELDS
from .urls import clean_url, platform

DATA_PROPERTIES = {
    **{key: {"type": ["string", "null"]} for key in ("title", "yield_text", "category")},
    **{key: {"type": "array", "items": {"type": "string", "minLength": 1}} for key in ("ingredients", "tags", "instructions")},
    **{key: {"type": ["number", "null"], "minimum": 0} for key in ("prep_minutes", "cook_minutes", "total_minutes")},
    "servings": {"type": ["number", "null"], "exclusiveMinimum": 0},
}
DATA_SCHEMA = {"type": "object", "properties": DATA_PROPERTIES, "required": list(FIELDS), "additionalProperties": False}
RECORD_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["id", "urls", "platform", "data", "provenance", "manual", "experience", "reviewed_for_planning", "check", "quality"],
    "properties": {
        "id": {"type": "string", "pattern": "^recipe-[a-f0-9]{16}$"},
        "urls": {"type": "array", "uniqueItems": True, "items": {"type": "string"}},
        "platform": {"enum": ["website", "instagram", "tiktok", "name_only"]},
        "data": DATA_SCHEMA,
        "provenance": {"type": "object", "propertyNames": {"enum": list(FIELDS)}, "additionalProperties": {
            "type": "object", "required": ["url", "method"], "additionalProperties": False,
            "properties": {"url": {"type": ["string", "null"]}, "method": {"type": "string"}}}},
        "manual": {"type": "object", "properties": DATA_PROPERTIES, "additionalProperties": False},
        "experience": {"enum": ["unrated", "tried", "liked", "disliked"]},
        "reviewed_for_planning": {"type": "boolean"},
        "check": {"type": "object", "additionalProperties": False,
            "required": ["status", "last_attempt", "last_success", "next_attempt", "http_status", "error", "etag", "last_modified", "validator_url"],
            "properties": {
                "status": {"enum": ["unverified", "local_source", "ok", "blocked", "not_found", "rate_limited", "network_error", "unsafe_url", "robots_denied", "robots_unavailable", "crawl_delay", "server_error", "http_error", "unsupported_content", "response_too_large", "invalid_redirect", "redirect_limit"]},
                **{k: {"type": ["string", "null"]} for k in ("last_attempt", "last_success", "next_attempt", "error", "etag", "last_modified", "validator_url")},
                "http_status": {"type": ["integer", "null"]}}},
        "quality": {"type": "object", "additionalProperties": False,
            "required": ["completeness", "missing", "issues", "planning_ready"],
            "properties": {"completeness": {"enum": ["complete", "partial", "name_only"]},
                "missing": {"type": "array", "items": {"enum": list(FIELDS)}},
                "issues": {"type": "array", "items": {"type": "string"}},
                "planning_ready": {"type": "boolean"}}},
    },
}
CATALOG_SCHEMA = {"type": "object", "required": ["schema_version", "recipes"], "additionalProperties": False,
                  "properties": {"schema_version": {"const": 1}, "recipes": {"type": "array", "items": RECORD_SCHEMA}}}
PREFERENCES_SCHEMA = {
    "type": "object", "required": ["schema_version", "confirmed", "inferred", "planning"], "additionalProperties": False,
    "properties": {"schema_version": {"const": 1},
        "confirmed": {"type": "object", "additionalProperties": False,
            "required": ["liked_ingredients", "disliked_ingredients", "preferred_cuisines", "dietary_restrictions", "max_total_minutes"],
            "properties": {**{k: {"type": "array", "items": {"type": "string"}} for k in ("liked_ingredients", "disliked_ingredients", "preferred_cuisines", "dietary_restrictions")},
                "max_total_minutes": {"type": ["number", "null"], "exclusiveMinimum": 0}}},
        "inferred": {"type": "array", "items": {"type": "object", "additionalProperties": False,
            "required": ["signal", "recipe_ids", "confirmed"],
            "properties": {"signal": {"type": "string"}, "recipe_ids": {"type": "array", "minItems": 1, "items": {"type": "string"}}, "confirmed": {"const": False}}}},
        "planning": {"type": "object", "additionalProperties": False,
            "required": ["known_meals_target", "new_meals_target", "avoid_repeat_weeks"],
            "properties": {k: {"type": ["integer", "null"], "minimum": 0} for k in ("known_meals_target", "new_meals_target", "avoid_repeat_weeks")}},
    },
}


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_record(url=None, title=None):
    identity = url or "name:" + " ".join((title or "").casefold().split())
    record = {"id": "recipe-" + hashlib.sha256(identity.encode()).hexdigest()[:16],
              "urls": [url] if url else [], "platform": platform(url) if url else "name_only",
              "data": empty_data(), "provenance": {}, "manual": {}, "experience": "unrated",
              "reviewed_for_planning": False,
              "check": {"status": "unverified", **{k: None for k in ("last_attempt", "last_success", "next_attempt", "http_status", "error", "etag", "last_modified", "validator_url")}},
              "quality": {"completeness": "name_only", "missing": [], "issues": [], "planning_ready": False}}
    if title:
        record["data"]["title"] = title
        record["provenance"]["title"] = {"url": url, "method": "import_label"}
    refresh_quality(record)
    return record


def effective_data(record):
    return {**record["data"], **record["manual"]}


def refresh_quality(record):
    data = effective_data(record)
    missing = [key for key in ("title", "ingredients", "servings", "instructions", "total_minutes", "category") if not data[key]]
    quality = record["quality"]
    quality["missing"] = missing
    quality["completeness"] = "complete" if not missing else "partial" if data["ingredients"] or data["instructions"] else "name_only"
    quality["planning_ready"] = bool(not missing and record["reviewed_for_planning"] and
        record["check"]["status"] in {"ok", "local_source"} and record["experience"] != "disliked" and
        not set(quality["issues"]) & {"multiple_recipes", "weekly_shopping_list", "access_page", "conflicting_fields", "redirect_merge_conflict", "source_now_incomplete"})


def apply_extraction(record, extracted, source_url):
    changed = False
    conflicts = []
    for key, value in extracted["data"].items():
        if value is None or value == [] or value == "":
            continue  # retain previously successful fields; still flag missing in current source
        old = record["data"][key]
        if key == "title" and old and extracted["method"] in {"metadata", "public_caption"}:
            continue  # a generic page/platform title must not replace a known dish title
        if old != value:
            changed = True
            if old and record["provenance"].get(key, {}).get("method") != "import_label":
                conflicts.append(key)
        record["data"][key] = deepcopy(value)
        record["provenance"][key] = {"url": source_url, "method": extracted["method"]}
    retained = set(record["quality"]["issues"]) & {"redirect_merge_conflict"}
    record["quality"]["issues"] = sorted(set(extracted["issues"]) | retained)
    if conflicts:
        record["quality"]["issues"].append("conflicting_fields")
    incomplete = any(not extracted["data"][k] and record["data"][k] for k in ("ingredients", "servings", "instructions"))
    if incomplete:
        record["quality"]["issues"].append("source_now_incomplete")
    if changed or incomplete:
        record["reviewed_for_planning"] = False
    refresh_quality(record)


def validate_catalog(catalog):
    Draft202012Validator(CATALOG_SCHEMA).validate(catalog)
    ids, urls = set(), set()
    for record in catalog["recipes"]:
        if record["id"] in ids:
            raise ValueError("duplicate_recipe_id")
        ids.add(record["id"])
        for url in record["urls"]:
            if clean_url(url) != url or url in urls:
                raise ValueError("duplicate_or_unclean_url")
            urls.add(url)
        for source in record["provenance"].values():
            if source["url"] is not None and clean_url(source["url"]) != source["url"]:
                raise ValueError("unclean_provenance_url")
        for key in ("last_attempt", "last_success", "next_attempt"):
            if record["check"][key] is not None and datetime.fromisoformat(record["check"][key]).tzinfo is None:
                raise ValueError("timestamp_requires_timezone")
        expected = deepcopy(record)
        refresh_quality(expected)
        if record["quality"] != expected["quality"]:
            raise ValueError("stale_quality")


def validate_preferences(preferences, catalog):
    Draft202012Validator(PREFERENCES_SCHEMA).validate(preferences)
    ids = {r["id"] for r in catalog["recipes"]}
    for signal in preferences["inferred"]:
        if not set(signal["recipe_ids"]) <= ids:
            raise ValueError("unknown_preference_evidence")
    targets = preferences["planning"]
    if all(targets[k] is not None for k in ("known_meals_target", "new_meals_target")) and targets["known_meals_target"] + targets["new_meals_target"] != 5:
        raise ValueError("meal_targets_must_sum_to_five")
