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
            # dict.fromkeys(...) dedupes while preserving order: a record whose
            # own tags column repeats a tag (e.g. "eu,eu") must still add at
            # most 1 to that tag's count, since by_tag counts records carrying
            # a tag, not tag occurrences.
            for tag in dict.fromkeys(checked["tags"]):
                by_tag[tag] = by_tag.get(tag, 0) + 1

    if rejected:
        result["rejected"] = rejected
    result["by_tag"] = by_tag
    return result
