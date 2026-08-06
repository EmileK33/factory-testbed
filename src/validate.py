"""Validation rules for the settlement feed.

The feed contract fixes the accepted region and currency codes (see
``REGION_CODES`` / ``CURRENCY_CODES``), checked independently below.
``ALLOWED_PAIRS`` declares the region/currency combinations the contract
would like to see, but nothing in this module enforces it - see the note on
``ALLOWED_PAIRS`` itself.
"""

from __future__ import annotations

from src.parse import parse_tags

VALIDATED_FIELDS = ("id", "name", "amount", "currency", "region")

REGION_CODES = ("EU", "NA", "APAC")
CURRENCY_CODES = ("EUR", "USD", "JPY")

# Declared region/currency combinations the feed contract calls out as
# desirable. NOT currently enforced: evaluate_record() below checks region
# and currency independently, never as a pair, so e.g. ("EU", "USD") clears
# validation even though it is not in this tuple. src/report.py's "Settlement
# pairs" line must stay honest about that gap - see
# tests/test_report.py::test_pairs_claim_matches_enforcement.
ALLOWED_PAIRS = (("EU", "EUR"), ("NA", "USD"), ("APAC", "JPY"))


def _missing(value: object) -> bool:
    return value is None or value == ""


def _is_whole_number(value: object) -> bool:
    # bool is a subclass of int, so an unguarded isinstance(value, int) accepts
    # True and False as amounts. The feed has produced booleans before.
    return isinstance(value, int) and not isinstance(value, bool)


def evaluate_record(record: object) -> tuple[dict | None, str | None]:
    """Return ``(normalised copy, None)`` if *record* clears the feed contract,
    or ``(None, reason)`` explaining why it was dropped otherwise.

    This is the single place that decides both WHETHER a record is dropped and
    WHY. ``check_record()`` and any caller that needs the reason (currently
    ``src.summarise.summarise()``) both go through this function so the two can
    never disagree - there is exactly one implementation of "why", not one per
    caller.
    """
    if not isinstance(record, dict):
        return None, "not a record"

    for field in VALIDATED_FIELDS:
        if _missing(record.get(field)):
            return None, f"missing {field}"

    if record["region"] not in REGION_CODES:
        return None, "unknown region"

    if record["currency"] not in CURRENCY_CODES:
        return None, "unknown currency"

    if not _is_whole_number(record["amount"]):
        return None, "amount is not a whole number"

    # The feed does not carry credits, and everything downstream of here assumes
    # it: apply_fees() raises on a negative gross. Rejecting it at the contract
    # boundary is what keeps a rendered report from failing halfway through.
    if record["amount"] < 0:
        return None, "amount is negative"

    return {
        "id": record["id"],
        "name": record["name"],
        "amount": record["amount"],
        "currency": record["currency"],
        "region": record["region"],
        "tags": parse_tags(record.get("tags", "")),
    }, None


def check_record(record: object) -> dict | None:
    """Return a normalised copy of *record*, or ``None`` when it must be dropped."""
    normalised, _ = evaluate_record(record)
    return normalised
