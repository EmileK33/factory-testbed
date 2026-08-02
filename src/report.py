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


# Deliberately not imported from src.validate. That predicate decides what the
# settlement feed REJECTS and moves with the feed contract; this one decides
# which cells the report prints as blank. They agree today, and keeping them
# apart is what stops a formatting change from editing the validator's notion
# of a missing value.
def _missing(value: object) -> bool:
    return value is None or value == ""


def _quote_tag(tag: str) -> str:
    # Mirror the upstream exporter's own convention, the same one
    # src.parse.parse_tags() now honours: a tag containing a comma (or a
    # literal double quote) is wrapped in double quotes, with any double
    # quote inside it doubled. Plain tags are left bare. This is what makes
    # the rendered cell round-trip through parse_tags() back to the original
    # list -- if it didn't, the column would silently misreport how many
    # tags a record has, exactly the defect #15 fixed at the parsing end.
    if "," in tag or '"' in tag:
        return '"{}"'.format(tag.replace('"', '""'))
    return tag


def _format_tags(tags: list) -> str:
    return ", ".join(_quote_tag(str(tag)) for tag in tags) if tags else "-"


def _cell(row: dict, field: str) -> str:
    value = row.get(field)
    if isinstance(value, list):
        # tags is normalised to a list by check_record(); render it as the
        # quoted, comma-joined display string it stands for, not Python's
        # repr of a list. An empty list carries no tags, which is the same
        # "nothing here" the rest of the table renders as "-".
        return _format_tags(value)
    return "-" if _missing(value) else str(value)


def _column_widths(rows: list[dict]) -> list[int]:
    return [
        max([len(field)] + [len(_cell(row, field)) for row in rows])
        for field in REPORTED_FIELDS
    ]


def _table(rows: list[dict], widths: list[int]) -> list[str]:
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

    # Widths are computed once, globally, across every accepted record -- not
    # recomputed per region -- so a column (e.g. amount) lines up at the same
    # horizontal position in every group. Per-group widths would let a
    # narrower region's columns drift out of alignment with a wider region's,
    # which is the failure mode this report has never had and shouldn't gain
    # just because the rows are now split across region blocks.
    widths = _column_widths(accepted)
    for region in validate.REGION_CODES:
        group = [row for row in accepted if row["region"] == region]
        if not group:
            # A region with no accepted records is omitted entirely: no
            # header, no empty table, no zero subtotal.
            continue
        lines.append(region)
        lines.extend(_table(group, widths))
        subtotal_cents = sum(to_usd_cents(row["amount"], row["currency"]) for row in group)
        lines.append(f"Subtotal (USD): {_money(subtotal_cents)}")
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
    # No "All N reported fields are checked by the validation rules." line here.
    # That was only ever true because REPORTED_FIELDS and validate.VALIDATED_FIELDS
    # happened to be the same five fields; tags is reported but not one of the
    # fields check_record() can reject on, so the claim would be false the moment
    # tags joined REPORTED_FIELDS. The line immediately below states the narrower,
    # true fact instead of a reworded version of the false one.
    pairs = ", ".join(f"{region}/{currency}" for region, currency in ALLOWED_PAIRS)
    lines.append(f"Settlement pairs in force: {pairs}")
    lines.append(f"Validation covers: {', '.join(validate.VALIDATED_FIELDS)}")

    return "\n".join(lines) + "\n"
