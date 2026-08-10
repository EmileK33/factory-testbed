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
#     shape once believed to close the unlabelled line's equivalent gap --
#     round 11 review proved it never actually did; see the unlabelled
#     line's own history below `_TOTAL_LINE_RE`) was ALSO wrong (round 9,
#     Finding 1, BLOCKING): it refuses an id containing TWO consecutive
#     spaces ("R  1001"), which check_record() still accepts and
#     render_report() still emits. The single-space-token principle was
#     BELIEVED to work for the unlabelled line, on the theory that names
#     are joined with ", " -- a fixed format the renderer controls -- but
#     round 11 review disproved that too: `", "` bounds the join BETWEEN
#     names, not the content WITHIN one, and a name is exactly as
#     free-form as an id. The single-space-token pattern was never sound
#     on either line; it happened to catch the one attack SHAPE tried
#     against the unlabelled line before round 11, the same way this
#     net-row attempt happened to catch the one shape tried before round 9
#     -- the trap being the same trap, worn twice.
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
# History on the unlabelled line, kept because the mistake it documents is
# this item's most instructive one: rounds 6 through 10 iterated on a
# character pattern for this line's CONTENT --
#   - round 6: `.+` after the prefix -- an unconstrained wildcard, `in`
#     spelled as `fullmatch` (round 7, Finding 1/A1: a claim appended
#     after the real name still passed).
#   - round 7: `\S+(?: \S+)*` -- one-or-more single-space-separated
#     tokens, on the theory that names are joined with ", " and never
#     contain a run of 2+ spaces themselves, so a double-spaced append
#     could never be consumed as the pattern's own single literal space.
#   - round 10: made the empty tail an explicit alternative (a record
#     with both id and name empty legitimately emits nothing after the
#     prefix), without widening what non-empty content the pattern
#     accepted.
#   - round 11 review: proved round 7's pattern was never actually
#     correct in class, only in the one FORM every attack up to round 10
#     happened to use. "One-or-more single-space-separated tokens" is
#     also what an ordinary English sentence is -- a claim worded WITHOUT
#     a run of 2+ spaces ("Fennel Labs all 6 reported fields are checked
#     by the validation rules") fullmatches it exactly as readily as a
#     legitimate multi-word name. It also, in the other direction,
#     refused a REAL name containing a run of 2+ spaces ("ACME  Labs"),
#     which check_record() never forbids -- so the same regex was
#     simultaneously too loose (round 11's Finding 1) and too tight
#     (round 10's original escalation) at once. No replacement pattern
#     closes both without reopening the other: this function receives
#     TEXT ONLY, and `name` carries no format constraint at all, so a
#     legitimate name and a forbidden claim can be byte-for-byte the same
#     string. No character pattern can separate two identical strings by
#     origin.
#
# So this function no longer tries. Once the "Unlabelled records:" prefix
# is found, the line is consumed WITHOUT checking its content -- this
# function's job for that one line is reduced to confirming it occupies
# exactly the right POSITION (one line, in the right place in the
# document), which is the one thing about it that text alone genuinely
# does bound. Content is checked elsewhere, where a stronger invariant
# than text-shape is actually available: see expected_unlabelled_line()
# below, which tools/write_golden.py compares against the rendered line
# by EXACT equality against a value re-derived from the raw feed --
# closing both directions at once, because it is bounded by the source
# data itself rather than by a guess at what an attack looks like.


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
      only / a blank line / an OPTIONAL "Unlabelled records: ..." line,
      checked by POSITION only, content unchecked (see the paragraph
      below and expected_unlabelled_line() for why) / a "Total (USD):
      <amount>" line, exact
      shape, amount digits only (the amount's VALUE is a wildcard, never
      pinned -- see FROZEN_FOOTER_TAIL's own comment) / exactly
      FROZEN_FOOTER_TAIL, byte-for-byte.

    The governing principle for every data-bearing line above (the header,
    the two row sections, the unlabelled line): free-form content cannot be
    bounded by a character pattern at all, because the data can legitimately
    take exactly the shape the attack does. Measured directly, three times:
    a table-row name containing a real internal double-space (round 8), a
    net-row id containing real DOUBLE spaces, not just one (round 9), and
    an unlabelled-line name containing a run of 2+ spaces (round 10). The
    unlabelled line went a step further than the other two (round 11,
    Finding 1): a single-space-token pattern was believed to close it, on
    the theory that "," `join()`s names with a fixed single space and a
    real name never contains a run of 2+ spaces of its own -- both true,
    and still not enough, because "one-or-more single-space-separated
    tokens" is also what an ordinary English sentence is. A claim worded
    WITHOUT a run of 2+ spaces fullmatched that pattern exactly as readily
    as a legitimate multi-word name; the pattern only ever happened to
    catch the ONE shape every attack against this line used before round
    11, never the class. Every OTHER check on a data-bearing line above is
    bounded by something render_report() itself GUARANTEES -- a fixed
    column width (the table rows), an exact cross-check against a value
    already recovered from elsewhere in the SAME rendered text via a
    fixed-width slice rather than a delimiter split (the net rows, cross-
    checked against the table rows' own id column), or a count derived
    from the same source data (the table/net row count cross-check below)
    -- never by a pattern chosen to match what an attack is expected to
    look like. The unlabelled line has no such renderer-guaranteed TEXTUAL
    invariant: `", "` genuinely does bound the join BETWEEN names, but
    nothing bounds the content WITHIN one, because check_record() places
    no format constraint on `name` at all -- a legitimate name may be,
    byte for byte, the same text as a forbidden claim. This function no
    longer tries to check that line's content at all (see the block
    comment above `_TOTAL_LINE_RE` for the full history) -- it checks only
    that the line, if present, sits in the right POSITION, which is the
    one thing about it text alone genuinely bounds. Content is closed
    elsewhere, in tools/write_golden.py, which has something this function
    does not: the raw feed. See expected_unlabelled_line() below for the
    source-derived check write_golden() runs in addition to this
    function, and for why it succeeds where every character-pattern
    candidate on this line failed, in both directions at once.

    A settlement-table row's own CELL CONTENT is not checked by this
    function either, for the identical reason the unlabelled line's is
    not: no field this table renders carries a format constraint from
    check_record(), so a legitimate value and a fabricated one can be the
    same shape and the same width -- a mutation to `_cell()` substituting
    a sentence for one real cell's value produces a row of the CORRECT
    width and separators, because `_table()` pads to whatever the data
    needs (round 11 review priced this as requiring "exact per-column
    widths, which depend on the feed data" and rated it non-blocking on
    that basis; round 12 review measured the true cost -- three lines, no
    width arithmetic at all, since the renderer computes the widths for
    the attacker -- and corrected the rating). Closed the same way as the
    unlabelled line: see expected_table_rows() below, which
    tools/write_golden.py compares against the rendered rows by exact
    equality against `check_record(load_records())` -- the same records
    render_report() itself checks and renders -- rather than against
    anything this function could check from the text alone.

    What this still does not close, honestly, is the narrower residual
    that remains once both of the above are closed: a coordinated edit to
    BOTH a source-side function (render_report()'s own construction, or
    `_cell()`/`_table()`) AND its independent writer-side re-derivation
    (expected_unlabelled_line(), expected_table_rows()) passes
    undetected, because the two sides would then agree with each other
    while both being wrong. That is the genuine forged-record threat
    model -- false DATA, not a false CLAIM about data honestly rendered --
    and it is adjudicated out of scope for this item: no per-line check
    can distinguish a coordinated lie from the truth, and
    tests/test_golden.py cannot serve as an independent backstop for it
    either, since `write_golden()` re-renders the very artifact that test
    compares against. Concretely, it still covers: the settlement table's
    row count is cross-checked against the net-after-fees table's row
    count (both derived from the same `accepted` list, in the same order,
    so they are ALWAYS equal in real output), but neither table is
    cross-checked against `Records accepted: N`, which is a printed
    number, not a re-derived one -- a single crafted record inserted into
    BOTH tables with `Records accepted:` adjusted to agree is internally
    consistent under every check here.

    Used two ways: tools/write_golden.py refuses to write an artifact that
    fails this check (and, separately, one that fails either source-
    derived check below), and tests/test_report.py pins render_report()'s
    own output against it the same way.
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

    # Position only, deliberately -- CONTENT is not, and cannot be, checked
    # here. See the block comment above this function's definition and the
    # history above `_RECORDS_READ_RE` for why: no character pattern over
    # this line's text can distinguish a legitimate multi-space name from
    # an appended claim, because check_record() places no format
    # constraint on `name` at all. Real closure is
    # expected_unlabelled_line(), checked against the raw feed by
    # tools/write_golden.py, not by this function.
    if not at_end() and lines[pos].startswith("Unlabelled records:"):
        pos += 1

    if not matching(_TOTAL_LINE_RE):
        return False

    return lines[pos:] == _FROZEN_FOOTER_LINES


def expected_unlabelled_line(raw: list[dict]) -> str | None:
    """The exact "Unlabelled records: ..." line render_report() must emit
    for *raw*, or None when it must emit no such line at all (nothing in
    *raw* is missing an id).

    Why this exists, and why report_matches_expected_shape() above cannot
    do this job itself: that function only ever sees the RENDERED TEXT,
    and no character pattern over that text can distinguish a legitimate
    name containing a run of 2+ spaces from an attacker's claim spliced in
    with the same shape -- check_record() places no format constraint on
    `name` at all, so a name is legitimately allowed to be any string,
    including the literal text of a forbidden claim (PR #236 review round
    11, Finding 1: the one-or-more single-space-token pattern this line
    was previously checked against accepts a claim worded WITHOUT a run
    of 2+ spaces -- "Fennel Labs all 6 reported fields are checked by the
    validation rules" fullmatches it, because that is indistinguishable,
    from inside the text alone, from an ordinary English name -- which is
    why report_matches_expected_shape() no longer checks this line's
    content by pattern at all).

    `tools/write_golden.py` is not limited to the text, though: it already
    calls `load_records()` to produce the report it is about to write, so
    it can compare the EMITTED line against a value re-derived from the
    SAME raw feed by exact equality, rather than by guessing at shape. Any
    difference -- appended, prepended, reworded, comma-joined differently,
    single- or double-spaced -- fails the comparison, because there is no
    wording that survives exact equality against source data the way it
    can survive a character pattern.

    Deliberately written as its OWN, independent selection over *raw*
    (`_missing(row.get("id"))`, the `"?"` fallback) rather than calling
    into render_report()'s internals, or having render_report() call this.
    Sharing one helper between the two would turn this into an oracle that
    compares an implementation to itself: a mutation to a SHARED helper
    would be invisible to both sides at once, which is exactly the trap
    this item has spent ten rounds getting out of on every other line.
    Independence is what makes this a genuine cross-check instead of a
    restatement.

    The residual that independence trades for: a coordinated edit to BOTH
    this function and render_report()'s own unlabelled-list construction
    passes undetected -- the same forged-record threat model
    report_matches_expected_shape() already adjudicates out of scope, for
    the same reason (no per-line check distinguishes coordinated false
    data from the truth). Ordinary, UNintentional drift between the two --
    one changed, the other forgotten, no adversary involved -- is a
    different risk and is guarded separately: see
    tests/test_report.py::test_expected_unlabelled_line_matches_render_
    reports_own_construction, which pins the two against each other
    directly across a sweep of inputs, so an accidental divergence fails
    a named test in CI long before it could reach write_golden()'s gate.
    """
    names = [row.get("name", "?") for row in raw if _missing(row.get("id"))]
    return f"Unlabelled records: {', '.join(names)}" if names else None


def rendered_unlabelled_line(text: str) -> str | None:
    """The "Unlabelled records: ..." line actually present in *text*,
    located by POSITION, not by scanning for its literal prefix anywhere
    in the document (PR #236 review round 12, Finding 2, BLOCKING: a
    decoy elsewhere -- an id or a table cell containing the literal text
    "Unlabelled records: ..." -- shadows the real summary line under a
    prefix scan in BOTH directions: a decoy earlier in the text gets
    returned INSTEAD of the real line further down, which can (a) make a
    perfectly valid report look like it disagrees with
    expected_unlabelled_line() -- a false refusal -- and (b) make a real
    attack on the genuine summary line invisible, because the scan never
    reaches it).

    The real line's position is fixed by construction: render_report()
    emits it (or omits it) immediately before the "Total (USD): ..."
    line, which is immediately before FROZEN_FOOTER_TAIL -- both fixed,
    checkable facts about the tail of the document, independent of
    anything earlier in it (including a decoy). Walking from the END,
    past the byte-fixed footer and the Total line, lands on exactly that
    position regardless of what a decoy anywhere earlier in the table,
    the net rows, or an id contains.

    Returns None both when there is legitimately no unlabelled line AND
    when *text* does not have the expected tail shape at all (the footer
    or the Total line is not where it should be) -- this function makes
    no claim about overall shape; report_matches_expected_shape() already
    covers that and is always checked first in tools/write_golden.py, so
    by the time this runs the tail shape is guaranteed.
    """
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    total_index = len(lines) - len(_FROZEN_FOOTER_LINES) - 1
    if total_index < 0 or lines[total_index + 1:] != _FROZEN_FOOTER_LINES:
        return None
    if not _TOTAL_LINE_RE.fullmatch(lines[total_index]):
        return None
    candidate_index = total_index - 1
    if candidate_index < 0:
        return None
    candidate = lines[candidate_index]
    return candidate if candidate.startswith("Unlabelled records:") else None


def table_column_boundaries(rule_line: str) -> list[tuple[int, int]] | None:
    """Each settlement-table column's [start, end) character span, read
    off *rule_line* by position. Splitting the RULE line on runs of 2+
    spaces is safe in a way splitting a data row is not -- its cell
    content is pure dashes, which can never itself contain a run of 2+
    spaces the way a real id, name, or tag list can (see
    report_matches_expected_shape()'s own row-loop comment for the full
    reasoning; this is the identical technique, reused rather than
    reimplemented). None if *rule_line* does not split into exactly
    len(REPORTED_FIELDS) segments."""
    widths = [len(seg) for seg in _COLUMN_GAP_RE.split(rule_line)]
    if len(widths) != len(REPORTED_FIELDS):
        return None
    boundaries = []
    start = 0
    for width in widths:
        boundaries.append((start, start + width))
        start += width + 2  # +2 for _table()'s own "  " join
    return boundaries


def rendered_table_rows(text: str) -> tuple[str, list[str]] | None:
    """Return (rule_line, [data_row, ...]) for the settlement table in
    *text*, located by POSITION -- render_report()'s own fixed preamble
    puts the banner, top rule, and a blank line first (indices 0-2), the
    table header at index 3, and the table's own rule line at index 4;
    every line after that up to (not including) the next blank line is a
    data row. Independent of report_matches_expected_shape()'s own walk
    over the same structure -- this function duplicates only the WALK,
    never a value comparison, so a bug in one cannot mask a bug in the
    other. None if *text* is too short to contain the fixed preamble
    (never reached in practice: tools/write_golden.py always checks
    report_matches_expected_shape() first, which guarantees this much
    structure before this function ever runs)."""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    if len(lines) < 5:
        return None
    rule_line = lines[4]
    rows: list[str] = []
    pos = 5
    while pos < len(lines) and lines[pos] != "":
        rows.append(lines[pos])
        pos += 1
    return rule_line, rows


def expected_table_rows(
    accepted: list[dict], boundaries: list[tuple[int, int]]
) -> list[str]:
    """The exact row TEXT `_table()` must render for each of *accepted*'s
    already-checked/normalised records, in order, using *boundaries*
    (from table_column_boundaries()) for each column's WIDTH only -- the
    width is data recovered from the rendered rule line, not logic
    borrowed from `_table()`, so using it does not make this an oracle
    that compares an implementation to itself.

    Deliberately reimplements `_cell()`'s and `_table()`'s own formatting
    rules (the blank-is-"-" rule, the list-join rule, ljust/rjust
    alignment, the "  " join, and the whole-line trailing `.rstrip()`)
    rather than calling either of them (PR #236 review round 12, Finding
    1, BLOCKING: the reviewer's own first attempt at this called `_cell()`
    -- the function under test -- to compute the "expected" side, which
    made a mutation to `_cell()` invisible to both sides of the
    comparison at once and reported a false pass; discarded and rewritten
    to read the checked record's values directly instead, which is what
    this does). This is exactly the independence trade already made for
    expected_unlabelled_line() versus render_report()'s own construction,
    for the identical reason -- see that function's own docstring. The
    residual it carries is the same one, too: a coordinated edit to BOTH
    this function and `_cell()`/`_table()` passes undetected, which is
    the forged-record threat model report_matches_expected_shape()
    already adjudicates out of scope. Ordinary, non-adversarial drift is
    guarded the same way round 11 guarded it for the unlabelled line: see
    tests/test_report.py::test_expected_table_rows_matches_render_reports_own_construction.

    Also does NOT call `_missing()` or `_format()` -- both of those are
    genuinely shared, general-purpose helpers `_cell()` itself calls, so
    routing through them would put the SAME code on both sides of the
    comparison for a mutation targeting either one, not only for a
    mutation inside `_cell()` directly. The blank-value rule
    (`value is None or value == ""`) and the list-join rule
    (`", ".join(value)`) are inlined below instead, each a one-line
    restatement small enough that its own correctness is obvious on
    sight, same as expected_unlabelled_line()'s own inlined selection
    logic.
    """
    rows = []
    for record in accepted:
        parts = []
        for (start, end), field in zip(boundaries, REPORTED_FIELDS):
            width = end - start
            value = record.get(field)
            is_missing = value is None or value == ""
            if field in LIST_VALUED_FIELDS and isinstance(value, list):
                text = "-" if (is_missing or value == []) else ", ".join(value)
            else:
                text = "-" if is_missing else str(value)
            parts.append(text.rjust(width) if field in RIGHT_ALIGNED else text.ljust(width))
        rows.append("  ".join(parts).rstrip())
    return rows


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
