"""Counting what the feed produced."""

from __future__ import annotations

from src.validate import evaluate_record


def summarise(records: list[dict]) -> dict:
    """Return the feed's counts, the ids that were rejected and why, and tag totals.

    ``rejected_reasons`` maps each rejection reason (as named by
    ``src.validate.evaluate_record()``, the feed contract that decides what a
    rejection means) to how many records fell to it, in first-encountered
    order. ``by_tag`` maps each tag carried by an accepted record to how many
    accepted records carry it.

    Both are always present - even as ``{}`` - unlike ``rejected``, so a caller
    can tell "nothing was rejected" apart from "this wasn't computed" without
    guessing at a default.
    """
    result = {"total": len(records), "accepted": 0}

    rejected = []
    rejected_reasons: dict[str, int] = {}
    by_tag: dict[str, int] = {}
    for record in records:
        normalised, reason = evaluate_record(record)
        if normalised is None:
            rejected.append(record.get("id", "<unlabelled>"))
            rejected_reasons[reason] = rejected_reasons.get(reason, 0) + 1
        else:
            result["accepted"] += 1
            for tag in normalised["tags"]:
                by_tag[tag] = by_tag.get(tag, 0) + 1

    if rejected:
        result["rejected"] = rejected
    result["rejected_reasons"] = rejected_reasons
    result["by_tag"] = by_tag
    return result
