"""Loading the raw settlement feed."""

from __future__ import annotations

import json
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "records.json"


def load_records(path: str | Path | None = None) -> list[dict]:
    """Return the feed as a list of dicts, in file order.

    Each element is a fresh dict, so callers may mutate what they get back
    without disturbing another caller's view of the same feed.
    Raises:
        ValueError: if the payload is not a JSON array (the message names
            only the file), or if any element of the array is not a JSON
            object -- a string, number, list, bool, or null (the message
            names the file and the element's 0-based index within the feed).
    """
    target = Path(path) if path is not None else DATA_PATH
    with target.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ValueError(f"{target}: expected a JSON array of records")
    records = []
    for index, row in enumerate(payload):
        if not isinstance(row, dict):
            raise ValueError(f"{target}: record at index {index} is not a JSON object")
        records.append(dict(row))
    return records
