"""Loading the raw settlement feed."""

from __future__ import annotations

import json
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "records.json"

# JSON type name for each Python type json.load can produce. Keyed by exact type so that
# bool (a subclass of int) is reported as "boolean", never "number".
_JSON_KIND = {
    type(None): "null",
    bool: "boolean",
    int: "number",
    float: "number",
    str: "string",
    list: "array",
    dict: "object",
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
    for index, row in enumerate(payload):
        if not isinstance(row, dict):
            kind = _JSON_KIND.get(type(row), type(row).__name__)
            raise ValueError(f"{target}: element at index {index} (0-based) is not a JSON object (found {kind})")
    return [dict(row) for row in payload]
