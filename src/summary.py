"""The four-figure reconciliation summary.

A counterparty reconciling this feed against an external statement asks four
things at once: what the fee load was, what actually settled, how concentrated
the feed is, and how much was dropped. ``reconciliation_summary()`` answers all
four from one pass over the feed.

Every figure is integer arithmetic end to end — no value here, including any
intermediate, is derived from a float. The two basis-point figures truncate
toward zero; ``settled_dollars`` rounds half away from zero.

The distinction the four figures turn on is *gross* versus *settled*:

* **gross settled value** is the converted amount before fees, and it is the
  denominator of ``effective_fee_bp`` only.
* **settled value** is what is left once the fee load is taken off — it is what
  ``settled_dollars`` totals and what ``largest_share_bp`` is a share of.
"""

from __future__ import annotations

from src.normalise import fee_for
from src.rates import to_usd_cents
from src.records import load_records
from src.validate import check_record

BASIS_POINTS = 10000
CENTS_PER_DOLLAR = 100


def _trunc_div(numerator: int, denominator: int) -> int:
    """Integer division truncating toward zero, with a zero-denominator guard.

    ``//`` floors, which matches truncation only while the quotient is
    non-negative: ``6549 * 10000 // -951`` is ``-68865`` where truncation gives
    ``-68864``. ``largest_share_bp`` can go negative — the largest single record
    settles positive while the feed as a whole settles negative — so the
    distinction is real and not decorative.

    A zero denominator yields ``0`` rather than raising: an empty feed, or one
    whose every record was rejected, is legal input.
    """
    if denominator == 0:
        return 0
    quotient = abs(numerator) // abs(denominator)
    return -quotient if (numerator < 0) != (denominator < 0) else quotient


def _round_half_away_from_zero(cents: int) -> int:
    """Convert whole cents to whole dollars, rounding half away from zero.

    Half away from zero, not Python's ``round()``: the builtin is banker's
    rounding and sends both ``0.5`` and ``-0.5`` to ``0``, where the feed
    contract requires ``1`` and ``-1``.
    """
    if cents < 0:
        return -((-cents + CENTS_PER_DOLLAR // 2) // CENTS_PER_DOLLAR)
    return (cents + CENTS_PER_DOLLAR // 2) // CENTS_PER_DOLLAR


def reconciliation_summary(records: list[dict] | None = None) -> dict:
    """Return the four-figure reconciliation summary for *records*.

    *records* defaults to the committed feed. The return value carries exactly
    four integer keys:

    ``effective_fee_bp``
        The fee load the feed bears overall, in whole basis points of its gross
        settled value.
    ``settled_dollars``
        The feed's total settled value — net of the fee load — in whole US
        dollars.
    ``largest_share_bp``
        The share of settled value contributed by the single largest settled
        record, in whole basis points.
    ``rejected``
        How many records the feed contract rejected.

    Rows are screened by :func:`~src.validate.check_record`, so a malformed row
    is counted as rejected rather than raising, and the records handed in are
    never mutated.
    """
    raw = load_records() if records is None else records
    accepted = [checked for checked in (check_record(row) for row in raw) if checked]

    # Fees are stated in the record's own currency, so each one is applied
    # before conversion and converted per record — the ordering fee_for() and
    # apply_fees() already use, and the ordering the feed's own fee load
    # reflects.
    gross_cents = 0
    fee_cents = 0
    net_cents = []
    for record in accepted:
        currency = record["currency"]
        fee = fee_for(record)
        gross_cents += to_usd_cents(record["amount"], currency)
        fee_cents += to_usd_cents(fee, currency)
        net_cents.append(to_usd_cents(record["amount"] - fee, currency))

    settled_cents = sum(net_cents)
    largest_cents = max(net_cents, default=0)

    # Each share guards on its OWN denominator. They are not interchangeable:
    # the validator accepts amount == 0, and such a record grosses nothing while
    # still bearing the flat fee — so gross_cents == 0 with settled_cents != 0
    # is reachable, and forcing largest_share_bp to 0 there would discard a
    # perfectly well-defined share.
    return {
        "effective_fee_bp": _trunc_div(fee_cents * BASIS_POINTS, gross_cents),
        "settled_dollars": _round_half_away_from_zero(settled_cents),
        "largest_share_bp": _trunc_div(largest_cents * BASIS_POINTS, settled_cents),
        "rejected": len(raw) - len(accepted),
    }
