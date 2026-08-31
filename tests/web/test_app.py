from datetime import date
from io import BytesIO

import pytest

from wg_finanztracker.domain.models import Item, Member, Payment, Receipt
from wg_finanztracker.web.app import app, parse_price_cents


def test_receipts_returns_receipts(monkeypatch) -> None:
    member = Member(id=1, name="Deniz")

    receipt = Receipt(
        store="REWE",
        purchase_date=date(2026, 8, 21),
        price_cents=1299,
        paid_by=member,
        items=[],
    )

    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_receipts",
        lambda: [(42, receipt)],
    )

    client = app.test_client()
    response = client.get("/receipts")

    assert response.status_code == 200
    assert b"REWE" in response.data
    assert b"Deniz" in response.data
    assert b"/receipts/42" in response.data


def test_receipt_detail_returns_receipt(monkeypatch) -> None:
    member = Member(id=1, name="Deniz")

    receipt = Receipt(
        store="REWE",
        purchase_date=date(2026, 8, 21),
        price_cents=1299,
        paid_by=member,
        items=[
            Item(
                name="Pizza",
                price_cents=799,
                assigned_to=[member],
            ),
        ],
    )

    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_receipt",
        lambda receipt_id: receipt,
    )
    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_receipts",
        lambda: [(42, receipt)],
    )
    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_payments",
        list,
    )

    client = app.test_client()
    response = client.get("/receipts/42")

    assert response.status_code == 200
    assert b"REWE" in response.data
    assert b"Pizza" in response.data
    assert b"Deniz" in response.data


def test_receipts_returns_empty_page(monkeypatch) -> None:
    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_receipts",
        list,
    )

    client = app.test_client()
    response = client.get("/receipts")

    assert response.status_code == 200
    assert b"REWE" not in response.data


def test_receipt_detail_unknown_receipt_returns_404(monkeypatch) -> None:
    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_receipt",
        lambda receipt_id: None,
    )

    client = app.test_client()
    response = client.get("/receipts/999")

    assert response.status_code == 404


def test_receipt_detail_returns_multiple_items(monkeypatch) -> None:
    member = Member(id=1, name="Deniz")

    receipt = Receipt(
        store="Lidl",
        purchase_date=date(2026, 8, 22),
        price_cents=1498,
        paid_by=member,
        items=[
            Item(
                name="Pizza",
                price_cents=799,
                assigned_to=[member],
            ),
            Item(
                name="Milch",
                price_cents=699,
                assigned_to=[member],
            ),
        ],
    )

    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_receipt",
        lambda receipt_id: receipt,
    )
    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_receipts",
        lambda: [(42, receipt)],
    )
    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_payments",
        list,
    )

    client = app.test_client()
    response = client.get("/receipts/42")

    assert response.status_code == 200
    assert b"Pizza" in response.data
    assert b"Milch" in response.data


def test_receipt_detail_returns_multiple_assigned_members(monkeypatch) -> None:
    member_1 = Member(id=1, name="Deniz")
    member_2 = Member(id=2, name="Max")

    receipt = Receipt(
        store="REWE",
        purchase_date=date(2026, 8, 22),
        price_cents=799,
        paid_by=member_1,
        items=[
            Item(
                name="Pizza",
                price_cents=799,
                assigned_to=[member_1, member_2],
            ),
        ],
    )

    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_receipt",
        lambda receipt_id: receipt,
    )
    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_receipts",
        lambda: [(42, receipt)],
    )
    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_payments",
        list,
    )

    client = app.test_client()
    response = client.get("/receipts/42")

    assert response.status_code == 200
    assert b"Deniz" in response.data
    assert b"Max" in response.data


def test_receipt_detail_without_items(monkeypatch) -> None:
    member = Member(id=1, name="Deniz")

    receipt = Receipt(
        store="REWE",
        purchase_date=date(2026, 8, 22),
        price_cents=0,
        paid_by=member,
        items=[],
    )

    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_receipt",
        lambda receipt_id: receipt,
    )
    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_receipts",
        lambda: [(42, receipt)],
    )
    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_payments",
        list,
    )

    client = app.test_client()
    response = client.get("/receipts/42")

    assert response.status_code == 200
    assert b"Keine Artikel vorhanden" in response.data


def test_receipt_detail_hides_settled_debts(monkeypatch) -> None:
    payer = Member(id=1, name="Deniz")
    debtor = Member(id=2, name="Max")

    receipt = Receipt(
        store="REWE",
        purchase_date=date(2026, 8, 22),
        price_cents=799,
        paid_by=payer,
        items=[
            Item(
                name="Pizza",
                price_cents=799,
                assigned_to=[debtor],
            ),
        ],
    )

    payment = Payment(
        from_member=debtor,
        to_member=payer,
        amount_cents=799,
        payment_date=date(2026, 8, 23),
    )

    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_receipt",
        lambda receipt_id: receipt,
    )
    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_receipts",
        lambda: [(42, receipt)],
    )
    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_payments",
        lambda: [payment],
    )

    client = app.test_client()
    response = client.get("/receipts/42")

    assert response.status_code == 200
    assert b"schuldet" not in response.data


def test_members_returns_members(monkeypatch) -> None:
    members = [
        Member(id=1, name="Deniz"),
        Member(id=2, name="Max"),
    ]

    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_members",
        lambda: members,
    )

    client = app.test_client()
    response = client.get("/members")

    assert response.status_code == 200
    assert b"Deniz" in response.data
    assert b"Max" in response.data


def test_members_returns_empty_page(monkeypatch) -> None:
    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_members",
        list,
    )

    client = app.test_client()
    response = client.get("/members")

    assert response.status_code == 200


def test_delete_member_route(monkeypatch) -> None:
    member = Member(id=42, name="Testuser")
    deleted_member_ids = []

    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_member",
        lambda member_id: member,
    )

    monkeypatch.setattr(
        "wg_finanztracker.web.app.delete_member",
        lambda member_id: deleted_member_ids.append(member_id),
    )

    client = app.test_client()
    response = client.post("/members/42/delete")

    assert response.status_code == 302
    assert response.headers["Location"] == "/members"
    assert deleted_member_ids == [42]


def test_create_member(monkeypatch) -> None:
    added_names = []

    monkeypatch.setattr(
        "wg_finanztracker.web.app.add_member",
        lambda name: added_names.append(name),
    )
    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_members",
        list,
    )

    client = app.test_client()
    response = client.post(
        "/members/create",
        data={"name": "Max"},
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/members"
    assert added_names == ["Max"]


def test_create_member_rejects_empty_name(monkeypatch) -> None:
    added_names = []

    monkeypatch.setattr(
        "wg_finanztracker.web.app.add_member",
        lambda name: added_names.append(name),
    )
    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_members",
        list,
    )

    client = app.test_client()
    response = client.post(
        "/members/create",
        data={"name": "           "},
    )

    assert response.status_code == 200
    assert b"Bitte einen Namen angeben." in response.data
    assert added_names == []


def test_create_member_strips_whitespace(monkeypatch) -> None:
    added_names = []

    monkeypatch.setattr(
        "wg_finanztracker.web.app.add_member",
        lambda name: added_names.append(name),
    )
    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_members",
        list,
    )

    client = app.test_client()
    response = client.post(
        "/members/create",
        data={"name": "  Max  "},
    )

    assert response.status_code == 302
    assert added_names == ["Max"]


def test_edit_member_page(monkeypatch) -> None:
    member = Member(id=42, name="Max")

    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_member",
        lambda member_id: member,
    )

    client = app.test_client()
    response = client.get("/members/42/edit")

    assert response.status_code == 200
    assert b"Max" in response.data


def test_edit_member(monkeypatch) -> None:
    member = Member(id=42, name="Max")
    updated_members = []

    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_member",
        lambda member_id: member,
    )
    monkeypatch.setattr(
        "wg_finanztracker.web.app.update_member",
        lambda updated_member: updated_members.append(updated_member),
    )

    client = app.test_client()
    response = client.post(
        "/members/42/edit",
        data={"name": "Maximilian"},
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/members"

    assert updated_members == [
        Member(id=42, name="Maximilian"),
    ]


def test_edit_member_rejects_empty_name(monkeypatch) -> None:
    member = Member(id=42, name="Max")
    updated_members = []

    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_member",
        lambda member_id: member,
    )
    monkeypatch.setattr(
        "wg_finanztracker.web.app.update_member",
        lambda updated_member: updated_members.append(updated_member),
    )

    client = app.test_client()
    response = client.post(
        "/members/42/edit",
        data={"name": "   "},
    )

    assert response.status_code == 200
    assert b"Bitte einen Namen angeben." in response.data
    assert updated_members == []


def test_edit_unknown_member_returns_404(monkeypatch) -> None:
    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_member",
        lambda member_id: None,
    )

    client = app.test_client()
    response = client.get("/members/9999999999/edit")

    assert response.status_code == 404


def test_create_member_rejects_get() -> None:
    client = app.test_client()

    response = client.get("/members/create")

    assert response.status_code == 405


def test_delete_receipt_route(monkeypatch) -> None:
    member = Member(id=1, name="Deniz")

    receipt = Receipt(
        store="REWE",
        purchase_date=date(2026, 8, 22),
        price_cents=1299,
        paid_by=member,
        items=[],
    )

    deleted_receipt_ids = []

    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_receipt",
        lambda receipt_id: receipt,
    )

    monkeypatch.setattr(
        "wg_finanztracker.web.app.delete_receipt",
        lambda receipt_id: deleted_receipt_ids.append(receipt_id),
    )

    client = app.test_client()
    response = client.post("/receipts/42/delete")

    assert response.status_code == 302
    assert response.headers["Location"] == "/receipts"
    assert deleted_receipt_ids == [42]


def test_delete_member_route_rejects_get() -> None:
    client = app.test_client()

    response = client.get("/members/42/delete")

    assert response.status_code == 405


def test_delete_receipt_route_rejects_get() -> None:
    client = app.test_client()

    response = client.get("/receipts/42/delete")

    assert response.status_code == 405


def test_edit_receipt_page(monkeypatch) -> None:
    member = Member(id=1, name="Deniz")

    receipt = Receipt(
        store="REWE",
        purchase_date=date(2026, 8, 21),
        price_cents=1299,
        paid_by=member,
        items=[
            Item(
                name="Pizza",
                price_cents=799,
                assigned_to=[member],
            ),
        ],
    )

    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_receipt",
        lambda receipt_id: receipt,
    )
    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_members",
        lambda: [member],
    )

    client = app.test_client()
    response = client.get("/receipts/42/edit")

    assert response.status_code == 200
    assert b"REWE" in response.data
    assert b"Pizza" in response.data
    assert b"Deniz" in response.data
    assert b"Kassenbon bearbeiten" in response.data


def test_edit_receipt(monkeypatch) -> None:
    member_1 = Member(id=1, name="Deniz")
    member_2 = Member(id=2, name="Max")

    receipt = Receipt(
        store="REWE",
        purchase_date=date(2026, 8, 21),
        price_cents=1299,
        paid_by=member_1,
        items=[
            Item(
                name="Pizza",
                price_cents=799,
                assigned_to=[member_1],
            ),
        ],
    )

    updated_receipts = []

    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_receipt",
        lambda receipt_id: receipt,
    )
    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_members",
        lambda: [member_1, member_2],
    )
    monkeypatch.setattr(
        "wg_finanztracker.web.app.update_receipt",
        lambda receipt_id, updated_receipt: updated_receipts.append(
            (receipt_id, updated_receipt)
        ),
    )

    client = app.test_client()
    response = client.post(
        "/receipts/42/edit",
        data={
            "store": "Lidl",
            "purchase_date": "2026-08-25",
            "price": "14,98",
            "paid_by": "2",
            "item_index": ["0"],
            "item_name_0": "Milch",
            "item_price_0": "1,99",
            "item_members_0": ["1", "2"],
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/receipts/42"

    assert len(updated_receipts) == 1

    receipt_id, updated_receipt = updated_receipts[0]

    assert receipt_id == 42
    assert updated_receipt.store == "Lidl"
    assert updated_receipt.purchase_date == date(2026, 8, 25)
    assert updated_receipt.price_cents == 1498
    assert updated_receipt.paid_by == member_2

    assert len(updated_receipt.items) == 1
    assert updated_receipt.items[0].name == "Milch"
    assert updated_receipt.items[0].price_cents == 199
    assert updated_receipt.items[0].assigned_to == [member_1, member_2]


def test_edit_receipt_rejects_empty_store(monkeypatch) -> None:
    member = Member(id=1, name="Deniz")

    receipt = Receipt(
        store="REWE",
        purchase_date=date(2026, 8, 21),
        price_cents=1299,
        paid_by=member,
        items=[],
    )

    updated_receipts = []

    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_receipt",
        lambda receipt_id: receipt,
    )
    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_members",
        lambda: [member],
    )
    monkeypatch.setattr(
        "wg_finanztracker.web.app.update_receipt",
        lambda receipt_id, updated_receipt: updated_receipts.append(updated_receipt),
    )

    client = app.test_client()
    response = client.post(
        "/receipts/42/edit",
        data={
            "store": "",
            "purchase_date": "2026-08-21",
            "price": "12,99",
            "paid_by": "1",
            "item_index": [],
        },
    )

    assert response.status_code == 200
    assert b"Bitte einen H" in response.data
    assert updated_receipts == []


def test_edit_receipt_rejects_invalid_date(monkeypatch) -> None:
    member = Member(id=1, name="Deniz")

    receipt = Receipt(
        store="REWE",
        purchase_date=date(2026, 8, 21),
        price_cents=1299,
        paid_by=member,
        items=[],
    )

    updated_receipts = []

    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_receipt",
        lambda receipt_id: receipt,
    )
    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_members",
        lambda: [member],
    )
    monkeypatch.setattr(
        "wg_finanztracker.web.app.update_receipt",
        lambda receipt_id, updated_receipt: updated_receipts.append(updated_receipt),
    )

    client = app.test_client()
    response = client.post(
        "/receipts/42/edit",
        data={
            "store": "REWE",
            "purchase_date": "kein-datum",
            "price": "12,99",
            "paid_by": "1",
            "item_index": [],
        },
    )

    assert response.status_code == 200
    assert b"Datum ist ung" in response.data
    assert updated_receipts == []


def test_edit_receipt_rejects_invalid_price(monkeypatch) -> None:
    member = Member(id=1, name="Deniz")

    receipt = Receipt(
        store="REWE",
        purchase_date=date(2026, 8, 21),
        price_cents=1299,
        paid_by=member,
        items=[],
    )

    updated_receipts = []

    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_receipt",
        lambda receipt_id: receipt,
    )
    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_members",
        lambda: [member],
    )
    monkeypatch.setattr(
        "wg_finanztracker.web.app.update_receipt",
        lambda receipt_id, updated_receipt: updated_receipts.append(updated_receipt),
    )

    client = app.test_client()
    response = client.post(
        "/receipts/42/edit",
        data={
            "store": "REWE",
            "purchase_date": "2026-08-21",
            "price": "abc",
            "paid_by": "1",
            "item_index": [],
        },
    )

    assert response.status_code == 200
    assert b"Ung" in response.data
    assert updated_receipts == []


def test_edit_receipt_rejects_unknown_member(monkeypatch) -> None:
    member = Member(id=1, name="Deniz")

    receipt = Receipt(
        store="REWE",
        purchase_date=date(2026, 8, 21),
        price_cents=1299,
        paid_by=member,
        items=[],
    )

    updated_receipts = []

    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_receipt",
        lambda receipt_id: receipt,
    )
    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_members",
        lambda: [member],
    )
    monkeypatch.setattr(
        "wg_finanztracker.web.app.update_receipt",
        lambda receipt_id, updated_receipt: updated_receipts.append(updated_receipt),
    )

    client = app.test_client()
    response = client.post(
        "/receipts/42/edit",
        data={
            "store": "REWE",
            "purchase_date": "2026-08-21",
            "price": "12,99",
            "paid_by": "999",
            "item_index": [],
        },
    )

    assert response.status_code == 200
    assert b"existiert nicht" in response.data
    assert updated_receipts == []


def test_edit_receipt_rejects_empty_item_name(monkeypatch) -> None:
    member = Member(id=1, name="Deniz")

    receipt = Receipt(
        store="REWE",
        purchase_date=date(2026, 8, 21),
        price_cents=1299,
        paid_by=member,
        items=[
            Item(
                name="Pizza",
                price_cents=799,
                assigned_to=[member],
            ),
        ],
    )

    updated_receipts = []

    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_receipt",
        lambda receipt_id: receipt,
    )
    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_members",
        lambda: [member],
    )
    monkeypatch.setattr(
        "wg_finanztracker.web.app.update_receipt",
        lambda receipt_id, updated_receipt: updated_receipts.append(updated_receipt),
    )

    client = app.test_client()
    response = client.post(
        "/receipts/42/edit",
        data={
            "store": "REWE",
            "purchase_date": "2026-08-21",
            "price": "12,99",
            "paid_by": "1",
            "item_index": ["0"],
            "item_name_0": "",
            "item_price_0": "7,99",
            "item_members_0": ["1"],
        },
    )

    assert response.status_code == 200
    assert b"Jeder Artikel ben" in response.data
    assert updated_receipts == []


def test_edit_receipt_rejects_item_without_member(monkeypatch) -> None:
    member = Member(id=1, name="Deniz")

    receipt = Receipt(
        store="REWE",
        purchase_date=date(2026, 8, 21),
        price_cents=1299,
        paid_by=member,
        items=[
            Item(
                name="Pizza",
                price_cents=799,
                assigned_to=[member],
            ),
        ],
    )

    updated_receipts = []

    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_receipt",
        lambda receipt_id: receipt,
    )
    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_members",
        lambda: [member],
    )
    monkeypatch.setattr(
        "wg_finanztracker.web.app.update_receipt",
        lambda receipt_id, updated_receipt: updated_receipts.append(updated_receipt),
    )

    client = app.test_client()
    response = client.post(
        "/receipts/42/edit",
        data={
            "store": "REWE",
            "purchase_date": "2026-08-21",
            "price": "12,99",
            "paid_by": "1",
            "item_index": ["0"],
            "item_name_0": "Pizza",
            "item_price_0": "7,99",
        },
    )

    assert response.status_code == 200
    assert b"mindestens einem Mitglied" in response.data
    assert updated_receipts == []


def test_edit_unknown_receipt_returns_404(monkeypatch) -> None:
    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_receipt",
        lambda receipt_id: None,
    )

    client = app.test_client()
    response = client.get("/receipts/9999999999/edit")

    assert response.status_code == 404


def test_delete_unknown_member_returns_404(monkeypatch) -> None:
    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_member",
        lambda member_id: None,
    )

    client = app.test_client()
    response = client.post("/members/9999999999/delete")

    assert response.status_code == 404


def test_delete_unknown_receipt_returns_404(monkeypatch) -> None:
    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_receipt",
        lambda receipt_id: None,
    )

    client = app.test_client()
    response = client.post("/receipts/9999999999/delete")

    assert response.status_code == 404


def test_parse_price_cents_accepts_comma() -> None:
    assert parse_price_cents("12,34") == 1234


def test_parse_price_cents_rejects_more_than_two_decimals() -> None:
    with pytest.raises(ValueError, match="h.chstens zwei Nachkommastellen"):
        parse_price_cents("12.345")


def test_parse_price_cents_rejects_negative_values() -> None:
    with pytest.raises(ValueError, match="nicht negativ"):
        parse_price_cents("-0.01")


def test_create_payment_rejects_non_numeric_member_ids() -> None:
    client = app.test_client()
    response = client.post(
        "/payments/create",
        data={
            "debtor_id": "x",
            "creditor_id": "1",
        },
    )

    assert response.status_code == 400


def test_create_payment_returns_404_for_unknown_member(monkeypatch) -> None:
    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_member",
        lambda member_id: None,
    )

    client = app.test_client()
    response = client.post(
        "/payments/create",
        data={
            "debtor_id": "1",
            "creditor_id": "2",
        },
    )

    assert response.status_code == 404


def test_create_payment_rejects_same_member(monkeypatch) -> None:
    member = Member(id=1, name="Deniz")

    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_member",
        lambda member_id: member,
    )

    client = app.test_client()
    response = client.post(
        "/payments/create",
        data={
            "debtor_id": "1",
            "creditor_id": "1",
        },
    )

    assert response.status_code == 400


def test_create_payment_rejects_when_pair_has_no_open_debt(monkeypatch) -> None:
    debtor = Member(id=1, name="Deniz")
    creditor = Member(id=2, name="Max")
    members = {
        1: debtor,
        2: creditor,
    }

    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_member",
        lambda member_id: members.get(member_id),
    )
    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_receipts",
        list,
    )
    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_payments",
        list,
    )

    client = app.test_client()
    response = client.post(
        "/payments/create",
        data={
            "debtor_id": "1",
            "creditor_id": "2",
        },
    )

    assert response.status_code == 400


def test_upload_receipt_requires_file(monkeypatch) -> None:
    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_members",
        lambda: [Member(id=1, name="Deniz")],
    )

    client = app.test_client()
    response = client.post(
        "/receipts/upload",
        data={},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert b"Kassenbon ausw" in response.data


def test_upload_receipt_rejects_unsupported_extension(monkeypatch) -> None:
    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_members",
        lambda: [Member(id=1, name="Deniz")],
    )

    client = app.test_client()
    response = client.post(
        "/receipts/upload",
        data={
            "receipt": (BytesIO(b"pdf"), "bon.pdf"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert b"Nur JPG- und PNG-Dateien" in response.data


def test_upload_receipt_shows_ocr_error(monkeypatch) -> None:
    class FailingOcrService:
        def recognize(self, image_path):
            raise ValueError("OCR fehlgeschlagen")

    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_members",
        lambda: [Member(id=1, name="Deniz")],
    )
    monkeypatch.setattr(
        "wg_finanztracker.web.app.ocr_service",
        FailingOcrService(),
    )

    client = app.test_client()
    response = client.post(
        "/receipts/upload",
        data={
            "receipt": (BytesIO(b"image"), "bon.png"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert b"OCR fehlgeschlagen" in response.data


def test_statistics_page_renders_aggregations(monkeypatch) -> None:
    deniz = Member(id=1, name="Deniz")
    max_member = Member(id=2, name="Max")

    receipt = Receipt(
        store="REWE",
        purchase_date=date(2026, 8, 24),
        price_cents=400,
        paid_by=deniz,
        items=[
            Item(
                name="Milch",
                price_cents=200,
                assigned_to=[deniz],
            ),
            Item(
                name="Spülmittel",
                price_cents=200,
                assigned_to=[max_member],
            ),
        ],
    )

    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_receipts",
        lambda: [(1, receipt)],
    )
    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_members",
        lambda: [deniz, max_member],
    )

    client = app.test_client()
    response = client.get("/statistics")

    assert response.status_code == 200
    assert b"Diagramm pro Kategorie" in response.data
    assert b"Ausgaben pro Person" in response.data
    assert b"Monats" in response.data
    assert b"Jahres" in response.data
    assert b"Lebensmittel" in response.data
    assert b"Haushalt" in response.data
