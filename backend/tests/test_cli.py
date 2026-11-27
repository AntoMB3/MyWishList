"""Pruebas de los comandos de administración `reset-password` y `migrate-db`."""

from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.cli import (
    generate_temporary_password,
    migrate_database_data,
    migrate_db_main,
    reset_user_password,
)
from backend.database import Base, create_db_engine
from backend.models import User, Wishlist, WishlistItem
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


class TestMigrateDatabase:
    def test_copies_users_wishlists_and_items_preserving_ids(
        self,
        tmp_path: Path,
    ) -> None:
        source_url = f"sqlite:///{tmp_path / 'source.db'}"
        target_url = f"sqlite:///{tmp_path / 'target.db'}"
        source_engine = create_db_engine(source_url)
        target_engine = create_db_engine(target_url)

        try:
            Base.metadata.create_all(source_engine)
            with Session(source_engine) as src:
                user = User(id=7, username="alex", hashed_password="h1", token_version=2)
                wishlist = Wishlist(
                    id=15,
                    title="Cumple",
                    description="Ideas",
                    share_id="a" * 32,
                    user_id=7,
                )
                item = WishlistItem(
                    id=42,
                    title="Teclado",
                    price=Decimal("99.50"),
                    description="Mecánico",
                    url="https://example.com/kb",
                    image_url="/media/11111111-1111-1111-1111-111111111111.webp",
                    wishlist_id=15,
                )
                src.add_all([user, wishlist, item])
                src.commit()

            exit_code = migrate_db_main(["--from", source_url, "--to", target_url])
            assert exit_code == 0

            with Session(target_engine) as dst:
                migrated_user = dst.get(User, 7)
                assert migrated_user is not None
                assert migrated_user.username == "alex"
                assert migrated_user.token_version == 2

                migrated_wishlist = dst.get(Wishlist, 15)
                assert migrated_wishlist is not None
                assert migrated_wishlist.share_id == "a" * 32
                assert migrated_wishlist.user_id == 7

                migrated_item = dst.get(WishlistItem, 42)
                assert migrated_item is not None
                assert migrated_item.title == "Teclado"
                assert migrated_item.price == Decimal("99.50")
                assert migrated_item.wishlist_id == 15
        finally:
            source_engine.dispose()
            target_engine.dispose()

    def test_rejects_non_empty_target_database(self, tmp_path: Path) -> None:
        source_engine = create_db_engine(f"sqlite:///{tmp_path / 'source.db'}")
        target_engine = create_db_engine(f"sqlite:///{tmp_path / 'target.db'}")
        try:
            Base.metadata.create_all(source_engine)
            Base.metadata.create_all(target_engine)
            with Session(target_engine) as dst:
                dst.add(User(username="existing", hashed_password="h"))
                dst.commit()

            with pytest.raises(ValueError, match="no está vacía"):
                migrate_database_data(source_engine, target_engine)
        finally:
            source_engine.dispose()
            target_engine.dispose()

    def test_rejects_same_source_and_target_url(self, tmp_path: Path) -> None:
        same_url = f"sqlite:///{tmp_path / 'same.db'}"
        assert migrate_db_main(["--from", same_url, "--to", same_url]) == 2
