"""Counting what the feed produced."""

from __future__ import annotations

from src.validate import check_record, rejection_reason


def summarise(records: list[dict]) -> dict:
    """Return the feed's counts, the ids that were rejected, and why.

    ``rejected_by_reason`` maps each rejection reason (as decided by
    ``src.validate.rejection_reason``) to how many records fell to it. It is
    always present, even as ``{}`` when nothing was rejected, so a caller never
    has to special-case a missing key — only an empty one.
    """
    result = {"total": len(records), "accepted": 0}

    rejected = []
    rejected_by_reason: dict[str, int] = {}
    for record in records:
        if check_record(record) is None:
            rejected.append(record.get("id", "<unlabelled>"))
            reason = rejection_reason(record)
            rejected_by_reason[reason] = rejected_by_reason.get(reason, 0) + 1
        else:
            result["accepted"] += 1

    if rejected:
        result["rejected"] = rejected
    result["rejected_by_reason"] = rejected_by_reason
    return result
