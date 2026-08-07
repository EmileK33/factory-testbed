"""Counting what the feed produced."""

from __future__ import annotations

from src.validate import check_record, rejection_reason


def summarise(records: list[dict]) -> dict:
    """Return the feed's counts, the ids that were rejected, and why.

    ``rejected_by_reason`` maps each rejection reason (as decided by
    ``src.validate.rejection_reason``) to how many records fell to it. It is
    always present, even as ``{}`` when nothing was rejected, so a caller never
    has to special-case a missing key — only an empty one.

    ``by_tag`` maps each tag to the number of *accepted* records carrying it
    (a record listing the same tag twice still counts once). It is always
    present, even as an empty mapping when there are no accepted records or
    none carry tags -- unlike ``rejected``, an empty mapping is its own valid
    empty state and callers shouldn't need a fallback.
    """
    result = {"total": len(records), "accepted": 0}

    rejected = []
    rejected_by_reason: dict[str, int] = {}
    by_tag: dict[str, int] = {}
    for record in records:
        checked = check_record(record)
        if checked is None:
            rejected.append(record.get("id", "<unlabelled>"))
            reason = rejection_reason(record)
            rejected_by_reason[reason] = rejected_by_reason.get(reason, 0) + 1
            continue
        result["accepted"] += 1
        for tag in dict.fromkeys(checked["tags"]):
            by_tag[tag] = by_tag.get(tag, 0) + 1

    if rejected:
        result["rejected"] = rejected
    result["rejected_by_reason"] = rejected_by_reason
    result["by_tag"] = by_tag
    return result
