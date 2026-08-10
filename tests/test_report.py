"""Tests for the rendered settlement report."""

from src import validate
from src.records import load_records
from src.report import LIST_VALUED_FIELDS, REPORTED_FIELDS, _cell, _missing, render_report
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
    """PR #236 review round 2, finding 4/A5: a second list-valued reported
    column added without updating LIST_VALUED_FIELDS silently renders raw
    Python repr instead of a joined value, and nothing fails. Pinning the
    exact set here means adding a column to REPORTED_FIELDS without a
    matching, deliberate edit to LIST_VALUED_FIELDS is a visible test
    failure. Full rendering coverage for a SECOND list-valued column is not
    added — no such column exists — see the CP2 marker's uncovered: field."""
    assert LIST_VALUED_FIELDS == frozenset({"tags"})
    assert LIST_VALUED_FIELDS <= set(REPORTED_FIELDS)


def test_a_non_tags_list_field_renders_with_str_not_a_dash():
    """The blank-on-[] rule is scoped to the tags column only (PR #236
    review, finding B1/B2: a type-based rule applied to every column both
    crashed on a non-string list and silently started dashing `id: []`).
    Every other field keeps its original str(value) rendering, unchanged."""
    assert _cell({"id": []}, "id") == "[]"


def test_a_non_list_tags_value_renders_via_str_not_a_char_join_or_crash():
    """Regression test for PR #236 review round 2, finding 3/A4: the first
    fix scoped list-shaped rendering by FIELD NAME alone, deleting the
    isinstance() guard _format() used to have. Field name is orthogonal to
    type, so a tags value that reaches _cell() as anything other than a
    list — a direct caller of _cell(), or any future code path that stops
    normalising before this point — got joined regardless: a string silently
    split into characters (", ".join("settled") -> "s, e, t, t, l, e, d"),
    and an int/bool/float raised TypeError where the pre-fix code rendered
    them fine via str(value). The discriminator is now
    `field in LIST_VALUED_FIELDS and isinstance(value, list)`, so every
    non-list value — whatever the field name — falls back to the same
    str(value) every other field already uses, unconditionally."""
    assert _cell({"tags": "settled"}, "tags") == "settled"
    assert _cell({"tags": 42}, "tags") == "42"
    assert _cell({"tags": True}, "tags") == "True"
    assert _cell({"tags": 0.5}, "tags") == "0.5"
    assert _cell({"tags": {"a": 1}}, "tags") == str({"a": 1})


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


# Authored by hand, independent of REPORTED_FIELDS, VALIDATED_FIELDS, and of
# tools/write_golden.py (which writes artifacts/report.golden.txt, never this
# file). PR #236 review round 2, finding 1/A1 (BLOCKING): the prior version
# of this test asserted only the ABSENCE of one known-bad substring
# ("checked by the validation rules"). The set of possible false derived
# claims is unbounded, so an absence check can never enumerate it — the
# reviewer reworded the claim ("5/6 reported fields are validated; all
# reported fields are covered", still false: tags is reported but not
# validated) and it shipped green through all 41 tests, including after
# `python -m tools.write_golden`. An exact whole-block match has no pattern
# to evade: ANY added, removed, or reworded line changes the bytes and fails
# this assertion, whatever its wording.
_FROZEN_FOOTER_FACTS = (
    "Reported fields (6): id, name, region, amount, currency, tags\n"
    "Validated fields (5): id, name, amount, currency, region\n"
    "Settlement pairs in force: EU/EUR, NA/USD, APAC/JPY\n"
)


def test_report_footer_facts_match_a_frozen_hand_authored_block():
    text = render_report()
    assert _FROZEN_FOOTER_FACTS in text
