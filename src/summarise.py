"""Counting what the feed produced."""

from __future__ import annotations

from src.validate import check_record


def summarise(records: list[dict]) -> dict:
    """Return the feed's counts, along with the ids that were rejected."""
<<<<<<< HEAD
    result = {
        "total": len(records),
        "accepted": 0,
        "source": "branch-a",
        "origin": "branch-b",
    }
=======
    result = {"total": len(records), "accepted": 0, "origin": "branch-b"}
>>>>>>> 3424b47 (T3/R7 branch B: label the summary with its origin)

    rejected = []
    for record in records:
        if check_record(record) is None:
            rejected.append(record.get("id", "<unlabelled>"))
        else:
            result["accepted"] += 1

    if rejected:
        result["rejected"] = rejected
    return result
