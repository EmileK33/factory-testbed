"""Tests for the rendered settlement report."""

from src.normalise import apply_fees
from src.records import load_records
from src.report import REPORTED_FIELDS, render_report
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


def test_report_shows_the_tags_column_header():
    assert "tags" in REPORTED_FIELDS
    header_line = render_report().splitlines()[3]
    assert "tags" in header_line


def test_report_shows_each_accepted_records_tags():
    # LITERAL expectations, deliberately not derived from check_record().
    # The earlier form built the expected string by calling check_record() again,
    # so both sides of the assertion came from the same parse_tags() call: it
    # could catch a rendering bug in report.py but was structurally incapable of
    # catching a MIS-PARSE, because the mis-parse appeared identically on both
    # sides. A test comparing the implementation to itself passes by construction.
    text = render_report()
    for expected in ("na, settled", "apac, bulk", "na, small", "eu, crossborder"):
        assert expected in text, "expected tag rendering %r missing" % expected


def test_report_renders_a_quoted_tag_as_the_feed_declares_it():
    # R-1001's tags column is 'eu,"high,priority",settled'. parse.py's own
    # docstring says a tag containing a comma is wrapped in double quotes, so
    # this record carries THREE tags and the middle one is "high,priority".
    # src/parse.py now honours that quoting (issue #87), so this asserts
    # normally instead of being pinned as a known-wrong xfail.
    text = render_report()
    assert "eu, high,priority, settled" in text


def test_report_renders_an_empty_tag_list_as_a_dash():
    record = {
        "id": "R-9001",
        "name": "No Tags Co",
        "amount": 100,
        "currency": "USD",
        "region": "NA",
    }
    text = render_report(records=[record])
    row_line = [line for line in text.splitlines() if line.startswith("R-9001")][0]
    assert row_line.split()[-1] == "-"


# --- Net after fees: the amount column aligns on a stable right edge (#97) ---


def test_net_after_fees_amounts_align_on_a_stable_right_edge():
    """Criteria 1 & 2: every line ends at the same column, and that column is
    the widest rendered net's width plus the fixed label width (the id column,
    padded to its own widest value, plus the 2-space gutter).

    R-1's net (925) and R-22's net (94975) deliberately differ in both id
    length and net digit-length, so a fixed-width-8 implementation would
    still "pass" a naive length check by coincidence - the formula assertion
    below is what actually pins the alignment to the data instead of to the
    number 8.
    """
    records = [
        {"id": "R-1", "name": "One", "amount": 1000, "currency": "USD", "region": "NA"},
        {"id": "R-22", "name": "Two", "amount": 100000, "currency": "USD", "region": "NA"},
    ]
    text = render_report(records=records)
    lines = text.splitlines()
    start = lines.index("Net after fees") + 2
    row_lines = lines[start : start + len(records)]
    assert len(row_lines) == len(records)

    accepted = [check_record(r) for r in records]
    nets = apply_fees(accepted)
    assert [row["net"] for row in nets] == [925, 94975]
    net_width = max(len(str(row["net"])) for row in nets)
    id_width = max(len(row["id"]) for row in accepted)
    # The two nets differ in digit-length, so this genuinely exercises padding
    # rather than being satisfied vacuously.
    assert len({len(str(row["net"])) for row in nets}) > 1

    assert len({len(line) for line in row_lines}) == 1
    assert len(row_lines[0]) == net_width + id_width + 2
    assert row_lines[0].endswith(str(925).rjust(net_width))
    assert row_lines[1].endswith(str(94975).rjust(net_width))


def test_net_after_fees_uniform_8_char_width_matches_todays_fixed_padding():
    """Criterion 3 (as corrected on #97): a feed whose nets are all exactly 8
    characters wide - today's hardcoded field width - must render identically
    to the legacy fixed-width formula ``f"{id}  {net:>8}"``. This is the one
    uniform width where the old code and the data-derived width coincide;
    any other uniform width legitimately changes (that's covered by the
    alignment test above, not asserted here).
    """
    records = [
        {"id": "R-1", "name": "One", "amount": 10_000_025, "currency": "JPY", "region": "APAC"},
        {"id": "R-2", "name": "Two", "amount": 100_000_024, "currency": "JPY", "region": "APAC"},
    ]
    accepted = [check_record(r) for r in records]
    nets = apply_fees(accepted)
    assert [len(str(row["net"])) for row in nets] == [8, 8]  # both exactly today's width

    text = render_report(records=records)
    lines = text.splitlines()
    start = lines.index("Net after fees") + 2
    row_lines = lines[start : start + len(records)]

    legacy_formula = [f"{row['id']}  {row['net']:>8}" for row in nets]
    assert row_lines == legacy_formula


def test_net_after_fees_handles_no_accepted_records():
    """Robustness: an all-rejected feed must not raise (``max()`` over an
    empty sequence would, without the ``default=0`` guard) and the block's
    header/divider must still render.
    """
    rejected_only = [{"name": "No Id", "amount": 100, "currency": "USD", "region": "NA"}]
    text = render_report(records=rejected_only)
    lines = text.splitlines()
    start = lines.index("Net after fees")
    assert lines[start + 1] == "--------------"
    assert lines[start + 2] == ""


def test_report_states_how_many_reported_fields_are_validated():
    assert "5 of 6 reported fields are checked by the validation rules." in render_report()


def test_pairs_claim_matches_enforcement():
    """The report's settlement-pairs sentence must not claim more than the
    validator actually enforces.

    Builds a probe record whose region and currency are each individually
    valid but whose combination is outside ALLOWED_PAIRS, then asks
    check_record() - not this test's assumptions - whether pairs are
    enforced today. The report text must agree with that live answer. This
    fails in BOTH directions: if the wording claims enforcement that
    check_record() doesn't perform, or if check_record() starts enforcing
    pairs without the wording being restored to say so.
    """
    from src.validate import ALLOWED_PAIRS, CURRENCY_CODES, REGION_CODES, check_record

    declared = set(ALLOWED_PAIRS)
    unpaired = next(
        (region, currency)
        for region in REGION_CODES
        for currency in CURRENCY_CODES
        if (region, currency) not in declared
    )
    region, currency = unpaired
    probe = {
        "id": "TEST-PAIR-PROBE",
        "name": "probe",
        "amount": 100,
        "currency": currency,
        "region": region,
    }
    pairs_enforced = check_record(probe) is None

    text = render_report(records=[probe])
    if pairs_enforced:
        assert "Settlement pairs in force" in text
    else:
        assert "Settlement pairs in force" not in text
        assert "not enforced" in text.lower()


# --- The rejection footer: closes the report, sourced only from summarise(). ---


def test_report_footer_lists_the_rejection_reason_and_count():
    text = render_report()
    lines = text.splitlines()
    header_index = lines.index("Rejected records")
    assert lines[header_index + 1] == "-" * len("Rejected records")
    assert lines[header_index + 2] == "missing id: 1"
    # Nothing trails the footer.
    assert len(lines) == header_index + 3


def test_report_footer_states_no_rejections_when_the_feed_is_clean():
    # The empty case: a feed in which nothing is rejected must still produce a
    # coherent footer - an explicit line, not a silently-omitted section (the
    # defect the existing "Unlabelled records" guard has: it just disappears
    # when there's nothing to report).
    clean_records = [
        {"id": "R-1", "name": "One", "amount": 100, "currency": "USD", "region": "NA"},
        {"id": "R-2", "name": "Two", "amount": 200, "currency": "EUR", "region": "EU"},
    ]
    text = render_report(records=clean_records)
    lines = text.splitlines()
    header_index = lines.index("Rejected records")
    assert lines[header_index + 1] == "-" * len("Rejected records")
    assert lines[header_index + 2] == "No records were rejected."
    assert len(lines) == header_index + 3


def test_report_footer_lists_multiple_reasons_each_on_its_own_line():
    mixed_records = [
        {"id": "R-1", "name": "One", "amount": 100, "currency": "USD", "region": "NA"},
        {"name": "No Id", "amount": 100, "currency": "USD", "region": "NA"},
        {"id": "R-3", "name": "Bad Currency", "amount": 100, "currency": "GBP", "region": "NA"},
    ]
    text = render_report(records=mixed_records)
    lines = text.splitlines()
    header_index = lines.index("Rejected records")
    assert lines[header_index + 2] == "missing id: 1"
    assert lines[header_index + 3] == "unknown currency: 1"
    assert len(lines) == header_index + 4


def test_report_footer_reason_total_matches_the_records_rejected_line():
    text = render_report()
    assert "Records rejected: 1" in text
    assert "missing id: 1" in text
