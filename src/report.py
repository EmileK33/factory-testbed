"""Renders the settlement report artifact.

The rendered text is committed at ``artifacts/report.golden.txt`` and compared
byte-for-byte by ``tests/test_golden.py``.
"""

from __future__ import annotations

from src import validate
from src.normalise import apply_fees
from src.rates import to_usd_cents
from src.records import load_records
from src.validate import ALLOWED_PAIRS, check_record

# The columns the report puts on the page, in order.
REPORTED_FIELDS = ("id", "name", "region", "amount", "currency", "tags")

RIGHT_ALIGNED = frozenset({"amount"})

# parse_tags() does not filter or sanitise the feed's raw tag text (that is its own, separately
# tracked, pre-existing gap -- not this module's to fix). A tag carrying a character str.isprintable()
# rejects -- e.g. a line break -- would otherwise reach _cell() untouched. That is not just the
# ASCII control range: str.splitlines() (which tools/write_golden.py's summarise_artifact() calls
# on the rendered report) also breaks on U+0085 NEL, U+2028 LINE SEPARATOR and U+2029 PARAGRAPH
# SEPARATOR, none of which "\x00-\x1f\x7f" would catch. Rather than enumerate line-break characters
# one discovery at a time, escape by the property that actually matters: every character
# str.isprintable() rejects (verified exhaustively over the full Unicode range to be exactly the
# ten codepoints splitlines() treats as a break: 0x0a-0x0d, 0x1c-0x1e, 0x85, 0x2028, 0x2029) is
# escaped, and every printable character -- letters, digits, space, punctuation, emoji -- passes
# through unchanged. This is scoped to the tags cell only; every other REPORTED_FIELDS column is
# untouched.
def _escape_char(char: str) -> str:
    if char.isprintable():
        return char
    codepoint = ord(char)
    if codepoint <= 0xFF:
        return f"\\x{codepoint:02x}"
    if codepoint <= 0xFFFF:
        return f"\\u{codepoint:04x}"
    return f"\\U{codepoint:08x}"


def _escape_tag(tag: str) -> str:
    """Escape non-printable characters in a single tag so it cannot forge a new physical report
    row (or otherwise corrupt a terminal/file rendering of the report)."""
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


def render_report(records: list[dict] | None = None) -> str:
    """Return the settlement report for *records* (defaults to the live feed)."""
    raw = load_records() if records is None else records

    accepted = [checked for checked in (check_record(row) for row in raw) if checked]
    rejected = len(raw) - len(accepted)

    lines = ["Settlement report", "=================", ""]
    lines.extend(_table(accepted))
    lines.append("")

    lines.append("Net after fees")
    lines.append("--------------")
    for row in apply_fees(accepted):
        lines.append(f"{row['id']}  {row['net']:>8}")
    lines.append("")

    total_cents = sum(to_usd_cents(row["amount"], row["currency"]) for row in accepted)

    lines.append(f"Records read: {len(raw)}")
    lines.append(f"Records accepted: {len(accepted)}")
    lines.append(f"Records rejected: {rejected}")
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
    lines.append(f"Validation covers: {', '.join(validate.VALIDATED_FIELDS)}")

    return "\n".join(lines) + "\n"
