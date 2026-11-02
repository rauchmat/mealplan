"""Run with python -m tools.recipe_import (from the repository root)."""
import argparse
import json
from pathlib import Path
import sys

from jsonschema.exceptions import ValidationError

from .importer import run_import
from .inputs import load_input
from .model import refresh_quality, validate_catalog, validate_preferences
from .network import Fetcher
from .storage import atomic_json, read_json


def main(argv=None):
    parser = argparse.ArgumentParser(description="Bereinigte Rezeptkataloge prüfen; keine WhatsApp-Rohchats.")
    parser.add_argument("--input", type=Path, help="Bereinigter JSON-/CSV-Katalog")
    parser.add_argument("--catalog", type=Path, default=Path("data/recipes.json"))
    parser.add_argument("--preferences", type=Path, default=Path("data/preferences.json"))
    parser.add_argument("--report", type=Path, default=Path("reports/recipe-import.json"))
    parser.add_argument("--dry-run", action="store_true", help="Abrufen und Änderungen berichten, Katalog nicht schreiben")
    parser.add_argument("--offline", action="store_true", help="Nur Eingaben aufnehmen, keine HTTP-Abfragen")
    parser.add_argument("--force", action="store_true", help="Auch noch nicht fällige Einträge erneut prüfen")
    parser.add_argument("--limit", type=int, default=1000, help="Maximale Zahl geprüfter Katalogeinträge")
    parser.add_argument("--validate", action="store_true", help="Nur Katalog und Geschmacksprofil validieren")
    args = parser.parse_args(argv)
    if args.limit < 0:
        parser.error("--limit muss mindestens 0 sein")
    if args.catalog.resolve() in {args.report.resolve(), args.preferences.resolve()} or (args.input and args.input.resolve() in {args.catalog.resolve(), args.report.resolve(), args.preferences.resolve()}):
        parser.error("Eingabe-, Ausgabe- und Profildateien müssen getrennt sein")
    try:
        original = args.catalog.read_bytes() if args.catalog.exists() else None
        catalog = json.loads(original) if original is not None else {"schema_version": 1, "recipes": []}
        # Quality is derived, so manual changes can be validated/recomputed without HTTP.
        if not args.validate:
            for record in catalog["recipes"]:
                refresh_quality(record)
        validate_catalog(catalog)
        preferences = read_json(args.preferences)
        if preferences is None:
            raise ValueError("preferences_file_missing")
        validate_preferences(preferences, catalog)
        if args.validate:
            print("Rezeptkatalog und Geschmacksprofil sind gültig.")
            return 0
        rows, rejected = load_input(args.input) if args.input else ([], [])
        fetcher = None if args.offline else Fetcher()
        try:
            report = run_import(catalog, rows, fetcher, force=args.force, limit=args.limit)
        finally:
            if fetcher:
                fetcher.close()
        report.update(rejected=rejected, dry_run=args.dry_run)
        validate_preferences(preferences, catalog)
        # Rejecting any input prevents a silent partial write; report row numbers only.
        if rejected:
            report["catalog_written"] = False
        else:
            report["catalog_written"] = not args.dry_run
            if not args.dry_run:
                atomic_json(args.catalog, catalog, original, validate_catalog)
        atomic_json(args.report, report, args.report.read_bytes() if args.report.exists() else None)
        print(json.dumps({k: report[k] for k in ("added", "input_duplicates", "checked", "skipped", "catalog_written")}, ensure_ascii=False))
        print(f"Bericht: {args.report}")
        return 2 if rejected else 0
    except (OSError, ValueError, KeyError, TypeError, ValidationError) as exc:
        # Never echo raw input, URL queries, HTTP responses or credentials.
        reason = exc.message.splitlines()[0] if isinstance(exc, ValidationError) else str(exc)
        safe = reason if reason.replace("_", "").isalnum() and len(reason) < 80 else type(exc).__name__
        print(f"Import abgebrochen: {safe}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
