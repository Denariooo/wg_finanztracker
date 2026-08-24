import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import torch
from PIL import Image
from transformers import (
    DonutProcessor,
    VisionEncoderDecoderModel,
)

from wg_finanztracker.ocr.models import (
    OcrItem,
    OcrReceipt,
)

MODEL_NAME = "naver-clova-ix/" "donut-base-finetuned-cord-v2"

TASK_PROMPT = "<s_cord-v2>"


class DonutOcrService:
    def __init__(self) -> None:
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        self.processor = DonutProcessor.from_pretrained(MODEL_NAME, use_fast=False)

        self.model = VisionEncoderDecoderModel.from_pretrained(MODEL_NAME)

        self.model.to(self.device)

        self.model.eval()

    def recognize(
        self,
        image_path: str | Path,
    ) -> OcrReceipt:
        image = Image.open(image_path).convert("RGB")

        pixel_values = self.processor(
            image,
            return_tensors="pt",
        ).pixel_values.to(self.device)

        decoder_input_ids = self.processor.tokenizer(
            TASK_PROMPT,
            add_special_tokens=False,
            return_tensors="pt",
        ).input_ids.to(self.device)

        with torch.no_grad():
            outputs = self.model.generate(
                pixel_values,
                decoder_input_ids=(decoder_input_ids),
                max_length=768,
                early_stopping=True,
                pad_token_id=(self.processor.tokenizer.pad_token_id),
                eos_token_id=(self.processor.tokenizer.eos_token_id),
                use_cache=True,
                num_beams=1,
                bad_words_ids=[[self.processor.tokenizer.unk_token_id]],
                return_dict_in_generate=True,
            )

        sequence = self.processor.batch_decode(outputs.sequences)[0]

        cleaned = _clean_sequence(sequence)

        structured = self.processor.token2json(cleaned)

        return parse_donut_result(
            structured,
            raw_text=cleaned,
        )


def parse_donut_result(
    data: dict[str, Any],
    raw_text: str = "",
) -> OcrReceipt:
    menu = data.get("menu", [])

    if isinstance(menu, dict):
        menu = [menu]

    items: list[OcrItem] = []

    for item in menu:
        if not isinstance(
            item,
            dict,
        ):
            continue

        parsed_item = _parse_item(item)

        if parsed_item is not None:
            items.append(parsed_item)

    total_data = data.get("total", {})

    if not isinstance(
        total_data,
        dict,
    ):
        total_data = {}

    return OcrReceipt(
        store=_find_store(data),
        purchase_date=_find_date(data),
        price_cents=_find_total(total_data),
        items=items,
        raw_text=raw_text,
        confidence=None,
    )


def _parse_item(
    item: dict[str, Any],
) -> OcrItem | None:
    name = _first_string(
        item,
        (
            "nm",
            "name",
            "description",
        ),
    )

    price = _first_string(
        item,
        (
            "price",
            "unitprice",
            "unit_price",
        ),
    )

    count = _first_string(
        item,
        (
            "cnt",
            "count",
            "qty",
            "quantity",
        ),
    )

    if name is None:
        return None

    price_cents = _to_cents(price)

    if price_cents is None:
        return None

    quantity = _to_number(count)

    if quantity is not None and quantity > 1:
        price_cents = round(price_cents * quantity)

    return OcrItem(
        name=name.strip(),
        price_cents=price_cents,
    )


def _find_store(
    data: dict[str, Any],
) -> str | None:
    return _first_string(
        data,
        (
            "store_name",
            "merchant_name",
            "merchant",
            "store",
        ),
    )


def _find_date(
    data: dict[str, Any],
) -> date | None:
    value = _first_string(
        data,
        (
            "date",
            "purchase_date",
        ),
    )

    if value is None:
        return None

    patterns = (
        "%Y-%m-%d",
        "%d.%m.%Y",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d.%m.%y",
        "%d/%m/%y",
    )

    for pattern in patterns:
        try:
            return date.fromisoformat(
                date.strptime(
                    value,
                    pattern,
                ).isoformat()
            )
        except (
            ValueError,
            AttributeError,
        ):
            continue

    return None


def _find_total(
    total: dict[str, Any],
) -> int | None:
    value = _first_string(
        total,
        (
            "total_price",
            "total",
            "price",
            "cashprice",
        ),
    )

    return _to_cents(value)


def _first_string(
    data: dict[str, Any],
    keys: tuple[str, ...],
) -> str | None:
    for key in keys:
        value = data.get(key)

        if value is None:
            continue

        text = str(value).strip()

        if text:
            return text

    return None


def _to_cents(
    value: str | None,
) -> int | None:
    if value is None:
        return None

    normalized = value.replace("€", "").replace("EUR", "").strip()

    normalized = re.sub(
        r"[^\d,.-]",
        "",
        normalized,
    )

    if not normalized:
        return None

    if "," in normalized and "." in normalized:
        if normalized.rfind(",") > normalized.rfind("."):
            normalized = normalized.replace(".", "").replace(",", ".")
        else:
            normalized = normalized.replace(",", "")
    else:
        normalized = normalized.replace(",", ".")

    try:
        amount = Decimal(normalized)
    except InvalidOperation:
        return None

    return int((amount * 100).quantize(Decimal(1)))


def _to_number(
    value: str | None,
) -> float | None:
    if value is None:
        return None

    try:
        return float(
            value.replace(
                ",",
                ".",
            )
        )
    except ValueError:
        return None


def _clean_sequence(
    sequence: str,
) -> str:
    sequence = sequence.replace(TASK_PROMPT, "")

    sequence = re.sub(
        r"<.*?>",
        lambda match: (
            match.group(0)
            if match.group(0).startswith("</s_") or match.group(0).startswith("<s_")
            else ""
        ),
        sequence,
    )

    return sequence.strip()
