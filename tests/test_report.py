"""Tests for the rendered settlement report."""

from unittest.mock import patch

import pytest

from src import validate
from src.records import load_records
from src.report import (
    LIST_VALUED_FIELDS,
    REPORTED_FIELDS,
    _cell,
    _check_list_valued_fields,
    _format,
    _missing,
    expected_unlabelled_line,
    render_report,
    rendered_unlabelled_line,
    report_matches_expected_shape,
)
from src.validate import _missing as validate_missing
from src.validate import check_record


def test_report_lists_every_accepted_record():
    text = render_report()
    accepted = [row for row in (check_record(r) for r in load_records()) if row]
    for row in accepted:
        assert row["id"] in text


def test_report_reports_the_counts_it_read():
    text = render_report()
    assert f"Records read: {len(load_records())}" in text


def test_report_ends_with_a_newline():
    assert render_report().endswith("\n")


def test_report_names_the_unlabelled_record():
    assert "Unlabelled records: Fennel Labs" in render_report()


def test_report_binds_tags_to_the_owning_record_row():
    text = render_report(records=[
        {"id": "R-A", "name": "Alpha", "amount": 100, "currency": "USD",
         "region": "NA", "tags": "alpha-only"},
        {"id": "R-B", "name": "Beta", "amount": 200, "currency": "USD",
         "region": "NA", "tags": "beta-only"},
    ])
    row_a = next(line for line in text.splitlines() if line.startswith("R-A"))
    row_b = next(line for line in text.splitlines() if line.startswith("R-B"))
    assert "alpha-only" in row_a and "beta-only" not in row_a
    assert "beta-only" in row_b and "alpha-only" not in row_b


def test_report_header_includes_tags_column():
    text = render_report()
    header = next(line for line in text.splitlines() if line.startswith("id"))
    assert "tags" in header


def test_blank_tags_cell_renders_as_a_dash():
    assert _cell({"tags": []}, "tags") == "-"


# Authored by hand against the stated contract ("only None and '' count as
# missing" — see the comment above report._missing()), independent of either
# predicate's own source. PR #236 review round 2, finding A2 (BLOCKING): the
# previous test only asserted that report._missing() and validate._missing()
# AGREE with each other — that pins nothing about what they agree ON, so
# weakening both identically (e.g. dropping the `value == ""` clause from
# both, which makes check_record() start accepting name="") passed the whole
# suite. Every case below is checked against this frozen table for EACH
# predicate independently in the two tests that follow; neither test compares
# the two predicates to each other, so a change that moves both away from the
# table in the same direction fails both tests on its own.
_MISSING_CASES = (
    (None, True),
    ("", True),
    ("x", False),
    (0, False),
    (False, False),
    ({}, False),
    ([], False),
    ((), False),
    (["x"], False),
)


def test_report_missing_matches_a_frozen_table_of_expected_answers():
    for value, expected in _MISSING_CASES:
        assert _missing(value) is expected, value


def test_validate_missing_matches_the_same_frozen_table():
    for value, expected in _MISSING_CASES:
        assert validate_missing(value) is expected, value


def test_report_and_validate_missing_still_agree():
    """Kept alongside the two absolute tests above, not instead of them: this
    one caught a one-sided revert of report._missing() (PR #236 review round
    1) that the absolute tests also catch, so it adds no new coverage on its
    own, but it costs nothing and documents the agreement invariant the
    module comment states."""
    for value, _ in _MISSING_CASES:
        assert _missing(value) == validate_missing(value), value


def test_list_valued_fields_is_pinned_and_a_subset_of_reported_fields():
    """Pins today's exact LIST_VALUED_FIELDS value, and the one direction
    _check_list_valued_fields() genuinely checks: a name declared here that
    has drifted out of REPORTED_FIELDS (dead config -- harmless, since an
    unreported field is never rendered). This does NOT, on its own, catch a
    REPORTED field whose real value turns out to be list-shaped without
    being declared here (PR #236 review round 3, Finding 3 -- growing
    REPORTED_FIELDS leaves this subset relation true and this test green).
    That direction is checked separately, against real data, by
    test_every_actually_reported_list_value_is_declared_list_valued below."""
    assert LIST_VALUED_FIELDS == frozenset({"tags"})
    assert LIST_VALUED_FIELDS <= set(REPORTED_FIELDS)
    _check_list_valued_fields()  # must not raise on today's real values


def test_check_list_valued_fields_raises_as_a_named_test_failure_not_a_collect_error(
    monkeypatch,
):
    """PR #236 review round 4, Finding 2 (MEDIUM): the invariant used to live
    in a module-level `raise` in src/report.py, executed the instant
    anything imported the module -- including every test file that touches
    reporting. A violated invariant therefore surfaced as a pytest
    COLLECTION error (0 named failures, 0 tests executed, 23 of 49 tests
    never even collected), not as a failing test, which is the one column a
    CI summary actually reads. Moving the check into
    _check_list_valued_fields() and calling it from render_report() instead
    of at import time means: the module always imports cleanly regardless
    of LIST_VALUED_FIELDS's value, and a violation raises INSIDE a normal
    test function's body -- this one -- producing an ordinary FAILED line
    with a traceback, while every other test in the suite still collects
    and runs. Monkeypatches the real constant (not the source file) so this
    proves the runtime behaviour without needing a subprocess or a second
    mutated copy of the module."""
    import src.report as report_mod

    monkeypatch.setattr(report_mod, "LIST_VALUED_FIELDS", frozenset({"tags", "refs"}))
    with pytest.raises(ValueError, match="LIST_VALUED_FIELDS"):
        report_mod._check_list_valued_fields()


def test_every_actually_reported_list_value_is_declared_list_valued():
    """PR #236 review round 3, Finding 3 (BLOCKING): the honest, data-driven
    check for the direction the import-time guard above cannot see. A
    REPORTED field whose real accepted value is a list, but which is not in
    LIST_VALUED_FIELDS, renders as raw Python repr (e.g. "['INV-7',
    'INV-8']") in the committed settlement artifact -- the reviewer
    reproduced this end to end by adding a `refs` column with real list
    data and getting exactly that, 45/45 green. Checked against the real
    accepted feed (load_records() -> check_record()) rather than a
    synthetic case, because the failure only exists once real list-shaped
    data reaches a real reported field; it is written generically over
    REPORTED_FIELDS so it fires for whatever field this happens to in the
    future, not "tags" by name."""
    accepted = [row for row in (check_record(r) for r in load_records()) if row]
    for row in accepted:
        for field in REPORTED_FIELDS:
            value = row.get(field)
            if isinstance(value, list):
                assert field in LIST_VALUED_FIELDS, (
                    f"{field!r} holds a list value in accepted data but is "
                    f"not declared in LIST_VALUED_FIELDS -- it will render "
                    f"as raw Python repr in the committed artifact"
                )


def test_a_non_tags_list_field_renders_with_str_not_a_dash():
    """The blank-on-[] rule is scoped to the tags column only (PR #236
    review, finding B1/B2: a type-based rule applied to every column both
    crashed on a non-string list and silently started dashing `id: []`).
    Every other field keeps its original str(value) rendering, unchanged."""
    assert _cell({"id": []}, "id") == "[]"


def test_a_non_list_tags_value_renders_via_str_not_a_char_join_or_crash():
    """End-to-end sanity check, kept alongside (not instead of) the two
    isolated guard tests below: exercises _cell() the way a real caller
    would, with both guards intact."""
    assert _cell({"tags": "settled"}, "tags") == "settled"
    assert _cell({"tags": 42}, "tags") == "42"
    assert _cell({"tags": True}, "tags") == "True"
    assert _cell({"tags": 0.5}, "tags") == "0.5"
    assert _cell({"tags": {"a": 1}}, "tags") == str({"a": 1})


def test_cells_own_discriminator_never_hands_format_a_non_list_value():
    """PR #236 review round 3, Finding 2 (BLOCKING): _cell()'s discriminator
    (`field in LIST_VALUED_FIELDS and isinstance(value, list)`) and
    _format()'s own isinstance guard mutually mask each other -- reverting
    EITHER one alone left the combined test above green, because the other
    guard silently absorbed the regression. Neither guard was individually
    pinned. This test isolates _cell()'s own guard by replacing _format()
    with a stub that raises on any call: it fails if _cell() ever reaches
    _format() for a non-list value, regardless of whether the real
    _format() would also have caught it. Only reverting _cell()'s own
    discriminator to field-name-only can fail this test."""
    with patch("src.report._format", side_effect=AssertionError("must not be called")):
        assert _cell({"tags": "settled"}, "tags") == "settled"
        assert _cell({"tags": 42}, "tags") == "42"
        assert _cell({"tags": {"a": 1}}, "tags") == str({"a": 1})


def test_format_rejects_a_non_list_value_on_its_own():
    """PR #236 review round 3, Finding 2 (BLOCKING): the companion isolated
    test to the one above. Calls _format() directly, bypassing _cell()
    entirely, so _cell()'s discriminator state is irrelevant here. Only
    deleting _format()'s own isinstance guard can fail this test."""
    assert _format("settled") == "settled"
    assert _format(42) == "42"
    assert _format({"a": 1}) == str({"a": 1})


def test_a_list_valued_non_tags_field_does_not_crash_the_report():
    """Regression test for PR #236 review finding B1 (codex P2, raised to
    BLOCKING by the orchestrator): check_record() does not type-check id or
    name, so a malformed feed row can legally carry a non-string list there.
    Before this issue, `str(value)` handled that without ever raising;
    _format()'s `", ".join(value)` raises TypeError on a non-string element,
    and the type-based branch that reached it for every field took down the
    whole report on one such row, not just one cell."""
    text = render_report(records=[
        {"id": [1, 2], "name": "Zeta", "amount": 100, "currency": "USD",
         "region": "NA", "tags": "settled"},
    ])
    row = next(line for line in text.splitlines() if "Zeta" in line)
    assert str([1, 2]) in row


def test_a_record_with_an_empty_id_list_is_accepted_and_not_unlabelled():
    """Regression test for PR #236 review finding F4: with report._missing()
    widened, a raw record with id=[] was ACCEPTED (validate._missing([]) is
    False -- id reads as present) yet also treated as unlabelled by
    render_report() (the widened report._missing([]) was True on the raw
    row) -- accepted and unlabelled at once, self-contradicting. With the
    two predicates restored to agreement, id=[] must not be unlabelled."""
    text = render_report(records=[
        {"id": [], "name": "Zeta", "amount": 100, "currency": "USD",
         "region": "NA", "tags": "settled"},
    ])
    assert "Records accepted: 1" in text
    assert "Unlabelled records" not in text


def test_report_states_the_current_reported_and_validated_field_lists():
    """Literal strings, independent of REPORTED_FIELDS/VALIDATED_FIELDS.

    PR #236 review, finding F1 (BLOCKING): the prior version of this test
    built its expected strings from those same two tuples, so it compared
    the implementation to itself and could not fail for any content of
    either — measured by the reviewer appending a bogus field to
    REPORTED_FIELDS and getting a green run. Hardcoding today's real values
    here means a change to either tuple's membership is a deliberate,
    visible edit to this test too, the same way artifacts/report.golden.txt
    is already pinned rather than regenerated-and-trusted.
    """
    text = render_report()
    assert "Reported fields (6): id, name, region, amount, currency, tags" in text
    assert "Validated fields (5): id, name, amount, currency, region" in text
    assert set(REPORTED_FIELDS) != set(validate.VALIDATED_FIELDS)


def test_report_matches_its_expected_shape():
    """PR #236 review, five rounds of the same underlying finding, each at a
    wider scope than the last:

    - round 2: the footer test used `_FROZEN_FOOTER_FACTS in text` --
      containment, proving the block present *somewhere*, not *where*.
    - round 3: `str.endswith` fixed containment but only bounds the END --
      a claim inserted directly ABOVE the anchor still shipped, 49/49 green.
    - round 4: bounding two more lines above the anchor closed THAT position
      -- but a claim inserted further up still shipped, 53/53 green, in
      TWO more positions: between "Records rejected: N" and the blank line
      that follows it, and inside the "Net after fees" block (the second
      one shipping the ORIGINAL round-2 wording, "checked by the validation
      rules", the exact sentence this item's very first oracle existed to
      forbid). Anchoring a wider window each round does not terminate --
      there is always a line above wherever the window starts.

    report_matches_expected_shape() ends that sequence by owning the WHOLE
    document: every line, from "Settlement report" to the final
    "Settlement pairs in force: ..." line, must match one of the shapes
    render_report() can legitimately emit, in the order it emits them.
    There is no remaining region an inserted line can occupy undetected
    except the settlement table's own data rows, which this function
    deliberately leaves unvalidated in detail (see its own docstring for
    why) because that content is independently covered elsewhere,
    byte-for-byte, by tests/test_golden.py.

    See the mutation tests below for each of the five demonstrated
    insertion/appension positions across all five rounds, each closed by
    name.
    """
    assert report_matches_expected_shape(render_report())


def test_shape_rejects_a_false_claim_appended_after_the_report():
    """Round 3's Variant 1: a line appended after everything render_report()
    emits."""
    corrupted = render_report() + "Coverage: all reported fields are covered.\n"
    assert not report_matches_expected_shape(corrupted)


def test_shape_rejects_a_false_claim_inserted_inside_the_frozen_tail():
    """Round 3's Variant 2: a line inserted between "Amounts are shown in
    USD." and the "Reported fields" line, i.e. inside FROZEN_FOOTER_TAIL's
    own region."""
    text = render_report()
    corrupted = text.replace(
        "Amounts are shown in USD.\n",
        "Amounts are shown in USD.\n"
        "All 6 reported fields are checked by the settlement rules.\n",
    )
    assert corrupted != text  # the replacement landed
    assert not report_matches_expected_shape(corrupted)


def test_shape_rejects_a_false_claim_inserted_above_the_total():
    """Round 4's Variant 3, the one that defeated round 3's `endswith` fix:
    a line inserted between "Records rejected: N" / "Unlabelled
    records: ..." and "Total (USD): ...", entirely above where round 4's
    predicate started looking."""
    text = render_report()
    corrupted = text.replace(
        "Total (USD): ",
        "Coverage: 5/6 reported fields are validated; all reported fields "
        "are covered.\nTotal (USD): ",
        1,
    )
    assert corrupted != text  # the replacement landed
    assert not report_matches_expected_shape(corrupted)


def test_shape_rejects_a_false_claim_inserted_after_records_rejected():
    """Round 5's Position A, the one that defeated round 4's fix: a line
    inserted between "Records rejected: N" and the blank line that follows
    it -- above even round 4's own extended window."""
    text = render_report()
    corrupted = text.replace(
        "Records rejected: 3\n",
        "Records rejected: 3\n"
        "Coverage: 5/6 reported fields are validated; all reported fields "
        "are covered.\n",
        1,
    )
    assert corrupted != text  # the replacement landed
    assert not report_matches_expected_shape(corrupted)


def test_shape_rejects_a_false_claim_inserted_inside_net_after_fees():
    """Round 5's Position B: a line inserted directly after the "Net after
    fees" separator, before the first net row. Ships the ORIGINAL round-2
    wording ("checked by the validation rules") in the reviewer's own
    reproduction -- the exact sentence this item's first oracle existed to
    forbid, reinstated three representation changes later."""
    text = render_report()
    corrupted = text.replace(
        "Net after fees\n--------------\n",
        "Net after fees\n--------------\n"
        "All 6 reported fields are checked by the validation rules.\n",
        1,
    )
    assert corrupted != text  # the replacement landed
    assert not report_matches_expected_shape(corrupted)


def test_shape_rejects_a_false_claim_inserted_between_the_header_and_rule():
    """Invented position, not one either reviewer demonstrated: a line
    inserted between the settlement table's header row and its rule-of-
    dashes row. Closed the same way the header/rule sequence always was --
    the rule row must match only "-"/space, which a sentence does not."""
    text = render_report()
    corrupted = text.replace(
        "id      name            region  amount  currency  tags\n",
        "id      name            region  amount  currency  tags\n"
        "All 6 reported fields are checked by the validation rules.\n",
        1,
    )
    assert corrupted != text  # the replacement landed
    assert not report_matches_expected_shape(corrupted)


def test_shape_rejects_a_false_claim_inserted_among_the_table_data_rows():
    """A line inserted among the settlement table's own data rows (after
    the last real row, before the blank line that ends the table) --
    initially left unvalidated in this function's first draft this round
    (any non-blank line was accepted as "a row"), since a per-row regex
    that extracts individual cell VALUES would need the same
    whitespace-splitting logic this item's test suite has twice found
    ambiguous. Closed without reintroducing that: real rows always have at
    least len(REPORTED_FIELDS)-1 runs of 2+ spaces (the column-boundary
    count _table() always produces), and an inserted English sentence
    essentially never does -- a boundary COUNT, not a value SPLIT."""
    text = render_report()
    corrupted = text.replace(
        "R-1005  Eiger Metals    EU        2750  USD       eu, crossborder\n",
        "R-1005  Eiger Metals    EU        2750  USD       eu, crossborder\n"
        "All 6 reported fields are checked by the validation rules.\n",
        1,
    )
    assert corrupted != text  # the replacement landed
    assert not report_matches_expected_shape(corrupted)


def test_shape_rejects_a_report_with_no_total_line_at_all():
    """PR #236 review round 5, Finding 2 (MEDIUM): round 4's predicate had
    two clauses that overlapped -- the "line above the tail must start with
    Total (USD): " clause and the "line above THAT must be blank or
    Unlabelled" clause covered the same ground for every insertion
    position, so deleting the Total clause alone still passed 53/53 (its
    one distinct effect, rejecting a report with no Total line, is
    unreachable through render_report(), which always emits one). This
    function's single sequential pass checks the "Total (USD): " line
    exactly once, non-overlapping with any other clause, so this is what
    pins it: a Total line removed entirely (not displaced, actually
    deleted) must fail, independent of whether render_report() itself can
    currently produce that state.

    PR #236 review round 6, Finding "A4"/LOW: the total's actual VALUE is
    derived from the live text rather than hard-coded, so this fixture does
    not itself reintroduce the data-coupling FROZEN_FOOTER_TAIL deliberately
    removed -- it would not have fired spuriously on a legitimate total
    change (round 4's concern) or been mistaken for a real detection on an
    unrelated mutation (round 6's P7, which the hard-coded version was).
    """
    text = render_report()
    total_line = next(line for line in text.splitlines() if line.startswith("Total (USD): "))
    corrupted = text.replace(total_line + "\n", "", 1)
    assert corrupted != text  # the removal landed
    assert not report_matches_expected_shape(corrupted)


def test_shape_rejects_a_false_claim_appended_to_records_read():
    """PR #236 review round 6, Finding 1/P6 (BLOCKING): round 5's checks for
    the three "Records ..." lines used `startswith`, so anything could
    follow the number on the same line. The reviewer's reproduction shipped
    the ORIGINAL round-2 wording ("checked by the validation rules") on
    this exact line, in the committed artifact, 58/58 green. Fixed with an
    exact `fullmatch` shape (`^Records (?:read|accepted|rejected): \\d+$`)
    instead of a prefix check."""
    text = render_report()
    corrupted = text.replace(
        "Records read: 8\n",
        "Records read: 8  -- all 6 reported fields are checked by the "
        "validation rules.\n",
        1,
    )
    assert corrupted != text  # the replacement landed
    assert not report_matches_expected_shape(corrupted)


def test_shape_rejects_a_crafted_double_spaced_row_among_the_table_data():
    """PR #236 review round 6, Finding 1/P5 (BLOCKING) -- the builder's own
    self-flagged weak point, confirmed real by the reviewer: the round-5
    column-gap-count check (>= len(REPORTED_FIELDS)-1 runs of 2+ spaces)
    could be satisfied by nothing more than double-spacing an inserted
    sentence -- "NOTE:  all  6  reported  fields  are  checked  by  the
    validation  rules" has 10 such runs against a threshold of 5. Fixed by
    dropping per-row content validation entirely in favour of a count
    cross-check: the settlement table and the Net after fees table are
    both derived from the same `accepted` list in render_report(), so they
    always have the same number of data rows in real output, and an
    inserted extra line in either one breaks that equality regardless of
    its own spacing."""
    text = render_report()
    corrupted = text.replace(
        "R-1005  Eiger Metals    EU        2750  USD       eu, crossborder\n",
        "R-1005  Eiger Metals    EU        2750  USD       eu, crossborder\n"
        "NOTE:  all  6  reported  fields  are  checked  by  the  "
        "validation  rules\n",
        1,
    )
    assert corrupted != text  # the replacement landed
    assert not report_matches_expected_shape(corrupted)


def test_shape_accepts_a_net_row_whose_id_contains_a_space():
    """PR #236 review round 6, Finding 3/A3 (the item's first over-
    correction): the original net-row regex (`^\\S+ {2,}-?\\d+$`) refused an
    id containing whitespace, but check_record() never validates id
    FORMAT -- only that it is present -- so a raw feed id containing a
    space is legitimate, render_report() emits it, and the old regex made
    write_golden() refuse a genuinely correct artifact. Every round before
    this one tested only that the gate REJECTS bad input; this is the
    first test that it still ACCEPTS good input."""
    text = render_report(records=[
        {"id": "R 1001", "name": "Spacey", "amount": 100, "currency": "USD",
         "region": "NA", "tags": "settled"},
    ])
    assert "R 1001        70" in text  # the net row rendered with the id intact
    assert report_matches_expected_shape(text)


def test_shape_accepts_a_net_row_whose_id_contains_two_consecutive_spaces():
    """PR #236 review round 9, Finding 1 (BLOCKING) -- the item's third
    over-correction, caught before shipping a review pass on it: round 8's
    `_NET_ROW_RE` fix, `^\\S+(?: \\S+)* {2,}-?\\d+$` (single-space-separated
    tokens, the same shape that correctly closed _UNLABELLED_LINE_RE's
    equivalent gap), still refused an id containing TWO consecutive
    spaces -- `check_record()` places no format constraint on id at all, so
    "R  1001" is exactly as legitimate as "R 1001", and the single-space-
    token principle that works for the comma-joined unlabelled line does
    not hold for a free-form id. The prior test above verified ONE space;
    this is the class, not the example. Net rows are no longer pattern-
    matched against the id's own content at all -- see
    report_matches_expected_shape()'s own comment for the fixed-width
    cross-check against the settlement table that replaced it."""
    text = render_report(records=[
        {"id": "R  1001", "name": "Spacey", "amount": 100, "currency": "USD",
         "region": "NA", "tags": "settled"},
    ])
    assert "R  1001        70" in text
    assert report_matches_expected_shape(text)


def test_shape_rejects_a_false_claim_spliced_into_a_net_row():
    """PR #236 review round 8, Finding 1/A2 (BLOCKING): round 6's net-row
    regex relaxation (`^.+ {2,}-?\\d+$`, to fix the round-6 A3
    over-correction) went further than A3 required -- `.+` grants arbitrary
    content INCLUDING runs of 2+ spaces, so a whole sentence spliced
    before the numeric tail ("R-1001  -- all 6 reported fields are
    checked by the validation rules       995") still fullmatch'd, real
    source mutation, 76/76 green. Round 9 replaced pattern-matching this
    line entirely with a cross-check against the settlement table's own
    id (see report_matches_expected_shape()'s comment), which still
    closes this exact attack: the net row no longer starts with the
    table-validated id followed by exactly two spaces once a claim is
    spliced in."""
    text = render_report()
    corrupted = text.replace(
        "R-1001       995\n",
        "R-1001  -- all 6 reported fields are checked by the validation "
        "rules       995\n",
        1,
    )
    assert corrupted != text  # the replacement landed
    assert not report_matches_expected_shape(corrupted)


def test_shape_accepts_a_settlement_table_row_with_an_internal_double_space():
    """Accept-direction test for the width-bound table-row check (round 8,
    Finding 2/A3): a name containing a real internal run of 2+ spaces is
    legitimate (check_record() does not validate name format) and must
    still pass -- this is the exact case that would have produced a false
    refusal had the fix been an exact column-gap count instead of a width
    bound, which is why width was chosen over pattern-matching the row."""
    text = render_report(records=[
        {"id": "R-1", "name": "Acme  Corp", "amount": 100, "currency": "USD",
         "region": "NA", "tags": "settled"},
    ])
    assert "Acme  Corp" in text
    assert report_matches_expected_shape(text)


def test_shape_accepts_non_ascii_content_in_the_settlement_table():
    """PR #236 review round 9, item 4 (raised as a self-flagged question,
    answered here rather than left implicit): the table-row width bound
    compares `len()`, which counts Python str codepoints, not terminal
    DISPLAY columns. check_record() places no encoding constraint on any
    field, so non-ASCII content (accented Latin, CJK) is legitimate feed
    input. Verified this does not create a false refusal: `_table()`'s own
    column-width computation (`widths = [... len(_cell(...)) ...]`) uses
    the identical `len()` semantics this check does, so both sides of the
    comparison are measured consistently regardless of script. Only
    terminal DISPLAY alignment (a CJK character occupying two visual
    columns per codepoint) could differ from what `len()` reports, which
    is a pre-existing property of `_table()`'s own rendering, not something
    this check introduces or could address by measuring differently."""
    text = render_report(records=[
        {"id": "R-1", "name": "Über Corp", "amount": 100, "currency": "USD",
         "region": "NA", "tags": "settled"},
        {"id": "R-2", "name": "田中太郎", "amount": 200,
         "currency": "USD", "region": "NA", "tags": "settled"},
    ])
    assert report_matches_expected_shape(text)


def test_shape_rejects_a_false_claim_appended_to_a_settlement_table_row():
    """PR #236 review round 8, Finding 2/A3 (BLOCKING): settlement table
    data rows were counted (for the round-7 cross-check against the net
    table) but never content- or width-checked, so a claim appended to a
    real row -- "R-1001  Aster Holdings  ...  -- all 6 reported fields are
    checked by the validation rules" -- survived at 76/76 with zero
    failures and published on the committed artifact's own data line. The
    round-7 docstring's claim that row content was independently covered
    by tests/test_golden.py's byte-for-byte comparison does not hold for
    this threat: write_golden() re-renders the very artifact that test
    compares against, so a source mutation changes both sides together and
    one `python -m tools.write_golden` makes them agree again. Fixed by
    bounding each data row's LENGTH against the rule row directly above
    it, which _table() guarantees is always at least as wide as any real
    row (every column is padded to a width computed as the max across all
    rows, including the rule row's own dashes)."""
    text = render_report()
    corrupted = text.replace(
        "R-1001  Aster Holdings  EU        1200  EUR       eu, high, "
        "priority, settled\n",
        "R-1001  Aster Holdings  EU        1200  EUR       eu, high, "
        "priority, settled  -- all 6 reported fields are checked by the "
        "validation rules\n",
        1,
    )
    assert corrupted != text  # the replacement landed
    assert not report_matches_expected_shape(corrupted)


def test_shape_rejects_a_within_width_claim_spliced_into_a_settlement_table_row():
    """PR #236 review round 10, Finding 1 (BLOCKING): the width bound above
    (`len(row) <= len(rule_line)`) checks LENGTH, not CONTENT, so a claim
    that happens to FIT inside the table's own legitimate width still
    published, gate green: replacing the whole R-1001 row with
    "R-1001  all 6 reported fields are checked by the validation rules"
    (65 characters against a 77-character rule line) passed every prior
    check in this file, none of which caught it -- the round-8 fix above
    tests a claim APPENDED past the rule width, a strictly easier case.
    Closed by deriving each column's boundary from the rule line by
    position and requiring the literal "  " `_table()` always emits there;
    this claim has no real column structure at all, so it fails at the
    very first boundary."""
    text = render_report()
    short_claim = (
        "R-1001  all 6 reported fields are checked by the validation rules"
    )
    assert len(short_claim) < len(
        "------  --------------  ------  ------  --------  ---------------------------"
    )
    corrupted = text.replace(
        "R-1001  Aster Holdings  EU        1200  EUR       eu, high, "
        "priority, settled\n",
        short_claim + "\n",
        1,
    )
    assert corrupted != text  # the replacement landed
    assert not report_matches_expected_shape(corrupted)


def test_shape_accepts_the_degenerate_table_row_class():
    """Accept-direction sweep for the round-10 separator-position check,
    run as a class rather than one tidy example at a time -- the pattern
    every prior over-correction in this item shared was an accept-half
    tested against a single well-behaved case instead of the degenerate
    set the check must not reject. None of check_record()'s validated
    fields constrain name/tags content at all, so each of these is
    legitimate, reachable render_report() output: a name wide enough to
    force the id column's own width computation to move, a long joined
    tag list, a name with an internal double space (the exact shape the
    prior over-correction refused), and a record whose tags cell renders
    as the blank placeholder "-"."""
    wide_name = render_report(records=[
        {"id": "R-1", "name": "A Very Long Company Name Indeed Holdings",
         "amount": 100, "currency": "USD", "region": "NA", "tags": "x"},
    ])
    assert report_matches_expected_shape(wide_name)

    long_tags = render_report(records=[
        {"id": "R-1", "name": "Acme", "amount": 100, "currency": "USD",
         "region": "NA",
         "tags": "a,b,c,d,e,f,g,h,i,j,k,l,m,n,o,p"},
    ])
    assert report_matches_expected_shape(long_tags)

    two_space_name = render_report(records=[
        {"id": "R-1", "name": "ACME  Labs", "amount": 100, "currency": "USD",
         "region": "NA", "tags": "x"},
    ])
    assert "ACME  Labs" in two_space_name
    assert report_matches_expected_shape(two_space_name)

    empty_tags_cell = render_report(records=[
        {"id": "R-1", "name": "Acme", "amount": 100, "currency": "USD",
         "region": "NA", "tags": ""},
    ])
    assert report_matches_expected_shape(empty_tags_cell)

    # And the class together, in one multi-row report, so the width/
    # separator math is exercised against columns whose widths are driven
    # by different rows at once (not every row supplying the max width).
    mixed = render_report(records=[
        {"id": "R-1", "name": "A", "amount": 1, "currency": "USD",
         "region": "NA", "tags": ""},
        {"id": "R-2", "name": "A Very Long Company Name Indeed Holdings",
         "amount": 100, "currency": "USD", "region": "NA",
         "tags": "a,b,c,d,e,f,g,h,i,j,k,l,m,n,o,p"},
        {"id": "R-3", "name": "ACME  Labs", "amount": 100, "currency": "USD",
         "region": "NA", "tags": "x"},
    ])
    assert report_matches_expected_shape(mixed)


# PR #236 review round 6, Finding 2/A2 (MEDIUM): every fixture up to this
# point in the file INSERTS or DELETES a whole line, which the pass catches
# downstream regardless of which specific clause "should" have caught it --
# so deleting most individual clauses (proven directly, one at a time, with
# the clause's own `pos += 1` preserved so the pass does not merely
# desynchronise) left the suite green: 8 of 11 clauses were unobserved, not
# merely non-overlapping. Each test below corrupts ONE line IN PLACE --
# same line count, same position -- so it can only be caught by the clause
# that owns that specific line's content.
def test_shape_rejects_a_corrupted_banner_line():
    text = render_report()
    corrupted = text.replace("Settlement report\n", "Settlement Report\n", 1)
    assert corrupted != text
    assert not report_matches_expected_shape(corrupted)


def test_shape_rejects_a_corrupted_top_rule():
    text = render_report()
    corrupted = text.replace("=================\n", "====X============\n", 1)
    assert corrupted != text
    assert not report_matches_expected_shape(corrupted)


def test_shape_rejects_a_corrupted_table_header():
    text = render_report()
    corrupted = text.replace(
        "id      name            region  amount  currency  tags\n",
        "id      name            region  amount  currency  refs\n",
        1,
    )
    assert corrupted != text
    assert not report_matches_expected_shape(corrupted)


def test_shape_rejects_a_corrupted_table_rule():
    text = render_report()
    corrupted = text.replace(
        "------  --------------  ------  ------  --------  ---------------------------\n",
        "-X----  --------------  ------  ------  --------  ---------------------------\n",
        1,
    )
    assert corrupted != text
    assert not report_matches_expected_shape(corrupted)


def test_shape_rejects_a_table_rule_of_only_spaces():
    """PR #236 review round 8, Finding 4/A5 (LOW): `_TABLE_RULE_RE`
    (`^[- ]+$`) accepted a rule line made entirely of spaces, with no dash
    at all -- laxness, not an exploitable hole (no claim text can hide
    inside a space-only line that also has to be the exact width of the
    header it separates), but cheap to close since it was already being
    tightened for other reasons this round. Now requires at least one "-"
    character."""
    text = render_report()
    corrupted = text.replace(
        "------  --------------  ------  ------  --------  ---------------------------\n",
        " " * len(
            "------  --------------  ------  ------  --------  ---------------------------"
        ) + "\n",
        1,
    )
    assert corrupted != text
    assert not report_matches_expected_shape(corrupted)


def test_shape_rejects_a_corrupted_net_after_fees_banner():
    text = render_report()
    corrupted = text.replace("Net after fees\n", "Net After Fees\n", 1)
    assert corrupted != text
    assert not report_matches_expected_shape(corrupted)


def test_shape_rejects_a_corrupted_net_rule():
    """PR #236 review round 7, Finding 2/A3: the round-6 version of this
    fixture searched for the bare substring "--------------\n" (14 dashes
    then a newline), which also occurs INSIDE the settlement table's own
    27-dash tags-column rule (the last 14 of its 27 dashes are immediately
    followed by the line's own newline) -- so `.replace(..., count=1)`
    silently corrupted the table rule instead of the net rule, leaving c6
    (the net rule's own _TABLE_RULE_RE check) unpinned while making it look
    covered. Anchored on the unique preceding context ("Net after fees\\n")
    so this can only match the net rule's own line."""
    text = render_report()
    corrupted = text.replace(
        "Net after fees\n--------------\n",
        "Net after fees\n--------------X\n",
        1,
    )
    assert corrupted != text
    assert not report_matches_expected_shape(corrupted)


def test_shape_rejects_a_corrupted_records_accepted_line():
    """Each "Records ..." line now has its own exact regex
    (_RECORDS_READ_RE / _RECORDS_ACCEPTED_RE / _RECORDS_REJECTED_RE), not
    one shared pattern applied three times (PR #236 review round 7, Finding
    2/A2: the shared version validated "a" known label three times, not the
    three specific labels in order -- "read/read/rejected" and
    "rejected/accepted/read" both passed it). Demonstrated here on a
    different one of the three lines to show it is not only the first that
    is enforced; see test_shape_rejects_the_records_lines_out_of_order and
    test_shape_rejects_a_repeated_records_label below for the specific
    label-identity attacks this round found."""
    text = render_report()
    corrupted = text.replace(
        "Records accepted: 5\n", "Records accepted: 5 (verified)\n", 1
    )
    assert corrupted != text
    assert not report_matches_expected_shape(corrupted)


def test_shape_rejects_a_corrupted_records_rejected_line():
    """PR #236 review round 8, Finding 3/A4 (MEDIUM): the third of the three
    per-label regexes (_RECORDS_REJECTED_RE) had no in-place fixture of its
    own -- round 7 added one for "Records read:" (the P6 regression test)
    and one for "Records accepted:" (directly above), but not for
    "Records rejected:", which the consume-preserving clause sweep found
    genuinely unpinned: deletable from the source with the full suite
    still green. Closes the gap; 14 of 14 clauses now have their own
    in-place fixture."""
    text = render_report()
    corrupted = text.replace(
        "Records rejected: 3\n", "Records rejected: 3 (verified)\n", 1
    )
    assert corrupted != text
    assert not report_matches_expected_shape(corrupted)


def test_shape_rejects_the_records_lines_out_of_order():
    """PR #236 review round 7, Finding 2/A2, reproduced directly: with a
    single shared regex, "Records rejected: 3 / Records accepted: 5 /
    Records read: 8" (the three real lines, reordered) passed, because the
    check only verified each line was SOME recognised label, not that it
    was the SPECIFIC label expected at that position."""
    text = render_report()
    corrupted = text.replace(
        "Records read: 8\nRecords accepted: 5\nRecords rejected: 3\n",
        "Records rejected: 3\nRecords accepted: 5\nRecords read: 8\n",
        1,
    )
    assert corrupted != text
    assert not report_matches_expected_shape(corrupted)


def test_shape_rejects_a_repeated_records_label():
    """PR #236 review round 7, Finding 2/A2, the other reproduced case:
    "Records read: 8 / Records read: 8 / Records read: 8" -- three lines
    that are all individually a recognised label -- passed the shared
    regex, because nothing distinguished "the read label, three times"
    from "read, then accepted, then rejected"."""
    text = render_report()
    corrupted = text.replace(
        "Records read: 8\nRecords accepted: 5\nRecords rejected: 3\n",
        "Records read: 8\nRecords read: 8\nRecords read: 8\n",
        1,
    )
    assert corrupted != text
    assert not report_matches_expected_shape(corrupted)


def test_shape_rejects_a_net_row_whose_content_is_replaced_in_place():
    """PR #236 review round 7, Finding 2: the net-row shape check is masked
    by the round-6 row-count cross-check for INSERTED/DELETED lines (which
    the cross-check catches via the count mismatch), but not for a net row
    whose content is REPLACED with something differently-shaped while the
    total row count stays the same -- only the net row's own content check
    catches that (since round 9, the id-cross-check against the settlement
    table, described in report_matches_expected_shape()'s own comment).
    Preserves the row count (one line swapped for one line) so this
    isolates the shape check specifically."""
    text = render_report()
    corrupted = text.replace(
        "R-1001       995\n",
        "All 6 reported fields are checked by the validation rules.\n",
        1,
    )
    assert corrupted != text
    assert not report_matches_expected_shape(corrupted)


def test_shape_rejects_a_net_row_with_a_mismatched_id():
    """PR #236 review round 9, follow-up self-check: isolates the
    id-cross-check clause specifically from the trailing amount-shape
    check, since a mutation removing ONLY the id-prefix match (found by
    re-verifying this clause's own mutation-kill after round 9's redesign)
    survived when tested only against a sentence-splicing attack -- the
    amount-shape check alone already rejects a non-numeric tail, masking
    the id check's own absence. This corruption keeps the amount portion
    perfectly valid (a real, correctly-shaped integer) and changes only
    the id, which the amount check cannot see: it must be the id
    cross-check specifically that rejects a forged id with an otherwise
    well-formed net row."""
    text = render_report()
    corrupted = text.replace("R-1001       995\n", "FAKE-999       995\n", 1)
    assert corrupted != text
    assert not report_matches_expected_shape(corrupted)


def test_shape_rejects_a_corrupted_unlabelled_prefix():
    text = render_report()
    corrupted = text.replace(
        "Unlabelled records: Fennel Labs\n",
        "Unlabeled records: Fennel Labs\n",  # typo'd prefix
        1,
    )
    assert corrupted != text
    assert not report_matches_expected_shape(corrupted)


def test_shape_no_longer_bounds_the_unlabelled_lines_content_by_pattern():
    """SUPERSEDES the round-7 test that used to live under this name
    (`test_shape_rejects_a_false_claim_appended_to_unlabelled_records`),
    kept here renamed rather than deleted so the history stays attached to
    the line it is about. Round 7 fixed `_UNLABELLED_LINE_RE` to
    `\\S+(?: \\S+)*` -- one-or-more single-space-separated tokens -- which
    caught the double-spaced append below. PR #236 review round 11,
    Finding 1 proved that pattern was never correct in class, only in the
    one FORM every attack against this line happened to use: it also
    refused a legitimate name containing a real run of 2+ spaces
    ("ACME  Labs"), and it accepted the SAME claim worded without a double
    space. No pattern closes both directions without reopening the other,
    because check_record() places no format constraint on `name` at all
    -- a legitimate name and a forbidden claim can be byte-for-byte the
    same string. `report_matches_expected_shape()` therefore no longer
    checks this line's content by pattern (see the block comment above
    `_TOTAL_LINE_RE` and its own comment inline at the check site), so
    this SAME double-spaced attack -- once caught here -- is now
    correctly ACCEPTED by this function alone. It is caught instead by
    the source-derived check: see
    test_unlabelled_line_source_check_rejects_the_class_of_attacks_regardless_of_spacing
    and test_write_golden_refuses_to_write_when_the_unlabelled_line_does_not_match_the_source_feed
    below, which supersede this test's old assertion with the mechanism
    that actually closes both directions."""
    text = render_report()
    corrupted = text.replace(
        "Unlabelled records: Fennel Labs\n",
        "Unlabelled records: Fennel Labs  -- all 6 reported fields are "
        "checked by the validation rules.\n",
        1,
    )
    assert corrupted != text
    assert report_matches_expected_shape(corrupted)  # intentionally True now


def test_shape_accepts_an_unlabelled_line_with_several_names():
    """Accept-direction test for the tightened _UNLABELLED_LINE_RE (PR #236
    review round 7's own invitation-to-contradict: "if `\\S+(?: \\S+)*`
    rejects something render_report() can legitimately emit for the
    unlabelled line, that is the over-correction class again"). Real
    unlabelled names are joined with ", " (comma-space, a SINGLE space) --
    never a run of 2+ spaces -- so multiple names, and a hyphenated one,
    must still pass."""
    text = render_report(records=[
        {"name": "Fennel Labs", "amount": 100, "currency": "USD", "region": "NA", "tags": ""},
        {"name": "Jean-Pierre Holdings", "amount": 200, "currency": "USD", "region": "NA",
         "tags": ""},
    ])
    assert "Unlabelled records: Fennel Labs, Jean-Pierre Holdings" in text
    assert report_matches_expected_shape(text)


def test_shape_accepts_an_unlabelled_line_with_an_empty_tail():
    """PR #236 review round 10 (found by the coordinator, not a reviewer,
    before spending a review pass on it): a raw record with an empty id
    AND an empty name contributes "" to `unlabelled`, so render_report()
    legitimately emits "Unlabelled records: " with NOTHING after the
    trailing space -- a line shape that predates this PR (the base golden
    already has "Unlabelled records: Fennel Labs"; the renderer's own
    choice to emit an empty name here is out of scope and not touched).
    Round 10 fixed this by making the tail's empty case an explicit
    regex alternative; round 11 review replaced that regex entirely (see
    `report_matches_expected_shape()`'s own comment at the check site) --
    the position-only check this test now exercises accepts every tail,
    empty included, by construction, which is a strict superset of round
    10's fix. See
    test_unlabelled_line_source_check_accepts_the_legitimate_class below
    for the source-derived check's own coverage of this same case."""
    text = render_report(records=[{"id": "", "name": ""}])
    assert "Unlabelled records: \n" in text
    assert report_matches_expected_shape(text)


def test_shape_no_longer_bounds_an_appended_claim_after_an_empty_unlabelled_line():
    """SUPERSEDES the round-10 test that used to live under this name
    (`test_shape_rejects_a_false_claim_appended_after_an_empty_unlabelled_line`),
    kept renamed rather than deleted for the same reason as the test
    directly above test_shape_accepts_an_unlabelled_line_with_several_names:
    the history stays attached to the line it is about. Round 10's fix
    made the empty tail an explicit alternative inside a still-pattern-
    based regex, so appending a claim after the empty tail still failed
    that pattern. Round 11 review replaced the pattern entirely --
    `report_matches_expected_shape()` no longer checks this line's
    content at all (see its own comment at the check site) -- so this
    SAME append is now correctly ACCEPTED by this function alone. It is
    caught instead by the source-derived check: see
    test_unlabelled_line_source_check_rejects_the_class_of_attacks_regardless_of_spacing
    below."""
    text = render_report(records=[{"id": "", "name": ""}])
    corrupted = text.replace(
        "Unlabelled records: \n",
        "Unlabelled records:  -- all 6 reported fields are checked by the "
        "validation rules.\n",
        1,
    )
    assert corrupted != text  # the replacement landed
    assert report_matches_expected_shape(corrupted)  # intentionally True now


def test_the_rendered_unlabelled_line_matches_the_source_feed_on_the_real_report():
    """PR #236 review round 11, Finding 1 (BLOCKING): `_UNLABELLED_LINE_RE`
    (`^Unlabelled records: (?:\\S+(?: \\S+)*)?$`) accepts a claim worded
    WITHOUT a run of 2+ spaces -- "Fennel Labs all 6 reported fields are
    checked by the validation rules" fullmatches it, because "one-or-more
    single-space-separated tokens" is also what an ordinary English
    sentence is. `report_matches_expected_shape()` is a check on TEXT
    alone and cannot close this (see its own docstring). The actual
    closure runs against the SOURCE feed instead: `rendered_unlabelled_line()`
    recovers whatever line is really in the text; `expected_unlabelled_line()`
    re-derives what that line must be from `load_records()`'s raw feed,
    independently of render_report()'s own construction. Deliberately
    exercises the real, UNMOCKED render_report()/load_records() pipeline
    (unlike the monkeypatched write_golden() tests below) so that a real
    source mutation to render_report()'s unlabelled-line construction --
    appending a claim with or without a double space -- flows through this
    test and fails it BECAUSE the two values genuinely differ, not because
    a `.replace()` fixture literal stopped matching."""
    raw = load_records()
    text = render_report()
    assert rendered_unlabelled_line(text) == expected_unlabelled_line(raw)


def test_expected_unlabelled_line_matches_render_reports_own_construction():
    """Drift guard for expected_unlabelled_line()'s deliberate independence
    from render_report()'s own unlabelled-list construction (see
    expected_unlabelled_line()'s docstring for why the two are NOT allowed
    to share a helper -- sharing one would make the write_golden() check
    an oracle that compares an implementation to itself). Independence
    trades security for a real maintenance risk: an ordinary, non-
    adversarial code change to one side's selection logic (which field
    counts as "missing", the "?" fallback, the join separator) and not
    the other would silently make write_golden() start refusing legitimate
    output. This test is the guard against exactly that -- pinning the two
    against each other, across a sweep of inputs, so an accidental
    divergence fails a NAMED test in CI rather than surfacing later as a
    write_golden() refusal on real production output."""
    feeds = {
        "no unlabelled records": [
            {"id": "R-1", "name": "A", "amount": 1, "currency": "USD",
             "region": "NA", "tags": ""},
        ],
        "one unlabelled, plain name": [
            {"id": None, "name": "Fennel Labs", "amount": 1, "currency": "USD",
             "region": "NA", "tags": ""},
        ],
        "one unlabelled, internal double space": [
            {"id": None, "name": "ACME  Labs", "amount": 1, "currency": "USD",
             "region": "NA", "tags": ""},
        ],
        "two unlabelled": [
            {"id": None, "name": "Fennel Labs", "amount": 1, "currency": "USD",
             "region": "NA", "tags": ""},
            {"id": None, "name": "ACME  Labs", "amount": 1, "currency": "USD",
             "region": "NA", "tags": ""},
        ],
        "missing name entirely": [
            {"id": None, "amount": 1, "currency": "USD", "region": "NA", "tags": ""},
        ],
        "empty id and empty name": [
            {"id": "", "name": "", "amount": 1, "currency": "USD",
             "region": "NA", "tags": ""},
        ],
        "empty feed": [],
    }
    for label, raw in feeds.items():
        text = render_report(records=raw)
        assert rendered_unlabelled_line(text) == expected_unlabelled_line(raw), (
            f"expected_unlabelled_line() diverged from render_report()'s own "
            f"output on {label!r}"
        )


def test_unlabelled_line_source_check_accepts_the_legitimate_class():
    """Accept-direction sweep for the source-derived unlabelled-line check,
    run as a class (PR #236 review round 11, Section 1's 8-case accept
    table) -- every one of these is a legitimate render_report() output
    the source-comparison check must not refuse."""
    accept_cases = {
        "plain unlabelled name": [
            {"id": None, "name": "Fennel Labs", "amount": 1, "currency": "USD",
             "region": "NA", "tags": ""},
        ],
        "name with two consecutive spaces": [
            {"id": None, "name": "ACME  Labs", "amount": 1, "currency": "USD",
             "region": "NA", "tags": ""},
        ],
        "name with five consecutive spaces": [
            {"id": None, "name": "ACME     Labs", "amount": 1, "currency": "USD",
             "region": "NA", "tags": ""},
        ],
        "two unlabelled, one multi-space": [
            {"id": None, "name": "ACME  Labs", "amount": 1, "currency": "USD",
             "region": "NA", "tags": ""},
            {"id": None, "name": "Beta Co", "amount": 1, "currency": "USD",
             "region": "NA", "tags": ""},
        ],
        "missing name (the '?' fallback)": [
            {"id": None, "amount": 1, "currency": "USD", "region": "NA", "tags": ""},
        ],
        "empty id and empty name": [
            {"id": "", "name": "", "amount": 1, "currency": "USD",
             "region": "NA", "tags": ""},
        ],
        "no unlabelled records at all": [
            {"id": "R-1", "name": "A", "amount": 1, "currency": "USD",
             "region": "NA", "tags": ""},
        ],
        "name that reads like a claim": [
            {"id": None,
             "name": "all 6 reported fields are checked by the validation rules",
             "amount": 1, "currency": "USD", "region": "NA", "tags": ""},
        ],
    }
    for label, raw in accept_cases.items():
        text = render_report(records=raw)
        assert rendered_unlabelled_line(text) == expected_unlabelled_line(raw), (
            f"legitimate case {label!r} was refused by the source comparison"
        )


def test_unlabelled_line_source_check_rejects_the_class_of_attacks_regardless_of_spacing():
    """Reject-direction sweep (PR #236 review round 11, Section 1's 5-case
    reject table) -- including the case the current `_UNLABELLED_LINE_RE`
    gets WRONG (a claim worded without a run of 2+ spaces) and two more
    the regex was never even asked about (comma-joined, prepended). The
    source comparison must reject all five, unlike the regex, which only
    ever caught the double-spaced one."""
    raw = [{"id": None, "name": "Fennel Labs", "amount": 1, "currency": "USD",
            "region": "NA", "tags": ""}]
    text = render_report(records=raw)
    attacks = {
        "double-spaced claim (the one shape the old regex caught)": (
            "Unlabelled records: Fennel Labs\n",
            "Unlabelled records: Fennel Labs  -- all 6 reported fields are "
            "checked by the validation rules.\n",
        ),
        "single-spaced claim (Finding 1 -- the regex accepts this)": (
            "Unlabelled records: Fennel Labs\n",
            "Unlabelled records: Fennel Labs all 6 reported fields are "
            "checked by the validation rules\n",
        ),
        "claim appended after a comma": (
            "Unlabelled records: Fennel Labs\n",
            "Unlabelled records: Fennel Labs, all 6 fields checked\n",
        ),
        "claim prepended before the real name": (
            "Unlabelled records: Fennel Labs\n",
            "Unlabelled records: all 6 fields checked, Fennel Labs\n",
        ),
    }
    for label, (needle, replacement) in attacks.items():
        corrupted = text.replace(needle, replacement, 1)
        assert corrupted != text, f"{label!r} fixture did not land"
        assert rendered_unlabelled_line(corrupted) != expected_unlabelled_line(raw), (
            f"attack {label!r} was NOT detected by the source comparison"
        )

    # A fifth shape: the attack targets a name that is ALREADY multi-space,
    # proving the check does not merely fall back to the old regex's
    # double-space heuristic once a legitimate multi-space name is present.
    raw_multispace = [{"id": None, "name": "ACME  Labs", "amount": 1,
                        "currency": "USD", "region": "NA", "tags": ""}]
    text_multispace = render_report(records=raw_multispace)
    corrupted = text_multispace.replace(
        "Unlabelled records: ACME  Labs\n",
        "Unlabelled records: ACME  Labs  -- all 6 reported fields are "
        "checked\n",
        1,
    )
    assert corrupted != text_multispace
    assert rendered_unlabelled_line(corrupted) != expected_unlabelled_line(raw_multispace)


def test_write_golden_refuses_to_write_when_the_unlabelled_line_does_not_match_the_source_feed(
    tmp_path, monkeypatch
):
    """End-to-end reject-direction test for tools/write_golden.py's new
    source-comparison gate (PR #236 review round 11, Section 1's fix).
    Monkeypatches write_golden_mod.render_report to return a report whose
    unlabelled line carries a claim worded WITHOUT a run of 2+ spaces --
    exactly Finding 1's shape, which report_matches_expected_shape() alone
    (unchanged this round) still accepts -- while write_golden_mod.
    load_records is left returning the REAL feed, so the new check's
    comparison genuinely disagrees. Fails BECAUSE
    expected_unlabelled_line(raw) != rendered_unlabelled_line(rendered)
    inside write_golden(), not because a fixture literal stopped
    matching -- the raised RuntimeError's own message is read directly
    below, not just its type."""
    import tools.write_golden as write_golden_mod

    real_rendered = render_report()
    corrupted = real_rendered.replace(
        "Unlabelled records: Fennel Labs\n",
        "Unlabelled records: Fennel Labs all 6 reported fields are checked "
        "by the validation rules\n",
        1,
    )
    assert corrupted != real_rendered
    # The corrupted text must still pass the EXISTING shape check -- this
    # isolates the new check specifically, proving it catches what the old
    # one misses rather than merely restating it.
    assert report_matches_expected_shape(corrupted)

    monkeypatch.setattr(write_golden_mod, "render_report", lambda records=None: corrupted)

    with pytest.raises(RuntimeError) as excinfo:
        write_golden_mod.write_golden(tmp_path / "out.txt")
    assert not (tmp_path / "out.txt").exists()

    message = str(excinfo.value)
    assert "expected_unlabelled_line" in message
    assert "rendered:" in message and "expected:" in message
    assert "Fennel Labs all 6 reported fields are checked" in message  # the actual (wrong) line


def test_write_golden_writes_when_a_legitimate_multi_space_name_is_unlabelled(
    tmp_path, monkeypatch
):
    """Accept-direction companion, exercised through write_golden() itself
    (not just the comparison functions): a legitimate multi-space name --
    the exact case the old regex refused and this PR's escalation
    originally reported as unclosable -- must be ACCEPTED and written."""
    import tools.write_golden as write_golden_mod

    raw = [{"id": None, "name": "ACME  Labs", "amount": 100, "currency": "USD",
            "region": "NA", "tags": "settled"}]
    text = render_report(records=raw)
    assert "Unlabelled records: ACME  Labs" in text

    monkeypatch.setattr(write_golden_mod, "render_report", lambda records=None: text)
    monkeypatch.setattr(write_golden_mod, "load_records", lambda *a, **k: raw)

    out = write_golden_mod.write_golden(tmp_path / "out.txt")
    assert out.exists()
    assert "Unlabelled records: ACME  Labs" in out.read_text(encoding="utf-8")


def test_shape_accepts_reports_from_degenerate_feeds():
    """PR #236 review round 10, item 4: every over-correction on this item
    so far tested the reject direction and assumed the accept direction
    from a tidy example. Sweeps the accept direction across degenerate
    inputs AS A CLASS rather than one at a time: an empty feed, a feed
    where every record is rejected, and records missing id, missing name,
    or missing both -- any of which, if it produced a report the gate
    refused, would be the same finding again."""
    degenerate_feeds = {
        "empty feed": [],
        "every record rejected": [
            {"id": "R-1", "name": "X", "amount": "not-a-number",
             "currency": "USD", "region": "NA", "tags": ""},
        ],
        "record missing id": [
            {"name": "NoId", "amount": 100, "currency": "USD", "region": "NA", "tags": ""},
        ],
        "record missing name": [
            {"id": "R-1", "amount": 100, "currency": "USD", "region": "NA", "tags": ""},
        ],
        "record missing both id and name": [
            {"amount": 100, "currency": "USD", "region": "NA", "tags": ""},
        ],
        "record with empty-string id and name": [
            {"id": "", "name": "", "amount": 100, "currency": "USD", "region": "NA", "tags": ""},
        ],
        "one accepted record alongside one missing id": [
            {"id": "R-1", "name": "Ok", "amount": 100, "currency": "USD", "region": "NA",
             "tags": "settled"},
            {"name": "Ghost", "amount": 50, "currency": "USD", "region": "NA", "tags": ""},
        ],
    }
    for label, records in degenerate_feeds.items():
        text = render_report(records=records)
        assert report_matches_expected_shape(text), (
            f"degenerate feed {label!r} produced a report the gate refuses:\n{text!r}"
        )


def test_shape_rejects_a_corrupted_total_line_shape():
    """Distinct from test_shape_rejects_a_report_with_no_total_line_at_all
    (which deletes the line): this corrupts the line'S SHAPE in place --
    still present, still starts with the right prefix, but not a bare
    signed decimal -- proving _TOTAL_LINE_RE's fullmatch, not merely the
    line's presence."""
    text = render_report()
    corrupted = text.replace("Total (USD): 4595.66\n", "Total (USD): TBD\n", 1)
    assert corrupted != text
    assert not report_matches_expected_shape(corrupted)


def test_shape_rejects_a_corrupted_frozen_tail_line():
    text = render_report()
    corrupted = text.replace(
        "Amounts are shown in USD.\n", "Amounts are shown in USD!\n", 1
    )
    assert corrupted != text
    assert not report_matches_expected_shape(corrupted)


def test_write_golden_refuses_to_write_when_the_expected_shape_is_violated(
    tmp_path, monkeypatch
):
    """PR #236 review round 3, item 2 (coordinator-directed structural fix):
    every surviving false-claim mutation across rounds 2 through 5 needed
    exactly one `python -m tools.write_golden` run to go quiet against
    tests/test_golden.py, because that test only ever compares against
    whatever was last regenerated. Gating the regeneration step itself on
    report_matches_expected_shape() closes that path structurally: a render
    that would violate it is never written to disk in the first place,
    regardless of which (if any) test would otherwise have caught it.
    """
    import tools.write_golden as write_golden_mod

    monkeypatch.setattr(
        write_golden_mod, "render_report", lambda records=None: "not the real report\n"
    )
    with pytest.raises(RuntimeError):
        write_golden_mod.write_golden(tmp_path / "out.txt")
    assert not (tmp_path / "out.txt").exists()
