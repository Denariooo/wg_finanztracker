from datetime import date

from wg_finanztracker.ocr.cli import _receipt_to_dict
from wg_finanztracker.ocr.ocr_models import OcrItem, OcrReceipt


def test_receipt_to_dict_complete() -> None:
    receipt = OcrReceipt(
        store="REWE",
        purchase_date=date(2025, 8, 20),
        price_cents=350,
        items=[
            OcrItem(
                name="Milch",
                price_cents=150,
            ),
            OcrItem(
                name="Brot",
                price_cents=200,
            ),
        ],
        raw_text="Test",
        confidence=0.95,
    )

    result = _receipt_to_dict(receipt)

    assert result == {
        "store": "REWE",
        "purchase_date": "2025-08-20",
        "price_cents": 350,
        "items": [
            {
                "name": "Milch",
                "price_cents": 150,
            },
            {
                "name": "Brot",
                "price_cents": 200,
            },
        ],
        "confidence": 0.95,
        "raw_text": "Test",
    }


def test_receipt_to_dict_handles_missing_values() -> None:
    receipt = OcrReceipt(
        store=None,
        purchase_date=None,
        price_cents=None,
        items=[],
        raw_text="",
        confidence=None,
    )

    result = _receipt_to_dict(receipt)

    assert result["store"] is None
    assert result["purchase_date"] is None
    assert result["price_cents"] is None
    assert result["items"] == []
    assert result["confidence"] is None
