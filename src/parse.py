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
    """The one normalisation every tag text goes through.

    Every run of Unicode whitespace (the ``str.split()`` set: space, TAB, LF, VT,
    FF, CR, NBSP, U+2007, U+202F and the rest) becomes one space and the ends are
    trimmed. It runs on the whole column before ``csv`` reads it, so no line
    break ever reaches the parser, and on each tag the parser returns.
    """
    return " ".join(text.split())


def parse_tags(raw: object) -> list[str]:
    """Split the feed's ``tags`` column into individual tags.

    The column is a comma-separated list; a tag containing a comma is wrapped
    in double quotes by the upstream exporter and stays one tag. Parsing is
    ``csv`` with ``skipinitialspace``; there is no second parser. A value
    ``csv`` rejects (a field longer than ``csv.field_size_limit()``) is not
    split: it yields one tag holding the whitespace-normalised raw text.

    A feed row is free-form JSON, so the column is not guaranteed to be a
    string. A column that is already a sequence is already split: each element
    is normalised, ``None`` and empty elements are dropped, and nothing is
    split again. Anything else yields no tags rather than raising, because
    ``check_record()`` promises a normalised record or ``None`` and cannot keep
    that promise if this throws. Passing this function its own output returns
    that output unchanged.
    """
    if isinstance(raw, (list, tuple)):
        return [tag for tag in (_squash(str(item)) for item in raw if item is not None) if tag]
    if not isinstance(raw, str):
        return []
    text = _squash(raw)
    if not text:
        return []
    try:
        row = next(csv.reader([text], skipinitialspace=True), [])
    except csv.Error:
        return [text]
    return [tag for tag in (_squash(field) for field in row) if tag]
