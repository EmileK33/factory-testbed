"""Loading the raw settlement feed."""

from __future__ import annotations

import json
from pathlib import Path

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
    result = []
    for index, row in enumerate(payload):
        if not isinstance(row, dict):
            raise ValueError(
                f"{target}: row {index} is not a JSON object "
                f"(got {type(row).__name__})"
            )
        result.append(dict(row))
    return result
