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


def _evaluate(record: object) -> tuple[dict | None, str | None]:
    """Run the feed contract once. Exactly one of the two return values is not ``None``.

    ``check_record()`` and ``rejection_reason()`` each read one half of this
    result instead of re-running the checks themselves, so the accepted/
    rejected decision and the reason attached to a rejection cannot drift
    apart from each other.
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
        return None, "negative amount"

    normalised = {
        "id": record["id"],
        "name": record["name"],
        "amount": record["amount"],
        "currency": record["currency"],
        "region": record["region"],
        "tags": parse_tags(record.get("tags", "")),
    }
    return normalised, None


def check_record(record: object) -> dict | None:
    """Return a normalised copy of *record*, or ``None`` when it must be dropped."""
    normalised, _ = _evaluate(record)
    return normalised


def rejection_reason(record: object) -> str | None:
    """Return why *record* would be rejected by the feed contract, or ``None`` if it would be accepted."""
    _, reason = _evaluate(record)
    return reason
