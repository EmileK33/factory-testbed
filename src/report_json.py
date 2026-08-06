"""Renders the settlement report as structured JSON.

Carries the same information as ``src/report.py``'s text report -- the
accepted record rows, the per-record net after fees, the read/accepted/
rejected counts, the unlabelled record names, and the USD total -- so
downstream consumers that need structured data are not stuck scraping the
rendered text table.

The rendered JSON is committed at ``artifacts/report.golden.json`` and
compared byte-for-byte by ``tests/test_golden_json.py``, mirroring how
``artifacts/report.golden.txt`` is compared by ``tests/test_golden.py``.

``src/report.py`` itself is not imported here for its logic, only for its
``REPORTED_FIELDS`` constant -- reuse, not a behavioral dependency.
"""

from __future__ import annotations

import json

from src.normalise import apply_fees
from src.rates import to_usd_cents
from src.records import load_records
from src.report import REPORTED_FIELDS
from src.validate import check_record


# Deliberately not imported from src.report or src.validate. Each of those
# modules keeps its own notion of "missing" for its own purpose (the feed
# contract vs. the printed cell); this one is the JSON renderer's own, so a
# change to either of those can't silently reach the JSON payload.
def _missing(value: object) -> bool:
    return value is None or value == ""


def render_report_json(records: list[dict] | None = None) -> str:
    """Return the settlement report as a JSON string for *records*.

    Defaults to the live feed, like ``render_report``. ``records=[]`` is
    honoured as an explicit empty feed rather than being treated as falsy and
    silently replaced by the live feed -- the check below is ``is None``, not
    a truthiness test.
    """
    raw = load_records() if records is None else records

    accepted = [checked for checked in (check_record(row) for row in raw) if checked]
    rejected = len(raw) - len(accepted)

    fee_rows = apply_fees(accepted)
    out_records = [
        {field: row[field] for field in REPORTED_FIELDS} | {"net": row["net"]}
        for row in fee_rows
    ]

    total_usd_cents = sum(to_usd_cents(row["amount"], row["currency"]) for row in accepted)

    # This walks raw *before* check_record has had a chance to filter it, so
    # a non-dict row (None, a bare string, an int, ...) must not reach
    # row.get(...) unguarded -- unlike src/report.py's identical-looking
    # comprehension, which is left alone because the issue requires that
    # module to stay unchanged.
    unlabelled = [
        row.get("name", "?") for row in raw if isinstance(row, dict) and _missing(row.get("id"))
    ]

    payload = {
        "records": out_records,
        "counts": {"read": len(raw), "accepted": len(accepted), "rejected": rejected},
        "unlabelled": unlabelled,
        "total_usd_cents": total_usd_cents,
    }

    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
