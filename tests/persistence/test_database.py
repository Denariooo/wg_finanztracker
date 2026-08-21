from collections.abc import Iterator
from datetime import date

import pytest

from wg_finanztracker.domain.models import Item, Member, Receipt
from wg_finanztracker.persistence.database import (
    add_item,
    add_member,
    add_receipt,
    assign_member_to_item,
    delete_item,
    delete_member,
    delete_receipt,
    get_item_members,
    get_items,
    get_member,
    get_members,
    get_receipt,
    get_receipts,
    remove_member_from_item,
    update_item,
    update_member,
    update_receipt,
)


@pytest.fixture
def member() -> Iterator[Member]:
    member = add_member("Testuser")

    yield member

    if get_member(member.id) is not None:
        delete_member(member.id)


@pytest.fixture
def receipt(member: Member) -> Iterator[tuple[int, Receipt]]:
    receipt = Receipt(
        store="Test Store",
        purchase_date=date(2026, 8, 20),
        price_cents=299,
        paid_by=member,
        items=[],
    )
    receipt_id = add_receipt(receipt)

    yield receipt_id, receipt

    if get_receipt(receipt_id) is not None:
        delete_receipt(receipt_id)


@pytest.fixture
def receipt_with_item(member: Member) -> Iterator[tuple[int, Receipt]]:
    item = Item(
        name="Milk",
        price_cents=199,
        assigned_to=[member],
    )

    receipt = Receipt(
        store="REWE",
        purchase_date=date(2026, 8, 20),
        price_cents=199,
        paid_by=member,
        items=[item],
    )

    receipt_id = add_receipt(receipt)

    yield receipt_id, receipt

    if get_receipt(receipt_id) is not None:
        delete_receipt(receipt_id)


def test_add_and_get_member(member: Member) -> None:
    loaded_member = get_member(member.id)

    assert loaded_member == member


def test_get_unknown_member_returns_none() -> None:
    assert get_member(99999999999999999999) is None


def test_update_member(member: Member) -> None:
    updated = Member(
        id=member.id,
        name="Neu",
    )

    update_member(updated)

    assert get_member(member.id) == updated


def test_delete_member(member: Member) -> None:
    delete_member(member.id)

    assert get_member(member.id) is None


def test_get_members_contains_created_member(member: Member) -> None:
    members = get_members()

    assert member in members


def test_add_and_get_item(
    receipt: tuple[int, Receipt],
) -> None:
    receipt_id, _ = receipt

    item = Item(
        name="Milk",
        price_cents=299,
        assigned_to=[],
    )
    add_item(receipt_id, item)
    items = get_items(receipt_id)
    assert item in items


def test_assign_member_to_item(
    member: Member,
    receipt: tuple[int, Receipt],
) -> None:
    receipt_id, _ = receipt

    item = Item(
        name="Milk",
        price_cents=299,
        assigned_to=[],
    )
    item_id = add_item(receipt_id, item)
    assign_member_to_item(item_id, member.id)
    assigned_members = get_item_members(item_id)
    assert member in assigned_members


def test_remove_member_from_item(
    member: Member,
    receipt: tuple[int, Receipt],
) -> None:
    receipt_id, _ = receipt

    item = Item(
        name="Milk",
        price_cents=299,
        assigned_to=[],
    )
    item_id = add_item(receipt_id, item)

    assign_member_to_item(item_id, member.id)
    remove_member_from_item(item_id, member.id)

    assigned_members = get_item_members(item_id)

    assert member not in assigned_members


def test_delete_item(
    receipt: tuple[int, Receipt],
) -> None:
    receipt_id, _ = receipt

    item = Item(
        name="Milk",
        price_cents=299,
        assigned_to=[],
    )
    item_id = add_item(receipt_id, item)

    delete_item(item_id)

    items = get_items(receipt_id)

    assert item not in items


def test_get_receipt(
    receipt: tuple[int, Receipt],
) -> None:
    receipt_id, expected_receipt = receipt

    loaded_receipt = get_receipt(receipt_id)

    assert loaded_receipt == expected_receipt


def test_update_receipt(
    member: Member,
    receipt: tuple[int, Receipt],
) -> None:
    receipt_id, _ = receipt

    updated_receipt = Receipt(
        store="Lidl",
        purchase_date=date(2026, 8, 21),
        price_cents=799,
        paid_by=member,
        items=[],
    )

    update_receipt(receipt_id, updated_receipt)
    loaded_receipt = get_receipt(receipt_id)

    assert loaded_receipt == updated_receipt


def test_delete_receipt(
    receipt: tuple[int, Receipt],
) -> None:
    receipt_id, _ = receipt

    delete_receipt(receipt_id)

    assert get_receipt(receipt_id) is None


def test_get_receipts_contains_created_receipt(
    receipt: tuple[int, Receipt],
) -> None:
    receipt_id, expected_receipt = receipt

    receipts = get_receipts()

    assert (receipt_id, expected_receipt) in receipts


def test_update_item(
    member: Member,
    receipt: tuple[int, Receipt],
) -> None:
    receipt_id, _ = receipt

    item = Item(
        name="Milk",
        price_cents=200,
        assigned_to=[],
    )

    item_id = add_item(receipt_id, item)

    updated_item = Item(
        name="Oat Milk",
        price_cents=250,
        assigned_to=[member],
    )

    update_item(item_id, updated_item)

    items = get_items(receipt_id)

    assert updated_item in items


def test_add_receipt_with_items(
    receipt_with_item: tuple[int, Receipt],
) -> None:
    receipt_id, expected_receipt = receipt_with_item

    loaded_receipt = get_receipt(receipt_id)

    assert loaded_receipt == expected_receipt
