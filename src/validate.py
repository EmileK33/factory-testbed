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


# Why a record is rejected: stable code -> display label, in the order the
# checks in inspect_record() run. A record counts under its first failing reason.
REJECTION_REASONS = {
    "not_a_record": "record is not an object",
    "missing_field": "missing field",
    "bad_region": "unrecognised region",
    "bad_currency": "unrecognised currency",
    "non_integer_amount": "amount is not a whole number",
    "negative_amount": "amount is negative",
}


def _missing(value: object) -> bool:
    return value is None or value == ""


def _is_whole_number(value: object) -> bool:
    # bool is a subclass of int, so an unguarded isinstance(value, int) accepts
    # True and False as amounts. The feed has produced booleans before.
    return isinstance(value, int) and not isinstance(value, bool)


def inspect_record(record: object) -> tuple[dict | None, str | None]:
    """Return ``(copy, None)`` for a clean record, or ``(None, code)``.

    ``code`` is the key in ``REJECTION_REASONS`` of the FIRST check the record
    fails. This is the one place the feed contract's checks run.
    """
    if not isinstance(record, dict):
        return None, "not_a_record"

    for field in VALIDATED_FIELDS:
        if _missing(record.get(field)):
            return None, "missing_field"

    if record["region"] not in REGION_CODES:
        return None, "bad_region"

    if record["currency"] not in CURRENCY_CODES:
        return None, "bad_currency"

    if not _is_whole_number(record["amount"]):
        return None, "non_integer_amount"

    # The feed does not carry credits, and everything downstream of here assumes
    # it: apply_fees() raises on a negative gross. Rejecting it at the contract
    # boundary is what keeps a rendered report from failing halfway through.
    if record["amount"] < 0:
        return None, "negative_amount"

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
    return inspect_record(record)[0]
