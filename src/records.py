"""Loading the raw settlement feed."""

from __future__ import annotations

import json
from pathlib import Path

from src.validate import check_record

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "records.json"


def load_records(path: str | Path | None = None) -> list[dict]:
    """Return the feed as a list of dicts, in file order.

    Each element is a fresh dict, so callers may mutate what they get back
    without disturbing another caller's view of the same feed.
    """
    target = Path(path) if path is not None else DATA_PATH
    with target.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ValueError(f"{target}: expected a JSON array of records")
    return [dict(row) for row in payload]


def summarise_records(records: list[dict]) -> dict:
    """Return counts for *records*: how many were seen, valid, and dropped.

    A record is valid when ``check_record`` accepts it (returns a normalised
    copy rather than ``None``); that includes a record missing its ``id``
    field, which ``check_record`` always drops. Elements that are not even a
    dict (``check_record`` guards on ``isinstance``) are counted as dropped,
    not raised on.
    """
    total = len(records)
    valid = sum(1 for record in records if check_record(record) is not None)
    return {"total": total, "valid": valid, "dropped": total - valid}
