"""Helpers for the feed's packed columns."""

from __future__ import annotations

import re

_TAG_SEPARATOR = re.compile(r",\s*")


def parse_tags(raw: str | None) -> list[str]:
    """Split the feed's ``tags`` column into individual tags.

    The column is a comma-separated list; a tag containing a comma is wrapped
    in double quotes by the upstream exporter.
    """
    if not raw:
        return []
    return [part.strip().strip('"') for part in _TAG_SEPARATOR.split(raw) if part.strip()]
