from wg_finanztracker.domain.models import Member
from wg_finanztracker.persistence.database import (
    add_member,
    delete_member,
    get_member,
    get_members,
    update_member,
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
