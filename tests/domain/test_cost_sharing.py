from datetime import date

import pytest
from hypothesis import given
from hypothesis import strategies as st

from wg_finanztracker.domain.cost_sharing import calculate_debts, calculate_shares
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


def test_calculate_debts_with_payer_share() -> None:
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

    debts = calculate_debts(purchase)

    assert debts == {2: 300}


def test_calculate_debts_without_payer_share() -> None:
    member_a = Member(id=1, name="A")
    member_b = Member(id=2, name="B")

    purchase = Purchase(
        store="Test Store",
        purchase_date=date(2026, 8, 18),
        price_cents=500,
        paid_by=member_a,
        items=[
            Item(
                name="Item",
                price_cents=500,
                assigned_to=[member_b],
            )
        ],
    )

    debts = calculate_debts(purchase)

    assert debts == {2: 500}


def test_calculate_debts_multiple_members() -> None:
    member_a = Member(id=1, name="A")
    member_b = Member(id=2, name="B")
    member_c = Member(id=3, name="C")

    purchase = Purchase(
        store="Test Store",
        purchase_date=date(2026, 8, 18),
        price_cents=900,
        paid_by=member_a,
        items=[
            Item(
                name="Item A",
                price_cents=300,
                assigned_to=[member_a],
            ),
            Item(
                name="Item B",
                price_cents=200,
                assigned_to=[member_b],
            ),
            Item(
                name="Item C",
                price_cents=400,
                assigned_to=[member_c],
            ),
        ],
    )

    debts = calculate_debts(purchase)

    assert debts == {2: 200, 3: 400}


@given(
    payer_share=st.integers(min_value=0, max_value=100_000),
    other_share=st.integers(min_value=0, max_value=100_000),
)
def test_debts_match_non_payer_share(
    payer_share: int,
    other_share: int,
) -> None:
    payer = Member(id=1, name="Payer")
    other = Member(id=2, name="Other")

    purchase = Purchase(
        store="Test Store",
        purchase_date=date(2026, 8, 18),
        price_cents=payer_share + other_share,
        paid_by=payer,
        items=[
            Item(
                name="Payer Item",
                price_cents=payer_share,
                assigned_to=[payer],
            ),
            Item(
                name="Other Item",
                price_cents=other_share,
                assigned_to=[other],
            ),
        ],
    )

    debts = calculate_debts(purchase)

    assert sum(debts.values()) == other_share
