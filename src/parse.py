"""Helpers for the feed's packed columns."""

from __future__ import annotations

import re

_TAG_SEPARATOR = re.compile(r",\s*")

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


def parse_tags(raw: str | None) -> list[str]:
    """Split the feed's ``tags`` column into individual tags.

    The column is a comma-separated list; a tag containing a comma is wrapped
    in double quotes by the upstream exporter.

    A feed row is free-form JSON, so the column is not guaranteed to be a
    string. A column that is already a sequence is already split and passes
    through; anything else yields no tags rather than raising, because
    ``check_record()`` promises a normalised record or ``None`` and cannot keep
    that promise if this throws. Passing this function its own output returns
    that output unchanged.
    """
    if isinstance(raw, (list, tuple)):
        return [str(tag).strip() for tag in raw if str(tag).strip()]
    if not isinstance(raw, str) or not raw:
        return []
    return [part.strip().strip('"') for part in _TAG_SEPARATOR.split(raw) if part.strip()]
