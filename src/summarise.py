"""Counting what the feed produced."""

from __future__ import annotations

from src.validate import validate_record


def summarise(records: list[dict]) -> dict:
    """Return the feed's counts, along with the ids that were rejected.

    When anything is rejected, ``rejected_by_reason`` maps each reason
    ``validate_record()`` gave to the number of records that fell to it, keys
    sorted. A record counts under its first failing reason only, so the counts
    sum to ``len(rejected)``. Like ``rejected``, the key is absent when nothing
    is rejected.

    ``by_tag`` maps each tag to the number of accepted records carrying it. The
    tags are read from the normalised record ``check_record()`` returns, the same
    field the report's tags column renders. A tag repeated within one record
    counts once for that record; tags are compared exactly as ``parse_tags()``
    returns them (case-sensitive); rejected records add nothing. The key is always
    present, and keys are sorted by tag.
    """
    result = {"total": len(records), "accepted": 0}

    rejected = []
    reason_counts: dict[str, int] = {}
    tag_counts: dict[str, int] = {}
    for record in records:
        checked, reason = validate_record(record)
        if checked is None:
            rejected.append(record.get("id", "<unlabelled>"))
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        else:
            result["accepted"] += 1
            for tag in set(checked["tags"]):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

    if rejected:
        result["rejected"] = rejected
        result["rejected_by_reason"] = dict(sorted(reason_counts.items()))
    result["by_tag"] = dict(sorted(tag_counts.items()))
    return result
