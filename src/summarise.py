"""Counting what the feed produced."""

from __future__ import annotations

from src.validate import check_record


def summarise(records: list[dict]) -> dict:
    """Return the feed's counts, along with the ids that were rejected."""
    result = {"total": len(records), "accepted": 0}

    rejected = []
    for record in records:
        if check_record(record) is None:
            rejected.append(record.get("id", "<unlabelled>"))
        else:
            result["accepted"] += 1

    if rejected:
        result["rejected"] = rejected
    return result


def region_totals(records: list[dict]) -> dict:
    """Return per-region accepted counts and summed gross amounts.

    Records that ``check_record()`` drops are ignored entirely, and a region
    enters the result only when it has an accepted record — a region whose
    records were all dropped is absent rather than present with zeros.

    ``check_record()`` guarantees ``amount`` is a non-negative whole number, so
    ``gross`` stays integer arithmetic end to end.
    """
    totals: dict[str, dict[str, int]] = {}

    for record in records:
        checked = check_record(record)
        if checked is None:
            continue
        entry = totals.setdefault(checked["region"], {"accepted": 0, "gross": 0})
        entry["accepted"] += 1
        entry["gross"] += checked["amount"]

    return totals
