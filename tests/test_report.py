"""Tests for the rendered settlement report."""

import re
from decimal import Decimal

from src.parse import parse_tags
from src.records import load_records
from src.report import render_report
from src.validate import check_record

# The section of the report that comes after the region-grouped table and its
# subtotals: Net after fees, the three record counts, the unlabelled line,
# Total (USD), the settlement-pairs line and the validation-covers line. This
# is the literal, byte-for-byte tail that was committed to
# artifacts/report.golden.txt on origin/main *before* this item's grouping
# change landed (captured via `git show origin/main:artifacts/report.golden.txt`).
# The issue requires this section unchanged; pinning it here as a hardcoded
# before/after comparison catches a moved or altered tail even if a reader
# skimming the regenerated artifact would not notice.
PRE_CHANGE_TAIL = """Net after fees
--------------
R-1001       995
R-1002       403
R-1003      9775
R-1004       -15
R-1005      2313

Records read: 8
Records accepted: 5
Records rejected: 3

Unlabelled records: Fennel Labs
Total (USD): 4569.70
Amounts are shown in USD.
Settlement pairs in force: EU/EUR, NA/USD, APAC/JPY
Validation covers: id, name, amount, currency, region
"""


def _row_cells(text: str, id_prefix: str) -> list[str]:
    """Split a rendered table row back into its cell values.

    Cells are separated by runs of two or more spaces (the width-padding plus
    the two-space column separator `_table()` joins with); a lone comma or
    single space inside a cell (e.g. a tag) never produces a run that long.
    """
    line = next(line for line in text.splitlines() if line.startswith(id_prefix))
    return re.split(r"\s{2,}", line.strip())


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


def test_report_shows_each_records_tags():
    # R-1002's tags column in data/records.json is "na,settled", with no quoting
    # to worry about; the expected string is a literal here rather than
    # something produced by calling parse_tags()/check_record(), so this test
    # cannot be fooled by a shared bug in the code path it's checking.
    assert "na, settled" in render_report()


def test_report_tags_column_is_blank_for_no_tags():
    # A record with no "tags" key at all normalises to an empty list via
    # check_record() -> parse_tags(""). The report must show that as "-",
    # like every other blank cell, not as "[]" or an empty gap.
    record = {
        "id": "R-9001",
        "name": "No Tags Co",
        "amount": 100,
        "currency": "USD",
        "region": "NA",
    }
    text = render_report(records=[record])
    assert _row_cells(text, "R-9001")[-1] == "-"


def test_report_tags_column_round_trips_through_parse_tags():
    # R-1001's tags column in data/records.json is `eu,"high,priority",settled`
    # -- three tags, the middle one containing a comma. src.parse.parse_tags()
    # (fixed by #15) now honours the upstream quoting and recovers exactly
    # those three. The report's tags cell has to preserve that: if it joined
    # tags with a bare "," or ", " the way a naive renderer would, a reader
    # -- or a re-parse -- would see four tags instead of three, silently
    # reintroducing the same defect #15 fixed at the parsing end, just at the
    # output end instead.
    #
    # The expected value below is the known, hardcoded ground truth for
    # R-1001 (not something produced by calling parse_tags() to build its own
    # expectation); parse_tags() is called here only to check the round trip
    # through the *rendered* cell, which is the boundary this test exists to
    # pin.
    expected_tags = ["eu", "high,priority", "settled"]
    text = render_report()
    tags_cell = _row_cells(text, "R-1001")[-1]
    assert parse_tags(tags_cell) == expected_tags


def test_report_does_not_claim_all_fields_are_checked():
    # tags is reported but not one of validate.VALIDATED_FIELDS, so a report
    # that names 6 reported fields can no longer truthfully say "all reported
    # fields are checked by the validation rules." The fix is to not make that
    # claim at all (checked here), not to reword it into a different one.
    text = render_report()
    assert "reported fields are checked by the validation rules" not in text
    assert "Validation covers: id, name, amount, currency, region" in text


def test_report_groups_regions_in_declared_order():
    # The committed feed (data/records.json) has accepted records in all
    # three of validate.REGION_CODES, so this uses the real feed, not a
    # synthetic one. A line that is *exactly* one of the three region codes
    # can only come from the per-region header this item adds -- the flat,
    # ungrouped table never emits a line with just one of those tokens on it
    # (every data/header/rule line carries multiple space-separated fields) --
    # so this fails on the pre-grouping renderer, and also fails if the
    # groups are emitted in the wrong order (e.g. APAC before EU).
    text = render_report()
    region_lines = [line for line in text.splitlines() if line in ("EU", "NA", "APAC")]
    assert region_lines == ["EU", "NA", "APAC"]


def test_report_region_subtotals_are_bound_to_their_own_region():
    # Values from data/rates.json applied to data/records.json's accepted
    # rows via to_usd_cents()'s own formula (amount * rate // 100), computed
    # independently of render_report(): EU = 1200 EUR + 2750 USD -> 404600
    # cents (4046.00); NA = 450 USD + 10 USD -> 46000 cents (460.00);
    # APAC = 9800 JPY -> 6370 cents (63.70).
    #
    # Asserting the three "Subtotal (USD): ..." strings are merely *present*
    # would pass even if a subtotal were printed under the wrong region's
    # header (e.g. NA's amount shown under EU). Extracting the interleaved
    # sequence of region-header lines and subtotal lines and comparing it to
    # the exact expected sequence binds each subtotal to the region
    # immediately above it, so a swapped placement -- or a subtotal computed
    # from the wrong group -- fails this assertion.
    text = render_report()
    interleaved = re.findall(
        r"^(?:EU|NA|APAC|Subtotal \(USD\): [\d.-]+)$", text, flags=re.MULTILINE
    )
    assert interleaved == [
        "EU",
        "Subtotal (USD): 4046.00",
        "NA",
        "Subtotal (USD): 460.00",
        "APAC",
        "Subtotal (USD): 63.70",
    ]


def test_report_subtotals_sum_to_total():
    # Re-derives the "three subtotals sum to Total (USD)" invariant from the
    # rendered text itself (regex + Decimal), independent of the hardcoded
    # literals in test_report_region_subtotals_are_bound_to_their_own_region,
    # so a bug that changes all subtotal literals in a way that still summed
    # correctly (or a bug this test alone would need to catch) isn't hidden
    # by trusting the same fixed numbers twice. With no grouping there are
    # zero "Subtotal (USD):" matches, so the parsed sum is Decimal("0")
    # against a Total (USD) of 4569.70 -- this fails on the pre-grouping
    # renderer.
    text = render_report()
    subtotals = [Decimal(value) for value in re.findall(r"Subtotal \(USD\): (-?[\d.]+)", text)]
    (total,) = re.findall(r"Total \(USD\): (-?[\d.]+)", text)
    assert sum(subtotals) == Decimal(total)


def test_report_shows_exactly_one_region_header_for_a_single_region_feed():
    # The committed feed has accepted records in all three regions, so the
    # "region with no accepted records is omitted entirely" branch is
    # unreachable from it -- the only way to exercise that branch is a
    # synthetic record set that deliberately has just one region. This reuses
    # the single-record NA fixture from
    # test_report_tags_column_is_blank_for_no_tags (records=[...], not the
    # real feed) for exactly that reason.
    #
    # Asserting the absence of standalone "EU"/"APAC" lines would pass for a
    # reason unrelated to grouping: the flat, ungrouped renderer also never
    # emits those as standalone lines, for any input. Asserting there is
    # *exactly one* region-header line, that it is specifically "NA", and
    # that a subtotal line follows it, fails both when grouping is entirely
    # absent (zero header lines) and when the omit-empty-region rule is
    # dropped (three header lines, one per REGION_CODES entry, each with its
    # own -- here zero-record -- subtotal).
    record = {
        "id": "R-9002",
        "name": "Solo Region Co",
        "amount": 500,
        "currency": "USD",
        "region": "NA",
    }
    text = render_report(records=[record])
    lines = text.splitlines()
    region_lines = [line for line in lines if line in ("EU", "NA", "APAC")]
    assert region_lines == ["NA"]
    na_index = lines.index("NA")
    subsequent = lines[na_index + 1 :]
    assert any(re.match(r"^Subtotal \(USD\): [\d.-]+$", line) for line in subsequent)


def test_report_tail_after_grouped_table_is_byte_identical_to_pre_change_artifact():
    # Everything after the region-grouped table -- Net after fees, the three
    # record counts, the unlabelled line, Total (USD), settlement pairs and
    # validation-covers -- must be unchanged by this item (issue #19: "no
    # change to which records are accepted or rejected, and no change to
    # Net after fees" plus "everything after the table is unchanged"). A
    # regenerated golden artifact can preserve or subtly move this tail and
    # still *look* right to someone skimming it; comparing the rendered
    # text's tail against the literal pre-change content (captured from
    # origin/main's committed artifact, before this item's code ran) is a
    # real before/after check rather than a read-and-eyeball one.
    text = render_report()
    assert text.endswith(PRE_CHANGE_TAIL)


def test_report_column_widths_are_global_across_region_groups():
    # The plan's deliberate choice was widths computed once, globally, across
    # every accepted record (_column_widths(accepted)) and reused for every
    # region's _table(group, widths) call, specifically so columns line up
    # at the same horizontal position across region blocks. Comparing the
    # regenerated golden artifact to itself cannot police this: a per-group
    # rewrite (_table(group, _column_widths(group))) still passes
    # tests/test_golden.py's byte comparison once the artifact is
    # regenerated under the changed code, because both sides of that
    # comparison come from the same (broken) renderer. This test derives its
    # expectation from the rendered text's own structure instead, so it
    # fails on a per-group-widths renderer without touching the golden file.
    #
    # The committed feed (data/records.json) has near-equal name lengths
    # across regions, so a weak version of this assertion could pass by
    # coincidence even under per-group widths. This fixture is built
    # specifically to make global-vs-per-group widths diverge visibly: NA
    # gets a one-character name (its own narrowest possible column) while EU
    # gets a much longer one, so a per-group NA table would size its `name`
    # column to the 4-character field name itself, well short of EU's ~30
    # characters, and the two groups' header/rule/row lines would no longer
    # line up.
    records = [
        {
            "id": "R-9101",
            "name": "A",
            "amount": 1,
            "currency": "USD",
            "region": "NA",
        },
        {
            "id": "R-9102",
            "name": "A Very Long Company Name Company",
            "amount": 2,
            "currency": "EUR",
            "region": "EU",
        },
    ]
    text = render_report(records=records)
    lines = text.splitlines()

    region_lines = [line for line in lines if line in ("EU", "NA", "APAC")]
    assert region_lines == ["EU", "NA"]

    # Each region's header line is the line immediately after its region
    # code, and the rule line immediately after that (see _table(): header,
    # then the "----" rule, then data rows). Under global widths these are
    # character-identical across groups; under per-group widths the NA
    # group's shorter columns make its header/rule strings shorter than
    # EU's, and this assertion catches that without ever reading the golden
    # artifact.
    eu_index = lines.index("EU")
    na_index = lines.index("NA")
    eu_header, eu_rule = lines[eu_index + 1], lines[eu_index + 2]
    na_header, na_rule = lines[na_index + 1], lines[na_index + 2]

    assert na_header == eu_header
    assert na_rule == eu_rule

    # Belt-and-braces per the review finding's second suggested form: the
    # `amount` column (right-aligned, so its label sits flush against the
    # right edge of its slot) must start at the same character offset in
    # every group's data row, not just in the already-checked header/rule
    # lines. The header's "amount" label ends exactly where the currency
    # column's two-space separator begins, so that end index is the same
    # boundary a data row's amount cell is right-justified against.
    amount_label_end = eu_header.index("amount") + len("amount")
    assert amount_label_end == na_header.index("amount") + len("amount")

    eu_row = lines[eu_index + 3]
    na_row = lines[na_index + 3]
    assert eu_row[amount_label_end - 1] == "2"  # R-9102's amount, right-justified to the boundary
    assert na_row[amount_label_end - 1] == "1"  # R-9101's amount, at the SAME boundary under global widths
