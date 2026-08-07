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
            # check_record() returns None for a non-dict record too (that's its
            # first check), so record.get(...) can't be called unconditionally
            # here -- a bare string, None, or list would raise AttributeError.
            record_id = (
                record.get("id", "<unlabelled>") if isinstance(record, dict) else "<unlabelled>"
            )
            rejected.append(record_id)
        else:
            result["accepted"] += 1
            # dict.fromkeys() dedupes a record's own tag list before counting,
            # so a record whose raw tags column repeats a tag (e.g. "eu,eu")
            # still contributes at most 1 to that tag's total: by_tag counts
            # accepted records carrying a tag, not tag occurrences.
            for tag in dict.fromkeys(checked["tags"]):
                by_tag[tag] = by_tag.get(tag, 0) + 1

    if rejected:
        result["rejected"] = rejected
    result["by_tag"] = by_tag
    return result
