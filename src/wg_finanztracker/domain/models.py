from dataclasses import dataclass
from datetime import date


@dataclass
class Member:
    id: int
    name: str


@dataclass
class Item:
    name: str
    price_cents: int
    assigned_to: list[Member]


@dataclass
class Purchase:
    store: str
    purchase_date: date
    price_cents: int
    paid_by: Member
    items: list[Item]
