"""Counting what the feed produced."""

from __future__ import annotations

from src.validate import rejection_reason


def summarise(records: list[dict]) -> dict:
    """Return the feed's counts, the ids that were rejected, and why.

    ``rejected_reasons`` maps each rejection reason (as decided by
    ``src.validate.rejection_reason``, the feed contract's own account of why
    a record fails) to how many records fell to it, in first-seen order. It
    is always present, empty when nothing was rejected, so a caller never has
    to guard a missing key to render the empty case. ``rejected_count`` is
    likewise always an int. ``rejected`` (the list of rejected ids) keeps its
    original, conditionally-present shape for backward compatibility.
    """
    result: dict = {
        "total": len(records),
        "accepted": 0,
        "rejected_count": 0,
        "rejected_reasons": {},
    }

    rejected_ids: list[str] = []
    for record in records:
        reason = rejection_reason(record)
        if reason is None:
            result["accepted"] += 1
            continue
        # rejection_reason() accepts non-dict input defensively (it can be
        # called directly, not just via the real feed, which always yields
        # dicts); .get() would raise on anything else, so guard it here too.
        rejected_ids.append(record.get("id", "<unlabelled>") if isinstance(record, dict) else "<unlabelled>")
        result["rejected_reasons"][reason] = result["rejected_reasons"].get(reason, 0) + 1

    result["rejected_count"] = sum(result["rejected_reasons"].values())
    if rejected_ids:
        result["rejected"] = rejected_ids
    return result
