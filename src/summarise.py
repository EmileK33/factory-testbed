"""Counting what the feed produced."""

from __future__ import annotations

from src.validate import check_record


def summarise(records: list[dict]) -> dict:
    """Return the feed's counts, along with the ids that were rejected."""
    result = {"total": len(records), "accepted": 0, "source": "branch-a"}

    rejected = []
    for record in records:
        if check_record(record) is None:
            rejected.append(record.get("id", "<unlabelled>"))
        else:
            result["accepted"] += 1

    if rejected:
        result["rejected"] = rejected
    return result
