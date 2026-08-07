"""Counting what the feed produced."""

from __future__ import annotations

from src.validate import check_record, rejection_reason


def summarise(records: list[dict]) -> dict:
    """Return the feed's counts, along with the ids and reasons for what was rejected.

    ``rejected_count`` and ``rejection_reasons`` are the pipeline's single accounting
    of rejections: callers (the report renderer included) read them rather than
    re-deriving a count or a reason of their own, which is exactly how two
    independent accountings of the same feed would otherwise drift apart.
    """
    result = {"total": len(records), "accepted": 0}

    rejected = []
    reasons: dict[str, int] = {}
    for record in records:
        if check_record(record) is None:
            record_id = "<unlabelled>"
            if isinstance(record, dict):
                record_id = record.get("id", "<unlabelled>")
            rejected.append(record_id)
            reason = rejection_reason(record)
            reasons[reason] = reasons.get(reason, 0) + 1
        else:
            result["accepted"] += 1

    result["rejected_count"] = len(rejected)
    if rejected:
        result["rejected"] = rejected
        result["rejection_reasons"] = reasons
    return result
