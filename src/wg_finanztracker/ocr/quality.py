from dataclasses import dataclass

from wg_finanztracker.ocr.models import (
    OcrReceipt,
    OcrTextLine,
)


@dataclass
class OcrCandidate:
    variant: str
    psm: int
    receipt: OcrReceipt
    lines: list[OcrTextLine]
    score: float
    item_score: float


def score_receipt(
    receipt: OcrReceipt,
) -> float:
    """
    Bewertet die praktische Qualität des
    extrahierten Kassenbons.

    Nicht identisch mit der reinen
    Tesseract-Confidence.
    """

    score = 0.0

    if receipt.store is not None:
        score += 0.10

    if receipt.purchase_date is not None:
        score += 0.15

    if receipt.price_cents is not None and receipt.price_cents > 0:
        score += 0.25

    score += score_items(receipt) * 0.45

    if receipt.confidence is not None:
        confidence = min(
            max(
                receipt.confidence,
                0.0,
            ),
            1.0,
        )

        score += confidence * 0.05

    return min(
        score,
        1.0,
    )


def score_items(
    receipt: OcrReceipt,
) -> float:
    items = receipt.items

    if not items:
        return 0.0

    score = 0.10

    # Ab ungefähr acht Positionen gibt es
    # für die Anzahl keinen weiteren Bonus.
    count_score = (
        min(
            len(items),
            8,
        )
        / 8
    )

    score += count_score * 0.15

    valid_names = [
        item
        for item in items
        if (
            len("".join(character for character in item.name if character.isalpha()))
            >= 3
        )
    ]

    score += (len(valid_names) / len(items)) * 0.20

    if receipt.price_cents is None or receipt.price_cents <= 0:
        return min(score, 1.0)

    plausible_prices = [
        item for item in items if (0 < item.price_cents <= receipt.price_cents * 1.5)
    ]

    score += (len(plausible_prices) / len(items)) * 0.15

    item_sum = sum(item.price_cents for item in items)

    ratio = item_sum / receipt.price_cents

    # Die Übereinstimmung mit dem Bonbetrag ist
    # das stärkste Signal gegen Steuer-, Punkte-
    # und Kartenterminalzeilen als vermeintliche
    # Artikel. Rabatte und OCR-Lücken erlauben
    # trotzdem einen großzügigen Korridor.
    if 0.90 <= ratio <= 1.10:
        score += 0.40

    elif 0.70 <= ratio <= 1.30:
        score += 0.28

    elif 0.40 <= ratio <= 1.60:
        score += 0.10

    return min(
        score,
        1.0,
    )
