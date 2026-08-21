from datetime import date

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


def test_add_and_get_member() -> None:
    member = add_member("Testuser")
    loaded_member = get_member(member.id)
    assert loaded_member == member
    delete_member(member.id)


def test_get_unknown_member_returns_none() -> None:
    assert get_member(99999999999999999999) is None


def test_update_member() -> None:
    member = add_member("Alt")
    updated = Member(id=member.id, name="Neu")
    update_member(updated)
    assert get_member(member.id) == updated
    delete_member(member.id)


def test_delete_member() -> None:
    member = add_member("Delete Me")
    delete_member(member.id)
    assert get_member(member.id) is None


def test_get_members_contains_created_member() -> None:
    member = add_member("Testuser")
    members = get_members()
    assert member in members
    delete_member(member.id)


def test_add_and_get_item() -> None:
    member = add_member("Test Payer")
    receipt = Receipt(
        store="Test Store",
        purchase_date=date(2026, 8, 20),
        price_cents=299,
        paid_by=member,
        items=[],
    )
    receipt_id = add_receipt(receipt)
    item = Item(
        name="Milk",
        price_cents=299,
        assigned_to=[],
    )
    add_item(receipt_id, item)
    items = get_items(receipt_id)
    assert item in items
    delete_receipt(receipt_id)
    delete_member(member.id)


def test_assign_member_to_item() -> None:
    member = add_member("Testuser")
    receipt = Receipt(
        store="Test Store",
        purchase_date=date(2026, 8, 20),
        price_cents=299,
        paid_by=member,
        items=[],
    )
    receipt_id = add_receipt(receipt)
    item = Item(
        name="Milk",
        price_cents=299,
        assigned_to=[],
    )
    item_id = add_item(receipt_id, item)
    assign_member_to_item(item_id, member.id)
    assigned_members = get_item_members(item_id)
    assert member in assigned_members
    delete_receipt(receipt_id)
    delete_member(member.id)


def test_remove_member_from_item() -> None:
    member = add_member("Testuser")

    receipt = Receipt(
        store="Test Store",
        purchase_date=date(2026, 8, 20),
        price_cents=299,
        paid_by=member,
        items=[],
    )
    receipt_id = add_receipt(receipt)

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

    delete_receipt(receipt_id)
    delete_member(member.id)


def test_delete_item() -> None:
    member = add_member("Test Payer")

    receipt = Receipt(
        store="Test Store",
        purchase_date=date(2026, 8, 20),
        price_cents=299,
        paid_by=member,
        items=[],
    )
    receipt_id = add_receipt(receipt)

    item = Item(
        name="Milk",
        price_cents=299,
        assigned_to=[],
    )
    item_id = add_item(receipt_id, item)

    delete_item(item_id)

    items = get_items(receipt_id)

    assert item not in items

    delete_receipt(receipt_id)
    delete_member(member.id)


def test_get_receipt() -> None:
    member = add_member("Test Payer")

    receipt = Receipt(
        store="REWE",
        purchase_date=date(2026, 8, 20),
        price_cents=599,
        paid_by=member,
        items=[],
    )
    receipt_id = add_receipt(receipt)

    loaded_receipt = get_receipt(receipt_id)

    assert loaded_receipt == receipt

    delete_receipt(receipt_id)
    delete_member(member.id)


def test_update_receipt() -> None:
    member = add_member("Test Payer")

    receipt = Receipt(
        store="REWE",
        purchase_date=date(2026, 8, 20),
        price_cents=599,
        paid_by=member,
        items=[],
    )
    receipt_id = add_receipt(receipt)

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

    delete_receipt(receipt_id)
    delete_member(member.id)


def test_delete_receipt() -> None:
    member = add_member("Test Payer")

    receipt = Receipt(
        store="REWE",
        purchase_date=date(2026, 8, 20),
        price_cents=599,
        paid_by=member,
        items=[],
    )
    receipt_id = add_receipt(receipt)

    delete_receipt(receipt_id)

    assert get_receipt(receipt_id) is None

    delete_member(member.id)


def test_get_receipts_contains_created_receipt() -> None:
    member = add_member("Test Payer")

    receipt = Receipt(
        store="REWE",
        purchase_date=date(2026, 8, 20),
        price_cents=599,
        paid_by=member,
        items=[],
    )
    receipt_id = add_receipt(receipt)

    receipts = get_receipts()

    assert receipt in receipts

    delete_receipt(receipt_id)
    delete_member(member.id)


def test_update_item() -> None:
    member = add_member("Testuser")

    receipt = Receipt(
        store="REWE",
        purchase_date=date(2026, 8, 20),
        price_cents=500,
        paid_by=member,
        items=[],
    )

    receipt_id = add_receipt(receipt)

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

    delete_receipt(receipt_id)
    delete_member(member.id)


def test_add_receipt_with_items() -> None:
    member = add_member("Testuser")

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

    loaded = get_receipt(receipt_id)

    assert loaded == receipt

    delete_receipt(receipt_id)
    delete_member(member.id)
