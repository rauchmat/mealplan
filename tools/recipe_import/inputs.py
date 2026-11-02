"""Read only explicitly supported, curated JSON/CSV catalogs, never chat logs."""
import csv
import json
from pathlib import Path

from .urls import clean_url, UnsafeURL


def load_input(path):
    path = Path(path)
    if path.stat().st_size > 5_000_000:
        raise ValueError("input_too_large")
    if path.suffix.lower() == ".json":
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(value, list):
            rows = value
        elif isinstance(value, dict) and set(value) <= {"links", "dishes"}:
            rows = value.get("links", []) + [{"title": x} if isinstance(x, str) else x for x in value.get("dishes", [])]
        elif isinstance(value, dict) and set(value) == {"recipes"}:
            rows = value["recipes"]
        else:
            raise ValueError("unsupported_json_format")
    elif path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as stream:
            sample = stream.read(4096)
            stream.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except csv.Error:
                dialect = csv.excel
            reader = csv.DictReader(stream, dialect=dialect)
            if not reader.fieldnames or not set(reader.fieldnames) <= {"url", "link", "title", "name"}:
                raise ValueError("unsupported_csv_columns")
            rows = list(reader)
    else:
        raise ValueError("only_curated_json_or_csv")
    if not isinstance(rows, list):
        raise ValueError("input_rows_must_be_list")
    accepted, rejected = [], []
    for index, row in enumerate(rows, 1):
        if isinstance(row, str):
            row = {"url": row} if row.startswith(("http://", "https://")) else {"title": row}
        if not isinstance(row, dict) or not set(row) <= {"url", "link", "title", "name"}:
            raise ValueError("unsupported_input_fields")
        url, title = row.get("url") or row.get("link"), row.get("title") or row.get("name")
        if url is not None and not isinstance(url, str):
            rejected.append({"row": index, "reason": "invalid_url"})
            continue
        if title is not None and (not isinstance(title, str) or len(title) > 500 or "\n" in title or "\r" in title):
            rejected.append({"row": index, "reason": "invalid_title"})
            continue
        try:
            url = clean_url(url.strip()) if isinstance(url, str) and url.strip() else None
            if row.get("url") and row.get("link") and clean_url(row["url"]) != clean_url(row["link"]):
                raise UnsafeURL("ambiguous_urls")
        except UnsafeURL as exc:
            rejected.append({"row": index, "reason": str(exc)})
            continue
        title = title.strip() if title else None
        if not url and not title:
            rejected.append({"row": index, "reason": "empty_row"})
            continue
        accepted.append({"url": url, "title": title})
    return accepted, rejected
