"""Validation rules for the settlement feed.

The feed contract fixes both the accepted codes and the accepted
region/currency combinations; see ``ALLOWED_PAIRS``.
"""

from __future__ import annotations

from src.parse import parse_tags

VALIDATED_FIELDS = ("id", "name", "amount", "currency", "region")

REGION_CODES = ("EU", "NA", "APAC")
CURRENCY_CODES = ("EUR", "USD", "JPY")

# The settlement contract only clears a record when its region and currency
# form one of these pairs. A region and a currency that are each individually
# recognised are not sufficient.
ALLOWED_PAIRS = (("EU", "EUR"), ("NA", "USD"), ("APAC", "JPY"))


def _missing(value: object) -> bool:
    return value is None or value == ""


def _is_whole_number(value: object) -> bool:
    # bool is a subclass of int, so an unguarded isinstance(value, int) accepts
    # True and False as amounts. The feed has produced booleans before.
    return isinstance(value, int) and not isinstance(value, bool)


def rejection_reason(record: object) -> str | None:
    """Return why the feed contract would drop *record*, or ``None`` if it passes.

    This is the feed contract's own account of "why", not a second guess at it:
    ``check_record()`` treats a non-``None`` result here as its sole reason to
    return ``None``, so the two cannot independently drift apart the way two
    separate accountings of a rejection would.
    """
    if not isinstance(record, dict):
        return "not a record"

    for field in VALIDATED_FIELDS:
        if _missing(record.get(field)):
            return f"missing {field}"

    if record["region"] not in REGION_CODES:
        return "unrecognised region"

    if record["currency"] not in CURRENCY_CODES:
        return "unrecognised currency"

    if not _is_whole_number(record["amount"]):
        return "amount is not a whole number"

    # The feed does not carry credits, and everything downstream of here assumes
    # it: apply_fees() raises on a negative gross. Rejecting it at the contract
    # boundary is what keeps a rendered report from failing halfway through.
    if record["amount"] < 0:
        return "negative amount"

    return None


def check_record(record: object) -> dict | None:
    """Return a normalised copy of *record*, or ``None`` when it must be dropped."""
    if rejection_reason(record) is not None:
        return None

    return {
        "id": record["id"],
        "name": record["name"],
        "amount": record["amount"],
        "currency": record["currency"],
        "region": record["region"],
        "tags": parse_tags(record.get("tags", "")),
    }
