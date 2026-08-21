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
