import psycopg
from psycopg import Connection

from wg_finanztracker.domain.models import Member


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


def delete_member(member_id: int) -> None:
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            "DELETE FROM members WHERE id = %s",
            (member_id,),
        )
