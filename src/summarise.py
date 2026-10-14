"""Counting what the feed produced."""

from __future__ import annotations

from src.validate import REJECTION_REASONS, rejection_reason


def summarise(records: list[dict]) -> dict:
    """Return the feed's counts, the ids that were rejected, and why.

    ``rejection_reasons`` maps a reason code (see ``REJECTION_REASONS``) to the
    number of records that fell to it as their first failing check; like
    ``rejected`` it is absent when nothing is rejected.
    """
    result = {"total": len(records), "accepted": 0}

    rejected = []
    by_reason: dict[str, int] = {}
    for record in records:
        reason = rejection_reason(record)
        if reason is None:
            result["accepted"] += 1
        else:
            label = record.get("id", "<unlabelled>") if isinstance(record, dict) else "<unlabelled>"
            rejected.append(label)
            by_reason[reason] = by_reason.get(reason, 0) + 1

    if rejected:
        result["rejected"] = rejected
        result["rejection_reasons"] = {
            code: by_reason[code] for code in REJECTION_REASONS if code in by_reason
        }
    return result
