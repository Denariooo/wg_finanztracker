import argparse
import json
import sys
from pathlib import Path

from wg_finanztracker.ocr.ocr_models import OcrReceipt
from wg_finanztracker.ocr.tesseract_service import TesseractOcrService


def _receipt_to_dict(
    receipt: OcrReceipt,
) -> dict[str, object]:
    return {
        "store": receipt.store,
        "purchase_date": (
            receipt.purchase_date.isoformat()
            if receipt.purchase_date is not None
            else None
        ),
        "price_cents": receipt.price_cents,
        "items": [
            {
                "name": item.name,
                "price_cents": item.price_cents,
            }
            for item in receipt.items
        ],
        "confidence": receipt.confidence,
        "raw_text": receipt.raw_text,
    }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(
            encoding="utf-8",
            errors="replace",
        )

    parser = argparse.ArgumentParser(
        description="Liest einen deutschen Kassenbon als JSON.",
    )

    parser.add_argument(
        "image",
        type=Path,
        help="Pfad zu einem JPG- oder PNG-Bon",
    )

    parser.add_argument(
        "--debug-directory",
        type=Path,
        help="Schreibt getestete Bildvarianten in dieses Verzeichnis.",
    )

    arguments = parser.parse_args()

    result = TesseractOcrService(
        debug_directory=arguments.debug_directory,
    ).recognize(arguments.image)

    print(
        json.dumps(
            _receipt_to_dict(result),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
