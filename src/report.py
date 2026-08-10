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

_TABLE_RULE_RE = re.compile(r"^-[- ]*$")
_TOP_RULE_RE = re.compile(r"^=+$")
# Splits the table header on runs of 2+ spaces. Safe here in a way it is NOT
# safe for a data row: the header's cell content IS the literal field names
# in REPORTED_FIELDS -- known, fixed, single-word strings with no internal
# whitespace of their own -- so splitting it can never misfire the way
# splitting arbitrary data (a name, a joined tag list) can, which is why
# only the header gets this treatment and table data rows do not.
_COLUMN_GAP_RE = re.compile(r" {2,}")
# History on net-row validation, because a character pattern has now been
# wrong in both directions and a THIRD pattern attempt was wrong again:
#   - `^\S+ {2,}-?\d+$` (original) over-corrected (round 6, Finding 3/A3):
#     `\S+` refuses an id containing whitespace, but check_record() never
#     validates id FORMAT, only that it is present, so a raw feed id
#     containing a space is legitimate and render_report() emits it.
#   - `^.+ {2,}-?\d+$` (round 6's fix) went too far the other way (round 8,
#     Finding 1/A2, BLOCKING): `.+` grants arbitrary content INCLUDING runs
#     of 2+ spaces, so a whole sentence spliced in before the numeric tail
#     still fullmatch'd.
#   - `^\S+(?: \S+)* {2,}-?\d+$` (round 8's fix, the same single-space-token
#     shape that correctly closed _UNLABELLED_LINE_RE's equivalent gap) was
#     ALSO wrong (round 9, Finding 1, BLOCKING): it refuses an id containing
#     TWO consecutive spaces ("R  1001"), which check_record() still
#     accepts and render_report() still emits. The single-space-token
#     principle works for the UNLABELLED line (names are joined with ", ",
#     a fixed single-space-after-comma format the renderer controls) but
#     does NOT work here, because the id's own content is free-form and
#     under no such constraint -- the exact trap the table-row gap-count
#     check fell into one round earlier, now in a fourth guise.
# No pattern can distinguish a legitimate multi-space id from an inserted
# claim of the same shape, so this line is no longer pattern-matched at
# all. It is instead cross-checked against the id already recovered from
# the corresponding SETTLEMENT TABLE row via a fixed-width prefix slice
# (see the row loop above, and _NET_AMOUNT_RE below for the remainder).
_NET_AMOUNT_RE = re.compile(r"^\s*-?\d+$")
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
#
# The tail is made OPTIONAL, not widened, for one specific reachable case
# (round 10): a raw record with an empty id AND an empty name contributes
# `""` to `unlabelled`, so `render_report()` legitimately emits
# "Unlabelled records: " with NOTHING after the trailing space -- a line
# that predates this PR (the renderer's own behaviour on that input is out
# of scope; only the gate refusing output the renderer already produces is
# this PR's problem). The empty string is the ONLY new thing this accepts:
# it is not `\S+` (at least one non-space token) and it is not `.+` (at
# least one character of any kind) -- an empty tail carries no bytes at
# all, so it cannot carry an appended claim the way a wildcard could. A
# claim appended after an empty tail ("Unlabelled records:  -- claim",
# note the double space) still fails: the content after the fixed
# "Unlabelled records: " prefix is " -- claim", which starts with a space
# and so matches neither alternative.
_UNLABELLED_LINE_RE = re.compile(r"^Unlabelled records: (?:\S+(?: \S+)*)?$")


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
      order / a rule of "-"/space / zero or more table data rows, each no
      LONGER than the rule row above it (bounded by width, not by a
      character pattern -- see the row loop's own comment for why) / a
      blank line / "Net after fees" / a rule of "-" / zero or more net
      rows, each required to start with the SAME id already recovered from
      the corresponding settlement-table row (a fixed-width slice, not a
      pattern -- see _NET_AMOUNT_RE's own comment for why the id itself is
      never pattern-matched), followed by two spaces and an optionally-
      signed integer / a blank line / "Records read: N", "Records
      accepted: N", "Records rejected: N", each an exact match, digits
      only / a blank line / an OPTIONAL "Unlabelled records:
      <name>[, <name>...]" line / a "Total (USD): <amount>" line, exact
      shape, amount digits only (the amount's VALUE is a wildcard, never
      pinned -- see FROZEN_FOOTER_TAIL's own comment) / exactly
      FROZEN_FOOTER_TAIL, byte-for-byte.

    The governing principle for every data-bearing line above (the header,
    the two row sections, the unlabelled line): free-form content cannot be
    bounded by a character pattern at all, because the data can legitimately
    take exactly the shape the attack does. Measured directly, twice: a
    table-row name containing a real internal double-space (round 8), and a
    net-row id containing real DOUBLE spaces, not just one (round 9) --
    the single-space-token pattern that correctly fixed the unlabelled
    line one round earlier still assumes the field never contains a run of
    2+ spaces, which is true for names joined with ", " but not true for an
    arbitrary feed id. Every check on such a line is instead bounded by
    something render_report() itself GUARANTEES -- a fixed column width
    (the table rows), an exact cross-check against a value already
    recovered from elsewhere in the SAME rendered text via a fixed-width
    slice rather than a delimiter split (the net rows, cross-checked
    against the table rows' own id column), the specific single-space-token
    boundary the renderer's own join actually uses where that boundary
    really is fixed by construction (the unlabelled line's ", "-joined
    names), or a count derived from the same source data (the table/net row
    count cross-check below) -- never by a pattern chosen to match what an
    attack is expected to look like.

    What this still does not close, honestly: the settlement table's row
    count is cross-checked against the net-after-fees table's row count
    (both are derived from the same `accepted` list, in the same order, so
    they are ALWAYS equal in real output), but neither table is cross-
    checked against `Records accepted: N`, which is a printed number, not a
    re-derived one. A single crafted line that also imitates a plausible
    settlement record, inserted into BOTH tables with `Records accepted:`
    adjusted to agree, is internally consistent under every check here --
    that is the forged-record threat model, adjudicated out of scope for
    this item (it is false DATA, not a false CLAIM about the data; no
    per-line shape check can distinguish it, and tests/test_golden.py
    cannot serve as an independent backstop for it either, since
    `write_golden()` re-renders the very artifact that test compares
    against -- a source mutation changes both sides at once).

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
    if at_end():
        return False
    table_rule_width = len(lines[pos])
    # Every column's width, read off the RULE line specifically, not a data
    # row. This split is safe (unlike splitting a data row) because the
    # rule line's cell content is pure dashes -- it can never itself
    # contain a run of 2+ spaces the way a real id or name can -- so
    # _COLUMN_GAP_RE.split() always recovers the true column boundaries
    # here, the same reasoning that makes splitting the header safe too.
    column_widths = [len(seg) for seg in _COLUMN_GAP_RE.split(lines[pos])]
    if len(column_widths) != len(REPORTED_FIELDS):
        return False
    id_column_width = column_widths[0]
    # The POSITION, in the row, immediately after each non-last column's
    # own width -- this is where the literal "  " join separator must sit
    # for every real row (round 10, Finding 1/A1: the width bound alone
    # does not check CONTENT, only length, so a claim that happens to fit
    # inside the table's own legitimate width -- "R-1001  all 6 reported
    # fields are checked by the validation rules", 65 characters against a
    # 77-character rule line -- passed with the gate green). Every
    # _cell() value is non-empty (a blank cell renders "-", never ""), so
    # a real row always has real, non-space content in every column, and
    # `_table()`'s `line()` joins ljust-padded cells with EXACTLY two
    # literal spaces -- no more, no less -- between them; only the very
    # end of the whole line can be shortened by `line()`'s own
    # `.rstrip()`. So checking that exactly two spaces sit at each of
    # these positions is a POSITIONAL check derived from the rule line,
    # not a pattern guessed at the attack, and it does not require
    # splitting the row's own content by delimiter the way an earlier,
    # abandoned column-count oracle did.
    separator_positions: list[int] = []
    running = 0
    for width in column_widths[:-1]:
        running += width
        separator_positions.append(running)
        running += 2
    if not matching(_TABLE_RULE_RE):
        return False
    table_row_count = 0
    table_ids: list[str] = []
    while not at_end() and lines[pos] != "":
        # A data row can be SHORTER than the rule line (line()'s own
        # .rstrip() drops trailing padding on a narrow last cell) but never
        # LONGER: every column is padded to a fixed width computed as the
        # max over all rows, so the rule row (built from those same widths)
        # is always at least as wide as any real data row. This bounds a
        # row by an invariant _table() itself guarantees -- not a
        # character pattern -- so it does not reject any real row shape
        # (verified against an internal-double-space name, a
        # whitespace-containing id, a very long tag list, and a
        # single-record report) while still rejecting an appended claim,
        # which makes the row longer than the rule line that bounds its
        # own columns (round 8, Finding 2/A3).
        # `len()` here counts Python str codepoints, not terminal DISPLAY
        # columns -- a CJK character can occupy two terminal columns while
        # being one codepoint, for instance. That distinction does not
        # create an inconsistency here (round 9, asked and verified): both
        # sides of this comparison use the same `len()` semantics --
        # `_table()`'s own `ljust()`/`rjust()` padding is computed via
        # `len()` too (see `_table()`'s `widths` line), so the rule line's
        # width and a real row's width are measured the identical way that
        # produced them, non-ASCII content included. Verified against a
        # name containing accented Latin and CJK characters: renders
        # correctly, passes this check. Only DISPLAY alignment (how the
        # artifact looks in a terminal that renders CJK as double-width)
        # could differ from what `len()` reports, and that is a rendering
        # concern _table() already has -- not a new one this check
        # introduces or could fix by checking differently.
        if len(lines[pos]) > table_rule_width:
            return False
        # Verify a real separator sits at every inter-column boundary this
        # row reaches. A boundary beyond the row's own (possibly
        # rstrip()-shortened) length is fine -- that only means the final
        # column or two were short enough to have their trailing padding
        # stripped -- but a boundary the row DOES reach must be exactly
        # "  ", never anything else.
        for boundary in separator_positions:
            if boundary + 2 <= len(lines[pos]) and lines[pos][boundary:boundary + 2] != "  ":
                return False
        # The id column is always the first `id_column_width` characters,
        # ljust-padded by _table() regardless of any other column's
        # content -- a FIXED-WIDTH PREFIX SLICE, unlike delimiter
        # splitting, is safe even when the id itself contains a run of 2+
        # spaces (round 9, Finding 1: this is what net rows are
        # cross-checked against below, instead of pattern-matching the
        # id's own content, which cannot distinguish a legitimate
        # double-spaced id from an inserted claim of the same shape).
        table_ids.append(lines[pos][:id_column_width].rstrip())
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
        # Cross-checked against the settlement table's own id, extracted
        # above via a fixed-width slice, rather than pattern-matched --
        # round 8's `_NET_ROW_RE` (`\S+(?: \S+)* {2,}-?\d+$`) refused a
        # legitimate id containing two consecutive spaces
        # ("R  1001"), because no character pattern can distinguish that
        # from a claim spliced in the same shape (round 9, Finding 1,
        # BLOCKING). The net row's own format,
        # `f"{row['id']}  {row['net']:>8}"`, is exactly the id, two
        # literal spaces, then the net amount -- so requiring an EXACT
        # prefix match against the id already validated from the table
        # (not a pattern over what that id may contain) closes the
        # attack without touching the accept case for any id shape.
        if net_row_count >= len(table_ids):
            return False
        expected_prefix = table_ids[net_row_count] + "  "
        if not lines[pos].startswith(expected_prefix):
            return False
        if not _NET_AMOUNT_RE.fullmatch(lines[pos][len(expected_prefix):]):
            return False
        pos += 1
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
