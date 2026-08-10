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


def _format(value: object) -> str:
    """Render a list cell's value, joined with ", ". Only ``tags`` is
    list-valued today; see ``_cell()`` for why this is never called on any
    other field."""
    return ", ".join(value)


def _cell(row: dict, field: str) -> str:
    value = row.get(field)
    # tags is the one reported field whose accepted value can be a `[]` list
    # (parse_tags() always returns list[str] -- never None or ""), so it gets
    # its own blank rule and its own join-based rendering, both scoped to
    # this field by name rather than by type. Every other field keeps the
    # exact original None/""-only rule and the exact original str(value)
    # rendering: check_record() does not type-check id/name/etc, so a
    # malformed feed row can legally carry a list there, and a type-based
    # branch that joined *any* list crashed render_report() on one such row
    # (PR #236 review, finding B1/F1's crash) instead of rendering it the way
    # it always rendered before this column existed. A type-based rule also
    # silently started treating `id: []` as blank on every non-tags column,
    # which desynced this predicate from validate._missing() and let a
    # record be simultaneously ACCEPTED and listed as UNLABELLED (finding
    # F4) -- restoring _missing() above to its original body is what makes
    # the comment two lines up true again, and this field-name check is what
    # keeps the tags-only exception from leaking back into it.
    if field == "tags":
        return "-" if _missing(value) or value == [] else _format(value)
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
    # Two raw facts, not a derived claim about coverage between them: earlier
    # phrasing here asserted things like "All N reported fields are checked"
    # or "N of M reported fields are checked," and both went false the moment
    # REPORTED_FIELDS and VALIDATED_FIELDS diverged (they do today: tags is
    # reported but not validated). Stating both field sets independently lets
    # a reader compare them without the report asserting a relationship that
    # the next edit to either tuple could silently falsify.
    # Kept adjacent on purpose (PR #236 review, finding B5): these two lines
    # are the pair a reader is meant to compare against each other, so an
    # unrelated line between them made that comparison harder than it needed
    # to be. Not reordering either tuple's own member order to "line up" the
    # shared fields -- filtering one tuple's print order by membership in the
    # other would silently drop a name if a future validated field were ever
    # NOT also a reported field, while still claiming the correct count in
    # the parenthetical, which is exactly the kind of representation
    # fragility this item has spent four gate rounds eliminating. Each line
    # still prints its own tuple in its own real order; only their position
    # in the report moved.
    lines.append(
        f"Reported fields ({len(REPORTED_FIELDS)}): {', '.join(REPORTED_FIELDS)}"
    )
    lines.append(
        f"Validated fields ({len(validate.VALIDATED_FIELDS)}): "
        f"{', '.join(validate.VALIDATED_FIELDS)}"
    )
    pairs = ", ".join(f"{region}/{currency}" for region, currency in ALLOWED_PAIRS)
    lines.append(f"Settlement pairs in force: {pairs}")

    return "\n".join(lines) + "\n"
