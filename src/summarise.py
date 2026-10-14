"""Counting what the feed produced."""

from __future__ import annotations

from src.validate import check_record


def summarise(records: list[dict]) -> dict:
    """Return the feed's counts, the ids that were rejected, and accepted records per tag."""
    result = {"total": len(records), "accepted": 0}

    rejected = []
    tag_counts: dict[str, int] = {}
    for record in records:
        checked = check_record(record)
        if checked is None:
            rejected.append(record.get("id", "<unlabelled>"))
        else:
            result["accepted"] += 1
            # The normalised tags, as the report column reads them: no re-split,
            # no vocabulary filter. A tag repeated within one record counts once.
            for tag in set(checked["tags"]):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

    # Always present (``{}`` when nothing is tagged), unlike ``rejected``.
    result["by_tag"] = dict(sorted(tag_counts.items()))

    if rejected:
        result["rejected"] = rejected
    return result
