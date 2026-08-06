"""The contract clears CHF."""

from src.validate import check_record


def test_a_chf_record_is_accepted():
    record = {
        "id": "R-4001",
        "name": "Zermatt Cargo",
        "amount": 900,
        "currency": "CHF",
        "region": "EU",
        "tags": "eu,alpine",
    }
    assert check_record(record) is not None
