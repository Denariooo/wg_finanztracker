from dataclasses import dataclass
from datetime import date


@dataclass
class OcrWord:
    text: str
    confidence: float
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def center_y(self) -> float:
        return self.y + self.height / 2


@dataclass
class OcrTextLine:
    text: str
    confidence: float
    x1: int
    y1: int
    x2: int
    y2: int
    words: tuple[OcrWord, ...] = ()


@dataclass
class OcrItem:
    name: str
    price_cents: int


@dataclass
class OcrReceipt:
    store: str | None
    purchase_date: date | None
    price_cents: int | None
    items: list[OcrItem]
    raw_text: str
    confidence: float | None
