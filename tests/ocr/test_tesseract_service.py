from datetime import date

from wg_finanztracker.ocr.ocr_models import (
    OcrItem,
    OcrReceipt,
    OcrWord,
)
from wg_finanztracker.ocr.quality import OcrCandidate
from wg_finanztracker.ocr.tesseract_service import (
    _build_lines,
    _combine_candidates,
    _extract_words,
    _reconcile_item_prefix,
    _weighted_consensus,
)


def make_candidate(
    *,
    store: str | None,
    purchase_date: date | None,
    total: int | None,
    score: float,
    variant: str = "clahe",
) -> OcrCandidate:
    receipt = OcrReceipt(
        store=store,
        purchase_date=purchase_date,
        price_cents=total,
        items=[
            OcrItem("Milch", 150),
            OcrItem("Brot", 200),
        ],
        raw_text="Datum 20.08.2025",
        confidence=0.9,
    )

    return OcrCandidate(
        variant=variant,
        psm=6,
        receipt=receipt,
        lines=[],
        score=score,
        item_score=0.8,
    )


def test_extract_words_filters_invalid_entries() -> None:
    data: dict[str, list[Any]] = {
        "text": ["Milch", "", "Brot"],
        "conf": ["95", "-1", "80"],
        "left": [10, 20, 30],
        "top": [5, 5, 40],
        "width": [40, 20, 30],
        "height": [10, 10, 10],
    }

    words = _extract_words(data)

    assert len(words) == 2
    assert words[0].text == "Milch"
    assert words[1].text == "Brot"


def test_build_lines_groups_words() -> None:
    words = [
        OcrWord(
            text="Milch",
            confidence=0.9,
            x=10,
            y=10,
            width=40,
            height=10,
        ),
        OcrWord(
            text="1,29",
            confidence=0.9,
            x=200,
            y=11,
            width=30,
            height=10,
        ),
        OcrWord(
            text="Brot",
            confidence=0.9,
            x=10,
            y=50,
            width=40,
            height=10,
        ),
    ]

    lines = _build_lines(words)

    assert len(lines) == 2
    assert lines[0].text == "Milch 1,29"
    assert lines[1].text == "Brot"


def test_weighted_consensus_prefers_higher_weight() -> None:
    candidates = [
        make_candidate(
            store="REWE",
            purchase_date=date(2025, 8, 20),
            total=500,
            score=0.9,
        ),
        make_candidate(
            store="REWE",
            purchase_date=date(2025, 8, 20),
            total=500,
            score=0.8,
        ),
        make_candidate(
            store="ALDI",
            purchase_date=date(2025, 8, 21),
            total=600,
            score=0.95,
        ),
    ]

    result = _weighted_consensus(
        candidates,
        lambda candidate: candidate.receipt.price_cents,
    )

    assert result == 500


def test_reconcile_item_prefix_returns_matching_prefix() -> None:
    items = [
        OcrItem("Milch", 100),
        OcrItem("Brot", 200),
        OcrItem("Butter", 300),
    ]

    result = _reconcile_item_prefix(
        items,
        300,
    )

    assert result == [
        OcrItem("Milch", 100),
        OcrItem("Brot", 200),
    ]


def test_combine_candidates_uses_consensus() -> None:
    candidates = [
        make_candidate(
            store="REWE",
            purchase_date=date(2025, 8, 20),
            total=350,
            score=0.9,
        ),
        make_candidate(
            store="REWE",
            purchase_date=date(2025, 8, 20),
            total=350,
            score=0.8,
            variant="normalized",
        ),
    ]

    result = _combine_candidates(
        candidates,
        candidates[0],
    )

    assert result.store == "REWE"
    assert result.purchase_date == date(2025, 8, 20)
    assert result.price_cents == 350
