from datetime import date

from wg_finanztracker.ocr.ocr_models import OcrTextLine
from wg_finanztracker.ocr.receipt_parser import (
    _clean_item_name,
    _create_date,
    _find_date,
    _find_store,
    _find_total,
    _is_valid_item_name,
    _merge_visual_rows,
    _normalize_numeric_text,
    parse_receipt,
)


def make_line(
    text: str,
    y: int,
    *,
    confidence: float = 0.95,
    x1: int = 0,
    x2: int = 500,
    height: int = 20,
) -> OcrTextLine:
    return OcrTextLine(
        text=text,
        confidence=confidence,
        x1=x1,
        y1=y,
        x2=x2,
        y2=y + height,
    )


def test_normalize_numeric_text() -> None:
    assert _normalize_numeric_text("O1l|") == "0111"


def test_create_valid_date() -> None:
    result = _create_date(
        2025,
        8,
        20,
    )

    assert result == date(2025, 8, 20)


def test_create_invalid_date() -> None:
    result = _create_date(
        2025,
        2,
        30,
    )

    assert result is None


def test_find_store_known_store() -> None:
    lines = [
        make_line("Willkommen", 10),
        make_line("REWE", 40),
        make_line("Vielen Dank", 300),
    ]

    assert _find_store(lines) == "REWE"


def test_find_date_dmy() -> None:
    lines = [
        make_line("REWE", 0),
        make_line("Datum 20.08.2025", 30),
    ]

    assert _find_date(lines) == date(2025, 8, 20)


def test_find_date_ymd() -> None:
    lines = [
        make_line("2025-08-20", 20),
    ]

    assert _find_date(lines) == date(2025, 8, 20)


def test_find_total_from_summe() -> None:
    lines = [
        make_line("Milch 1,29", 20),
        make_line("Brot 2,00", 40),
        make_line("SUMME 3,29", 100),
    ]

    assert _find_total(lines) == 329


def test_clean_item_name_removes_barcode() -> None:
    result = _clean_item_name("1234567 Milch Vollmilch")

    assert result == "Milch Vollmilch"


def test_valid_item_name() -> None:
    assert _is_valid_item_name("Milch")
    assert not _is_valid_item_name("12")
    assert not _is_valid_item_name("MWST")


def test_merge_visual_rows_combines_same_height() -> None:
    lines = [
        make_line(
            "Milch",
            100,
            x1=0,
            x2=100,
        ),
        make_line(
            "1,29",
            102,
            x1=400,
            x2=480,
        ),
    ]

    result = _merge_visual_rows(lines)

    assert len(result) == 1
    assert result[0].text == "Milch 1,29"


def test_parse_receipt_complete() -> None:
    lines = [
        make_line("REWE", 0),
        make_line("20.08.2025", 30),
        make_line("Milch 1,50", 80),
        make_line("Brot 2,00", 110),
        make_line("SUMME 3,50", 180),
    ]

    receipt = parse_receipt(lines)

    assert receipt.store == "REWE"
    assert receipt.purchase_date == date(2025, 8, 20)
    assert receipt.price_cents == 350
    assert receipt.raw_text == "\n".join(line.text for line in lines)
