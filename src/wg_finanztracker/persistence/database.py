from collections import defaultdict

import psycopg
from psycopg import Connection

from wg_finanztracker.domain.models import Item, Member, Payment, Receipt


def get_connection() -> Connection:
    return psycopg.connect(
        host="localhost",
        port=5432,
        dbname="wg_finanztracker",
        user="wg_user",
        password="wg_password",
    )


def get_members() -> list[Member]:
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT id, name FROM members WHERE active = true")
        rows = cursor.fetchall()

    return [Member(id=row[0], name=row[1]) for row in rows]


def get_member(member_id: int) -> Member | None:
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            "SELECT id, name FROM members WHERE id = %s",
            (member_id,),
        )
        row = cursor.fetchone()

    if row is None:
        return None

    return Member(id=row[0], name=row[1])


def add_member(name: str) -> Member:
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO members (name) VALUES (%s) RETURNING id",
            (name,),
        )
        row = cursor.fetchone()

    if row is None:
        raise RuntimeError("Failed to insert member: database did not return an id")

    return Member(id=row[0], name=name)


def update_member(member: Member) -> None:
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            "UPDATE members SET name = %s WHERE id = %s",
            (member.name, member.id),
        )

        if cursor.rowcount == 0:
            raise ValueError("Member not found")


def delete_member(member_id: int) -> None:
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            "UPDATE members SET active = false WHERE id = %s",
            (member_id,),
        )

        if cursor.rowcount == 0:
            raise ValueError("Member not found")


def get_item_members(item_id: int) -> list[Member]:
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT members.id, members.name
            FROM members, item_assignments
            WHERE members.id = item_assignments.member_id AND item_assignments.item_id = %s
            """,
            (item_id,),
        )
        rows = cursor.fetchall()

    return [Member(id=row[0], name=row[1]) for row in rows]


def get_items(receipt_id: int) -> list[Item]:
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, name, price_cents
            FROM items
            WHERE receipt_id = %s
            """,
            (receipt_id,),
        )
        rows = cursor.fetchall()

    items = []
    for row in rows:
        item_id = row[0]
        items.append(
            Item(
                name=row[1],
                price_cents=row[2],
                assigned_to=get_item_members(item_id),
            )
        )
    return items


def add_item(receipt_id: int, item: Item) -> int:
    with get_connection() as conn, conn.cursor() as cursor:
        item_id = _add_item(cursor, receipt_id, item)

        for member in item.assigned_to:
            _assign_member_to_item(cursor, item_id, member.id)

    return item_id


def _add_item(
    cursor,
    receipt_id: int,
    item: Item,
) -> int:
    cursor.execute(
        """
        INSERT INTO items (receipt_id, name, price_cents)
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        (receipt_id, item.name, item.price_cents),
    )

    row = cursor.fetchone()

    if row is None:
        raise RuntimeError("Failed to insert item")

    return row[0]


def update_item(item_id: int, item: Item) -> None:
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            UPDATE items
            SET name = %s, price_cents = %s
            WHERE id = %s
            """,
            (item.name, item.price_cents, item_id),
        )

        if cursor.rowcount == 0:
            raise ValueError("Item not found")

        cursor.execute(
            "DELETE FROM item_assignments WHERE item_id = %s",
            (item_id,),
        )

        for member in item.assigned_to:
            _assign_member_to_item(cursor, item_id, member.id)


def delete_item(item_id: int) -> None:
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            "DELETE FROM items WHERE id = %s",
            (item_id,),
        )

        if cursor.rowcount == 0:
            raise ValueError("Item not found")


def assign_member_to_item(item_id: int, member_id: int) -> None:
    with get_connection() as conn, conn.cursor() as cursor:
        _assign_member_to_item(cursor, item_id, member_id)


def _assign_member_to_item(
    cursor,
    item_id: int,
    member_id: int,
) -> None:
    cursor.execute(
        """
        INSERT INTO item_assignments (item_id, member_id)
        VALUES (%s, %s)
        """,
        (item_id, member_id),
    )


def remove_member_from_item(item_id: int, member_id: int) -> None:
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            DELETE FROM item_assignments
            WHERE item_id = %s AND member_id = %s
            """,
            (item_id, member_id),
        )
        if cursor.rowcount == 0:
            raise ValueError("Item assignment not found")


def get_receipt(receipt_id: int) -> Receipt | None:
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT store, purchase_date, price_cents, paid_by
            FROM receipts
            WHERE id = %s
            """,
            (receipt_id,),
        )
        row = cursor.fetchone()

    if row is None:
        return None

    paid_by = get_member(row[3])
    if paid_by is None:
        raise RuntimeError("Receipt references an unknown member")

    return Receipt(
        store=row[0],
        purchase_date=row[1],
        price_cents=row[2],
        paid_by=paid_by,
        items=get_items(receipt_id),
    )


def get_receipts() -> list[tuple[int, Receipt]]:
    query = """
            SELECT
                r.id AS receipt_id, r.store, r.purchase_date, r.price_cents AS receipt_price,
                rm.id AS payer_id, rm.name AS payer_name,
                i.id AS item_id, i.name AS item_name, i.price_cents AS item_price,
                am.id AS assignee_id, am.name AS assignee_name
            FROM receipts r
                     JOIN members rm ON r.paid_by = rm.id
                     LEFT JOIN items i ON r.id = i.receipt_id
                     LEFT JOIN item_assignments ia ON i.id = ia.item_id
                     LEFT JOIN members am ON ia.member_id = am.id
            ORDER BY r.purchase_date DESC, r.id, i.id; \
            """

    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    receipts_dict = {}
    items_dict = {}

    for row in rows:
        (
            receipt_id,
            store,
            purchase_date,
            receipt_price,
            payer_id,
            payer_name,
            item_id,
            item_name,
            item_price,
            assignee_id,
            assignee_name,
        ) = row

        if receipt_id not in receipts_dict:
            payer = Member(id=payer_id, name=payer_name)
            receipts_dict[receipt_id] = {
                "store": store,
                "purchase_date": purchase_date,
                "price_cents": receipt_price,
                "paid_by": payer,
                "items": [],
            }

        if item_id is not None:
            if item_id not in items_dict:
                items_dict[item_id] = {
                    "receipt_id": receipt_id,
                    "name": item_name,
                    "price_cents": item_price,
                    "assigned_to": [],
                }

            if assignee_id is not None:
                items_dict[item_id]["assigned_to"].append(
                    Member(id=assignee_id, name=assignee_name)
                )

    items_by_receipt = defaultdict(list)
    for item_id, item_data in items_dict.items():
        item_obj = Item(
            name=item_data["name"],
            price_cents=item_data["price_cents"],
            assigned_to=item_data["assigned_to"],
        )
        items_by_receipt[item_data["receipt_id"]].append(item_obj)

    final_receipts = []
    for receipt_id, r_data in receipts_dict.items():
        receipt = Receipt(
            store=r_data["store"],
            purchase_date=r_data["purchase_date"],
            price_cents=r_data["price_cents"],
            paid_by=r_data["paid_by"],
            items=items_by_receipt.get(receipt_id, []),
        )
        final_receipts.append((receipt_id, receipt))

    return final_receipts


def add_receipt(receipt: Receipt) -> int:
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO receipts (
                store,
                purchase_date,
                price_cents,
                paid_by
            )
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (
                receipt.store,
                receipt.purchase_date,
                receipt.price_cents,
                receipt.paid_by.id,
            ),
        )
        row = cursor.fetchone()

        if row is None:
            raise RuntimeError(
                "Failed to insert receipt: database did not return an id"
            )

        receipt_id = row[0]

        for item in receipt.items:
            item_id = _add_item(cursor, receipt_id, item)

            for member in item.assigned_to:
                _assign_member_to_item(
                    cursor,
                    item_id,
                    member.id,
                )

    return receipt_id


def update_receipt(receipt_id: int, receipt: Receipt) -> None:
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            UPDATE receipts
            SET store = %s,
                purchase_date = %s,
                price_cents = %s,
                paid_by = %s
            WHERE id = %s
            """,
            (
                receipt.store,
                receipt.purchase_date,
                receipt.price_cents,
                receipt.paid_by.id,
                receipt_id,
            ),
        )

        if cursor.rowcount == 0:
            raise ValueError("Receipt not found")


def delete_receipt(receipt_id: int) -> None:
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            "DELETE FROM receipts WHERE id = %s",
            (receipt_id,),
        )

        if cursor.rowcount == 0:
            raise ValueError("Receipt not found")


def get_payments() -> list[Payment]:
    query = """
            SELECT
                p.amount_cents,
                p.payment_date,
                fm.id AS from_id,
                fm.name AS from_name,
                tm.id AS to_id,
                tm.name AS to_name
            FROM payments p
                     JOIN members fm ON p.from_member = fm.id
                     JOIN members tm ON p.to_member = tm.id
            ORDER BY p.payment_date \
            """

    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    payments: list[Payment] = []

    for row in rows:
        amount_cents, payment_date, from_id, from_name, to_id, to_name = row
        from_member = Member(id=from_id, name=from_name)
        to_member = Member(id=to_id, name=to_name)

        payments.append(
            Payment(
                from_member=from_member,
                to_member=to_member,
                amount_cents=amount_cents,
                payment_date=payment_date,
            )
        )

    return payments


def add_payment(payment: Payment) -> int:
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO payments (
                from_member,
                to_member,
                amount_cents,
                payment_date
            )
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (
                payment.from_member.id,
                payment.to_member.id,
                payment.amount_cents,
                payment.payment_date,
            ),
        )

        row = cursor.fetchone()

        if row is None:
            raise RuntimeError(
                "Failed to insert payment: database did not return an id"
            )

    return row[0]
