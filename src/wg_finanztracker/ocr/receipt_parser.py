import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from statistics import median

from wg_finanztracker.ocr.models import (
    OcrItem,
    OcrReceipt,
    OcrTextLine,
)

DATE_DMY_PATTERN = re.compile(
    r"(?<!\d)" r"(\d{1,2})" r"\s*[./-]\s*" r"(\d{1,2})" r"\s*[./-]\s*" r"(\d{2,4})"
)

DATE_YMD_PATTERN = re.compile(
    r"(?<!\d)" r"(\d{4})" r"\s*[./-]\s*" r"(\d{1,2})" r"\s*[./-]\s*" r"(\d{1,2})"
)

MONEY_PATTERN = re.compile(
    r"(?<!\d)" r"(\d{1,5})" r"\s*([,.'’])\s*" r"(\d{2})" r"(?!\d)"
)

COMPACT_ITEM_MONEY_PATTERN = re.compile(r"(?<!\d)" r"(\d{3,4})" r"(?=\s*[A-D]\b)")

POSTAL_CODE_PATTERN = re.compile(r"\b\d{5}\b")

ARTICLE_COUNT_PATTERN = re.compile(
    r"\b\d+\s+artikel\b",
    re.IGNORECASE,
)

BARCODE_PREFIX_PATTERN = re.compile(
    r"^\s*" r"[^\d]{0,3}" r"\s*" r"\d[\d/|]{4,16}" r"[.\s:;-]*"
)

TOTAL_KEYWORDS = (
    "summe",
    "gesamt",
    "endsumme",
    "zu zahlen",
    "zu bezahlen",
    "endbetrag",
    "aldi preis",
)

PAYMENT_KEYWORDS = (
    "kartenzahlung",
    "karte",
    "girocard",
    "ec-karte",
    "ec karte",
    "visa",
    "mastercard",
    "barzahlung",
    "bar bezahlt",
    "ec-cash",
    "ec cash",
)

DISCOUNT_KEYWORDS = (
    "rabatt",
    "coupon",
    "gutschein",
    "preisvorteil",
    "gespart",
)

METADATA_KEYWORDS = (
    "mwst",
    "ust",
    "steuer",
    "netto",
    "brutto",
    "rückgeld",
    "rueckgeld",
    "wechselgeld",
    "gegeben",
    "transaktion",
    "lastschrift",
    "beleg",
    "tse",
    "signatur",
    "payback",
    "punktestand",
    "fiskalinformation",
)

TOTAL_EXCLUSION_KEYWORDS = (
    *DISCOUNT_KEYWORDS,
    "ersparnis",
    "punkte",
    "punktestand",
    "netto",
    "brutto",
    "mwst",
    "ust",
    "steuer",
)

KNOWN_STORES: tuple[
    tuple[
        str,
        tuple[str, ...],
    ],
    ...,
] = (
    ("ALDI SÜD", (r"\baldi\s+s[üu]d\b",)),
    ("ALDI", (r"\baldi\s+preis\b", r"\baldi\b")),
    ("Lidl", (r"\blidl\b",)),
    ("REWE", (r"\brewe\b",)),
    ("PENNY", (r"\bpenny\b",)),
    ("Netto Marken-Discount", (r"netto\s+(?:marken|filiale)",)),
    ("EDEKA", (r"\bedeka\b",)),
    ("Kaufland", (r"\bkaufland\b",)),
    ("dm", (r"\bdm[-\s]?drogerie", r"\bdm\.de\b")),
    ("ROSSMANN", (r"\brossmann\b",)),
    ("Action", (r"\baction\b",)),
    ("NORMA", (r"\bnorma\b",)),
    ("Globus", (r"\bglobus\b",)),
    ("Müller", (r"\bm[üu]ller\b",)),
    ("IKEA", (r"\bikea\b",)),
)


@dataclass
class _ItemCandidate:
    line: OcrTextLine
    name: str
    price_cents: int
    price_x: float


def parse_receipt(
    lines: list[OcrTextLine],
) -> OcrReceipt:
    rows = _merge_visual_rows(lines)

    total = _find_total(rows)

    return OcrReceipt(
        store=_find_store(rows),
        purchase_date=_find_date(rows),
        price_cents=total,
        items=_find_items_by_layout(
            rows,
            total,
        ),
        raw_text="\n".join(line.text for line in rows),
        confidence=_calculate_confidence(rows),
    )


def _merge_visual_rows(
    lines: list[OcrTextLine],
) -> list[OcrTextLine]:
    """
    Tesseract kann Namen und Preis derselben
    sichtbaren Zeile in unterschiedliche Blöcke
    aufteilen.

    Diese Funktion fügt Textblöcke zusammen,
    wenn sie ungefähr auf derselben Höhe liegen.
    """

    if not lines:
        return []

    sorted_lines = sorted(
        lines,
        key=lambda line: (
            line.y1,
            line.x1,
        ),
    )

    groups: list[list[OcrTextLine]] = []

    for line in sorted_lines:
        matching_group: list[OcrTextLine] | None = None

        for group in groups[-6:]:
            if _belongs_to_same_row(
                line,
                group,
            ):
                matching_group = group
                break

        if matching_group is None:
            groups.append([line])
        else:
            matching_group.append(line)

    result: list[OcrTextLine] = []

    for group in groups:
        group.sort(key=lambda line: line.x1)

        text = " ".join(line.text.strip() for line in group if line.text.strip())

        if not text:
            continue

        total_length = sum(
            max(
                len(line.text),
                1,
            )
            for line in group
        )

        confidence = (
            sum(
                line.confidence
                * max(
                    len(line.text),
                    1,
                )
                for line in group
            )
            / total_length
        )

        result.append(
            OcrTextLine(
                text=text,
                confidence=confidence,
                x1=min(line.x1 for line in group),
                y1=min(line.y1 for line in group),
                x2=max(line.x2 for line in group),
                y2=max(line.y2 for line in group),
                words=tuple(
                    sorted(
                        (word for line in group for word in line.words),
                        key=lambda word: word.x,
                    )
                ),
            )
        )

    result.sort(
        key=lambda line: (
            line.y1,
            line.x1,
        )
    )

    return result


def _belongs_to_same_row(
    line: OcrTextLine,
    group: list[OcrTextLine],
) -> bool:
    group_y1 = min(item.y1 for item in group)

    group_y2 = max(item.y2 for item in group)

    line_height = max(
        line.y2 - line.y1,
        1,
    )

    group_height = max(
        group_y2 - group_y1,
        1,
    )

    overlap = max(
        0,
        min(
            line.y2,
            group_y2,
        )
        - max(
            line.y1,
            group_y1,
        ),
    )

    minimum_height = min(
        line_height,
        group_height,
    )

    if overlap >= minimum_height * 0.35:
        return True

    line_center = (line.y1 + line.y2) / 2

    group_center = (group_y1 + group_y2) / 2

    tolerance = (
        max(
            line_height,
            group_height,
        )
        * 0.35
    )

    return abs(line_center - group_center) <= tolerance


def _find_store(
    lines: list[OcrTextLine],
) -> str | None:
    if not lines:
        return None

    known_store = _find_known_store(lines)

    if known_store is not None:
        return known_store

    document_height = max(line.y2 for line in lines)

    # Ein Händlername sollte normalerweise
    # im oberen Viertel des Bons stehen.
    maximum_y = document_height * 0.25

    header_lines = [line for line in lines if line.y1 <= maximum_y]

    if not header_lines:
        header_lines = lines[:10]

    maximum_height = max(
        max(
            line.y2 - line.y1,
            1,
        )
        for line in header_lines
    )

    candidates: list[tuple[float, str]] = []

    for index, line in enumerate(header_lines):
        text = line.text.strip()

        if not _is_store_candidate(text):
            continue

        score = line.confidence

        line_height = max(
            line.y2 - line.y1,
            1,
        )

        score += (line_height / maximum_height) * 0.20

        score += max(
            0.0,
            0.20 - index * 0.02,
        )

        letters = "".join(character for character in text if character.isalpha())

        if letters.isupper() and 3 <= len(letters) <= 20:
            score += 0.20

        word_count = len(text.split())

        if word_count <= 3:
            score += 0.05

        if len(text) > 40:
            score -= 0.20

        candidates.append(
            (
                score,
                text,
            )
        )

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda candidate: candidate[0],
    )[1]


def _find_known_store(
    lines: list[OcrTextLine],
) -> str | None:
    # Auch der Artikelbereich zählt: Logos werden
    # häufig schlecht erkannt, während z. B.
    # "Lidl Plus" oder eine EDEKA-Webadresse sehr
    # zuverlässig lesbar bleibt.
    text = "\n".join(line.text for line in lines).casefold()

    for store, patterns in KNOWN_STORES:
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns):
            return store

    return None


def _is_store_candidate(
    text: str,
) -> bool:
    if len(text) < 3:
        return False

    if _contains_date(text):
        return False

    if MONEY_PATTERN.search(text):
        return False

    if POSTAL_CODE_PATTERN.search(text):
        return False

    if _is_metadata(text):
        return False

    normalized = text.lower()

    if any(
        value in normalized
        for value in (
            "www.",
            "http",
            "telefon",
            "tel.",
        )
    ):
        return False

    # Adresse möglichst ausschließen.
    if re.search(
        r"\b\w*" r"(?:straße|strasse|str)" r"\.?\b",
        normalized,
    ):
        return False

    letters = sum(character.isalpha() for character in text)

    return letters >= 3


def _find_date(
    lines: list[OcrTextLine],
) -> date | None:
    for index, line in enumerate(lines):
        text = _normalize_numeric_text(line.text)

        match = DATE_YMD_PATTERN.search(text)

        if match is not None:
            result = _create_date(
                year=int(match.group(1)),
                month=int(match.group(2)),
                day=int(match.group(3)),
            )

            if result is not None:
                return result

        match = DATE_DMY_PATTERN.search(text)

        if match is None:
            continue

        day = int(match.group(1))

        month = int(match.group(2))

        year = int(match.group(3))

        if year < 100:
            year += 2000

        result = _create_date(
            year=year,
            month=month,
            day=day,
        )

        if result is not None:
            return result

    return None


def _create_date(
    year: int,
    month: int,
    day: int,
) -> date | None:
    try:
        result = date(
            year,
            month,
            day,
        )
    except ValueError:
        return None

    today = datetime.now(UTC).date()

    if result.year < 2000 or result > today + timedelta(days=7):
        return None

    return result


def _contains_date(
    text: str,
) -> bool:
    text = _normalize_numeric_text(text)

    return (
        DATE_DMY_PATTERN.search(text) is not None
        or DATE_YMD_PATTERN.search(text) is not None
    )


def _normalize_numeric_text(
    text: str,
) -> str:
    """Repariert typische OCR-Verwechslungen nur für Zahlenfelder."""

    return text.translate(
        str.maketrans(
            "OoIl|",
            "00111",
        )
    )


def _find_total(
    lines: list[OcrTextLine],
) -> int | None:
    candidates: list[tuple[float, int]] = []

    line_count = max(len(lines), 1)

    for index, line in enumerate(lines):
        label_score = _total_label_score(line.text)

        if label_score <= 0:
            continue

        price = _rightmost_price(line.text)

        if price is None or price <= 0:
            continue

        # Bei gleicher Beschriftung ist eine Zeile
        # im späteren Bonverlauf etwas wahrscheinlicher
        # als Kopf- oder Werbetext.
        position_bonus = (index / line_count) * 0.20

        candidates.append(
            (
                label_score + position_bonus,
                price,
            )
        )

    explicit_total = (
        max(
            candidates,
            key=lambda candidate: candidate[0],
        )[1]
        if candidates
        else None
    )

    tax_total = _find_tax_table_total(lines)

    # Zwei Steuerklassen liefern eine unabhängige
    # Prüfsumme. Sie repariert z. B. ein als 1
    # gelesenes 7 in "Zu zahlen 47,32".
    if tax_total is not None and (
        explicit_total is None or abs(tax_total - explicit_total) > 1
    ):
        return tax_total

    return explicit_total


def _find_tax_table_total(
    lines: list[OcrTextLine],
) -> int | None:
    for header_index, line in enumerate(lines):
        normalized = line.text.casefold()

        netto_match = re.search(
            r"ne[tl]{2}[o0]",
            normalized,
        )

        brutto_match = re.search(
            r"brutt[o0]",
            normalized,
        )

        gross_is_rightmost = (
            netto_match is not None
            and brutto_match is not None
            and brutto_match.start() > netto_match.start()
        ) or (
            "exkl" in normalized
            and "inkl" in normalized
            and normalized.rfind("inkl") > normalized.rfind("exkl")
        )

        if not gross_is_rightmost:
            continue

        gross_values: list[int] = []

        for tax_line in lines[header_index + 1 : header_index + 6]:
            tax_text = tax_line.text.casefold()

            merged_values = _gross_values_from_merged_tax_line(
                tax_line.text,
            )

            if merged_values:
                gross_values.extend(merged_values)

                if len(gross_values) >= 2:
                    return sum(gross_values)

                continue

            if re.search(r"\bsumme\b", tax_text):
                break

            prices = list(MONEY_PATTERN.finditer(tax_line.text))

            if len(prices) < 2:
                if gross_values:
                    break

                continue

            gross_value = _money_match_to_cents(prices[-1])

            if gross_value is not None:
                gross_values.append(gross_value)

        if len(gross_values) >= 2:
            return sum(gross_values)

    return None


def _gross_values_from_merged_tax_line(
    text: str,
) -> list[int]:
    class_matches = list(
        re.finditer(
            r"(?<!\w)[a-d]\s*(?:7|19)\s*%",
            text,
            re.IGNORECASE,
        )
    )

    if len(class_matches) < 2:
        return []

    values: list[int] = []

    for index, class_match in enumerate(class_matches):
        end = (
            class_matches[index + 1].start()
            if index + 1 < len(class_matches)
            else len(text)
        )

        segment = text[class_match.end() : end]

        # Eine hineingerutschte Summenzeile gehört
        # nicht mehr zur ersten Steuerklasse.
        segment = re.split(
            r"\bsumme\b",
            segment,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]

        prices = list(MONEY_PATTERN.finditer(segment))

        if not prices:
            continue

        value = _money_match_to_cents(prices[-1])

        if value is not None:
            values.append(value)

    return values


def _total_label_score(
    text: str,
) -> float:
    normalized = re.sub(
        r"\s+",
        " ",
        text.casefold(),
    ).strip()

    # OCR liest das Z in "Zu zahlen" nicht selten
    # als 2, 7 oder Schrägstrich.
    if re.search(
        r"(?:\bzu|\b[27/]u)\s+(?:be)?zahlen\b",
        normalized,
    ):
        return 7.0

    if re.search(
        r"^\s*(?:end)?summe\b",
        normalized,
    ):
        if any(keyword in normalized for keyword in TOTAL_EXCLUSION_KEYWORDS):
            return 0.0

        return 6.0

    if re.search(
        r"^\s*(?:gesamtbetrag|endsumme|endbetrag|total)\b",
        normalized,
    ):
        return 6.0

    if "aldi preis" in normalized:
        return 6.0

    if _is_payment_line(text):
        return 5.0

    if any(keyword in normalized for keyword in TOTAL_EXCLUSION_KEYWORDS):
        return 0.0

    if re.search(
        r"^\s*gesamt(?:\s|:|$)",
        normalized,
    ):
        return 4.5

    return 0.0


def _find_items_by_layout(
    lines: list[OcrTextLine],
    total_cents: int | None,
) -> list[OcrItem]:
    if not lines:
        return []

    document_right = max(line.x2 for line in lines)

    document_height = max(line.y2 for line in lines)

    end_y = _find_item_end_y(
        lines,
        document_height,
    )

    candidates: list[_ItemCandidate] = []

    heights: list[int] = []

    for index, line in enumerate(lines):
        if line.y1 >= end_y:
            continue

        text = line.text.strip()

        if not text:
            continue

        if _contains_date(text):
            continue

        if _is_metadata(text):
            previous_text = lines[index - 1].text if index > 0 else None

            item_text = _item_text_from_total_row(
                text,
                previous_text,
            )

            if item_text is None:
                continue

            text = item_text

        for item_text in _split_merged_item_row(
            text,
            total_cents,
        ):
            price_match = _find_rightmost_item_price(
                item_text,
                total_cents,
            )

            if price_match is None:
                continue

            match, price_cents = price_match

            name = item_text[: match.start()]

            name = _clean_item_name(name)

            if not _is_valid_item_name(name):
                continue

            price_x = _price_x(
                line,
                item_text,
                match,
            )

            candidates.append(
                _ItemCandidate(
                    line=line,
                    name=name,
                    price_cents=(price_cents),
                    price_x=price_x,
                )
            )

            heights.append(
                max(
                    line.y2 - line.y1,
                    1,
                )
            )

    if not candidates:
        return []

    typical_height = median(heights) if heights else 20

    x_tolerance = max(
        typical_height * 3.0,
        document_right * 0.035,
    )

    price_column = _find_dominant_price_column(
        candidates,
        document_right,
        x_tolerance,
    )

    if price_column is None:
        return []

    aligned = [
        candidate
        for candidate in candidates
        if (abs(candidate.price_x - price_column) <= x_tolerance)
    ]

    if not aligned:
        return []

    article_run = _find_best_article_run(
        aligned,
        typical_height,
    )

    return [
        OcrItem(
            name=candidate.name,
            price_cents=(candidate.price_cents),
        )
        for candidate in article_run
    ]


def _split_merged_item_row(
    text: str,
    total_cents: int | None,
) -> list[str]:
    matches = [
        match
        for match in MONEY_PATTERN.finditer(text)
        if not _is_negative_money(text, match)
        and not _is_unit_price_match(text, match)
        and (
            total_cents is None
            or (_money_match_to_cents(match) or total_cents + 1) <= total_cents
        )
    ]

    if len(matches) < 2:
        return [text]

    split_indexes: list[int] = []

    for index in range(1, len(matches)):
        bridge = text[matches[index - 1].end() : matches[index].start()]

        bridge = re.sub(
            r"^\s*[A-D]\b[\s,;|]*",
            "",
            bridge,
            flags=re.IGNORECASE,
        )

        if sum(character.isalpha() for character in bridge) >= 3:
            split_indexes.append(index)

    if not split_indexes:
        return [text]

    result: list[str] = []
    start = 0

    for split_index in split_indexes:
        previous_match = matches[split_index - 1]

        result.append(text[start : previous_match.end()])

        start = previous_match.end()

    result.append(text[start:])

    return result


def _price_x(
    line: OcrTextLine,
    text: str,
    match: re.Match[str],
) -> float:
    """Bestimmt die echte statt einer geschätzten Preisposition."""

    if line.words:
        matched_value = _money_match_to_cents(match)

        for word in sorted(
            line.words,
            key=lambda current: current.x,
            reverse=True,
        ):
            for word_match in MONEY_PATTERN.finditer(word.text):
                if _money_match_to_cents(word_match) == matched_value:
                    return float(word.right)

        offset = 0

        for word in sorted(
            line.words,
            key=lambda current: current.x,
        ):
            word_start = offset
            word_end = word_start + len(word.text)

            if word_end >= match.end() and word_start <= match.end():
                return float(word.right)

            offset = word_end + 1

    line_width = max(
        line.x2 - line.x1,
        1,
    )

    relative_position = match.end() / max(
        len(text),
        1,
    )

    return line.x1 + line_width * relative_position


def _item_text_from_total_row(
    text: str,
    previous_text: str | None,
) -> str | None:
    """Rettet Artikel, die OCR mit der SUMME-Zeile verschmolzen hat."""

    if (
        re.match(
            r"^\s*(?:end)?summe\b",
            text,
            re.IGNORECASE,
        )
        is None
    ):
        return None

    item_text = re.sub(
        r"^\s*(?:end)?summe\b" r"(?:\s+(?:eur|eu|e|€|z)){0,4}\s*",
        "",
        text,
        count=1,
        flags=re.IGNORECASE,
    )

    price_match = MONEY_PATTERN.search(item_text)

    if price_match is None:
        return None

    item_name = item_text[: price_match.start()]

    if sum(character.isalpha() for character in item_name) < 3:
        if (
            previous_text is None
            or _is_metadata(previous_text)
            or not _is_valid_item_name(previous_text)
        ):
            return None

        item_text = f"{previous_text} " f"{price_match.group(0)}"

    return item_text


def _find_dominant_price_column(
    candidates: list[_ItemCandidate],
    document_right: float,
    tolerance: float,
) -> float | None:
    clusters: list[list[_ItemCandidate]] = []

    for candidate in sorted(
        candidates,
        key=lambda current: current.price_x,
    ):
        matching_cluster: list[_ItemCandidate] | None = None

        for cluster in clusters:
            center = sum(item.price_x for item in cluster) / len(cluster)

            if abs(candidate.price_x - center) <= tolerance:
                matching_cluster = cluster
                break

        if matching_cluster is None:
            clusters.append([candidate])
        else:
            matching_cluster.append(candidate)

    valid_clusters: list[
        tuple[
            float,
            list[_ItemCandidate],
        ]
    ] = []

    for cluster in clusters:
        center = sum(item.price_x for item in cluster) / len(cluster)

        # Preise sollten sich eher auf der
        # rechten Bonhälfte befinden.
        if center < document_right * 0.50:
            continue

        valid_clusters.append(
            (
                center,
                cluster,
            )
        )

    if not valid_clusters:
        return None

    center, _ = max(
        valid_clusters,
        key=lambda entry: (
            len(entry[1]),
            entry[0],
        ),
    )

    return center


def _find_best_article_run(
    candidates: list[_ItemCandidate],
    typical_height: float,
) -> list[_ItemCandidate]:
    sorted_candidates = sorted(
        candidates,
        key=lambda candidate: candidate.line.y1,
    )

    if len(sorted_candidates) <= 1:
        return sorted_candidates

    maximum_gap = max(
        typical_height * 6.0,
        30,
    )

    runs: list[list[_ItemCandidate]] = []

    current_run = [sorted_candidates[0]]

    for candidate in sorted_candidates[1:]:
        previous = current_run[-1]

        gap = candidate.line.y1 - previous.line.y2

        if gap <= maximum_gap:
            current_run.append(candidate)
        else:
            runs.append(current_run)

            current_run = [candidate]

    runs.append(current_run)

    return max(
        runs,
        key=lambda run: (
            len(run),
            sum(candidate.line.confidence for candidate in run),
        ),
    )


def _find_item_end_y(
    lines: list[OcrTextLine],
    default_y: float,
) -> float:
    for line in lines:
        normalized = line.text.lower()

        if ARTICLE_COUNT_PATTERN.search(normalized):
            return line.y2 + 1

        if _total_label_score(line.text) > 0:
            return line.y2 + 1

        if _is_payment_line(line.text):
            return line.y2 + 1

        if any(
            keyword in normalized
            for keyword in (
                "mwst",
                "netto",
                "brutto",
            )
        ):
            return line.y2 + 1

    return default_y


def _find_rightmost_item_price(
    text: str,
    total_cents: int | None,
) -> (
    tuple[
        re.Match[str],
        int,
    ]
    | None
):
    matches = [
        *MONEY_PATTERN.finditer(text),
        *COMPACT_ITEM_MONEY_PATTERN.finditer(text),
    ]

    matches.sort(key=lambda current: current.start())

    if not matches:
        return None

    for match in reversed(matches):
        if _is_negative_money(
            text,
            match,
        ):
            continue

        if _is_unit_price_match(
            text,
            match,
        ):
            continue

        price = _money_match_to_cents(match)

        if price is None:
            continue

        if total_cents is None or price <= total_cents:
            return (
                match,
                price,
            )

    return None


def _is_unit_price_match(
    text: str,
    match: re.Match[str],
) -> bool:
    suffix = text[match.end() : match.end() + 20].casefold()

    return (
        re.match(
            r"\s*(?:€|eur)?\s*/\s*(?:kg|g|l|ml|st)",
            suffix,
        )
        is not None
    )


def _is_negative_money(
    text: str,
    match: re.Match[str],
) -> bool:
    start = max(
        match.start() - 3,
        0,
    )

    prefix = text[start : match.start()]

    return any(
        marker in prefix
        for marker in (
            "-",
            "−",
            "–",
            "~",
        )
    )


def _rightmost_price(
    text: str,
) -> int | None:
    matches = list(MONEY_PATTERN.finditer(text))

    if not matches:
        return None

    return _money_match_to_cents(matches[-1])


def _money_match_to_cents(
    match: re.Match[str],
) -> int | None:
    if match.re is COMPACT_ITEM_MONEY_PATTERN:
        digits = match.group(1)

        return _to_cents(
            digits[:-2],
            digits[-2:],
        )

    return _to_cents(
        match.group(1),
        match.group(3),
    )


def _to_cents(
    integer_part: str,
    decimal_part: str,
) -> int | None:
    try:
        amount = Decimal(f"{integer_part}." f"{decimal_part}")
    except InvalidOperation:
        return None

    return int(amount * 100)


def _clean_item_name(
    name: str,
) -> str:
    name = BARCODE_PREFIX_PATTERN.sub(
        "",
        name,
    )

    name = re.sub(
        r"[\[\]{}|]",
        "",
        name,
    )

    name = re.sub(
        r"^\s*(?:[A-D]\b|[ı'‚]\s+|i\s+(?=[A-ZÄÖÜ]))[\s,;]*",
        "",
        name,
        flags=re.IGNORECASE,
    )

    name = re.sub(
        r"\s+",
        " ",
        name,
    )

    # Mengenangaben wie "1,79 x 3" gehören nicht
    # zum Artikelnamen; Größen wie "400 g" bleiben
    # dagegen erhalten.
    name = re.sub(
        r"\s+\d{1,4}\s*[,.'’]\s*\d{2}" r"\s*[x×]\s*\d+\s*$",
        "",
        name,
        flags=re.IGNORECASE,
    )

    return name.strip(" .,:;-=<>_*")


def _is_valid_item_name(
    name: str,
) -> bool:
    if not name:
        return False

    if _is_metadata(name):
        return False

    letters = sum(character.isalpha() for character in name)

    if letters < 3:
        return False

    return len(name) <= 100


def _is_payment_line(
    text: str,
) -> bool:
    normalized = text.lower()

    return any(keyword in normalized for keyword in PAYMENT_KEYWORDS)


def _is_metadata(
    text: str,
) -> bool:
    normalized = text.lower()

    if ARTICLE_COUNT_PATTERN.search(normalized):
        return True

    if _total_label_score(text) > 0:
        return True

    if any(
        keyword in normalized
        for keyword in (
            *DISCOUNT_KEYWORDS,
            *METADATA_KEYWORDS,
        )
    ):
        return True

    return _is_payment_line(text)


def _calculate_confidence(
    lines: list[OcrTextLine],
) -> float | None:
    if not lines:
        return None

    total_length = sum(
        max(
            len(line.text),
            1,
        )
        for line in lines
    )

    return (
        sum(
            line.confidence
            * max(
                len(line.text),
                1,
            )
            for line in lines
        )
        / total_length
    )
