"""Counting what the feed produced."""

from __future__ import annotations

from src.validate import REJECTION_REASONS, inspect_record


def summarise(records: list[dict]) -> dict:
    """Return the feed's counts, the tag counts, and the ids that were rejected.

    ``by_tag`` maps each tag, exactly as ``check_record()`` returns it, to the
    number of accepted records carrying it: a tag repeated within one record
    counts once for that record, and rejected records contribute nothing. It is
    always present, and ``{}`` when no accepted record has a tag.

    ``rejected_count`` is the number of rejected records and
    ``rejected_by_reason`` maps each reason code (see
    ``validate.REJECTION_REASONS``) to how many records fell to it as their
    FIRST failing check, in taxonomy order, omitting codes with no records. Both
    are always present; the counts sum to ``rejected_count``. A non-dict record
    is rejected as ``not_a_record`` and listed as ``"<unlabelled>"``.
    """
    result = {"total": len(records), "accepted": 0}

    by_tag: dict[str, int] = {}
    rejected = []
    by_code: dict[str, int] = {}
    for record in records:
        checked, code = inspect_record(record)
        if checked is None:
            by_code[code] = by_code.get(code, 0) + 1
            if isinstance(record, dict):
                rejected.append(record.get("id", "<unlabelled>"))
            else:
                rejected.append("<unlabelled>")
        else:
            result["accepted"] += 1
            for tag in dict.fromkeys(checked["tags"]):
                by_tag[tag] = by_tag.get(tag, 0) + 1

    result["by_tag"] = by_tag
    result["rejected_count"] = len(rejected)
    result["rejected_by_reason"] = {
        code: by_code[code] for code in REJECTION_REASONS if code in by_code
    }
    if rejected:
        result["rejected"] = rejected
    return result
