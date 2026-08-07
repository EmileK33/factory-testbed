"""Counting what the feed produced."""

from __future__ import annotations

from src.validate import check_record


def summarise(records: list[dict]) -> dict:
    """Return the feed's counts, along with the ids that were rejected.

    ``by_tag`` maps each tag to the number of *accepted* records carrying it
    (a record listing the same tag twice still counts once). It is always
    present, even as an empty mapping when there are no accepted records or
    none carry tags -- unlike ``rejected``, an empty mapping is its own valid
    empty state and callers shouldn't need a fallback.
    """
    result = {"total": len(records), "accepted": 0}

    rejected = []
    by_tag: dict[str, int] = {}
    for record in records:
        checked = check_record(record)
        if checked is None:
            rejected.append(record.get("id", "<unlabelled>"))
            continue
        result["accepted"] += 1
        for tag in dict.fromkeys(checked["tags"]):
            by_tag[tag] = by_tag.get(tag, 0) + 1

    if rejected:
        result["rejected"] = rejected
    result["by_tag"] = by_tag
    return result
