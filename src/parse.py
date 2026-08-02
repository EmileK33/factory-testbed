"""Helpers for the feed's packed columns."""

from __future__ import annotations

import csv
import io
import re

_TAG_SEPARATOR = re.compile(r",\s*")


def _split_without_quoting(raw: str) -> list[str]:
    """The pre-quoting-aware split. Cannot raise for any ``str``: ``re.split``

    and the ``str`` methods it calls have no failure mode for a ``str``
    argument. Kept as the fallback below rather than deleted.
    """
    return [part.strip().strip('"') for part in _TAG_SEPARATOR.split(raw) if part.strip()]


def parse_tags(raw: str | None) -> list[str]:
    """Split the feed's ``tags`` column into individual tags.

    The column is a comma-separated list; a tag containing a comma is wrapped
    in double quotes by the upstream exporter. Parsing is delegated to the
    standard library's CSV reader, which understands that quoting. If the
    column contains something CSV parsing cannot handle at all (for example a
    bare CR, or a field past ``csv.field_size_limit()``), parsing falls back
    to a plain comma split with no quote awareness -- the same behaviour this
    function had before quoting support was added -- rather than raising,
    because ``check_record()`` promises a normalised record or ``None`` and
    cannot keep that promise if this throws.

    A feed row is free-form JSON, so the column is not guaranteed to be a
    string. A column that is already a sequence is already split and passes
    through; anything else yields no tags rather than raising. Passing this
    function its own output returns that output unchanged.
    """
    if isinstance(raw, (list, tuple)):
        return [str(tag).strip() for tag in raw if str(tag).strip()]
    if not isinstance(raw, str) or not raw:
        return []
    try:
        fields = [
            field
            for row in csv.reader(io.StringIO(raw), skipinitialspace=True)
            for field in row
        ]
        return [field.strip() for field in fields if field.strip()]
    except Exception:
        # Deliberately broad: check_record() promises a normalised record or
        # None and cannot keep that promise if this throws, so any failure
        # mode of the CSV reader -- not just csv.Error -- must fall back
        # rather than propagate. Do not narrow this to `except csv.Error`;
        # that reintroduces the class of defect this fallback exists to end.
        return _split_without_quoting(raw)
