"""Counting what the feed produced.

This is also where the rejected side of the feed gets its accounting: the
count, the ids, and the reasons. ``src/report.py`` presents these numbers; it
must not recompute any of them (see ``rejection_reason()`` in
``src/validate.py`` for why a record was rejected).
"""

from __future__ import annotations

from src.validate import check_record, rejection_reason


def summarise(records: list[dict]) -> dict:
    """Return the feed's counts, the ids rejected, why each was rejected, and by-tag counts.

    ``rejected`` is the rejected COUNT; the ids live in ``rejected_ids``. The
    report reads these rather than recomputing them.

    ``by_tag`` maps each tag to the number of *accepted* records carrying it.
    A record is counted at most once per tag even if its own tags repeat the
    same value — this counts records, not raw tag occurrences.

    One ``check_record()`` call per record serves both halves: its normalised
    return feeds ``by_tag``, and ``rejection_reason()`` names why a rejection
    happened, so the accept/reject decision and the reason cannot disagree.
    """
    result = {"total": len(records), "accepted": 0, "rejected": 0}

    rejected_ids = []
    reasons: dict[str, int] = {}
    by_tag: dict[str, int] = {}
    for record in records:
        normalised = check_record(record)
        if normalised is not None:
            result["accepted"] += 1
            for tag in dict.fromkeys(normalised["tags"]):
                by_tag[tag] = by_tag.get(tag, 0) + 1
            continue

        result["rejected"] += 1
        rejected_ids.append(
            record.get("id", "<unlabelled>") if isinstance(record, dict) else "<unlabelled>"
        )
        reason = rejection_reason(record)
        reasons[reason] = reasons.get(reason, 0) + 1

    if rejected_ids:
        result["rejected_ids"] = rejected_ids
    if reasons:
        result["rejection_reasons"] = reasons
    result["by_tag"] = by_tag
    return result
