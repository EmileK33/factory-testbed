"""Loading the raw settlement feed."""

from __future__ import annotations

import json
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "records.json"


def load_records(path: str | Path | None = None) -> list[dict]:
    """Return the feed as a list of dicts, in file order.

    Each element is a fresh dict, so callers may mutate what they get back
    without disturbing another caller's view of the same feed.

    Raises ValueError if the payload is not a JSON array, or if an element is
    not a JSON object; the message names the file and the element's index.
    """
    target = Path(path) if path is not None else DATA_PATH
    with target.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ValueError(f"{target}: expected a JSON array of records")
    for index, row in enumerate(payload):
        if not isinstance(row, dict):
            raise ValueError(
                f"{target}: element at index {index} must be a JSON object, "
                f"got {type(row).__name__}"
            )
    return [dict(row) for row in payload]
