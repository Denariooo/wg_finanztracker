from datetime import date

from wg_finanztracker.domain.models import Item, Member, Receipt
from wg_finanztracker.web.app import app


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

    client = app.test_client()
    response = client.get("/receipts/42")

    assert response.status_code == 200
    assert b"Keine Artikel vorhanden" in response.data


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
