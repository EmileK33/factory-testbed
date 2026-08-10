"""Renders the settlement report artifact.

The rendered text is committed at ``artifacts/report.golden.txt`` and compared
byte-for-byte by ``tests/test_golden.py``.
"""

from __future__ import annotations

import re

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
# None-or-""-is-blank rule (see _cell()).
#
# This check only catches ONE direction: a name in LIST_VALUED_FIELDS that
# is no longer in REPORTED_FIELDS (dead/stale config -- harmless, since a
# field not in REPORTED_FIELDS is never rendered at all). It does NOT catch
# the dangerous direction -- a field in REPORTED_FIELDS whose real accepted
# value turns out to be a list without being declared here, which renders
# raw Python repr instead of a joined value. That direction cannot be
# detected from these two tuples' shapes alone (neither carries type
# information); it is checked against real data instead by
# tests/test_report.py::test_every_actually_reported_list_value_is_declared_list_valued.
LIST_VALUED_FIELDS = frozenset({"tags"})


def _check_list_valued_fields() -> None:
    """Raise if LIST_VALUED_FIELDS references a name that has drifted out of
    REPORTED_FIELDS. An explicit raise, not a bare `assert`, so it survives
    `python -O` (a bare assert is compiled out entirely under -O).

    Called from render_report() below, NOT at import time. A module-level
    raise here would fire the instant anything imports src.report -- which
    every test file that touches reporting does -- so a single mutated
    constant turned into a pytest COLLECTION error: 0 named test failures,
    0 tests executed, the invariant's own pinning test
    (test_list_valued_fields_is_pinned_and_a_subset_of_reported_fields)
    included, since collecting its file is what raised. Calling this from
    render_report() instead means a violation surfaces as an ordinary
    exception inside whichever test happens to call render_report() --
    a normal FAILED line, in the column CI actually reads -- while every
    other test in the suite still collects and runs.
    """
    if not LIST_VALUED_FIELDS <= set(REPORTED_FIELDS):
        raise ValueError(
            f"LIST_VALUED_FIELDS {sorted(LIST_VALUED_FIELDS)} contains a field "
            f"not in REPORTED_FIELDS {REPORTED_FIELDS} -- remove the stale name."
        )


# Hand-authored, frozen expectation for the fixed TAIL of the emitted report
# -- the four lines report_matches_expected_shape() below requires to match
# byte-for-byte, in order, once the body ahead of them checks out. Starts at
# "Amounts are shown in USD." rather than at "Total (USD): ..." -- the total
# is data-dependent (it moves with the feed and the exchange rates) and
# embedding its current value here would make every legitimate total change
# refuse the writer gate below, training whoever hits that refusal to edit
# this "frozen" literal routinely to make it go away, which disarms the gate
# and the oracle in the same edit (see PLAN.md's Superseded section). Not
# derived from REPORTED_FIELDS or VALIDATED_FIELDS either, so it cannot be
# defeated by editing those tuples.
FROZEN_FOOTER_TAIL = (
    "Amounts are shown in USD.\n"
    "Reported fields (6): id, name, region, amount, currency, tags\n"
    "Validated fields (5): id, name, amount, currency, region\n"
    "Settlement pairs in force: EU/EUR, NA/USD, APAC/JPY\n"
)
_FROZEN_FOOTER_LINES = FROZEN_FOOTER_TAIL.rstrip("\n").split("\n")

_TABLE_RULE_RE = re.compile(r"^[- ]+$")
_TOP_RULE_RE = re.compile(r"^=+$")
_NET_ROW_RE = re.compile(r"^\S+ {2,}-?\d+$")
_COLUMN_GAP_RE = re.compile(r" {2,}")
# _table()'s line() joins every cell with "  " (two spaces), so a real
# settlement-table row has at least this many runs of 2+ spaces -- one per
# column boundary. A LOWER bound, not an exact count: a cell's own content
# can legitimately contain a run of 2+ spaces (this item's test suite has
# twice found that a real risk to plan around, not a hypothetical one), and
# that only ever ADDS boundary-shaped runs, never removes a real one. An
# inserted English sentence essentially never contains a run of 2+ spaces,
# so this rejects that without needing to correctly split a row into its
# individual cell values -- which is the exact parsing this item backed
# away from twice already (round 4's abandoned column-count oracle; see
# PLAN.md).
_MIN_COLUMN_GAPS = len(REPORTED_FIELDS) - 1


def report_matches_expected_shape(text: str) -> bool:
    """True if EVERY line of *text* matches one of the shapes
    render_report() can legitimately emit, in the order it emits them --
    the whole document, not a window at either end.

    History this replaces: round 3 checked the tail by containment
    (`in`), which any wording placed before or after it passed. Round 4
    checked the tail by position (`str.endswith`), which only bounds the
    END -- a false claim inserted anywhere in the 20+ lines ABOVE the tail
    (between "Records rejected: N" and the blank line that follows it; or
    inside the "Net after fees" block) still shipped, 53/53 green, because
    nothing examined that region at all. Both were "a check whose scope is
    claimed to be complete" without actually being complete -- this item's
    own signature defect, reproduced one level up each time the previous
    instance was fixed. Extending the anchored window a further time does
    not terminate that sequence; owning the WHOLE document does, because
    there is no longer an unexamined region for the next attack to use.

    What this checks, top to bottom -- a single sequential pass, each line
    consumed exactly once, so no two checks overlap the same line (the
    overlap between two of round 4's checks was itself a defect: a clause
    that only ever restates what its neighbour already covers can be
    deleted with the suite still green, because nothing distinguishes
    "removed" from "redundant"):

      "Settlement report" / a rule of "=" / a blank line / a table header
      starting "id" / a rule of "-"/space / zero or more table data rows,
      each required to have at least len(REPORTED_FIELDS)-1 runs of 2+
      spaces (the column-boundary count _table() always produces; see
      _MIN_COLUMN_GAPS' own comment for why this is a lower bound, not an
      exact split, and why that keeps it robust rather than fragile) / a
      blank line / "Net after fees" / a rule of "-" / zero or more net
      rows, each matching an id, 2+ spaces, an optionally-signed integer /
      a blank line / "Records read: N" / "Records accepted: N" / "Records
      rejected: N" / a blank line / an OPTIONAL "Unlabelled records: ..."
      line / a "Total (USD): <amount>" line (the amount is a wildcard,
      never pinned -- see FROZEN_FOOTER_TAIL's own comment) / exactly
      FROZEN_FOOTER_TAIL, byte-for-byte.

    What this deliberately does NOT check: table rows are recognised by
    their column-boundary COUNT, not by extracting or validating individual
    cell VALUES -- this function never splits a row into fields. That
    stops it from needing the same whitespace-splitting logic this item's
    test suite has twice found ambiguous once a cell's own content (a name,
    a joined tag list) can itself contain a run of 2+ spaces -- exactly the
    fragility class an earlier round of this item deliberately backed away
    from. A row's actual field-by-field content is still covered,
    independently, by tests/test_golden.py's byte-for-byte comparison
    against the committed artifact, by
    test_report_binds_tags_to_the_owning_record_row, and by
    test_report_header_includes_tags_column.

    Used two ways: tools/write_golden.py refuses to write an artifact that
    fails this check, and tests/test_report.py pins render_report()'s own
    output against it the same way.
    """
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]  # text ends with "\n"; drop the trailing split
    pos = 0
    n = len(lines)

    def at_end() -> bool:
        return pos >= n

    def literal(expected: str) -> bool:
        nonlocal pos
        if at_end() or lines[pos] != expected:
            return False
        pos += 1
        return True

    def prefixed(prefix: str) -> bool:
        nonlocal pos
        if at_end() or not lines[pos].startswith(prefix):
            return False
        pos += 1
        return True

    def matching(pattern: re.Pattern) -> bool:
        nonlocal pos
        if at_end() or not pattern.fullmatch(lines[pos]):
            return False
        pos += 1
        return True

    if not literal("Settlement report"):
        return False
    if not matching(_TOP_RULE_RE):
        return False
    if not literal(""):
        return False

    if at_end() or not lines[pos].startswith("id"):
        return False
    pos += 1
    if not matching(_TABLE_RULE_RE):
        return False
    while not at_end() and lines[pos] != "":
        if len(_COLUMN_GAP_RE.findall(lines[pos])) < _MIN_COLUMN_GAPS:
            return False
        pos += 1
    if not literal(""):
        return False

    if not literal("Net after fees"):
        return False
    if not matching(_TABLE_RULE_RE):
        return False
    while not at_end() and lines[pos] != "":
        if not matching(_NET_ROW_RE):
            return False
    if not literal(""):
        return False

    if not prefixed("Records read: "):
        return False
    if not prefixed("Records accepted: "):
        return False
    if not prefixed("Records rejected: "):
        return False
    if not literal(""):
        return False

    if not at_end() and lines[pos].startswith("Unlabelled records: "):
        pos += 1

    if not prefixed("Total (USD): "):
        return False

    return lines[pos:] == _FROZEN_FOOTER_LINES


# Deliberately not imported from src.validate. That predicate decides what the
# settlement feed REJECTS and moves with the feed contract; this one decides
# which cells the report prints as blank. They agree today, and keeping them
# apart is what stops a formatting change from editing the validator's notion
# of a missing value.
def _missing(value: object) -> bool:
    return value is None or value == ""


def _format(value: object) -> str:
    """Join a list cell's values with ", "; anything that isn't a list is
    stringified unchanged via str(value), which cannot raise. That covers
    every non-list input, but NOT every list: a list whose elements are not
    all strings can still raise on the join itself (``_format([1, 2])``
    does). Unreached through render_report() today -- check_record() only
    ever produces a list-valued cell via parse_tags(), which always returns
    list[str] -- but this guard does not claim to cover that case, only the
    non-list one."""
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
    _check_list_valued_fields()
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
    # each in its own real tuple order, so a reader can compare them
    # directly without the report doing that comparison for them. This
    # entire function's output -- not only this tail -- must keep matching
    # report_matches_expected_shape() above; both `tools/write_golden.py`
    # (refuses to write otherwise) and tests/test_report.py check it.
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
