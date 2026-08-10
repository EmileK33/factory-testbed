"""Counting what the feed produced."""

from __future__ import annotations

from src.validate import check_record


def summarise(records: list[dict]) -> dict:
    """Return the feed's counts, along with the ids that were rejected.

    ``by_tag`` maps each tag to the number of ACCEPTED RECORDS carrying it --
    a record count, not an occurrence count. ``check_record()``'s normalised
    ``tags`` list is not deduplicated (a raw column of ``"na,na"`` really does
    come back as ``["na", "na"]``), so counting is done over
    ``set(checked["tags"])`` per record: a record whose tags list happens to
    repeat a tag still only adds 1 to that tag's count. Always present, even
    as ``{}`` for a feed with no accepted records or no tags among them --
    unlike ``rejected`` below, there is no existing convention to match here,
    and an unconditional key is one fewer case for a caller to special-case.
    """
    result = {"total": len(records), "accepted": 0, "by_tag": {}}

    rejected = []
    for record in records:
        checked = check_record(record)
        if checked is None:
            rejected.append(record.get("id", "<unlabelled>"))
        else:
            result["accepted"] += 1
            for tag in set(checked["tags"]):
                result["by_tag"][tag] = result["by_tag"].get(tag, 0) + 1

    if rejected:
        result["rejected"] = rejected
    return result
