"""Counting what the feed produced."""

from __future__ import annotations

from src.validate import check_record, reject_reason


def summarise(records: list[dict]) -> dict:
    """Return the feed's counts, the ids that were rejected, and why.

    ``rejection_reasons`` is always present, even when nothing was rejected
    (an empty list) -- unlike ``rejected`` below, which is a pre-existing,
    deliberately-untouched gap: it appears only when non-empty. New callers
    must not have to special-case a missing key the way that one requires.
    """
    result = {"total": len(records), "accepted": 0, "by_tag": {}}

    rejected = []
    reason_counts: dict[str, int] = {}
    for record in records:
        checked = check_record(record)
        if checked is None:
            rejected.append(record.get("id", "<unlabelled>"))
            reason = reject_reason(record)
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        else:
            result["accepted"] += 1
            for tag in dict.fromkeys(checked["tags"]):
                result["by_tag"][tag] = result["by_tag"].get(tag, 0) + 1

    if rejected:
        result["rejected"] = rejected
    result["rejection_reasons"] = [
        {"reason": reason, "count": count} for reason, count in reason_counts.items()
    ]
    return result
