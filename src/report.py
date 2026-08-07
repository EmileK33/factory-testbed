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
    return value is None or value == ""


def _cell(row: dict, field: str) -> str:
    value = row.get(field)
    if field == "tags":
        # check_record() normalises "tags" to a list[str] (src.parse.parse_tags),
        # never a plain string, so it needs its own join instead of the generic
        # str(value) below, which would print Python's list repr.
        return ", ".join(value) if value else "-"
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
    summary = summarise(raw)

    # check_record() still runs per row here because the table and the fee
    # section need the normalised record content, not just a count. The
    # counts printed below come from `summary`, not from len(accepted) or
    # any subtraction against it, so this sweep can never disagree with the
    # summary about how many were accepted/rejected — only about what an
    # accepted row looks like.
    accepted = [checked for checked in (check_record(row) for row in raw) if checked]

    lines = ["Settlement report", "=================", ""]
    lines.extend(_table(accepted))
    lines.append("")

    lines.append("Net after fees")
    lines.append("--------------")
    for row in apply_fees(accepted):
        lines.append(f"{row['id']}  {row['net']:>8}")
    lines.append("")

    total_cents = sum(to_usd_cents(row["amount"], row["currency"]) for row in accepted)

    lines.append(f"Records read: {summary['total']}")
    lines.append(f"Records accepted: {summary['accepted']}")
    lines.append(f"Records rejected: {summary['rejected']}")
    lines.append("")

    unlabelled = [row.get("name", "?") for row in raw if _missing(row.get("id"))]
    if unlabelled:
        lines.append(f"Unlabelled records: {', '.join(unlabelled)}")

    lines.append(f"Total (USD): {_money(total_cents)}")
    lines.append("Amounts are shown in USD.")
    # The true count of reported fields that are also validated is an
    # intersection, not len(VALIDATED_FIELDS) — VALIDATED_FIELDS is not
    # guaranteed to be a subset of REPORTED_FIELDS, so a bare length compares
    # two independent cardinalities and can be wrong even though it happens to
    # match today (VALIDATED_FIELDS currently is a subset of REPORTED_FIELDS).
    validated_and_reported = len(set(REPORTED_FIELDS) & set(validate.VALIDATED_FIELDS))
    lines.append(
        f"{validated_and_reported} of {len(REPORTED_FIELDS)} reported fields "
        "are checked by the validation rules."
    )
    pairs = ", ".join(f"{region}/{currency}" for region, currency in ALLOWED_PAIRS)
    lines.append(f"Settlement pairs in force: {pairs}")
    lines.append(f"Validation covers: {', '.join(validate.VALIDATED_FIELDS)}")

    # The footer accounts for every rejected record: how many, and why. Both
    # the count and the reasons come straight from `summary` — the summary
    # the pipeline computes is the only place that decides what a rejection
    # means, so nothing here re-derives or recounts anything.
    lines.append("")
    lines.append("Rejections")
    lines.append("----------")
    reasons = summary.get("rejection_reasons")
    if reasons:
        lines.extend(f"{reason}: {count}" for reason, count in reasons.items())
    else:
        lines.append("No records were rejected.")

    return "\n".join(lines) + "\n"
