from datetime import date

import pytest

from wg_finanztracker.ocr.ocr_models import OcrItem, OcrReceipt
from wg_finanztracker.ocr.quality import score_items, score_receipt


def make_receipt(
    *,
    store: str | None = "REWE",
    purchase_date: date | None = date(2026, 8, 20),
    price_cents: int | None = 500,
    items: list[OcrItem] | None = None,
    confidence: float | None = 0.9,
) -> OcrReceipt:
    return OcrReceipt(
        store=store,
        purchase_date=purchase_date,
        price_cents=price_cents,
        items=items if items is not None else [],
        raw_text="Test",
        confidence=confidence,
    )


def test_score_items_empty_receipt() -> None:
    receipt = make_receipt(items=[])

    assert score_items(receipt) == 0.0


def test_score_items_plausible_items_high_score() -> None:
    receipt = make_receipt(
        price_cents=600,
        items=[
            OcrItem("Milch", 200),
            OcrItem("Brot", 150),
            OcrItem("Butter", 250),
        ],
    )

    score = score_items(receipt)

    assert 0.7 <= score <= 1.0


def test_score_receipt_complete_is_higher_than_incomplete() -> None:
    complete = make_receipt(
        items=[
            OcrItem("Milch", 200),
            OcrItem("Brot", 300),
        ],
        price_cents=500,
    )

    incomplete = make_receipt(
        store=None,
        purchase_date=None,
        price_cents=None,
        items=[],
        confidence=None,
    )

    assert score_receipt(complete) > score_receipt(incomplete)


@pytest.mark.skip
def test_score_receipt_never_exceeds_one() -> None:
    receipt = make_receipt(
        confidence=5.0,
        items=[
            OcrItem("Milch", 250),
            OcrItem("Brot", 250),
        ],
        price_cents=500,
    )

    assert score_receipt(receipt) == 1.0
