"""Counting what the feed produced."""

from __future__ import annotations

from src.validate import check_record


def summarise(records: list[dict]) -> dict:
    """Return the feed's counts, the tag counts, and the ids that were rejected.

    ``by_tag`` maps each tag, exactly as ``check_record()`` returns it, to the
    number of accepted records carrying it: a tag repeated within one record
    counts once for that record, and rejected records contribute nothing. It is
    always present, and ``{}`` when no accepted record has a tag.
    """
    result = {"total": len(records), "accepted": 0}

    by_tag: dict[str, int] = {}
    rejected = []
    for record in records:
        checked = check_record(record)
        if checked is None:
            rejected.append(record.get("id", "<unlabelled>"))
        else:
            result["accepted"] += 1
            for tag in dict.fromkeys(checked["tags"]):
                by_tag[tag] = by_tag.get(tag, 0) + 1

    result["by_tag"] = by_tag
    if rejected:
        result["rejected"] = rejected
    return result
