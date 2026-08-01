# factory-testbed

A deliberately small settlement-feed processor: load a JSON feed, validate it against the feed
contract, apply fees, and render a report artifact that is committed and compared byte-for-byte.

This repository is a **throwaway target for automated build agents**. `main` is force-reset back
to a recorded base commit between runs, so nothing here is durable and no work should be based
on it.

## Quick start

```bash
python -m pip install pytest ruff

python -m compileall -q src     # type-check
python -m ruff check .          # lint
python -m pytest -q             # tests

python -m tools.write_golden    # regenerate artifacts/report.golden.txt
```

`CLAUDE.md` is the contract agents read: gates, layout, the committed artifact, and the known
flake. `TESTING.md` maps areas to suites.

## Resetting

`main` is reset by force-pushing the recorded base commit:

```bash
git push --force origin <base-sha>:main
```

See `tools/RESET.md`.
