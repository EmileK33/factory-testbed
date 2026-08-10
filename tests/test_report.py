"""Tests for the rendered settlement report."""

from src import validate
from src.records import load_records
from src.report import REPORTED_FIELDS, _cell, _missing, render_report
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


def test_missing_agrees_with_validate_missing_for_every_case_including_empty_list():
    """PR #236 review, finding B4/F4: report._missing() was widened to treat
    `[]` as blank for every field, which desynced it from validate._missing()
    (the two are compared, not shared, on purpose — see the comment above
    report._missing()) and let a raw record with id=[] be simultaneously
    ACCEPTED by check_record() and listed as UNLABELLED by render_report().
    report._missing() is restored to its original body; this pins that it
    once again agrees with validate._missing() on every case, including the
    one that diverged. The tags-only blank-list rule lives in _cell(), not
    in this predicate — see test_blank_tags_cell_renders_as_a_dash above and
    test_a_non_tags_list_field_renders_with_str_not_a_dash below."""
    for value in (None, "", [], (), 0, False, {}, "x", ["x"], ["x", "y"]):
        assert _missing(value) == validate_missing(value), value


def test_a_non_tags_list_field_renders_with_str_not_a_dash():
    """The blank-on-[] rule is scoped to the tags column only (PR #236
    review, finding B1/B2: a type-based rule applied to every column both
    crashed on a non-string list and silently started dashing `id: []`).
    Every other field keeps its original str(value) rendering, unchanged."""
    assert _cell({"id": []}, "id") == "[]"


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


def test_report_never_states_a_derived_field_coverage_claim():
    """Pins the actual design property this item's four CP1 gate rounds were
    about: the report must never assert a relationship between REPORTED_FIELDS
    and VALIDATED_FIELDS ("All N reported fields are checked...", "N of M
    reported fields are checked...") -- it may only state each field set as
    an independent fact.

    PR #236 review, finding F1 (BLOCKING): no test asserted this absence.
    The reviewer reintroduced the old derived sentence, ran
    `python -m tools.write_golden` (the documented regeneration step), and
    the entire 37-test suite went green with a false claim baked into the
    committed artifact — because the golden test only compares against
    whatever was just regenerated, and no other test read the live text for
    this specific phrase. This assertion reads render_report()'s live output
    directly, not the committed golden file, so it is not defeated by
    regenerating the golden, and it does not derive its expected value from
    REPORTED_FIELDS or VALIDATED_FIELDS, so it is not defeated by editing
    either tuple.
    """
    text = render_report()
    assert "checked by the validation rules" not in text
