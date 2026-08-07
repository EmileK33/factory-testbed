"""Counting what the feed produced."""

from __future__ import annotations

from src.validate import check_record


def summarise(records: list[dict]) -> dict:
    """Return the feed's counts, along with the ids that were rejected."""
    result = {"total": len(records), "accepted": 0}

    rejected = []
    by_tag: dict[str, int] = {}
    for record in records:
        checked = check_record(record)
        if checked is None:
            rejected.append(record.get("id", "<unlabelled>"))
        else:
            result["accepted"] += 1
            for tag in checked["tags"]:
                by_tag[tag] = by_tag.get(tag, 0) + 1

    if rejected:
        result["rejected"] = rejected
    result["by_tag"] = by_tag
    return result
