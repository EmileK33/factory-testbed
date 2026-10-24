"""Helpers for the feed's packed columns."""

from __future__ import annotations

import csv

# The feed contract fixes the tag vocabulary: a tag outside this set is an
# exporter error rather than a new category. ``parse_tags()`` drops anything
# unrecognised before returning, so no downstream consumer has to re-check.
KNOWN_TAGS = (
    "air",
    "apac",
    "bulk",
    "crossborder",
    "eu",
    "high",
    "na",
    "priority",
    "rail",
    "settled",
    "small",
    "unlabelled",
)


def _squash(text: str) -> str:
    """The one normalisation: every run of Unicode whitespace becomes one space.

    ``str.split()`` with no argument splits on the whole Unicode whitespace set
    (space, TAB, NBSP, VT, FF, LF, CR, U+2007, U+202F and the rest), and the
    result carries no leading or trailing whitespace.
    """
    return " ".join(text.split())


def parse_tags(raw: object) -> list[str]:
    """Split the feed's ``tags`` column into individual tags.

    The column is a comma-separated list; a tag containing a comma is wrapped
    in double quotes by the upstream exporter. Whitespace is normalised first
    (see ``_squash``), so a line break or a non-breaking space never changes
    where a tag starts or ends. Empty tags are dropped.

    A value the csv reader rejects (an unterminated quote, text after a closing
    quote) is not split: it comes back as one tag holding the whole normalised
    text.

    A feed row is free-form JSON, so the column is not guaranteed to be a
    string. A list or tuple is already split: each element is normalised, and
    ``None`` and empty elements are dropped. Anything else yields no tags
    rather than raising, because ``check_record()`` promises a normalised
    record or ``None`` and cannot keep that promise if this throws. Passing
    this function its own output returns that output unchanged.
    """
    if isinstance(raw, (list, tuple)):
        parts = (_squash(str(tag)) for tag in raw if tag is not None)
        return [tag for tag in parts if tag]
    if not isinstance(raw, str):
        return []
    text = _squash(raw)
    if not text:
        return []
    try:
        fields = next(csv.reader([text], skipinitialspace=True, strict=True))
    except csv.Error:
        return [text]
    # The whole text is already squashed, so a field needs only its edges trimmed
    # (the space before a separating comma, or inside quotes next to a quote).
    return [tag for tag in (field.strip() for field in fields) if tag]
