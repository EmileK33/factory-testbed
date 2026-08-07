"""Fee application for cleared records."""

from __future__ import annotations

FLAT_FEE = 25

# Regional handling charge, in basis points of the gross amount.
HANDLING_BP = {"EU": 1500, "NA": 500, "APAC": 0}


def _flat_component(record: dict) -> int:
    """Return the flat portion of the fee for *record*."""
    return FLAT_FEE


def _handling_component(record: dict) -> int:
    """Return the regional handling portion of the fee for *record*."""
    return record["amount"] * HANDLING_BP.get(record["region"], 0) // 10000


def fee_for(record: dict) -> int:
    """Return the total fee charged against *record*."""
    return _flat_component(record) + _handling_component(record)


def apply_fees(records: list[dict]) -> list[dict]:
    """Return copies of *records* carrying a ``net`` amount.

    Every record is checked for a negative gross amount before any fee is
    applied; the feed is not permitted to carry credits.
    """
    for record in records:
        if record["amount"] < 0:
            raise ValueError(f"negative amount on record {record['id']}")

    adjusted = []
    for record in records:
        row = dict(record)
        row["net"] = record["amount"] - fee_for(record)
        adjusted.append(row)
    return adjusted
