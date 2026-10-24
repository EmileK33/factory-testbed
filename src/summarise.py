"""Counting what the feed produced."""

from __future__ import annotations

from src.validate import check_record


def summarise(records: list[dict]) -> dict:
    """Return the feed's counts, along with the ids that were rejected.

    ``by_tag`` maps each tag to the number of accepted records carrying it. The
    tags are read from the normalised record ``check_record()`` returns, the same
    field the report's tags column renders. A tag repeated within one record
    counts once for that record; tags are compared exactly as ``parse_tags()``
    returns them (case-sensitive); rejected records add nothing. The key is always
    present, and keys are sorted by tag.
    """
    result = {"total": len(records), "accepted": 0}

    rejected = []
    tag_counts: dict[str, int] = {}
    for record in records:
        checked = check_record(record)
        if checked is None:
            rejected.append(record.get("id", "<unlabelled>"))
        else:
            result["accepted"] += 1
            for tag in set(checked["tags"]):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

    if rejected:
        result["rejected"] = rejected
    result["by_tag"] = dict(sorted(tag_counts.items()))
    return result
