from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from backend.config import settings
from backend.dependencies import get_current_user, get_db
from backend.main import app
from backend.models import User, Wishlist, WishlistItem
from backend.schemas import (
    ItemCreate,
    ItemUpdate,
    TokenResponse,
    UserCreate,
    WishlistCreate,
    WishlistPublicResponse,
    WishlistUpdate,
)
from backend.services import auth_service, item_service, media_service, wishlist_service

CREATED_AT = datetime(2026, 1, 1, tzinfo=UTC)
SHARE_ID = "a" * 32


def _user(user_id: int = 1, username: str = "alex") -> User:
    return User(id=user_id, username=username, hashed_password="hash", created_at=CREATED_AT)


def _wishlist() -> Wishlist:
    return Wishlist(
        id=3,
        title="Cumpleaños",
        description=None,
        share_id=SHARE_ID,
        user_id=1,
        created_at=CREATED_AT,
    )


def _item() -> WishlistItem:
    return WishlistItem(
        id=10,
        title="Teclado",
        price=Decimal("99.90"),
        description=None,
        url="https://example.com/teclado",
        image_url="https://example.com/teclado.png",
        wishlist_id=3,
        created_at=CREATED_AT,
    )


def _item_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "title": "Teclado",
        "price": "99.90",
        "description": None,
        "url": "https://example.com/teclado",
        "image_url": "https://example.com/teclado.png",
    }
    payload.update(overrides)
    return payload


def _item_response_payload(**overrides: object) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": 10,
        "title": "Teclado",
        "price": "99.90",
        "description": None,
        "url": "https://example.com/teclado",
        "image_url": "https://example.com/teclado.png",
        "wishlist_id": 3,
        "created_at": CREATED_AT,
    }
    payload.update(overrides)
    return payload


@pytest.fixture()
def client(session: Session) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        yield session

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        test_client.close()
        app.dependency_overrides.clear()


@pytest.fixture()
def authenticated_client(client: TestClient) -> TestClient:
    app.dependency_overrides[get_current_user] = lambda: _user()
    return client


class TestAuthRouter:
    def test_register_returns_created_user(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def fake_register(db: Session, user_in: UserCreate) -> User:
            assert user_in.username == "alex"
            return _user()

        monkeypatch.setattr(auth_service, "register_user", fake_register)

        response = client.post(
            "/api/auth/register",
            json={"username": "Alex", "password": "secreto123"},
        )

        assert response.status_code == 201
        assert response.json() == {
            "id": 1,
            "username": "alex",
            "created_at": "2026-01-01T00:00:00Z",
        }
        assert "hashed_password" not in response.json()

    def test_register_rejects_invalid_payload(self, client: TestClient) -> None:
        response = client.post(
            "/api/auth/register",
            json={"username": "a!", "password": "corta"},
        )
        assert response.status_code == 422

    def test_login_accepts_json(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        calls: list[tuple[str, str]] = []

        def fake_authenticate(db: Session, username: str, password: str) -> TokenResponse:
            calls.append((username, password))
            return TokenResponse(access_token="token-123")

        monkeypatch.setattr(auth_service, "authenticate_user", fake_authenticate)

        response = client.post(
            "/api/auth/login",
            json={"username": "ALEX", "password": "secreto123"},
        )

        assert response.status_code == 200
        assert response.json() == {"access_token": "token-123", "token_type": "bearer"}
        assert calls == [("alex", "secreto123")]

    def test_login_accepts_form_data(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def fake_authenticate(db: Session, username: str, password: str) -> TokenResponse:
            return TokenResponse(access_token="token-form")

        monkeypatch.setattr(auth_service, "authenticate_user", fake_authenticate)

        response = client.post(
            "/api/auth/login",
            data={"username": "alex", "password": "secreto123"},
        )

        assert response.status_code == 200
        assert response.json()["access_token"] == "token-form"

    def test_login_rejects_malformed_json(self, client: TestClient) -> None:
        response = client.post("/api/auth/login", json=["alex", "secreto123"])
        assert response.status_code == 422

    def test_me_requires_token(self, client: TestClient) -> None:
        response = client.get("/api/auth/me")
        assert response.status_code == 401

    def test_me_returns_authenticated_user(self, authenticated_client: TestClient) -> None:
        response = authenticated_client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer token"},
        )
        assert response.status_code == 200
        assert response.json()["username"] == "alex"


class TestWishlistsRouter:
    def test_mine_requires_token(self, client: TestClient) -> None:
        assert client.get("/api/wishlists/mine").status_code == 401

    def test_mine_lists_own_wishlists(
        self,
        authenticated_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            wishlist_service,
            "list_own_wishlists",
            lambda db, current_user: [_wishlist()],
        )

        response = authenticated_client.get(
            "/api/wishlists/mine",
            headers={"Authorization": "Bearer token"},
        )

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["title"] == "Cumpleaños"
        assert body[0]["share_id"] == SHARE_ID

    def test_create_returns_created_wishlist(
        self,
        authenticated_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def fake_create(
            db: Session,
            wishlist_in: WishlistCreate,
            current_user: User,
        ) -> Wishlist:
            assert wishlist_in.title == "Cumpleaños"
            assert current_user.id == 1
            return _wishlist()

        monkeypatch.setattr(wishlist_service, "create_wishlist", fake_create)

        response = authenticated_client.post(
            "/api/wishlists",
            headers={"Authorization": "Bearer token"},
            json={"title": "  Cumpleaños  "},
        )

        assert response.status_code == 201
        assert response.json()["share_id"] == SHARE_ID

    def test_create_requires_token(self, client: TestClient) -> None:
        response = client.post("/api/wishlists", json={"title": "Lista"})
        assert response.status_code == 401

    def test_read_shared_wishlist_is_public(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        received: list[str] = []

        def fake_get(db: Session, share_id: str) -> WishlistPublicResponse:
            received.append(share_id)
            return WishlistPublicResponse(
                id=3,
                title="Cumpleaños",
                description=None,
                share_id=share_id,
                owner_username="alex",
                created_at=CREATED_AT,
                items=[],
            )

        monkeypatch.setattr(wishlist_service, "get_wishlist_by_share_id", fake_get)

        response = client.get(f"/api/wishlists/{SHARE_ID}")

        assert response.status_code == 200
        assert received == [SHARE_ID]
        body = response.json()
        assert body["share_id"] == SHARE_ID
        assert body["owner_username"] == "alex"
        assert body["items"] == []

    def test_read_shared_wishlist_rejects_invalid_share_id(
        self,
        client: TestClient,
    ) -> None:
        assert client.get("/api/wishlists/no-es-un-share-id").status_code == 422
        assert client.get("/api/wishlists/ZZZ").status_code == 422

    def test_read_shared_wishlist_404_when_missing(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def fake_get(db: Session, share_id: str) -> Wishlist:
            raise HTTPException(status_code=404, detail="Wishlist no encontrada")

        monkeypatch.setattr(wishlist_service, "get_wishlist_by_share_id", fake_get)

        assert client.get(f"/api/wishlists/{SHARE_ID}").status_code == 404

    def test_update_returns_updated_wishlist(
        self,
        authenticated_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def fake_update(
            db: Session,
            wishlist_id: int,
            wishlist_in: WishlistUpdate,
            current_user: User,
        ) -> Wishlist:
            assert wishlist_id == 3
            wishlist = _wishlist()
            wishlist.title = wishlist_in.title
            return wishlist

        monkeypatch.setattr(wishlist_service, "update_wishlist", fake_update)

        response = authenticated_client.put(
            "/api/wishlists/3",
            headers={"Authorization": "Bearer token"},
            json={"title": "Nuevo nombre"},
        )

        assert response.status_code == 200
        assert response.json()["title"] == "Nuevo nombre"

    def test_delete_returns_no_content(
        self,
        authenticated_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        deleted: list[int] = []
        monkeypatch.setattr(
            wishlist_service,
            "delete_wishlist",
            lambda db, wishlist_id, current_user: deleted.append(wishlist_id),
        )

        response = authenticated_client.delete(
            "/api/wishlists/3",
            headers={"Authorization": "Bearer token"},
        )

        assert response.status_code == 204
        assert response.content == b""
        assert deleted == [3]


class TestItemsRouter:
    def test_create_requires_token(self, client: TestClient) -> None:
        response = client.post("/api/wishlists/3/items", json=_item_payload())
        assert response.status_code == 401

    def test_create_returns_created_item(
        self,
        authenticated_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def fake_create(
            db: Session,
            wishlist_id: int,
            item_in: ItemCreate,
            current_user: User,
        ) -> WishlistItem:
            assert wishlist_id == 3
            assert item_in.title == "Teclado"
            assert current_user.id == 1
            return _item()

        monkeypatch.setattr(item_service, "create_item", fake_create)

        response = authenticated_client.post(
            "/api/wishlists/3/items",
            headers={"Authorization": "Bearer token"},
            json=_item_payload(),
        )

        assert response.status_code == 201
        assert response.json()["id"] == 10
        assert response.json()["wishlist_id"] == 3

    def test_create_rejects_invalid_payload(self, authenticated_client: TestClient) -> None:
        response = authenticated_client.post(
            "/api/wishlists/3/items",
            headers={"Authorization": "Bearer token"},
            json=_item_payload(price="-1"),
        )
        assert response.status_code == 422

    def test_create_accepts_item_without_image(
        self,
        authenticated_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def fake_create(
            db: Session,
            wishlist_id: int,
            item_in: ItemCreate,
            current_user: User,
        ) -> WishlistItem:
            assert item_in.image_url is None
            return WishlistItem(
                id=11,
                title=item_in.title,
                price=item_in.price,
                description=None,
                url=str(item_in.url),
                image_url=None,
                wishlist_id=wishlist_id,
                created_at=CREATED_AT,
            )

        monkeypatch.setattr(item_service, "create_item", fake_create)
        payload = _item_payload()
        payload.pop("image_url")

        response = authenticated_client.post(
            "/api/wishlists/3/items",
            headers={"Authorization": "Bearer token"},
            json=payload,
        )

        assert response.status_code == 201
        assert response.json()["image_url"] is None

    def test_create_404_when_wishlist_missing(
        self,
        authenticated_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def fake_create(db: Session, wishlist_id: int, item_in: ItemCreate, current_user: User):
            raise HTTPException(status_code=404, detail="Wishlist no encontrada")

        monkeypatch.setattr(item_service, "create_item", fake_create)

        response = authenticated_client.post(
            "/api/wishlists/999/items",
            headers={"Authorization": "Bearer token"},
            json=_item_payload(),
        )
        assert response.status_code == 404

    def test_update_returns_updated_item(
        self,
        authenticated_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def fake_update(
            db: Session,
            wishlist_id: int,
            item_id: int,
            item_in: ItemUpdate,
            current_user: User,
        ) -> WishlistItem:
            assert (wishlist_id, item_id) == (3, 10)
            item = _item()
            item.title = item_in.title
            return item

        monkeypatch.setattr(item_service, "update_item", fake_update)

        response = authenticated_client.put(
            "/api/wishlists/3/items/10",
            headers={"Authorization": "Bearer token"},
            json=_item_payload(title="Teclado nuevo"),
        )

        assert response.status_code == 200
        assert response.json()["title"] == "Teclado nuevo"

    def test_update_forbidden_propagates_403(
        self,
        authenticated_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def fake_update(*args: object, **kwargs: object) -> WishlistItem:
            raise HTTPException(status_code=403, detail="No es tu wishlist")

        monkeypatch.setattr(item_service, "update_item", fake_update)

        response = authenticated_client.put(
            "/api/wishlists/3/items/10",
            headers={"Authorization": "Bearer token"},
            json=_item_payload(),
        )
        assert response.status_code == 403

    def test_delete_returns_no_content(
        self,
        authenticated_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        deleted: list[tuple[int, int]] = []
        monkeypatch.setattr(
            item_service,
            "delete_item",
            lambda db, wishlist_id, item_id, current_user: deleted.append(
                (wishlist_id, item_id)
            ),
        )

        response = authenticated_client.delete(
            "/api/wishlists/3/items/10",
            headers={"Authorization": "Bearer token"},
        )

        assert response.status_code == 204
        assert response.content == b""
        assert deleted == [(3, 10)]


class TestMediaRouter:
    @pytest.fixture()
    def media_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        monkeypatch.setattr(settings, "media_dir", tmp_path)
        return tmp_path

    def test_unfurl_returns_found_image(
        self,
        authenticated_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            media_service,
            "fetch_product_image",
            lambda url: "https://cdn.example.com/producto.jpg",
        )

        response = authenticated_client.post(
            "/api/media/unfurl",
            headers={"Authorization": "Bearer token"},
            json={"url": "https://tienda.com/producto"},
        )

        assert response.status_code == 200
        assert response.json() == {
            "image_url": "https://cdn.example.com/producto.jpg"
        }

    def test_unfurl_returns_null_when_not_found(
        self,
        authenticated_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            media_service, "fetch_product_image", lambda url: None
        )

        response = authenticated_client.post(
            "/api/media/unfurl",
            headers={"Authorization": "Bearer token"},
            json={"url": "https://tienda.com/producto"},
        )

        assert response.status_code == 200
        assert response.json() == {"image_url": None}

    def test_unfurl_requires_token(self, client: TestClient) -> None:
        response = client.post(
            "/api/media/unfurl", json={"url": "https://tienda.com/producto"}
        )
        assert response.status_code == 401

    def test_unfurl_rejects_invalid_url(self, authenticated_client: TestClient) -> None:
        response = authenticated_client.post(
            "/api/media/unfurl",
            headers={"Authorization": "Bearer token"},
            json={"url": "javascript:alert(1)"},
        )
        assert response.status_code == 422

    def test_upload_stores_image_and_serves_it(
        self,
        authenticated_client: TestClient,
        media_dir,
    ) -> None:
        buffer = BytesIO()
        Image.new("RGB", (1200, 900), (10, 80, 160)).save(buffer, format="PNG")

        upload = authenticated_client.post(
            "/api/media",
            headers={"Authorization": "Bearer token"},
            files={"file": ("foto.png", buffer.getvalue(), "image/png")},
        )

        assert upload.status_code == 201
        image_url = upload.json()["image_url"]
        assert image_url.startswith("/media/")

        served = authenticated_client.get(image_url)
        assert served.status_code == 200
        assert served.headers["content-type"] == "image/webp"

    def test_upload_requires_token(self, client: TestClient) -> None:
        response = client.post(
            "/api/media",
            files={"file": ("foto.png", b"x", "image/png")},
        )
        assert response.status_code == 401

    def test_upload_rejects_non_image(
        self,
        authenticated_client: TestClient,
        media_dir,
    ) -> None:
        response = authenticated_client.post(
            "/api/media",
            headers={"Authorization": "Bearer token"},
            files={"file": ("nota.txt", b"no soy imagen", "image/png")},
        )
        assert response.status_code == 400

    def test_media_route_rejects_unknown_name(
        self,
        authenticated_client: TestClient,
        media_dir,
    ) -> None:
        assert authenticated_client.get("/media/inexistente.webp").status_code == 404
        assert (
            authenticated_client.get("/media/../whishlist.db").status_code == 404
        )
