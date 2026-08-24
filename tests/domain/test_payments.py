from datetime import date

from wg_finanztracker.domain.cost_sharing import calculate_total_debts
from wg_finanztracker.domain.models import Item, Member, Payment, Receipt


def test_payment_reduces_total_debt() -> None:
    member_a = Member(id=1, name="A")
    member_b = Member(id=2, name="B")

    purchase = Receipt(
        store="Test Store",
        purchase_date=date(2026, 8, 18),
        price_cents=1000,
        paid_by=member_a,
        items=[
            Item(
                name="Item",
                price_cents=1000,
                assigned_to=[member_b],
            )
        ],
    )

    payment = Payment(
        from_member=member_b,
        to_member=member_a,
        amount_cents=400,
        payment_date=date(2026, 8, 19),
    )

    debts = calculate_total_debts(
        [purchase],
        [payment],
    )

    assert debts == [
        (2, 1, 600),
    ]


def test_payment_can_fully_settle_debt() -> None:
    member_a = Member(id=1, name="A")
    member_b = Member(id=2, name="B")

    purchase = Receipt(
        store="Test Store",
        purchase_date=date(2026, 8, 18),
        price_cents=1000,
        paid_by=member_a,
        items=[
            Item(
                name="Item",
                price_cents=1000,
                assigned_to=[member_b],
            )
        ],
    )

    payment = Payment(
        from_member=member_b,
        to_member=member_a,
        amount_cents=1000,
        payment_date=date(2026, 8, 19),
    )

    debts = calculate_total_debts(
        [purchase],
        [payment],
    )

    assert debts == []
