from datetime import date

import pytest
from hypothesis import given
from hypothesis import strategies as st

from wg_finanztracker.domain.cost_sharing import calculate_shares
from wg_finanztracker.domain.models import Item, Member, Purchase


def test_calculate_shares_multiple_items() -> None:
    member_a = Member(id=1, name="A")
    member_b = Member(id=2, name="B")

    purchase = Purchase(
        store="Test Store",
        purchase_date=date(2026, 8, 18),
        price_cents=800,
        paid_by=member_a,
        items=[
            Item(
                name="Pizza",
                price_cents=600,
                assigned_to=[member_a, member_b],
            ),
            Item(
                name="Cola",
                price_cents=200,
                assigned_to=[member_a],
            ),
        ],
    )

    shares = calculate_shares(purchase)

    assert shares == {1: 500, 2: 300}


def test_calculate_shares_with_remainder() -> None:
    member_a = Member(id=1, name="A")
    member_b = Member(id=2, name="B")
    member_c = Member(id=3, name="C")

    purchase = Purchase(
        store="Test Store",
        purchase_date=date(2026, 8, 18),
        price_cents=100,
        paid_by=member_a,
        items=[
            Item(
                name="Item",
                price_cents=100,
                assigned_to=[member_a, member_b, member_c],
            )
        ],
    )

    shares = calculate_shares(purchase)

    assert shares == {1: 34, 2: 33, 3: 33}
    assert sum(shares.values()) == 100


def test_calculate_shares_without_assigned_members() -> None:
    member_a = Member(id=1, name="A")

    purchase = Purchase(
        store="Test Store",
        purchase_date=date(2026, 8, 18),
        price_cents=100,
        paid_by=member_a,
        items=[
            Item(
                name="Item",
                price_cents=100,
                assigned_to=[],
            )
        ],
    )

    with pytest.raises(ValueError):
        calculate_shares(purchase)


@given(
    price_cents=st.integers(min_value=0, max_value=100_000),
    member_count=st.integers(min_value=1, max_value=10),
)
def test_distribution_preserves_total(
    price_cents: int,
    member_count: int,
) -> None:
    members = [Member(id=i, name=f"Member {i}") for i in range(member_count)]

    purchase = Purchase(
        store="Test Store",
        purchase_date=date(2026, 8, 18),
        price_cents=price_cents,
        paid_by=members[0],
        items=[
            Item(
                name="Test Item",
                price_cents=price_cents,
                assigned_to=members,
            )
        ],
    )

    shares = calculate_shares(purchase)

    assert sum(shares.values()) == price_cents
