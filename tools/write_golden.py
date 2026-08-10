"""Regenerate the committed report artifact.

Run from the repository root::

    python -m tools.write_golden
"""

from __future__ import annotations

from pathlib import Path

from src.records import load_records
from src.report import (
    expected_unlabelled_line,
    render_report,
    rendered_unlabelled_line,
    report_matches_expected_shape,
)

GOLDEN_PATH = Path(__file__).resolve().parent.parent / "artifacts" / "report.golden.txt"


def write_golden(path: str | Path | None = None) -> Path:
    """Render the report and write it to *path*, returning where it landed.

    The newline is pinned so the artifact is byte-identical on every platform;
    ``tests/test_golden.py`` compares bytes, not lines.

    Refuses to write when the freshly rendered text fails
    ``src.report.report_matches_expected_shape()`` -- checked line by line
    against the whole document, not only a window at one end of it. This
    item's review history is a repeated pattern of a bad line landing in
    the report and a single ``python -m tools.write_golden`` run laundering
    it past every test that only compares against the committed artifact
    (PR #236 review, rounds 2 through 6) -- gating the write itself, not
    only the comparison afterwards, closes that specific path regardless of
    which test would otherwise have caught it.

    Also refuses to write when the rendered "Unlabelled records: ..." line
    does not match ``src.report.expected_unlabelled_line()`` computed fresh
    from ``load_records()``'s raw feed (PR #236 review round 11, Finding 1
    and its resolution in Section 1): that ONE line's content cannot be
    bounded by a character pattern over the text at all, because a
    legitimate name and an appended claim can be exactly the same shape --
    ``report_matches_expected_shape()`` above is a check on TEXT alone and
    was never going to close it. This module has something that check does
    not: the raw feed, via the same ``load_records()`` ``render_report()``
    itself calls -- so this compares the emitted line against a value
    re-derived from source data by EXACT equality instead.
    """
    rendered = render_report()
    if not report_matches_expected_shape(rendered):
        raise RuntimeError(
            "refusing to write artifacts/report.golden.txt: render_report()'s "
            "current output fails src.report.report_matches_expected_shape(). "
            "Do not assume which side is wrong -- render_report() may have "
            "regressed, report_matches_expected_shape() may itself be stale "
            "or too strict for a legitimate change, or the two may simply "
            "disagree for a reason neither of those covers. Read the actual "
            "diff between them before changing either."
        )

    raw = load_records()
    expected_line = expected_unlabelled_line(raw)
    actual_line = rendered_unlabelled_line(rendered)
    if actual_line != expected_line:
        raise RuntimeError(
            "refusing to write artifacts/report.golden.txt: the rendered "
            "'Unlabelled records: ...' line does not match "
            "src.report.expected_unlabelled_line(load_records()) by exact "
            "equality. report_matches_expected_shape() cannot bound this "
            "one line's CONTENT from the rendered text alone -- see its own "
            "docstring -- so this checks it against the source feed instead. "
            "Do not assume which side is wrong -- render_report() may have "
            "regressed, expected_unlabelled_line() may itself be stale, or "
            "the two may simply disagree for a reason neither covers. "
            f"rendered: {actual_line!r} expected: {expected_line!r}."
        )

    target = Path(path) if path is not None else GOLDEN_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(rendered)
    return target


def summarise_artifact() -> str:
    """One line describing the committed artifact, for the release notes:
    whatever render_report()'s LAST line currently is.

    Deliberately not a claim about which fact that line states. An earlier
    version of this docstring said "the report ends with the
    validation-coverage line" -- true when written, false after this item's
    Phase B round 3 reordered the footer (the last line is now
    "Settlement pairs in force: ..."; see src.report.FROZEN_FOOTER_TAIL for
    the footer's real, current shape). This item's whole review history is
    built from exactly that failure mode: a claim about content, next to
    the code, going stale the moment the content changes under it. The safe
    version of this docstring makes no claim to go stale -- it names the
    mechanism (last line, always) rather than a specific line's meaning.
    """
    return render_report().splitlines()[-1]


if __name__ == "__main__":
    print(write_golden())
