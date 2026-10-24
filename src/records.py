"""Loading the raw settlement feed."""

from __future__ import annotations

import json
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "records.json"

_JSON_TYPE_NAMES = {
    bool: "boolean",
    int: "number",
    float: "number",
    str: "string",
    list: "array",
    type(None): "null",
}


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
    records = []
    for index, row in enumerate(payload):
        if not isinstance(row, dict):
            kind = _JSON_TYPE_NAMES.get(type(row), type(row).__name__)
            raise ValueError(
                f"{target}: element at index {index} (counted from 0) is not a JSON object; "
                f"its JSON type is {kind}"
            )
        records.append(dict(row))
    return records
