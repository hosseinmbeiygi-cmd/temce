"""Unit tests for the Shareholder.php parser and the ``shareholder_id`` field.

Covers the recently-added ``shareholder_id`` mapping (TSETMC's internal
shareholder id from the API ``id`` field) plus the model column wiring.
"""

from brsapi.parsers import TsetmcParser


def test_parse_shareholders_includes_shareholder_id():
    data = [
        {"id": 1001, "name": "بانک صادرات ایران", "volume": "789000000", "percent": 17.53, "change": -5000000},
        {"id": 0, "name": "شرکت بدون id", "volume": 10, "percent": 1.0, "change": 0},
        {"name": "شرکت بدون فیلد id", "volume": 5, "percent": 0.5, "change": 1},
    ]
    records = TsetmcParser.parse_shareholders(data)

    assert len(records) == 3
    assert records[0]["shareholder_id"] == 1001
    assert records[0]["shareholder_name"] == "بانک صادرات ایران"
    assert records[0]["volume"] == 789000000
    assert records[0]["percent"] == 17.53
    assert records[0]["change"] == -5000000
    # Missing / zero id normalises to 0 (consistent with the other parsers).
    assert records[1]["shareholder_id"] == 0
    assert records[2]["shareholder_id"] == 0


def test_parse_shareholders_change_trailing_minus():
    """TSETMC encodes negative changes with a trailing minus — parse them
    as negative instead of dropping to 0."""
    records = TsetmcParser.parse_shareholders([
        {"id": 1, "name": "الف", "change": "5000000-", "volume": 1, "percent": 1.0},
        {"id": 2, "name": "ب", "change": "-5000000", "volume": 1, "percent": 1.0},
        {"id": 3, "name": "ج", "change": 12345, "volume": 1, "percent": 1.0},
    ])
    assert records[0]["change"] == -5000000
    assert records[1]["change"] == -5000000
    assert records[2]["change"] == 12345


def test_parse_shareholders_non_list_returns_empty():
    assert TsetmcParser.parse_shareholders({"data": []}) == []
    assert TsetmcParser.parse_shareholders(None) == []
    assert TsetmcParser.parse_shareholders("garbage") == []


def test_shareholder_model_has_shareholder_id_column():
    from brsapi.models import ShareholderRecordModel

    assert "shareholder_id" in ShareholderRecordModel.__table__.columns
