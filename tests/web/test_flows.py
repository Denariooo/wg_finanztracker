from datetime import date
from io import BytesIO

from wg_finanztracker.domain.models import Item, Member, Payment, Receipt
from wg_finanztracker.ocr.ocr_models import OcrItem, OcrReceipt
from wg_finanztracker.web.app import app


def test_create_receipt_flow_persists_and_shows_detail(monkeypatch) -> None:
    members = {
        1: Member(id=1, name="Deniz"),
        2: Member(id=2, name="Max"),
    }
    receipts: dict[int, Receipt] = {}
    payments: list[Payment] = []
    next_receipt_id = 1

    def get_members() -> list[Member]:
        return list(members.values())

    def get_member(member_id: int) -> Member | None:
        return members.get(member_id)

    def add_receipt(receipt: Receipt) -> int:
        nonlocal next_receipt_id
        receipt_id = next_receipt_id
        receipts[receipt_id] = receipt
        next_receipt_id += 1
        return receipt_id

    def get_receipt(receipt_id: int) -> Receipt | None:
        return receipts.get(receipt_id)

    def get_receipts() -> list[tuple[int, Receipt]]:
        return list(receipts.items())

    monkeypatch.setattr("wg_finanztracker.web.app.get_members", get_members)
    monkeypatch.setattr("wg_finanztracker.web.app.get_member", get_member)
    monkeypatch.setattr("wg_finanztracker.web.app.add_receipt", add_receipt)
    monkeypatch.setattr("wg_finanztracker.web.app.get_receipt", get_receipt)
    monkeypatch.setattr("wg_finanztracker.web.app.get_receipts", get_receipts)
    monkeypatch.setattr("wg_finanztracker.web.app.get_payments", lambda: payments)

    client = app.test_client()

    create_response = client.post(
        "/receipts/create",
        data={
            "store": "REWE",
            "purchase_date": "2026-08-24",
            "price": "10.00",
            "paid_by": "1",
            "item_index": ["0", "1"],
            "item_name_0": "Pizza",
            "item_price_0": "8.00",
            "item_members_0": ["1", "2"],
            "item_name_1": "Cola",
            "item_price_1": "2.00",
            "item_members_1": ["2"],
        },
        follow_redirects=False,
    )

    assert create_response.status_code == 302
    assert create_response.headers["Location"] == "/receipts/1"

    detail_response = client.get("/receipts/1")

    assert detail_response.status_code == 200
    assert b"REWE" in detail_response.data
    assert b"Pizza" in detail_response.data
    assert b"Cola" in detail_response.data
    assert b"Max" in detail_response.data
    assert b"schuldet" in detail_response.data


def test_payment_flow_settles_open_amounts_everywhere(monkeypatch) -> None:
    members = {
        1: Member(id=1, name="Deniz"),
        2: Member(id=2, name="Max"),
    }
    receipts = {
        1: Receipt(
            store="REWE",
            purchase_date=date(2026, 8, 24),
            price_cents=1000,
            paid_by=members[1],
            items=[
                Item(
                    name="Einkauf",
                    price_cents=1000,
                    assigned_to=[members[2]],
                )
            ],
        )
    }
    payments: list[Payment] = []
    payment_ids = 0

    def get_members() -> list[Member]:
        return list(members.values())

    def get_member(member_id: int) -> Member | None:
        return members.get(member_id)

    def get_receipt(receipt_id: int) -> Receipt | None:
        return receipts.get(receipt_id)

    def get_receipts() -> list[tuple[int, Receipt]]:
        return list(receipts.items())

    def add_payment(payment: Payment) -> int:
        nonlocal payment_ids
        payment_ids += 1
        payments.append(payment)
        return payment_ids

    monkeypatch.setattr("wg_finanztracker.web.app.get_members", get_members)
    monkeypatch.setattr("wg_finanztracker.web.app.get_member", get_member)
    monkeypatch.setattr("wg_finanztracker.web.app.get_receipt", get_receipt)
    monkeypatch.setattr("wg_finanztracker.web.app.get_receipts", get_receipts)
    monkeypatch.setattr("wg_finanztracker.web.app.get_payments", lambda: payments)
    monkeypatch.setattr("wg_finanztracker.web.app.add_payment", add_payment)

    client = app.test_client()

    index_before = client.get("/index")
    assert index_before.status_code == 200
    assert b"schuldet" in index_before.data

    pay_response = client.post(
        "/payments/create",
        data={
            "debtor_id": "2",
            "creditor_id": "1",
        },
        follow_redirects=False,
    )

    assert pay_response.status_code == 302
    assert pay_response.headers["Location"] == "/index"

    index_after = client.get("/index")
    assert index_after.status_code == 200
    assert b"schuldet" not in index_after.data

    detail_after = client.get("/receipts/1")
    assert detail_after.status_code == 200
    assert b"schuldet" not in detail_after.data


def test_upload_receipt_flow_shows_prefilled_form(monkeypatch) -> None:
    class FakeOcrService:
        def recognize(self, image_path) -> OcrReceipt:
            return OcrReceipt(
                store="REWE",
                purchase_date=date(2026, 8, 24),
                price_cents=378,
                items=[
                    OcrItem(
                        name="Milch",
                        price_cents=189,
                    )
                ],
                raw_text="REWE\nMilch 1,89\nSUMME 3,78",
                confidence=0.92,
            )

    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_members",
        lambda: [Member(id=1, name="Deniz")],
    )
    monkeypatch.setattr(
        "wg_finanztracker.web.app.ocr_service",
        FakeOcrService(),
    )

    client = app.test_client()
    response = client.post(
        "/receipts/upload",
        data={
            "receipt": (BytesIO(b"fake-image-content"), "bon.png"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert b"erkannten Daten" in response.data
    assert b"REWE" in response.data
    assert b"Milch" in response.data


def test_create_receipt_validation_error_without_item_assignment(monkeypatch) -> None:
    monkeypatch.setattr(
        "wg_finanztracker.web.app.get_members",
        lambda: [Member(id=1, name="Deniz"), Member(id=2, name="Max")],
    )

    client = app.test_client()
    response = client.post(
        "/receipts/create",
        data={
            "store": "REWE",
            "purchase_date": "2026-08-24",
            "price": "4.00",
            "paid_by": "1",
            "item_index": ["0"],
            "item_name_0": "Brot",
            "item_price_0": "4.00",
        },
    )

    assert response.status_code == 200
    assert b"mindestens einem Mitglied zugeordnet" in response.data
