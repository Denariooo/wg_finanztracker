import psycopg
from psycopg import Connection

from wg_finanztracker.domain.models import Item, Member, Receipt


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
        cursor.execute("SELECT id, name FROM members")
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
            "DELETE FROM members WHERE id = %s",
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
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT id FROM receipts")
        rows = cursor.fetchall()

    receipts = []
    for row in rows:
        receipt_id = row[0]
        receipt = get_receipt(receipt_id)

        if receipt is not None:
            receipts.append((receipt_id, receipt))

    return receipts


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
