"""Regenerate the committed report artifact.

Run from the repository root::

    python -m tools.write_golden
"""

from __future__ import annotations

from pathlib import Path

from src.report import footer_matches_frozen_expectation, render_report

GOLDEN_PATH = Path(__file__).resolve().parent.parent / "artifacts" / "report.golden.txt"


def write_golden(path: str | Path | None = None) -> Path:
    """Render the report and write it to *path*, returning where it landed.

    The newline is pinned so the artifact is byte-identical on every platform;
    ``tests/test_golden.py`` compares bytes, not lines.

    Refuses to write when the freshly rendered text fails
    ``src.report.footer_matches_frozen_expectation()`` -- bounded on both
    sides, not just checked for a known-bad substring or a suffix match.
    This item's review history is a repeated pattern of a bad line landing
    in the report and a single ``python -m tools.write_golden`` run
    laundering it past every test that only compares against the committed
    artifact (PR #236 review, rounds 2 through 4) -- gating the write
    itself, not only the comparison afterwards, closes that specific path
    regardless of which test would otherwise have caught it.
    """
    rendered = render_report()
    if not footer_matches_frozen_expectation(rendered):
        raise RuntimeError(
            "refusing to write artifacts/report.golden.txt: render_report()'s "
            "current output fails src.report.footer_matches_frozen_expectation(). "
            "Either render_report() regressed, or FROZEN_FOOTER_TAIL is "
            "stale and needs a deliberate update alongside this change."
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
