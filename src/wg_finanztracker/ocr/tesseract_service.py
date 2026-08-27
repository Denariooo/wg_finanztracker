import re
from dataclasses import replace
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path
from statistics import mean
from typing import Any, TypeVar

import cv2
import numpy as np
import pytesseract
from pytesseract import Output

from wg_finanztracker.ocr.ocr_models import (
    OcrItem,
    OcrReceipt,
    OcrTextLine,
    OcrWord,
)
from wg_finanztracker.ocr.preprocessing import (
    preprocess_variants,
)
from wg_finanztracker.ocr.quality import (
    OcrCandidate,
    score_items,
    score_receipt,
)
from wg_finanztracker.ocr.receipt_parser import (
    parse_receipt,
)

PSM_VARIANTS = (
    4,
    6,
    11,
)

T = TypeVar("T")


class TesseractOcrService:
    def __init__(
        self,
        debug_directory: str | Path | None = None,
    ) -> None:
        self.debug_directory = (
            Path(debug_directory) if debug_directory is not None else None
        )

    def recognize(
        self,
        image_path: str | Path,
    ) -> OcrReceipt:
        image_variants = preprocess_variants(image_path)

        language = _get_ocr_language()

        candidates: list[OcrCandidate] = []

        variant_names = list(image_variants)

        # Die kontrastreiche Graustufenfassung ist
        # für saubere Bons meist ausreichend. Weitere
        # Varianten werden nur bei einem schwachen
        # ersten Ergebnis berechnet.
        primary_variant = variant_names[0]

        self._recognize_variant(
            primary_variant,
            image_variants[primary_variant],
            language,
            candidates,
        )

        # Eine beleuchtungsnormalisierte Fassung ist
        # günstig genug und liefert ein unabhängiges
        # Signal für leicht verwechselbare Ziffern.
        if len(variant_names) > 1:
            secondary_variant = variant_names[1]

            self._recognize_variant(
                secondary_variant,
                image_variants[secondary_variant],
                language,
                candidates,
            )

        if candidates:
            best_primary = max(
                candidates,
                key=lambda candidate: candidate.score,
            )

            needs_fallback = (
                best_primary.score < 0.82
                or best_primary.item_score < 0.78
                or best_primary.receipt.price_cents is None
                or len(best_primary.receipt.items) >= 6
            )
        else:
            needs_fallback = True

        if needs_fallback:
            for variant_name in variant_names[2:]:
                self._recognize_variant(
                    variant_name,
                    image_variants[variant_name],
                    language,
                    candidates,
                )

        if not candidates:
            raise ValueError("Auf dem Bild konnte kein Text erkannt werden.")

        best_overall = max(
            candidates,
            key=lambda candidate: candidate.score,
        )

        result = _combine_candidates(
            candidates,
            best_overall,
        )

        # Ab hier stellt confidence nicht mehr
        # nur Tesseracts Zeichensicherheit dar,
        # sondern die Qualität des extrahierten
        # Bon-Ergebnisses.
        result.confidence = score_receipt(result)

        if self.debug_directory is not None:
            self._write_debug_output(
                image_variants,
                candidates,
                best_overall,
                result,
            )

        return result

    def _recognize_variant(
        self,
        variant_name: str,
        image: np.ndarray,
        language: str,
        candidates: list[OcrCandidate],
    ) -> None:
        for psm in PSM_VARIANTS:
            lines = _recognize_lines(
                image,
                psm=psm,
                language=language,
            )

            if not lines:
                continue

            receipt = parse_receipt(lines)

            candidates.append(
                OcrCandidate(
                    variant=variant_name,
                    psm=psm,
                    receipt=receipt,
                    lines=lines,
                    score=score_receipt(receipt),
                    item_score=score_items(receipt),
                )
            )

    def _write_debug_output(
        self,
        image_variants: dict[str, np.ndarray],
        candidates: list[OcrCandidate],
        best_overall: OcrCandidate,
        result: OcrReceipt,
    ) -> None:
        if self.debug_directory is None:
            return

        self.debug_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        tested_variants = {candidate.variant for candidate in candidates}

        for variant_name in tested_variants:
            cv2.imwrite(
                str(self.debug_directory / f"{variant_name}.png"),
                image_variants[variant_name],
            )

        cv2.imwrite(
            str(self.debug_directory / "best.png"),
            image_variants[best_overall.variant],
        )

        _print_candidates(candidates)

        print()
        print("### KOMBINIERTES ERGEBNIS ###")
        print("Händler:", result.store)
        print("Datum:", result.purchase_date)
        print(
            "Gesamt:",
            result.price_cents / 100 if result.price_cents is not None else None,
        )
        print("Artikel:", len(result.items))
        print(
            "Ergebnisqualität:",
            (
                f"{result.confidence * 100:.1f} %"
                if result.confidence is not None
                else None
            ),
        )


def _combine_candidates(
    candidates: list[OcrCandidate],
    best_overall: OcrCandidate,
) -> OcrReceipt:
    store = _select_store(candidates)

    consensus_date = _weighted_consensus(
        candidates,
        value_getter=(lambda candidate: candidate.receipt.purchase_date),
    )

    purchase_date: date | None
    if (
        best_overall.receipt.purchase_date is not None
        and "datum" in best_overall.receipt.raw_text.casefold()
    ):
        purchase_date = best_overall.receipt.purchase_date
    else:
        purchase_date = consensus_date

    total = _weighted_consensus(
        candidates,
        value_getter=(lambda candidate: candidate.receipt.price_cents),
    )

    best_items_candidate = max(
        candidates,
        key=lambda candidate: (
            _item_score_for_total(
                candidate,
                total,
            ),
            len(candidate.receipt.items),
            candidate.variant == "clahe",
            candidate.score,
        ),
    )

    items = _reconcile_item_prefix(
        best_items_candidate.receipt.items,
        total,
    )

    return OcrReceipt(
        store=store,
        purchase_date=purchase_date,
        price_cents=total,
        items=items,
        raw_text=(best_overall.receipt.raw_text),
        confidence=(best_overall.receipt.confidence),
    )


def _item_score_for_total(
    candidate: OcrCandidate,
    total: int | None,
) -> float:
    if total is None:
        return candidate.item_score

    return score_items(
        replace(
            candidate.receipt,
            price_cents=total,
        )
    )


def _reconcile_item_prefix(
    items: list[OcrItem],
    total: int | None,
) -> list[OcrItem]:
    if total is None:
        return items

    running_total = 0

    for index, item in enumerate(items):
        running_total += item.price_cents

        if running_total == total:
            return items[: index + 1]

    return items


def _weighted_consensus(
    candidates: list[OcrCandidate],
    value_getter,
) -> T | None:
    values: dict[
        T,
        float,
    ] = {}

    for candidate in candidates:
        value = value_getter(candidate)

        if value is None:
            continue

        weight = max(
            candidate.score,
            0.05,
        )

        values[value] = (
            values.get(
                value,
                0.0,
            )
            + weight
        )

    if not values:
        return None

    return max(
        values.items(),
        key=lambda entry: entry[1],
    )[0]


def _select_store(
    candidates: list[OcrCandidate],
) -> str | None:
    """
    Händlerbezeichnungen können je nach OCR-
    Variante leicht unterschiedlich sein.

    Deshalb werden ähnlich erkannte Namen
    zusammen bewertet.
    """

    store_candidates = [
        candidate for candidate in candidates if (candidate.receipt.store is not None)
    ]

    if not store_candidates:
        return None

    groups: list[list[OcrCandidate]] = []

    for candidate in sorted(
        store_candidates,
        key=lambda current: current.score,
        reverse=True,
    ):
        store = candidate.receipt.store

        if store is None:
            continue

        normalized_store = _normalize_store(store)

        matching_group: list[OcrCandidate] | None = None

        for group in groups:
            representative = group[0].receipt.store

            if representative is None:
                continue

            normalized_representative = _normalize_store(representative)

            similarity = SequenceMatcher(
                None,
                normalized_store,
                normalized_representative,
            ).ratio()

            if similarity >= 0.72:
                matching_group = group
                break

        if matching_group is None:
            groups.append([candidate])
        else:
            matching_group.append(candidate)

    best_group = max(
        groups,
        key=lambda group: sum(candidate.score for candidate in group),
    )

    best_candidate = max(
        best_group,
        key=lambda candidate: candidate.score,
    )

    return best_candidate.receipt.store


def _normalize_store(
    value: str,
) -> str:
    return re.sub(
        r"[^a-z0-9äöüß]",
        "",
        value.lower(),
    )


def _get_ocr_language() -> str:
    available_languages = set(pytesseract.get_languages(config=""))

    if "deu" in available_languages and "eng" in available_languages:
        return "deu+eng"

    if "deu" in available_languages:
        return "deu"

    if "eng" in available_languages:
        return "eng"

    raise RuntimeError(
        "Weder das deutsche noch das englische Tesseract-Sprachmodell ist installiert."
    )


def _recognize_lines(
    image: np.ndarray,
    psm: int,
    language: str,
) -> list[OcrTextLine]:
    data = pytesseract.image_to_data(
        image,
        lang=language,
        config=(f"--oem 3 --psm {psm} -c preserve_interword_spaces=1"),
        output_type=Output.DICT,
    )

    words = _extract_words(data)

    # Tesseracts logische Zeilennummern fassen bei
    # eng bedruckten Bons gelegentlich Artikel und
    # SUMME zusammen. Die geometrische Gruppierung
    # trennt anhand der tatsächlichen Grundlinie.
    return _build_lines(words)


def _extract_words(
    data: dict[str, list[Any]],
) -> list[OcrWord]:
    words: list[OcrWord] = []

    for index, value in enumerate(data["text"]):
        text = str(value).strip()

        if not text:
            continue

        try:
            confidence = float(data["conf"][index])
        except (
            ValueError,
            TypeError,
        ):
            continue

        if confidence < 0:
            continue

        words.append(
            OcrWord(
                text=text,
                confidence=confidence / 100,
                x=int(data["left"][index]),
                y=int(data["top"][index]),
                width=int(data["width"][index]),
                height=int(data["height"][index]),
            )
        )

    return words


def _build_lines(
    words: list[OcrWord],
) -> list[OcrTextLine]:
    if not words:
        return []

    words = sorted(
        words,
        key=lambda word: (
            word.center_y,
            word.x,
        ),
    )

    groups: list[list[OcrWord]] = []

    for word in words:
        matching_group = None

        for group in groups[-5:]:
            center = mean(item.center_y for item in group)

            height = mean(item.height for item in group)

            tolerance = max(
                height * 0.5,
                5,
            )

            if abs(word.center_y - center) <= tolerance:
                matching_group = group
                break

        if matching_group is None:
            groups.append([word])
        else:
            matching_group.append(word)

    lines: list[OcrTextLine] = []

    for group in groups:
        group.sort(key=lambda word: word.x)

        text = " ".join(word.text for word in group)

        confidence = mean(word.confidence for word in group)

        lines.append(
            OcrTextLine(
                text=text,
                confidence=confidence,
                x1=min(word.x for word in group),
                y1=min(word.y for word in group),
                x2=max(word.right for word in group),
                y2=max(word.y + word.height for word in group),
                words=tuple(group),
            )
        )

    lines.sort(key=lambda line: line.y1)

    return lines


def _extract_lines(
    data: dict[str, list[Any]],
) -> list[OcrTextLine]:
    groups: dict[
        tuple[int, int, int],
        list[int],
    ] = {}

    for index, value in enumerate(data["text"]):
        text = str(value).strip()

        if not text:
            continue

        try:
            confidence = float(data["conf"][index])
        except (
            ValueError,
            TypeError,
        ):
            continue

        if confidence < 0:
            continue

        key = (
            int(data["block_num"][index]),
            int(data["par_num"][index]),
            int(data["line_num"][index]),
        )

        groups.setdefault(
            key,
            [],
        ).append(index)

    lines: list[OcrTextLine] = []

    for indexes in groups.values():
        indexes.sort(key=lambda index: int(data["left"][index]))

        words: list[str] = []
        confidences: list[float] = []

        left_values: list[int] = []

        top_values: list[int] = []

        right_values: list[int] = []

        bottom_values: list[int] = []

        line_words: list[OcrWord] = []

        for index in indexes:
            text = str(data["text"][index]).strip()

            if not text:
                continue

            confidence = float(data["conf"][index])

            left = int(data["left"][index])

            top = int(data["top"][index])

            width = int(data["width"][index])

            height = int(data["height"][index])

            words.append(text)

            confidences.append(confidence / 100)

            left_values.append(left)

            top_values.append(top)

            right_values.append(left + width)

            bottom_values.append(top + height)

            line_words.append(
                OcrWord(
                    text=text,
                    confidence=confidence / 100,
                    x=left,
                    y=top,
                    width=width,
                    height=height,
                )
            )

        if not words:
            continue

        lines.append(
            OcrTextLine(
                text=" ".join(words),
                confidence=mean(confidences),
                x1=min(left_values),
                y1=min(top_values),
                x2=max(right_values),
                y2=max(bottom_values),
                words=tuple(line_words),
            )
        )

    lines.sort(
        key=lambda line: (
            line.y1,
            line.x1,
        )
    )

    return lines


def _print_candidates(
    candidates: list[OcrCandidate],
) -> None:
    print()
    print("### OCR-KANDIDATEN ###")

    sorted_candidates = sorted(
        candidates,
        key=lambda candidate: candidate.score,
        reverse=True,
    )

    for candidate in sorted_candidates:
        receipt = candidate.receipt

        store = receipt.store if receipt.store is not None else "-"

        receipt_date = (
            str(receipt.purchase_date) if (receipt.purchase_date is not None) else "-"
        )

        total = (
            f"{receipt.price_cents / 100:.2f}"
            if (receipt.price_cents is not None)
            else "-"
        )

        confidence = (
            (receipt.confidence * 100) if (receipt.confidence is not None) else 0.0
        )

        print(
            f"{candidate.variant:10} "
            f"PSM {candidate.psm:2} | "
            f"Score "
            f"{candidate.score * 100:5.1f}% | "
            f"Items "
            f"{candidate.item_score * 100:5.1f}% | "
            f"OCR "
            f"{confidence:5.1f}% | "
            f"Händler: {store} | "
            f"Datum: {receipt_date} | "
            f"Gesamt: {total} | "
            f"Artikel: "
            f"{len(receipt.items)}"
        )
