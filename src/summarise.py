"""Counting what the feed produced."""

from __future__ import annotations

from src.validate import check_record, reject_reason


def summarise(records: list[dict]) -> dict:
    """Return the feed's counts, the ids that were rejected, and why.

    ``rejected_count`` and ``rejection_reasons`` are always present, even when
    nothing was rejected (``0`` and ``[]`` respectively) -- unlike ``rejected``
    below, which is a pre-existing, deliberately-untouched gap: it appears
    only when non-empty. New callers must not have to special-case a missing
    key the way that one requires, and must not have to derive the rejected
    count themselves from ``total``/``accepted`` -- that arithmetic belongs
    here, once, not repeated at every call site.
    """
    result = {"total": len(records), "accepted": 0, "rejected_count": 0, "by_tag": {}}

    rejected = []
    reason_counts: dict[str, int] = {}
    for record in records:
        checked = check_record(record)
        if checked is None:
            result["rejected_count"] += 1
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
