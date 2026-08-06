"""Counting what the feed produced."""

from __future__ import annotations

from src.validate import evaluate_record


def summarise(records: list[dict]) -> dict:
    """Return the feed's counts, along with the ids that were rejected and why.

    ``rejected_reasons`` maps each rejection reason (as named by
    ``src.validate.evaluate_record()``, the feed contract that decides what a
    rejection means) to how many records fell to it, in first-encountered
    order. Unlike ``rejected``, it is always present - even as ``{}`` when
    nothing was rejected - so a caller (the report's footer) can tell "nothing
    was rejected" apart from "this wasn't computed" without guessing at a
    default.
    """
    result = {"total": len(records), "accepted": 0}

    rejected = []
    rejected_reasons: dict[str, int] = {}
    for record in records:
        normalised, reason = evaluate_record(record)
        if normalised is None:
            rejected.append(record.get("id", "<unlabelled>"))
            rejected_reasons[reason] = rejected_reasons.get(reason, 0) + 1
        else:
            result["accepted"] += 1

    if rejected:
        result["rejected"] = rejected
    result["rejected_reasons"] = rejected_reasons
    return result
