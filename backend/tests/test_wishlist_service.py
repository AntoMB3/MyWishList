from datetime import datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models import User, Wishlist, WishlistItem
from backend.schemas import WishlistCreate, WishlistUpdate
from backend.services import wishlist_service


def _add_user(session: Session, username: str = "alex") -> User:
    user = User(username=username, hashed_password="hash")
    session.add(user)
    session.commit()
    return user


def _add_wishlist(
    session: Session,
    user: User,
    title: str = "Cumpleaños",
    created_at: datetime = datetime(2026, 1, 1),
) -> Wishlist:
    wishlist = Wishlist(
        title=title,
        description=None,
        user_id=user.id,
        created_at=created_at,
    )
    session.add(wishlist)
    session.commit()
    return wishlist


def _add_item(
    session: Session,
    wishlist: Wishlist,
    title: str,
    created_at: datetime = datetime(2026, 1, 1),
) -> WishlistItem:
    item = WishlistItem(
        title=title,
        price=Decimal("99.90"),
        description=None,
        url="https://example.com/articulo",
        image_url="https://example.com/articulo.png",
        wishlist_id=wishlist.id,
        created_at=created_at,
    )
    session.add(item)
    session.commit()
    return item


class TestListOwnWishlists:
    def test_returns_only_own_wishlists_newest_first(self, session: Session) -> None:
        alex = _add_user(session)
        bob = _add_user(session, "bob")
        _add_wishlist(session, alex, "Antigua", datetime(2026, 1, 1))
        _add_wishlist(session, alex, "Reciente", datetime(2026, 2, 1))
        _add_wishlist(session, bob, "De Bob", datetime(2026, 3, 1))

        wishlists = wishlist_service.list_own_wishlists(session, alex)

        assert [wishlist.title for wishlist in wishlists] == ["Reciente", "Antigua"]
        assert [wishlist.item_count for wishlist in wishlists] == [0, 0]

    def test_includes_item_count(self, session: Session) -> None:
        alex = _add_user(session)
        wishlist = _add_wishlist(session, alex, "Con artículos")
        _add_item(session, wishlist, "Uno")
        _add_item(session, wishlist, "Dos")

        wishlists = wishlist_service.list_own_wishlists(session, alex)

        assert len(wishlists) == 1
        assert wishlists[0].item_count == 2


class TestCreateWishlist:
    def test_creates_wishlist_for_current_user(self, session: Session) -> None:
        alex = _add_user(session)

        wishlist = wishlist_service.create_wishlist(
            session,
            WishlistCreate(title="  Cumpleaños  ", description="  Lista  "),
            alex,
        )

        assert wishlist.id is not None
        assert wishlist.user_id == alex.id
        assert wishlist.title == "Cumpleaños"
        assert wishlist.description == "Lista"
        assert len(wishlist.share_id) == 32
        assert wishlist.created_at is not None
        assert session.get(Wishlist, wishlist.id) is not None


class TestWishlistLimit:
    def test_allows_wishlists_up_to_the_limit(
        self,
        session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "max_wishlists_per_user", 2)
        alex = _add_user(session)

        for index in range(2):
            created = wishlist_service.create_wishlist(
                session,
                WishlistCreate(title=f"Lista {index}"),
                alex,
            )
            assert created.id is not None

    def test_rejects_wishlist_over_the_limit(
        self,
        session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "max_wishlists_per_user", 2)
        alex = _add_user(session)
        _add_wishlist(session, alex, "Primera")
        _add_wishlist(session, alex, "Segunda")

        with pytest.raises(HTTPException) as exc_info:
            wishlist_service.create_wishlist(
                session,
                WishlistCreate(title="Tercera"),
                alex,
            )

        assert exc_info.value.status_code == 409
        assert "2 wishlists" in exc_info.value.detail

    def test_does_not_count_other_users_wishlists(
        self,
        session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "max_wishlists_per_user", 2)
        alex = _add_user(session)
        bob = _add_user(session, "bob")
        _add_wishlist(session, bob, "De Bob 1")
        _add_wishlist(session, bob, "De Bob 2")

        created = wishlist_service.create_wishlist(
            session,
            WishlistCreate(title="De Alex"),
            alex,
        )

        assert created.user_id == alex.id


class TestGetWishlistByShareId:
    def test_returns_public_wishlist_with_items_newest_first(
        self,
        session: Session,
    ) -> None:
        alex = _add_user(session)
        wishlist = _add_wishlist(session, alex)
        _add_item(session, wishlist, "Antiguo", datetime(2026, 1, 1))
        _add_item(session, wishlist, "Reciente", datetime(2026, 2, 1))

        response = wishlist_service.get_wishlist_by_share_id(session, wishlist.share_id)

        assert response.id == wishlist.id
        assert response.share_id == wishlist.share_id
        assert response.owner_username == "alex"
        assert [item.title for item in response.items] == ["Reciente", "Antiguo"]
        assert all(isinstance(item.url, str) for item in response.items)

    def test_raises_404_when_share_id_does_not_exist(self, session: Session) -> None:
        with pytest.raises(HTTPException) as exc_info:
            wishlist_service.get_wishlist_by_share_id(session, "a" * 32)

        assert exc_info.value.status_code == 404


class TestUpdateWishlist:
    def test_updates_own_wishlist(self, session: Session) -> None:
        alex = _add_user(session)
        wishlist = _add_wishlist(session, alex)
        share_id = wishlist.share_id

        updated = wishlist_service.update_wishlist(
            session,
            wishlist.id,
            WishlistUpdate(title="  Nuevo nombre  ", description="  Nueva  "),
            alex,
        )

        assert updated.title == "Nuevo nombre"
        assert updated.description == "Nueva"
        assert updated.share_id == share_id
        session.refresh(wishlist)
        assert wishlist.title == "Nuevo nombre"

    def test_raises_404_when_wishlist_does_not_exist(self, session: Session) -> None:
        alex = _add_user(session)

        with pytest.raises(HTTPException) as exc_info:
            wishlist_service.update_wishlist(
                session,
                999,
                WishlistUpdate(title="Nuevo"),
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
            wishlist_service.update_wishlist(
                session,
                wishlist.id,
                WishlistUpdate(title="Nuevo"),
                alex,
            )

        assert exc_info.value.status_code == 403


class TestDeleteWishlist:
    def test_deletes_own_wishlist_and_items(self, session: Session) -> None:
        alex = _add_user(session)
        wishlist = _add_wishlist(session, alex)
        _add_item(session, wishlist, "Teclado")
        wishlist_id = wishlist.id

        wishlist_service.delete_wishlist(session, wishlist_id, alex)

        assert session.get(Wishlist, wishlist_id) is None
        assert session.scalar(select(func.count()).select_from(WishlistItem)) == 0

    def test_removes_stored_images_of_its_items(
        self,
        session: Session,
        tmp_path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "media_dir", tmp_path)
        first = "2f1c9d8e-7a4b-4c3d-9e2f-1a2b3c4d5e6f.webp"
        second = "3f1c9d8e-7a4b-4c3d-9e2f-1a2b3c4d5e6f.webp"
        stored = [tmp_path / first, tmp_path / second]
        for path in stored:
            path.write_bytes(b"webp")

        alex = _add_user(session)
        wishlist = _add_wishlist(session, alex)
        for filename in (first, second):
            item = _add_item(session, wishlist, f"Artículo {filename[0]}")
            item.image_url = f"/media/{filename}"
        session.commit()

        wishlist_service.delete_wishlist(session, wishlist.id, alex)

        assert all(not path.exists() for path in stored)

    def test_ignores_external_images_and_missing_files(
        self,
        session: Session,
        tmp_path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "media_dir", tmp_path)
        alex = _add_user(session)
        wishlist = _add_wishlist(session, alex)
        external = _add_item(session, wishlist, "Externo")
        external.image_url = "https://example.com/articulo.png"
        missing = _add_item(session, wishlist, "Sin archivo")
        missing.image_url = (
            "/media/9f1c9d8e-7a4b-4c3d-9e2f-1a2b3c4d5e6f.webp"
        )
        session.commit()

        # No debe lanzar por la URL externa ni por el archivo ausente.
        wishlist_service.delete_wishlist(session, wishlist.id, alex)

        assert session.get(Wishlist, wishlist.id) is None

    def test_raises_404_when_wishlist_does_not_exist(self, session: Session) -> None:
        alex = _add_user(session)

        with pytest.raises(HTTPException) as exc_info:
            wishlist_service.delete_wishlist(session, 999, alex)

        assert exc_info.value.status_code == 404

    def test_raises_403_when_wishlist_belongs_to_another_user(
        self,
        session: Session,
    ) -> None:
        alex = _add_user(session)
        bob = _add_user(session, "bob")
        wishlist = _add_wishlist(session, bob)

        with pytest.raises(HTTPException) as exc_info:
            wishlist_service.delete_wishlist(session, wishlist.id, alex)

        assert exc_info.value.status_code == 403
        assert session.get(Wishlist, wishlist.id) is not None
