"""Counting what the feed produced."""

from __future__ import annotations

from src.validate import check_record


def summarise(records: list[dict]) -> dict:
    """Return the feed's counts, along with the ids that were rejected.

    ``by_tag`` maps each tag to the number of *accepted* records carrying it.
    A record is counted at most once per tag even if its own tags repeat the
    same value — this counts records, not raw tag occurrences.
    """
    result = {"total": len(records), "accepted": 0}

    rejected = []
    by_tag: dict[str, int] = {}
    for record in records:
        normalised = check_record(record)
        if normalised is None:
            rejected.append(record.get("id", "<unlabelled>"))
            continue
        result["accepted"] += 1
        for tag in dict.fromkeys(normalised["tags"]):
            by_tag[tag] = by_tag.get(tag, 0) + 1

    if rejected:
        result["rejected"] = rejected
    result["by_tag"] = by_tag
    return result
