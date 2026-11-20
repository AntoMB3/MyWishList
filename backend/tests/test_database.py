import asyncio
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import delete, func, inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend import main
from backend.database import create_db_engine
from backend.models import User, Wishlist, WishlistItem

EXPECTED_TABLES = {"users", "wishlists", "wishlist_items"}
EXPECTED_COLUMNS = {
    "users": {"id", "username", "hashed_password", "created_at"},
    "wishlists": {
        "id",
        "title",
        "description",
        "share_id",
        "user_id",
        "created_at",
    },
    "wishlist_items": {
        "id",
        "title",
        "price",
        "description",
        "url",
        "image_url",
        "wishlist_id",
        "created_at",
    },
}


def _new_wishlist(**overrides: object) -> Wishlist:
    values: dict[str, object] = {"title": "Cumpleaños", "description": None}
    values.update(overrides)
    return Wishlist(**values)


def _new_item(**overrides: object) -> WishlistItem:
    values: dict[str, object] = {
        "title": "Teclado",
        "price": Decimal("99.90"),
        "description": None,
        "url": "https://example.com/teclado",
        "image_url": "https://example.com/teclado.png",
    }
    values.update(overrides)
    return WishlistItem(**values)


def test_create_all_creates_expected_tables(engine: Engine) -> None:
    assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES


def test_tables_have_expected_columns(engine: Engine) -> None:
    inspector = inspect(engine)
    for table, expected_columns in EXPECTED_COLUMNS.items():
        found = {column["name"] for column in inspector.get_columns(table)}
        assert found == expected_columns, f"columnas inesperadas en {table}"


def test_lifespan_creates_database_and_tables(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "lifespan.db"
    lifespan_engine = create_db_engine(f"sqlite:///{database_path}")
    monkeypatch.setattr(main, "engine", lifespan_engine)

    async def run_lifespan() -> None:
        async with main.lifespan(main.app):
            pass

    asyncio.run(run_lifespan())

    assert database_path.exists()
    assert set(inspect(lifespan_engine).get_table_names()) == EXPECTED_TABLES
    lifespan_engine.dispose()


def test_wishlist_gets_unique_share_id(session: Session) -> None:
    first = _new_wishlist()
    second = _new_wishlist()
    user = User(username="alex", hashed_password="hash")
    user.wishlists.extend([first, second])
    session.add(user)
    session.commit()

    assert len(first.share_id) == 32
    assert first.share_id != second.share_id


def test_share_id_must_be_unique(session: Session) -> None:
    user = User(username="alex", hashed_password="hash")
    user.wishlists.extend(
        [
            _new_wishlist(share_id="a" * 32),
            _new_wishlist(share_id="a" * 32),
        ]
    )
    session.add(user)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_deleting_user_cascades_to_wishlists_and_items(session: Session) -> None:
    user = User(username="alex", hashed_password="hash")
    wishlist = _new_wishlist()
    wishlist.items.append(_new_item())
    user.wishlists.append(wishlist)
    session.add(user)
    session.commit()

    # Borrado directo en SQL para comprobar las FKs de la BD,
    # no solo la cascada del ORM.
    session.execute(delete(User).where(User.id == user.id))
    session.commit()

    assert session.scalar(select(func.count()).select_from(Wishlist)) == 0
    assert session.scalar(select(func.count()).select_from(WishlistItem)) == 0


def test_deleting_wishlist_cascades_to_items(session: Session) -> None:
    user = User(username="alex", hashed_password="hash")
    wishlist = _new_wishlist()
    wishlist.items.append(_new_item())
    user.wishlists.append(wishlist)
    session.add(user)
    session.commit()

    session.execute(delete(Wishlist).where(Wishlist.id == wishlist.id))
    session.commit()

    assert session.scalar(select(func.count()).select_from(WishlistItem)) == 0
    assert session.scalar(select(func.count()).select_from(Wishlist)) == 0


def test_price_cannot_be_negative(session: Session) -> None:
    user = User(username="alex", hashed_password="hash")
    wishlist = _new_wishlist()
    user.wishlists.append(wishlist)
    session.add(user)
    session.commit()

    session.add(_new_item(price=Decimal("-0.01"), wishlist_id=wishlist.id))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_username_must_be_unique(session: Session) -> None:
    session.add(User(username="alex", hashed_password="hash"))
    session.commit()

    session.add(User(username="alex", hashed_password="other-hash"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
