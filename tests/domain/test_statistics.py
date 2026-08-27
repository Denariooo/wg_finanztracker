from datetime import date

from wg_finanztracker.domain.models import Item, Member, Receipt
from wg_finanztracker.domain.stats import (
    calculate_category_totals,
    calculate_member_spending_totals,
    calculate_monthly_totals,
    calculate_yearly_totals,
    categorize_item_name,
)


def test_categorize_item_name_matches_keywords() -> None:
    assert categorize_item_name("Vollmilch 3,5%") == "Lebensmittel"
    assert categorize_item_name("Spülmittel Zitrone") == "Haushalt"
    assert categorize_item_name("Duschgel Sensitive") == "Hygiene"


def test_categorize_item_name_falls_back_to_sonstiges() -> None:
    assert categorize_item_name("USB-C Adapter") == "Sonstiges"


def test_calculate_category_totals() -> None:
    member = Member(id=1, name="Deniz")

    receipts = [
        Receipt(
            store="REWE",
            purchase_date=date(2026, 8, 1),
            price_cents=700,
            paid_by=member,
            items=[
                Item(name="Milch", price_cents=200, assigned_to=[member]),
                Item(name="Spülmittel", price_cents=500, assigned_to=[member]),
            ],
        )
    ]

    totals = calculate_category_totals(receipts)

    assert totals == {
        "Haushalt": 500,
        "Lebensmittel": 200,
    }


def test_calculate_member_spending_totals_uses_shares() -> None:
    member_a = Member(id=1, name="A")
    member_b = Member(id=2, name="B")
    member_c = Member(id=3, name="C")

    receipt = Receipt(
        store="Lidl",
        purchase_date=date(2026, 8, 10),
        price_cents=100,
        paid_by=member_a,
        items=[
            Item(
                name="Pizza",
                price_cents=100,
                assigned_to=[member_a, member_b, member_c],
            )
        ],
    )

    totals = calculate_member_spending_totals([receipt])

    assert totals[1] == 34
    assert totals[2] == 33
    assert totals[3] == 33


def test_calculate_monthly_and_yearly_totals_sorted() -> None:
    member = Member(id=1, name="Deniz")
    receipts = [
        Receipt(
            store="REWE",
            purchase_date=date(2026, 2, 15),
            price_cents=300,
            paid_by=member,
            items=[],
        ),
        Receipt(
            store="REWE",
            purchase_date=date(2025, 12, 15),
            price_cents=200,
            paid_by=member,
            items=[],
        ),
        Receipt(
            store="REWE",
            purchase_date=date(2026, 2, 20),
            price_cents=100,
            paid_by=member,
            items=[],
        ),
    ]

    monthly = calculate_monthly_totals(receipts)
    yearly = calculate_yearly_totals(receipts)

    assert monthly == [
        (2025, 12, 200),
        (2026, 2, 400),
    ]
    assert yearly == [
        (2025, 200),
        (2026, 400),
    ]
