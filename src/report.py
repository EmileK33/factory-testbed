"""Renders the settlement report artifact.

The rendered text is committed at ``artifacts/report.golden.txt`` and compared
byte-for-byte by ``tests/test_golden.py``.
"""

from __future__ import annotations

import unicodedata

from src import validate
from src.normalise import apply_fees
from src.rates import to_usd_cents
from src.records import load_records
from src.summarise import summarise
from src.validate import ALLOWED_PAIRS, check_record

# The columns the report puts on the page, in order.
REPORTED_FIELDS = ("id", "name", "region", "amount", "currency", "tags")

RIGHT_ALIGNED = frozenset({"amount"})

# parse_tags() does not filter or sanitise the feed's raw tag text (that is its own, separately
# tracked, pre-existing gap -- not this module's to fix). A tag carrying a character
# str.splitlines() treats as a line break -- e.g. "\n" -- would otherwise reach _cell() untouched
# and forge an extra physical report row. That threat is not just the ASCII control range:
# splitlines() -- the natural way any consumer (a terminal, a log viewer, a diff, or
# tests/test_report.py's own row-count assertions below) would split the rendered report
# into lines -- also breaks on U+0085 NEL, U+2028 LINE SEPARATOR and U+2029 PARAGRAPH SEPARATOR.
#
# Escaping by str.isprintable() (a prior version of this function) is NOT the right property: it
# rejects 965,114 codepoints, not 10, and mangles legitimate tag content it has no business
# touching -- a ZWJ-joined compound emoji comes apart into its individual parts, and a
# non-breaking space gets escaped. Escaping by Unicode GENERAL CATEGORY is the property that
# actually matches the threat: every one of the ten codepoints splitlines() treats as a break is in
# category Cc (control), Zl (line separator) or Zp (paragraph separator) -- verified exhaustively
# over the full Unicode range -- and escaping by that category set (67 codepoints total: the ten
# row-forgers plus other C0/C1 control characters that likewise do not belong in a report cell)
# leaves join-control characters (category Cf, e.g. ZWJ), marks (category Mn, e.g. variation
# selectors) and ordinary spacing (category Zs, e.g. non-breaking space) untouched. This is scoped
# to the tags cell only; every other REPORTED_FIELDS column is untouched.
_ESCAPED_CATEGORIES = frozenset({"Cc", "Zl", "Zp"})


def _escape_char(char: str) -> str:
    if unicodedata.category(char) not in _ESCAPED_CATEGORIES:
        return char
    codepoint = ord(char)
    if codepoint <= 0xFF:
        return f"\\x{codepoint:02x}"
    if codepoint <= 0xFFFF:
        return f"\\u{codepoint:04x}"
    return f"\\U{codepoint:08x}"


def _escape_tag(tag: str) -> str:
    """Escape control/line-break characters in a single tag so it cannot forge a new physical
    report row (or otherwise corrupt a terminal/file rendering of the report)."""
    return "".join(_escape_char(char) for char in tag)


# Deliberately not imported from src.validate. That predicate decides what the
# settlement feed REJECTS and moves with the feed contract; this one decides
# which cells the report prints as blank. They agree today, and keeping them
# apart is what stops a formatting change from editing the validator's notion
# of a missing value.
def _missing(value: object) -> bool:
    return value is None or value == ""


def _cell(row: dict, field: str) -> str:
    value = row.get(field)
    if field == "tags" and isinstance(value, list):
        return ", ".join(_escape_tag(tag) for tag in value) if value else "-"
    return "-" if _missing(value) else str(value)


def _table(rows: list[dict]) -> list[str]:
    widths = [
        max([len(field)] + [len(_cell(row, field)) for row in rows])
        for field in REPORTED_FIELDS
    ]

    def line(cells: list[str]) -> str:
        parts = [
            cell.rjust(width) if field in RIGHT_ALIGNED else cell.ljust(width)
            for cell, width, field in zip(cells, widths, REPORTED_FIELDS)
        ]
        return "  ".join(parts).rstrip()

    out = [line(list(REPORTED_FIELDS)), line(["-" * width for width in widths])]
    out.extend(line([_cell(row, field) for field in REPORTED_FIELDS]) for row in rows)
    return out


def _money(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}{cents // 100}.{cents % 100:02d}"


def validation_coverage_line() -> str:
    """The report's validation-coverage line, e.g. for release-note tooling.

    A single source of truth for this exact text -- render_report() below
    calls it too, rather than each formatting ``VALIDATED_FIELDS`` on its
    own -- kept as a dedicated function (not a shared constant) specifically
    so callers outside this module (tools/write_golden.py) never need to
    parse the rendered report to recover this fact. Parsing was considered
    and rejected: render_report() prints a record's ``name`` (and ``id``)
    completely unescaped -- a separate, pre-existing, out-of-scope gap; only
    the ``tags`` column is escaped against control/line-break characters --
    so a record can carry a ``name`` containing literal newlines and inject
    an entire extra report line anywhere earlier in the output, including
    one that starts with this exact prefix. This function sidesteps that
    whole class of risk by never reading rendered text at all.
    """
    return f"Validation covers: {', '.join(validate.VALIDATED_FIELDS)}"


def render_report(records: list[dict] | None = None) -> str:
    """Return the settlement report for *records* (defaults to the live feed)."""
    raw = load_records() if records is None else records

    accepted = [checked for checked in (check_record(row) for row in raw) if checked]
    # The pipeline's own accounting, not a second one derived here: report.py must not
    # recompute how many records were rejected or why -- that is summarise()'s job, backed
    # by src.validate.reject_reason(). Every count line below is printed directly from
    # `summary`, with no arithmetic in this function: "total", "accepted" and
    # "rejected_count" are the three keys summarise() ALWAYS sets (unlike "rejected", the
    # pre-existing conditional key -- present only when non-empty -- which this function
    # never reads at all), so nothing here can KeyError on an empty feed or an all-accepted
    # one, and nothing here can independently drift from what summarise() decided. Note
    # this does mean every record's validation predicate runs a second time here
    # (accepted() above already ran it once): still linear (O(n), not worse), just not
    # free -- not something this change tries to optimise away.
    summary = summarise(raw)

    lines = ["Settlement report", "=================", ""]
    lines.extend(_table(accepted))
    lines.append("")

    fee_rows = apply_fees(accepted)
    lines.append("Net after fees")
    lines.append("--------------")
    id_width = max([len("id")] + [len(str(row["id"])) for row in fee_rows])
    lines.append(f"{'id'.ljust(id_width)}  {'net':>8}  currency")
    for row in fee_rows:
        lines.append(f"{row['id']}  {row['net']:>8}  {row['currency']}")
    lines.append("")

    total_cents = sum(to_usd_cents(row["amount"], row["currency"]) for row in accepted)

    lines.append(f"Records read: {summary['total']}")
    lines.append(f"Records accepted: {summary['accepted']}")
    lines.append(f"Records rejected: {summary['rejected_count']}")
    lines.append("")

    unlabelled = [row.get("name", "?") for row in raw if _missing(row.get("id"))]
    if unlabelled:
        lines.append(f"Unlabelled records: {', '.join(unlabelled)}")

    lines.append(f"Total (USD): {_money(total_cents)}")
    lines.append("Amounts are shown in USD.")
    lines.append(
        f"{len(validate.VALIDATED_FIELDS)} of {len(REPORTED_FIELDS)} "
        "reported fields are checked by the validation rules."
    )
    pairs = ", ".join(f"{region}/{currency}" for region, currency in ALLOWED_PAIRS)
    lines.append(f"Settlement pairs in force: {pairs}")
    lines.append(validation_coverage_line())

    lines.append("")
    lines.append("Rejected records")
    lines.append("----------------")
    reasons = summary["rejection_reasons"]
    if reasons:
        lines.extend(f"{entry['reason']}: {entry['count']}" for entry in reasons)
    else:
        lines.append("None rejected.")

    return "\n".join(lines) + "\n"
