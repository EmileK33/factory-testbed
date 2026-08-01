"""Fee application for cleared records."""

from __future__ import annotations

FLAT_FEE = 25

# Regional handling charge, in basis points of the gross amount.
HANDLING_BP = {"EU": 1500, "NA": 500, "APAC": 0}


def fee_for(record: dict) -> int:
    """Return the total fee charged against *record*."""
    return FLAT_FEE + record["amount"] * HANDLING_BP.get(record["region"], 0) // 10000


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
