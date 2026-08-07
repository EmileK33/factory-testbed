"""Counting what the feed produced."""

from __future__ import annotations

from src.validate import check_record, rejection_reason


def summarise(records: list[dict]) -> dict:
    """Return the feed's counts, along with the ids and reasons for what was rejected.

    ``rejected_count`` and ``rejection_reasons`` are the pipeline's single accounting
    of rejections: callers (the report renderer included) read them rather than
    re-deriving a count or a reason of their own, which is exactly how two
    independent accountings of the same feed would otherwise drift apart.
    """
    result = {"total": len(records), "accepted": 0}

    rejected = []
    reasons: dict[str, int] = {}
    by_tag: dict[str, int] = {}
    for record in records:
        checked = check_record(record)
        if checked is None:
            record_id = "<unlabelled>"
            if isinstance(record, dict):
                record_id = record.get("id", "<unlabelled>")
            rejected.append(record_id)
            reason = rejection_reason(record)
            reasons[reason] = reasons.get(reason, 0) + 1
        else:
            result["accepted"] += 1
            # dict.fromkeys(...) dedupes while preserving order: a record whose
            # own tags column repeats a tag (e.g. "eu,eu") must still add at
            # most 1 to that tag's count, since by_tag counts records carrying
            # a tag, not tag occurrences.
            for tag in dict.fromkeys(checked["tags"]):
                by_tag[tag] = by_tag.get(tag, 0) + 1

    result["rejected_count"] = len(rejected)
    if rejected:
        result["rejected"] = rejected
        result["rejection_reasons"] = reasons
    result["by_tag"] = by_tag
    return result
