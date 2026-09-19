"""Tests for the rendered settlement report."""

import unittest.mock as mock

import pytest

from src.records import load_records
from src.report import _escape_tag, _table, render_report, validation_coverage_line
from src.validate import check_record

CLEAN = {
    "id": "R-8001",
    "name": "Report Test Co",
    "amount": 500,
    "currency": "USD",
    "region": "NA",
    "tags": "na,test",
}

# Hand-captured from artifacts/report.golden.txt as committed on main BEFORE #247 (i.e.
# before the "Rejected records" footer existed), NOT derived from render_report() itself --
# doing so would make the comparison below tautological. Everything through the final
# "Validation covers: ..." line, inclusive, must remain byte-for-byte identical: #247 may
# only ever APPEND a footer after it, never change a line above it.
PRE_FOOTER_TEXT = (
    "Settlement report\n=================\n\n"
    "id      name            region  amount  currency  tags\n"
    "------  --------------  ------  ------  --------  ---------------------------\n"
    "R-1001  Aster Holdings  EU        1200  EUR       eu, high, priority, settled\n"
    "R-1002  Borel Systems   NA         450  USD       na, settled\n"
    "R-1003  Chandra Foods   APAC      9800  JPY       apac, bulk\n"
    "R-1004  Delta Freight   NA          10  USD       na, small\n"
    "R-1005  Eiger Metals    EU        2750  USD       eu, crossborder\n"
    "R-1007  Garnet Rail     EU         640  EUR       eu, rail\n"
    "R-1008  Halcyon Air     NA         720  USD       na, air\n\n"
    "Net after fees\n--------------\n"
    "R-1001       995\nR-1002       403\nR-1003      9775\nR-1004       -15\n"
    "R-1005      2313\nR-1007       519\nR-1008       659\n\n"
    "Records read: 8\nRecords accepted: 7\nRecords rejected: 1\n\n"
    "Unlabelled records: Fennel Labs\n"
    "Total (USD): 5980.90\n"
    "Amounts are shown in USD.\n"
    "5 of 6 reported fields are checked by the validation rules.\n"
    "Settlement pairs in force: EU/EUR, NA/USD, APAC/JPY\n"
    "Validation covers: id, name, amount, currency, region\n"
)


def _line_starting_with(text, prefix):
    """The one line in *text* that starts with *prefix*, matched exactly (not a
    substring search) -- "Records read: 5" must not match a rendered "Records read: 51",
    which `"Records read: 5" in text` would silently accept."""
    return next(line for line in text.splitlines() if line.startswith(prefix))


def _footer_lines(text):
    """The footer's own lines, from the "Rejected records" header to the end, exactly --
    used to pin both the exact text of each line and their order, rather than checking
    each reason string is merely present somewhere in the whole report."""
    return text[text.index("Rejected records\n"):].rstrip("\n").splitlines()


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


def test_report_includes_a_tags_column_header():
    text = render_report()
    header = text.splitlines()[3]
    assert "tags" in header


def test_report_puts_each_records_tags_on_its_own_row():
    text = render_report()
    accepted = [row for row in (check_record(r) for r in load_records()) if row]
    lines = text.splitlines()
    for row in accepted:
        row_line = next(candidate for candidate in lines if candidate.startswith(row["id"] + " "))
        assert row_line.rstrip().endswith(", ".join(row["tags"]))


def test_report_blanks_a_record_with_no_tags():
    # No row in the shipped feed (data/records.json) has an empty tags column, so this synthetic
    # record is the only thing exercising _cell()'s empty-list-to-"-" branch at all.
    record = {
        "id": "R-9001",
        "name": "No Tags Co",
        "amount": 100,
        "currency": "USD",
        "region": "NA",
        "tags": "",
    }
    text = render_report(records=[record])
    lines = text.splitlines()
    row_line = next(candidate for candidate in lines if candidate.startswith("R-9001 "))
    assert row_line.rstrip().endswith("-")


def test_report_states_the_true_validated_vs_reported_field_counts():
    # Hardcoded, not derived from validate.VALIDATED_FIELDS / report.REPORTED_FIELDS: id, name,
    # amount, currency, region are checked by check_record() (5); tags is reported but only
    # normalised, not checked (+1) = 6 reported fields total.
    assert "5 of 6 reported fields are checked by the validation rules." in render_report()


@pytest.mark.parametrize("field", ["id", "name"])
def test_report_still_stringifies_a_non_tags_list_value(field):
    # check_record() has no type guard on id/name beyond _missing() -- region/currency/amount each
    # reject a list value outright via their own guards -- so a record with a list-valued id or
    # name is accepted unchanged. _cell()'s tags-only list branch must not fire for these fields:
    # today's formatting for a list value (str([1]) == "[1]") is odd and unintentional, not a
    # designed behaviour, but it must survive unchanged rather than raising TypeError from an
    # unscoped ", ".join(value). Two separate parametrised cases (not one test with two asserts)
    # so a mutation that breaks only one of id/name is attributed to the specific case, not "test
    # 5 in general".
    record = {
        "id": "R-9002",
        "name": "List Value Co",
        "amount": 50,
        "currency": "USD",
        "region": "NA",
        "tags": "",
    }
    record[field] = [1]
    text = render_report(records=[record])
    row_line = text.splitlines()[5]
    assert "[1]" in row_line


@pytest.mark.parametrize(
    "separator",
    [chr(0x0A), chr(0x0B), chr(0x0C), chr(0x0D), chr(0x1C), chr(0x1D), chr(0x1E), chr(0x85), chr(0x2028), chr(0x2029)],
    ids=["LF", "VT", "FF", "CR", "FS", "GS", "RS", "NEL", "LS", "PS"],
)
def test_report_never_lets_a_tag_forge_an_extra_physical_row(separator):
    # A tag carrying a character str.splitlines() treats as a line break reaches _cell()
    # unfiltered by parse_tags() -- a pre-existing gap in src/parse.py, tracked separately and
    # deliberately not fixed here. _table() must still guarantee exactly one physical output line
    # per logical row it returns. Asserting on splitlines() here, not split("\n"): split("\n")
    # cannot distinguish an escape that covers only ASCII "\n" from one that covers the whole
    # property str.isprintable() identifies, because U+0085/U+2028/U+2029 are not "\n" and
    # split("\n") would report the row count as unchanged even while it is actually forged.
    # splitlines() is also the natural way any real consumer -- a terminal, a log viewer, a
    # diff -- would split the rendered report into lines, which is the actual threat model.
    rows = [
        {
            "id": "R-9003",
            "name": "Newline Co",
            "region": "NA",
            "amount": 75,
            "currency": "USD",
            "tags": [f"high{separator}forged row, y"],
        }
    ]
    logical_lines = _table(rows)
    physical_lines = "\n".join(logical_lines).splitlines()
    assert len(physical_lines) == len(logical_lines)


def test_report_escapes_a_line_separator_from_the_raw_feed_through_the_full_pipeline():
    # No committed test exercised the full check_record() -> render_report() path with a raw feed
    # string carrying a line-breaking character -- only the already-parsed-list form (above) was
    # covered. U+2028 LINE SEPARATOR is used because it is one of the three separators the
    # ASCII-only "\x00-\x1f\x7f" denylist (this module's first attempt at this fix) missed.
    record = {
        "id": "R-9004",
        "name": "LS Co",
        "amount": 20,
        "currency": "USD",
        "region": "NA",
        "tags": "high" + chr(0x2028) + "forged row",
    }
    text = render_report(records=[record])
    lines = text.splitlines()
    # Checked directly by execution rather than assumed: render_report() now ends with the
    # "Rejected records" footer, not the coverage line -- for this single, valid record
    # lines[-1] is "None rejected." regardless of a forged row earlier in the table --
    # asserting on it would pass whether or not this fix exists, so it is deliberately not
    # asserted here. What a forged row actually corrupts is the table itself: the tag's text
    # spills past this record's own row into what looks like an extra, unattributed physical
    # line, so the row itself stops containing its own tag.
    row_line = next(candidate for candidate in lines if candidate.startswith("R-9004 "))
    assert "forged row" in row_line


@pytest.mark.parametrize(
    "char",
    [
        chr(0x0A), chr(0x0B), chr(0x0C), chr(0x0D), chr(0x1C), chr(0x1D), chr(0x1E),
        chr(0x85), chr(0x2028), chr(0x2029),
        chr(0x00), chr(0x07),
    ],
    ids=["LF", "VT", "FF", "CR", "FS", "GS", "RS", "NEL", "LS", "PS", "NUL", "BEL"],
)
def test_report_escapes_every_control_or_line_break_character_in_a_tag(char):
    # Reject half. The ten Unicode category Cc/Zl/Zp codepoints str.splitlines() treats as a line
    # break, plus two more Cc control characters (NUL, BEL) that do not forge a row but still do
    # not belong unescaped in a report cell -- _escape_tag() escapes by category, not by an
    # enumerated list of line breaks, so a plain control character must be caught by the same rule.
    tag = f"high{char}priority"
    escaped = _escape_tag(tag)
    assert char not in escaped
    assert "high" in escaped
    assert "priority" in escaped


@pytest.mark.parametrize(
    "value",
    [
        chr(0x1F468) + chr(0x200D) + chr(0x1F469) + chr(0x200D) + chr(0x1F467),  # ZWJ family emoji
        chr(0x2764) + chr(0xFE0F),  # heart + variation selector
        chr(0x1F44D) + chr(0x1F3FD),  # thumbs up + medium skin tone modifier
        "a" + chr(0xA0) + "b",  # non-breaking space
        chr(0xE9),  # e with acute (non-ASCII letter)
        "high  priority",  # internal double space (the column separator itself)
    ],
    ids=[
        "zwj_family_emoji",
        "emoji_variation_selector",
        "emoji_skin_tone_modifier",
        "nonbreaking_space",
        "non_ascii_letter",
        "internal_double_space",
    ],
)
def test_report_leaves_legitimate_tag_content_unchanged(value):
    # Accept half. A category-based escape that is tight enough to reject only Cc/Zl/Zp must still
    # say yes to everything else: a join-control character (Cf, ZWJ) joining a compound emoji into
    # one glyph, a combining mark (Mn, a variation selector or skin-tone modifier) attached to a
    # base emoji, ordinary spacing (Zs, non-breaking space) that is not a line break, a non-ASCII
    # letter, and a tag that itself contains the column separator (two spaces) -- none of these is
    # a line break or a C0/C1 control character, so none should be touched. This enumeration is not
    # exhaustive of every printable-but-unusual character that could appear in a tag (Cf format
    # characters other than ZWJ, or other combining-mark sequences, are not separately covered) --
    # it covers the specific classes named in review round 4, plus the column-separator case
    # flagged as a design note (not fixed, per instruction) to confirm this escape does not
    # incidentally interfere with it either.
    assert _escape_tag(value) == value


def test_report_body_above_the_footer_is_unchanged():
    assert render_report().startswith(PRE_FOOTER_TEXT)


def test_report_footer_dashes_match_the_header_length():
    text = render_report()
    idx = text.index("Rejected records\n")
    header_line, dash_line = text[idx:].splitlines()[:2]
    assert dash_line == "-" * len(header_line)
    assert len(dash_line) == 16


def test_report_handles_an_empty_feed_without_a_keyerror():
    # The footer's "Records rejected" line must never read summary["rejected"] (a
    # pre-existing, deliberately-untouched conditional key, absent when nothing is
    # rejected) -- doing so would KeyError on exactly this input. Each count line is
    # matched exactly, not by substring: "Records rejected: 0" in text would also accept
    # a corrupted "Records rejected: 01".
    text = render_report(records=[])
    assert _line_starting_with(text, "Records read:") == "Records read: 0"
    assert _line_starting_with(text, "Records accepted:") == "Records accepted: 0"
    assert _line_starting_with(text, "Records rejected:") == "Records rejected: 0"
    assert _footer_lines(text) == ["Rejected records", "----------------", "None rejected."]


def test_report_handles_an_all_accepted_feed_without_a_keyerror():
    # Same KeyError risk as the empty-feed case above, but with a non-empty feed where
    # everything is accepted -- "rejected" is still absent from the summary here.
    clean_feed = [{**CLEAN, "id": f"X-{i}"} for i in range(7)]
    text = render_report(records=clean_feed)
    assert _line_starting_with(text, "Records rejected:") == "Records rejected: 0"
    assert _footer_lines(text) == ["Rejected records", "----------------", "None rejected."]


def test_report_all_three_count_lines_come_from_the_summary_not_the_raw_input():
    # The load-bearing constraint: the renderer must PRESENT what summarise() reports,
    # never re-derive it -- byte for byte, not just numerically. Real input here is 2
    # accepted records (real total=2, accepted=2, rejected_count=0); the injected summary
    # uses total=5, accepted=3, and -- deliberately NOT total-accepted (which would be
    # 2) -- rejected_count=999, so a renderer that still computed `total - accepted`
    # itself, instead of printing summary["rejected_count"] directly, would fail this.
    # The injected reason is deliberately mixed-case WITH leading/trailing spaces and
    # not already title-cased: "zz-impossible-reason-xyz" (an earlier version of this
    # test) is already all-lowercase, so a renderer applying reason.lower() -- or
    # .upper() / .strip() / .title() -- before printing it would still pass. Every one
    # of those four transformations changes this string, so all four are observable.
    # Each line is matched exactly (via _line_starting_with / _footer_lines), not by
    # substring: "Records read: 5" in text would also accept a corrupted "Records read: 51".
    clean2 = {**CLEAN, "id": "R-8002"}
    fake_summary = {
        "total": 5, "accepted": 3, "rejected_count": 999, "by_tag": {},
        "rejection_reasons": [{"reason": "  Mixed Case REASON value  ", "count": 12}],
    }
    with mock.patch("src.report.summarise", return_value=fake_summary):
        text = render_report(records=[CLEAN, clean2])
    assert _line_starting_with(text, "Records read:") == "Records read: 5"
    assert _line_starting_with(text, "Records accepted:") == "Records accepted: 3"
    assert _line_starting_with(text, "Records rejected:") == "Records rejected: 999"
    assert _footer_lines(text) == [
        "Rejected records", "----------------", "  Mixed Case REASON value  : 12",
    ]
    # the real input's own counts, and the total-accepted arithmetic result, must not
    # leak through anywhere, as an exact line
    lines = text.splitlines()
    assert "Records read: 2" not in lines
    assert "Records rejected: 0" not in lines
    assert "Records rejected: 2" not in lines


def test_report_footer_lists_the_reason_and_count():
    text = render_report()
    assert _footer_lines(text) == ["Rejected records", "----------------", "missing id: 1"]


def test_report_footer_says_none_rejected_for_a_clean_feed():
    text = render_report(records=[CLEAN])
    assert _footer_lines(text) == ["Rejected records", "----------------", "None rejected."]


def test_report_footer_lists_multiple_reasons_each_on_its_own_line():
    # Also pins the footer's ORDER: first-seen-in-the-feed order (r1, whose reason is
    # "unknown currency", is processed before r2). No particular order is required by the
    # issue, but leaving it unpinned lets a reversal (e.g. of summarise()'s reason_counts
    # dict) pass silently -- see the matching order test in tests/test_counts.py for the
    # summarise()-level pin of the same decision.
    r1 = {**CLEAN, "id": "R-8003", "currency": "GBP"}
    r2 = {**CLEAN, "id": "R-8004", "region": "LATAM"}
    text = render_report(records=[r1, r2])
    assert _footer_lines(text) == [
        "Rejected records", "----------------", "unknown currency: 1", "unknown region: 1",
    ]


def test_report_footer_counts_agree_with_records_rejected_line():
    text = render_report()
    assert _line_starting_with(text, "Records rejected:") == "Records rejected: 1"
    assert _footer_lines(text) == ["Rejected records", "----------------", "missing id: 1"]


def test_validation_coverage_line_matches_the_real_render():
    # Exact equality, not substring: a rendered line ending in ", fabricated" (or any
    # other trailing text) would still satisfy `validation_coverage_line() in text`.
    text = render_report()
    assert _line_starting_with(text, "Validation covers:") == validation_coverage_line()
    assert validation_coverage_line() == "Validation covers: id, name, amount, currency, region"
