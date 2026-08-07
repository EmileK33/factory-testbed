"""Counting what the feed produced."""

from __future__ import annotations

from src.validate import _evaluate


def summarise(records: list[dict]) -> dict:
    """Return the feed's counts, the ids/reasons for what was rejected, and by-tag counts.

    ``rejected_reasons`` maps each rejection reason (as decided by
    ``src.validate._evaluate``, the feed contract's own account of why a
    record fails) to how many records fell to it, in first-seen order. It is
    always present, empty when nothing was rejected, so a caller never has to
    guard a missing key to render the empty case. ``rejected_count`` is
    likewise always an int. ``rejected`` (the list of rejected ids) keeps its
    original, conditionally-present shape for backward compatibility.

    ``by_tag`` maps each tag to the number of *accepted* records carrying it,
    deduped per record so a repeated tag in one record's own tags column
    still contributes at most 1 to that tag's total for that record.

    Both halves read a single ``_evaluate()`` call per record — the same
    normalised-dict-or-reason pair ``check_record()``/``rejection_reason()``
    each read one half of — so the accept/reject decision, the reason, and
    the tags counted can never drift apart from each other or from what
    ``check_record()`` would say on its own.
    """
    result: dict = {
        "total": len(records),
        "accepted": 0,
        "rejected_count": 0,
        "rejected_reasons": {},
    }

    rejected_ids: list[str] = []
    by_tag: dict[str, int] = {}
    for record in records:
        normalised, reason = _evaluate(record)
        if normalised is not None:
            result["accepted"] += 1
            # dict.fromkeys() dedupes a record's own tag list before counting,
            # so a record whose raw tags column repeats a tag (e.g. "eu,eu")
            # still contributes at most 1 to that tag's total: by_tag counts
            # accepted records carrying a tag, not tag occurrences.
            for tag in dict.fromkeys(normalised["tags"]):
                by_tag[tag] = by_tag.get(tag, 0) + 1
            continue
        # _evaluate() accepts non-dict input defensively (it can be called
        # directly, not just via the real feed, which always yields dicts);
        # .get() would raise on anything else, so guard it here too.
        rejected_ids.append(record.get("id", "<unlabelled>") if isinstance(record, dict) else "<unlabelled>")
        result["rejected_reasons"][reason] = result["rejected_reasons"].get(reason, 0) + 1

    result["rejected_count"] = sum(result["rejected_reasons"].values())
    if rejected_ids:
        result["rejected"] = rejected_ids
    result["by_tag"] = by_tag
    return result
