"""Tests for the rendered settlement report."""

from unittest.mock import patch

import pytest

from src import validate
from src.records import load_records
from src.report import (
    FROZEN_FOOTER_TAIL,
    LIST_VALUED_FIELDS,
    REPORTED_FIELDS,
    _cell,
    _format,
    _missing,
    render_report,
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
    """Pins today's exact LIST_VALUED_FIELDS value, and the one direction the
    module-level guard in src/report.py genuinely checks: a name declared
    here that has drifted out of REPORTED_FIELDS (dead config -- harmless,
    since an unreported field is never rendered). This does NOT, on its own,
    catch a REPORTED field whose real value turns out to be list-shaped
    without being declared here (PR #236 review round 3, Finding 3 --
    growing REPORTED_FIELDS leaves this subset relation true and this test
    green). That direction is checked separately, against real data, by
    test_every_actually_reported_list_value_is_declared_list_valued below."""
    assert LIST_VALUED_FIELDS == frozenset({"tags"})
    assert LIST_VALUED_FIELDS <= set(REPORTED_FIELDS)


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


def test_report_footer_facts_match_a_frozen_hand_authored_block():
    """PR #236 review round 3, Finding 1 (BLOCKING): round 2's version of
    this test used `_FROZEN_FOOTER_FACTS in text` -- substring containment,
    which proves the block is present *somewhere*, not *where*. A reworded
    false derived claim appended after the block, or inserted between
    "Amounts are shown in USD." and the block, left the block byte-identical
    and this assertion still held, even after `python -m tools.write_golden`.
    Fixed two ways: (1) `str.endswith`, not `in` -- constrains the block to
    be the literal end of the report, so nothing can be appended after it;
    (2) FROZEN_FOOTER_TAIL (in src/report.py, shared with
    tools/write_golden.py's own gate -- see the test below) now starts from
    "Total (USD): ..." rather than "Reported fields...", so there is no
    unowned line left between an earlier anchor this test already owns and
    the fields it cares about for an insertion to hide in.
    """
    assert render_report().endswith(FROZEN_FOOTER_TAIL)


def test_write_golden_refuses_to_write_when_the_frozen_footer_is_violated(
    tmp_path, monkeypatch
):
    """PR #236 review round 3, item 2 (coordinator-directed structural fix):
    every surviving false-claim mutation across rounds 2 and 3 needed
    exactly one `python -m tools.write_golden` run to go quiet against
    tests/test_golden.py, because that test only ever compares against
    whatever was last regenerated. Gating the regeneration step itself on
    FROZEN_FOOTER_TAIL closes that path structurally: a render that would
    violate the frozen tail is never written to disk in the first place,
    regardless of which (if any) test would otherwise have caught it."""
    import tools.write_golden as write_golden_mod

    monkeypatch.setattr(
        write_golden_mod, "render_report", lambda records=None: "not the real report\n"
    )
    with pytest.raises(RuntimeError):
        write_golden_mod.write_golden(tmp_path / "out.txt")
    assert not (tmp_path / "out.txt").exists()
