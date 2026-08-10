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
# Splits the table header on runs of 2+ spaces. Safe here in a way it is NOT
# safe for a data row: the header's cell content IS the literal field names
# in REPORTED_FIELDS -- known, fixed, single-word strings with no internal
# whitespace of their own -- so splitting it can never misfire the way
# splitting arbitrary data (a name, a joined tag list) can, which is why
# only the header gets this treatment and table data rows do not.
_COLUMN_GAP_RE = re.compile(r" {2,}")
# The old net-row check, `^\S+ {2,}-?\d+$`, over-corrected (round 6, Finding
# 3/A3): `\S+` refuses an id containing whitespace, but check_record() never
# validates id FORMAT, only that it is present, so a raw feed id containing a
# space is legitimate and render_report() emits it -- a rule that can never
# say yes on that real input is broken, not conservative. Relaxed to `.+`
# (any non-empty content, including spaces) before the mandatory "  " and
# trailing signed integer, which is the one part of a net row's shape
# `f"{row['id']}  {row['net']:>8}"` that a false claim generally cannot
# imitate (an inserted sentence does not end in a run of 2+ spaces followed
# by digits) -- see test_shape_accepts_a_net_row_whose_id_contains_a_space
# for the accept-direction test this change requires.
_NET_ROW_RE = re.compile(r"^.+ {2,}-?\d+$")
# Round 6 collapsed the three "Records ..." lines into one shared regex
# applied three times -- which validates "a" known label three times, not
# the three SPECIFIC labels in that specific order (round 7, Finding 2/A2:
# "read/read/rejected", "rejected/accepted/read", and "read/read/read" all
# passed). Each line now owns its own exact literal label.
_RECORDS_READ_RE = re.compile(r"^Records read: \d+$")
_RECORDS_ACCEPTED_RE = re.compile(r"^Records accepted: \d+$")
_RECORDS_REJECTED_RE = re.compile(r"^Records rejected: \d+$")
_TOTAL_LINE_RE = re.compile(r"^Total \(USD\): -?\d+\.\d{2}$")
# `.+` after "Unlabelled records: " (round 6's version) was `fullmatch`
# against a wildcard -- the same unconstrained tail `startswith` had, just
# spelled differently (round 7, Finding 1/A1: the P8 attack -- a suffix
# appended after the real name, "Fennel Labs  -- all 6 reported fields are
# checked..." -- still passed). Names are joined with ", " (comma-space),
# never a run of 2+ spaces, so this requires one-or-more single-space-
# separated non-space tokens: real names (including hyphenated or
# multi-word ones) match; an appended clause preceded by a double space (or
# any run of 2+ spaces) does not, because a run of 2+ spaces can never be
# consumed as the single literal space between two `\S+` tokens.
_UNLABELLED_LINE_RE = re.compile(r"^Unlabelled records: \S+(?: \S+)*$")


def report_matches_expected_shape(text: str) -> bool:
    """True if EVERY line of *text* matches one of the shapes
    render_report() can legitimately emit, in the order it emits them --
    the whole document, not a window at either end, and each line checked
    for its full content, not only its position or its opening prefix.

    History this replaces, each round finding the dimension the previous
    fix left unbounded:
      - round 3: the tail checked by containment (`in`) -- any wording
        placed before or after it passed.
      - round 4: the tail checked by position (`str.endswith`) -- bounds
        only the END; a claim inserted above it still shipped.
      - round 5 (this function's first version): every line checked for
        POSITION, but six of those checks stopped at a prefix or a lower-
        bound count -- `lines[pos].startswith("Records read: ")` accepts
        any suffix after the number; a settlement-table row needed only
        len(REPORTED_FIELDS)-1 runs of 2+ spaces, which ordinary
        double-spaced prose reaches with no other effort. A false claim
        appended to "Records read: 8" or spliced into the table as an
        extra double-spaced line both shipped, 58/58 green, one of them
        carrying the ORIGINAL round-2 wording ("checked by the validation
        rules") the very first oracle on this item existed to forbid.

    This version checks POSITION and CONTENT together: every line-shape
    below is either an exact literal, an exact regex (`fullmatch`, not
    `startswith`/`in`), or -- for the two data-row sections, where content
    is genuinely free-form -- a count cross-check that does not depend on
    any single row's content. A line can no longer pass by being in the
    right place with the wrong tail.

    What this checks, top to bottom -- a single sequential pass, each line
    consumed exactly once:

      "Settlement report" / a rule of "=" / a blank line / a table header
      that splits (on runs of 2+ spaces) into exactly REPORTED_FIELDS, in
      order / a rule of "-"/space / zero or more table data rows (content
      not shape-validated per row -- see below) / a blank line / "Net
      after fees" / a rule of "-" / zero or more net rows, each matching
      free-form content, 2+ spaces, then an optionally-signed integer / a
      blank line / "Records read: N", "Records accepted: N", "Records
      rejected: N", each an exact match, digits only / a blank line / an
      OPTIONAL "Unlabelled records: <non-empty>" line / a "Total (USD):
      <amount>" line, exact shape, amount digits only (the amount's VALUE
      is a wildcard, never pinned -- see FROZEN_FOOTER_TAIL's own comment)
      / exactly FROZEN_FOOTER_TAIL, byte-for-byte.

    What this deliberately does NOT check, and why that is not the same
    gap round 5 shipped: table data rows are not validated per row, because
    real cell content (a name, a joined tag list) can legitimately contain
    whitespace shapes that make any per-row regex either reject legitimate
    data or accept crafted prose -- the exact trap _NET_ROW_RE's own id
    clause fell into above. Instead, the number of table data rows is
    required to equal the number of net-after-fees rows (checked further
    down, once both counts are known): render_report() derives both from
    the same `accepted` list, in the same order, so they are ALWAYS equal
    in real output, and an inserted extra line in either section breaks
    that equality without needing to know what a legitimate row looks like.
    A row's actual field-by-field content is still covered, independently,
    by tests/test_golden.py's byte-for-byte comparison against the
    committed artifact, by test_report_binds_tags_to_the_owning_record_row,
    and by test_report_header_includes_tags_column. This does not close
    every attack shape (a single crafted line that also imitates a
    plausible settlement record, with the surrounding counts adjusted to
    match, is a materially different and harder forgery -- out of scope
    for what a per-line shape check can address at all), but it closes the
    one demonstrated this round: an inserted line that is not accompanied
    by a matching, consistent change to the sibling table.

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

    if at_end() or _COLUMN_GAP_RE.split(lines[pos]) != list(REPORTED_FIELDS):
        return False
    pos += 1
    if not matching(_TABLE_RULE_RE):
        return False
    table_row_count = 0
    while not at_end() and lines[pos] != "":
        table_row_count += 1
        pos += 1
    if not literal(""):
        return False

    if not literal("Net after fees"):
        return False
    if not matching(_TABLE_RULE_RE):
        return False
    net_row_count = 0
    while not at_end() and lines[pos] != "":
        if not matching(_NET_ROW_RE):
            return False
        net_row_count += 1
    if table_row_count != net_row_count:
        return False
    if not literal(""):
        return False

    if not matching(_RECORDS_READ_RE):
        return False
    if not matching(_RECORDS_ACCEPTED_RE):
        return False
    if not matching(_RECORDS_REJECTED_RE):
        return False
    if not literal(""):
        return False

    if not at_end() and lines[pos].startswith("Unlabelled records:"):
        if not matching(_UNLABELLED_LINE_RE):
            return False

    if not matching(_TOTAL_LINE_RE):
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
