from datetime import datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.models import User, Wishlist, WishlistItem
from backend.config import settings
from backend.schemas import ItemCreate, ItemUpdate
from backend.services import item_service


def _add_user(session: Session, username: str = "alex") -> User:
    user = User(username=username, hashed_password="hash")
    session.add(user)
    session.commit()
    return user


def _add_wishlist(session: Session, user: User, title: str = "Cumpleaños") -> Wishlist:
    wishlist = Wishlist(title=title, description=None, user_id=user.id)
    session.add(wishlist)
    session.commit()
    return wishlist


def _item_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "title": "Teclado",
        "price": Decimal("99.90"),
        "description": None,
        "url": "https://example.com/teclado",
        "image_url": "https://example.com/teclado.png",
    }
    payload.update(overrides)
    return payload


class TestCreateItem:
    def test_creates_item_in_own_wishlist(self, session: Session) -> None:
        alex = _add_user(session)
        wishlist = _add_wishlist(session, alex)

        item = item_service.create_item(
            session,
            wishlist.id,
            ItemCreate(**_item_payload(title="  Teclado  ")),
            alex,
        )

        assert item.id is not None
        assert item.wishlist_id == wishlist.id
        assert item.title == "Teclado"
        assert item.price == Decimal("99.90")
        assert item.url == "https://example.com/teclado"
        assert isinstance(item.url, str)
        assert isinstance(item.image_url, str)
        assert item.created_at is not None
        assert session.get(WishlistItem, item.id) is not None

    def test_raises_404_when_wishlist_does_not_exist(self, session: Session) -> None:
        alex = _add_user(session)

        with pytest.raises(HTTPException) as exc_info:
            item_service.create_item(
                session,
                999,
                ItemCreate(**_item_payload()),
                alex,
            )

        assert exc_info.value.status_code == 404

    def test_raises_403_when_wishlist_belongs_to_another_user(
        self,
        session: Session,
    ) -> None:
        alex = _add_user(session)
        bob = _add_user(session, "bob")
        wishlist = _add_wishlist(session, bob)

        with pytest.raises(HTTPException) as exc_info:
            item_service.create_item(
                session,
                wishlist.id,
                ItemCreate(**_item_payload()),
                alex,
            )

        assert exc_info.value.status_code == 403


class TestUpdateItem:
    def test_updates_item_in_own_wishlist(self, session: Session) -> None:
        alex = _add_user(session)
        wishlist = _add_wishlist(session, alex)
        item = item_service.create_item(
            session,
            wishlist.id,
            ItemCreate(**_item_payload()),
            alex,
        )

        updated = item_service.update_item(
            session,
            wishlist.id,
            item.id,
            ItemUpdate(
                **_item_payload(
                    title="  Teclado nuevo  ",
                    price=Decimal("120.00"),
                    url="https://example.com/nuevo",
                )
            ),
            alex,
        )

        assert updated.title == "Teclado nuevo"
        assert updated.price == Decimal("120.00")
        assert updated.url == "https://example.com/nuevo"
        session.refresh(item)
        assert item.title == "Teclado nuevo"

    def test_raises_404_when_item_belongs_to_another_wishlist(
        self,
        session: Session,
    ) -> None:
        alex = _add_user(session)
        first = _add_wishlist(session, alex, "Primera")
        second = _add_wishlist(session, alex, "Segunda")
        item = item_service.create_item(
            session,
            second.id,
            ItemCreate(**_item_payload()),
            alex,
        )

        with pytest.raises(HTTPException) as exc_info:
            item_service.update_item(
                session,
                first.id,
                item.id,
                ItemUpdate(**_item_payload()),
                alex,
            )

        assert exc_info.value.status_code == 404

    def test_raises_404_when_item_does_not_exist(self, session: Session) -> None:
        alex = _add_user(session)
        wishlist = _add_wishlist(session, alex)

        with pytest.raises(HTTPException) as exc_info:
            item_service.update_item(
                session,
                wishlist.id,
                999,
                ItemUpdate(**_item_payload()),
                alex,
            )

        assert exc_info.value.status_code == 404

    def test_raises_404_when_wishlist_does_not_exist(self, session: Session) -> None:
        alex = _add_user(session)

        with pytest.raises(HTTPException) as exc_info:
            item_service.update_item(
                session,
                999,
                999,
                ItemUpdate(**_item_payload()),
                alex,
            )

        assert exc_info.value.status_code == 404

    def test_raises_403_when_wishlist_belongs_to_another_user(
        self,
        session: Session,
    ) -> None:
        alex = _add_user(session)
        bob = _add_user(session, "bob")
        wishlist = _add_wishlist(session, bob)
        item = item_service.create_item(
            session,
            wishlist.id,
            ItemCreate(**_item_payload()),
            bob,
        )

        with pytest.raises(HTTPException) as exc_info:
            item_service.update_item(
                session,
                wishlist.id,
                item.id,
                ItemUpdate(**_item_payload()),
                alex,
            )

        assert exc_info.value.status_code == 403


class TestDeleteItem:
    def test_deletes_item_from_own_wishlist(self, session: Session) -> None:
        alex = _add_user(session)
        wishlist = _add_wishlist(session, alex)
        item = item_service.create_item(
            session,
            wishlist.id,
            ItemCreate(**_item_payload()),
            alex,
        )
        item_id = item.id

        item_service.delete_item(session, wishlist.id, item_id, alex)

        assert session.get(WishlistItem, item_id) is None

    def test_raises_404_when_item_belongs_to_another_wishlist(
        self,
        session: Session,
    ) -> None:
        alex = _add_user(session)
        first = _add_wishlist(session, alex, "Primera")
        second = _add_wishlist(session, alex, "Segunda")
        item = item_service.create_item(
            session,
            second.id,
            ItemCreate(**_item_payload()),
            alex,
        )

        with pytest.raises(HTTPException) as exc_info:
            item_service.delete_item(session, first.id, item.id, alex)

        assert exc_info.value.status_code == 404
        assert session.get(WishlistItem, item.id) is not None

    def test_raises_403_when_wishlist_belongs_to_another_user(
        self,
        session: Session,
    ) -> None:
        alex = _add_user(session)
        bob = _add_user(session, "bob")
        wishlist = _add_wishlist(session, bob)
        item = item_service.create_item(
            session,
            wishlist.id,
            ItemCreate(**_item_payload()),
            bob,
        )

        with pytest.raises(HTTPException) as exc_info:
            item_service.delete_item(session, wishlist.id, item.id, alex)

        assert exc_info.value.status_code == 403
        assert session.get(WishlistItem, item.id) is not None


class TestStoredImageCleanup:
    def test_item_can_be_created_without_image(self, session: Session) -> None:
        alex = _add_user(session)
        wishlist = _add_wishlist(session, alex)
        payload = _item_payload()
        payload.pop("image_url")

        item = item_service.create_item(
            session, wishlist.id, ItemCreate(**payload), alex
        )

        assert item.image_url is None

    def test_delete_item_removes_stored_file(
        self,
        session: Session,
        tmp_path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "media_dir", tmp_path)
        filename = "2f1c9d8e-7a4b-4c3d-9e2f-1a2b3c4d5e6f.webp"
        stored = tmp_path / filename
        stored.write_bytes(b"webp")
        image_url = f"/media/{filename}"

        alex = _add_user(session)
        wishlist = _add_wishlist(session, alex)
        item = item_service.create_item(
            session,
            wishlist.id,
            ItemCreate(**_item_payload(image_url=image_url)),
            alex,
        )

        item_service.delete_item(session, wishlist.id, item.id, alex)

        assert not stored.exists()

    def test_replacing_stored_image_removes_previous_file(
        self,
        session: Session,
        tmp_path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "media_dir", tmp_path)
        filename = "3f1c9d8e-7a4b-4c3d-9e2f-1a2b3c4d5e6f.webp"
        stored = tmp_path / filename
        stored.write_bytes(b"webp")

        alex = _add_user(session)
        wishlist = _add_wishlist(session, alex)
        item = item_service.create_item(
            session,
            wishlist.id,
            ItemCreate(**_item_payload(image_url=f"/media/{filename}")),
            alex,
        )

        item_service.update_item(
            session,
            wishlist.id,
            item.id,
            ItemUpdate(**_item_payload(image_url=None)),
            alex,
        )

        assert not stored.exists()
