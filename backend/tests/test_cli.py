"""Pruebas del comando de administración `reset-password`."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.cli import generate_temporary_password, reset_user_password
from backend.models import User
from backend.security import hash_password, verify_password

ORIGINAL_PASSWORD = "claveOriginal1"


@pytest.fixture()
def user(session: Session) -> User:
    db_user = User(username="alex", hashed_password=hash_password(ORIGINAL_PASSWORD))
    session.add(db_user)
    session.commit()
    return db_user


class TestGenerateTemporaryPassword:
    def test_default_length(self) -> None:
        assert len(generate_temporary_password()) == 14

    def test_custom_length(self) -> None:
        assert len(generate_temporary_password(32)) == 32

    def test_is_alphanumeric(self) -> None:
        password = generate_temporary_password(64)
        assert password.isalnum()

    def test_is_random(self) -> None:
        assert generate_temporary_password() != generate_temporary_password()


class TestResetUserPassword:
    def test_updates_hash_and_normalizes_username(
        self,
        session: Session,
        user: User,
    ) -> None:
        updated = reset_user_password(session, "  ALEX ", "temporal123")

        assert updated is not None
        assert updated.id == user.id
        assert updated.token_version == 1
        stored = session.scalar(select(User).where(User.id == user.id))
        assert verify_password("temporal123", stored.hashed_password)
        assert not verify_password(ORIGINAL_PASSWORD, stored.hashed_password)

    def test_unknown_user_returns_none(self, session: Session) -> None:
        assert reset_user_password(session, "nadie", "temporal123") is None

    def test_rejects_password_too_short(self, session: Session, user: User) -> None:
        with pytest.raises(ValueError):
            reset_user_password(session, "alex", "corta")

    def test_rejects_password_too_long(self, session: Session, user: User) -> None:
        with pytest.raises(ValueError):
            reset_user_password(session, "alex", "x" * 129)
