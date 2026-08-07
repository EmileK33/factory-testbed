"""Counting what the feed produced.

This is also where the rejected side of the feed gets its accounting: the
count, the ids, and the reasons. ``src/report.py`` presents these numbers; it
must not recompute any of them (see ``rejection_reason()`` in
``src/validate.py`` for why a record was rejected).
"""

from __future__ import annotations

from src.validate import rejection_reason


def summarise(records: list[dict]) -> dict:
    """Return the feed's counts, the ids rejected, and why each was rejected."""
    result = {"total": len(records), "accepted": 0, "rejected": 0}

    rejected_ids = []
    reasons: dict[str, int] = {}
    for record in records:
        reason = rejection_reason(record)
        if reason is None:
            result["accepted"] += 1
            continue

        result["rejected"] += 1
        rejected_ids.append(
            record.get("id", "<unlabelled>") if isinstance(record, dict) else "<unlabelled>"
        )
        reasons[reason] = reasons.get(reason, 0) + 1

    if rejected_ids:
        result["rejected_ids"] = rejected_ids
    if reasons:
        result["rejection_reasons"] = reasons
    return result
