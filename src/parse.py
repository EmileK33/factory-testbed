"""Helpers for the feed's packed columns."""

from __future__ import annotations

import re

_TAG_SEPARATOR = re.compile(r",\s*")


def parse_tags(raw: str | None) -> list[str]:
    """Split the feed's ``tags`` column into individual tags.

    The column is a comma-separated list; a tag containing a comma is wrapped
    in double quotes by the upstream exporter.

    A feed row is free-form JSON, so the column is not guaranteed to be a
    string. Anything that is not one yields no tags rather than raising:
    ``check_record()`` promises a normalised record or ``None``, and it cannot
    keep that promise if this throws.
    """
    if not isinstance(raw, str) or not raw:
        return []
    return [part.strip().strip('"') for part in _TAG_SEPARATOR.split(raw) if part.strip()]
