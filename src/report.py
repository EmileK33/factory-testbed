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

# The reported fields whose accepted value is a list, and so get join-based
# rendering and a `[]`-is-blank rule instead of the default str(value)/
# None-or-""-is-blank rule (see _cell()). Adding a second list-valued column
# without adding it here renders raw Python repr instead of a joined value —
# this assertion makes that mismatch fail on import instead of shipping
# silently corrupted output.
LIST_VALUED_FIELDS = frozenset({"tags"})
assert LIST_VALUED_FIELDS <= set(REPORTED_FIELDS)


# Deliberately not imported from src.validate. That predicate decides what the
# settlement feed REJECTS and moves with the feed contract; this one decides
# which cells the report prints as blank. They agree today, and keeping them
# apart is what stops a formatting change from editing the validator's notion
# of a missing value.
def _missing(value: object) -> bool:
    return value is None or value == ""


def _format(value: object) -> str:
    """Join a list cell's values with ", "; anything that isn't a list is
    stringified unchanged. The isinstance check is load-bearing on its own,
    not just a scoping convenience: it is what stops this from ever raising,
    regardless of how a caller reaches it."""
    if not isinstance(value, list):
        return str(value)
    return ", ".join(value)


def _cell(row: dict, field: str) -> str:
    """Render one row's value for one field.

    A field only gets list-shaped rendering (join, and `[]` counts as blank)
    when BOTH conditions hold: it is in LIST_VALUED_FIELDS, and the value it
    actually holds is a list. Field name alone is not the discriminator —
    ``tags`` can reach here holding something other than a list (a direct
    caller of this function, or any future code path that stops normalising
    before this point), and every such value must fall back to the total
    str(value) below, which can never raise and never mis-renders (no
    joining a string into its characters, no joining a dict's keys).
    """
    value = row.get(field)
    if field in LIST_VALUED_FIELDS and isinstance(value, list):
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
    # Each field set is stated as its own fact (count + members); nothing
    # here computes or asserts a relationship between the two. Kept adjacent,
    # each in its own real tuple order, so a reader can compare them directly
    # without the report doing that comparison — and asserting a claim about
    # it — for them. This exact block is pinned byte-for-byte by
    # tests/test_report.py::test_report_footer_facts_match_a_frozen_hand_authored_block.
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
