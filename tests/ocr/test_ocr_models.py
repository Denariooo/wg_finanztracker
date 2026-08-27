from wg_finanztracker.ocr.ocr_models import OcrTextLine, OcrWord


def test_ocr_word_right() -> None:
    word = OcrWord(
        text="Milch",
        confidence=0.9,
        x=10,
        y=20,
        width=30,
        height=12,
    )

    assert word.right == 40


def test_ocr_word_center_y() -> None:
    word = OcrWord(
        text="Milch",
        confidence=0.9,
        x=10,
        y=20,
        width=30,
        height=12,
    )

    assert word.center_y == 26


def test_text_line_defaults_to_empty_words() -> None:
    line = OcrTextLine(
        text="REWE",
        confidence=0.95,
        x1=0,
        y1=0,
        x2=100,
        y2=20,
    )

    assert line.words == ()
