from pathlib import Path
from typing import Protocol

from wg_finanztracker.ocr.ocr_models import OcrReceipt


class ReceiptOcrService(Protocol):
    def recognize(
        self,
        image_path: str | Path,
    ) -> OcrReceipt: ...
