"""Renders the settlement report artifact.

The rendered text is committed at ``artifacts/report.golden.txt`` and compared
byte-for-byte by ``tests/test_golden.py``.
"""

from __future__ import annotations

from src import validate
from src.normalise import apply_fees
from src.rates import to_usd_cents
from src.records import load_records
from src.summarise import summarise
from src.validate import ALLOWED_PAIRS, check_record

# The columns the report puts on the page, in order.
REPORTED_FIELDS = ("id", "name", "region", "amount", "currency", "tags")

RIGHT_ALIGNED = frozenset({"amount"})


# Deliberately not imported from src.validate. That predicate decides what the
# settlement feed REJECTS and moves with the feed contract; this one decides
# which cells the report prints as blank. They agree today, and keeping them
# apart is what stops a formatting change from editing the validator's notion
# of a missing value.
def _missing(value: object) -> bool:
    if isinstance(value, (list, tuple)):
        return not value
    return value is None or value == ""


def _cell(row: dict, field: str) -> str:
    value = row.get(field)
    if _missing(value):
        return "-"
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value)
    return str(value)


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
    # The footer below presents this; it does not derive its own counts or
    # reasons - see summarise() for why that split matters.
    summary = summarise(raw)

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
    checked_fields = [field for field in REPORTED_FIELDS if field in validate.VALIDATED_FIELDS]
    lines.append(
        f"{len(checked_fields)} of {len(REPORTED_FIELDS)} reported fields are checked by "
        "the validation rules."
    )
    pairs = ", ".join(f"{region}/{currency}" for region, currency in ALLOWED_PAIRS)
    lines.append(f"Settlement pairs in force: {pairs}")
    lines.append(f"Validation covers: {', '.join(validate.VALIDATED_FIELDS)}")

    # The footer: what was rejected, and why. Both the reasons and their counts
    # come from summary["rejected_reasons"] (computed by summarise(), which in
    # turn gets its reasons from validate.evaluate_record(), the feed contract
    # that decides what a rejection means) - this renderer only presents them.
    # The header always prints, and the empty case gets an explicit line rather
    # than the section silently vanishing (unlike the "Unlabelled records" line
    # above, which omits itself when there's nothing to report).
    footer_title = "Rejected records"
    lines.append("")
    lines.append(footer_title)
    lines.append("-" * len(footer_title))
    reasons = summary["rejected_reasons"]
    if reasons:
        for reason, count in reasons.items():
            lines.append(f"{reason}: {count}")
    else:
        lines.append("No records were rejected.")

    return "\n".join(lines) + "\n"
