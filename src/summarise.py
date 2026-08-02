"""Counting what the feed produced."""

from __future__ import annotations

from src.validate import check_record


def summarise(records: list[dict]) -> dict:
    """Return the feed's counts, along with the ids that were rejected.

    Two different presence conventions live here by design, not by accident:
    ``rejected`` is omitted when empty (it reports *anomalies*, and "no
    anomalies" is naturally silence); ``by_tag`` is always present, even as
    ``{}`` (it reports a *breakdown* of the accepted population, and a caller
    should not have to guess whether an absent key means "no tags" or "counts
    not computed"). Each key's own meaning decides its convention.
    """
    result = {"total": len(records), "accepted": 0}

    rejected = []
    by_tag: dict[str, int] = {}
    for record in records:
        checked = check_record(record)
        if checked is None:
            rejected.append(record.get("id", "<unlabelled>"))
        else:
            result["accepted"] += 1
            # A record's own tags list is deduplicated before counting: by_tag
            # counts *records carrying a tag*, not tag occurrences, so a
            # record whose tags list repeats a tag still contributes 1.
            for tag in set(checked["tags"]):
                by_tag[tag] = by_tag.get(tag, 0) + 1

    if rejected:
        result["rejected"] = rejected
    result["by_tag"] = by_tag
    return result
