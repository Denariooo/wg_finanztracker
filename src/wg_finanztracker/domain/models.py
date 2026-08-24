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
class Receipt:
    store: str
    purchase_date: date
    price_cents: int
    paid_by: Member
    items: list[Item]


@dataclass
class Payment:
    from_member: Member
    to_member: Member
    amount_cents: int
    payment_date: date
