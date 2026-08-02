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

    ``by_tag``'s presence is structural, not conditional: it is part of
    ``result``'s initial construction and mutated in place, rather than
    assigned by a separate line later that a guard could be wrapped around.
    This is deliberate -- an "accepted records exist but none of them are
    tagged" state is reachable (``check_record()`` accepts a record with no
    ``tags`` column and normalises it to ``[]``) but is not present in any
    fixture this repo ships, so a conditional attach here would be a guard
    that only well-formed, untagged-but-accepted input can trip -- exactly
    the shape least likely to be caught by example-based tests alone.
    """
    result = {"total": len(records), "accepted": 0, "by_tag": {}}

    rejected = []
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
                result["by_tag"][tag] = result["by_tag"].get(tag, 0) + 1

    if rejected:
        result["rejected"] = rejected
    return result
