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
    render_report,
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
    correction): the original _NET_ROW_RE (`^\\S+ {2,}-?\\d+$`) refused an
    id containing whitespace, but check_record() never validates id
    FORMAT -- only that it is present -- so a raw feed id containing a
    space is legitimate, render_report() emits it, and the old regex made
    write_golden() refuse a genuinely correct artifact. Every round before
    this one tested only that the gate REJECTS bad input; this is the
    first test that it still ACCEPTS good input. _NET_ROW_RE now allows
    arbitrary content before the mandatory "  " + signed-integer tail."""
    text = render_report(records=[
        {"id": "R 1001", "name": "Spacey", "amount": 100, "currency": "USD",
         "region": "NA", "tags": "settled"},
    ])
    assert "R 1001        70" in text  # the net row rendered with the id intact
    assert report_matches_expected_shape(text)


def test_shape_rejects_a_false_claim_spliced_into_a_net_row():
    """PR #236 review round 8, Finding 1/A2 (BLOCKING): round 6's
    `_NET_ROW_RE` relaxation (`^.+ {2,}-?\\d+$`, to fix the A3 over-
    correction) went further than A3 required -- `.+` grants arbitrary
    content INCLUDING runs of 2+ spaces, so a whole sentence spliced
    before the numeric tail ("R-1001  -- all 6 reported fields are
    checked by the validation rules       995") still fullmatch'd, real
    source mutation, 76/76 green. The prior round's own regression test
    for this regex used a corruption with no trailing digits -- a
    strictly weaker attack the regex already rejected, so it never
    actually isolated the gap. This corruption keeps the real numeric
    tail intact, which is what made the round-6 regex's `.+` head the
    actual hole. Fixed with the same principle as _UNLABELLED_LINE_RE:
    `\\S+(?: \\S+)*` -- single-space-separated tokens only, which
    `_table()`/`apply_fees()` never produce internally, so it excludes
    exactly the runs of 2+ spaces an inserted claim needs."""
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
    """PR #236 review round 7, Finding 2: c7 (_NET_ROW_RE) is masked by the
    round-6 row-count cross-check for INSERTED/DELETED lines (which the
    cross-check catches via the count mismatch), but not for a net row
    whose content is REPLACED with something differently-shaped while the
    total row count stays the same -- only _NET_ROW_RE's own fullmatch
    catches that. Preserves the row count (one line swapped for one line)
    so this isolates the shape check specifically."""
    text = render_report()
    corrupted = text.replace(
        "R-1001       995\n",
        "All 6 reported fields are checked by the validation rules.\n",
        1,
    )
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


def test_shape_rejects_a_false_claim_appended_to_unlabelled_records():
    """PR #236 review round 7, Finding 1/A1 (BLOCKING): round 6's
    `_UNLABELLED_LINE_RE = r"^Unlabelled records: .+$"` was a `fullmatch`
    against a wildcard -- the same unconstrained tail `startswith` had,
    just spelled with `fullmatch` instead. The reviewer's exact reproduction
    of the original P8 attack (round 6) still shipped, 71/71 effectively
    green: "Unlabelled records: Fennel Labs  -- all 6 reported fields are
    checked by the validation rules." Fixed with
    `\\S+(?: \\S+)*` after the prefix -- one-or-more single-space-separated
    tokens, which a run of 2+ spaces (the shape every appended clause in
    this item's history has used) cannot satisfy."""
    text = render_report()
    corrupted = text.replace(
        "Unlabelled records: Fennel Labs\n",
        "Unlabelled records: Fennel Labs  -- all 6 reported fields are "
        "checked by the validation rules.\n",
        1,
    )
    assert corrupted != text
    assert not report_matches_expected_shape(corrupted)


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
