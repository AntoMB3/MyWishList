from decimal import Decimal

import pytest
from pydantic import ValidationError

from backend.schemas import (
    ItemCreate,
    ItemResponse,
    ItemUpdate,
    UserCreate,
    UserLogin,
    WishlistCreate,
    WishlistPublicResponse,
    WishlistUpdate,
)


def _item_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "title": "Teclado",
        "price": "99.90",
        "description": "Mecánico",
        "url": "https://example.com/teclado",
        "image_url": "https://example.com/teclado.png",
    }
    payload.update(overrides)
    return payload


class TestUserSchemas:
    def test_username_is_normalized_to_lowercase(self) -> None:
        user = UserCreate(username="  Alex_01 ", password="secreto123")
        assert user.username == "alex_01"

    @pytest.mark.parametrize("username", ["al", "alex!", "alex munoz", "a" * 31])
    def test_invalid_usernames_are_rejected(self, username: str) -> None:
        with pytest.raises(ValidationError):
            UserCreate(username=username, password="secreto123")

    def test_password_has_minimum_length(self) -> None:
        with pytest.raises(ValidationError):
            UserCreate(username="alex", password="corta")

    def test_login_password_can_be_short(self) -> None:
        assert UserLogin(username="alex", password="x").username == "alex"


class TestItemSchemas:
    def test_valid_item_is_accepted(self) -> None:
        item = ItemCreate.model_validate(_item_payload())
        assert item.title == "Teclado"
        assert item.price == Decimal("99.90")
        assert str(item.url) == "https://example.com/teclado"

    @pytest.mark.parametrize("price", ["-0.01", "-100"])
    def test_negative_price_is_rejected(self, price: str) -> None:
        with pytest.raises(ValidationError):
            ItemCreate.model_validate(_item_payload(price=price))

    def test_price_with_more_than_two_decimals_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ItemCreate.model_validate(_item_payload(price="9.999"))

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("url", "javascript:alert(1)"),
            ("image_url", "javascript:alert(1)"),
            ("url", "ftp://example.com/archivo"),
            ("url", "no-es-una-url"),
        ],
    )
    def test_non_http_urls_are_rejected(self, field: str, value: str) -> None:
        with pytest.raises(ValidationError):
            ItemCreate.model_validate(_item_payload(**{field: value}))

    def test_title_cannot_be_blank(self) -> None:
        with pytest.raises(ValidationError):
            ItemCreate.model_validate(_item_payload(title="   "))

    def test_blank_description_becomes_none(self) -> None:
        item = ItemCreate.model_validate(_item_payload(description="   "))
        assert item.description is None

    def test_update_uses_same_rules_as_create(self) -> None:
        with pytest.raises(ValidationError):
            ItemUpdate.model_validate(_item_payload(price="-5"))

    def test_response_does_not_expose_private_fields(self) -> None:
        assert "hashed_password" not in ItemResponse.model_fields

    def test_image_is_optional(self) -> None:
        payload = _item_payload()
        payload.pop("image_url")

        assert ItemCreate.model_validate(payload).image_url is None

    @pytest.mark.parametrize("value", ["", "   ", None])
    def test_blank_image_becomes_none(self, value: str | None) -> None:
        assert ItemCreate.model_validate(_item_payload(image_url=value)).image_url is None

    def test_accepts_stored_media_path(self) -> None:
        path = "/media/2f1c9d8e-7a4b-4c3d-9e2f-1a2b3c4d5e6f.webp"
        assert ItemCreate.model_validate(_item_payload(image_url=path)).image_url == path

    def test_rejects_media_path_traversal(self) -> None:
        with pytest.raises(ValidationError):
            ItemCreate.model_validate(
                _item_payload(image_url="/media/../whishlist.db")
            )


class TestWishlistSchemas:
    def test_title_is_trimmed(self) -> None:
        wishlist = WishlistCreate(title="  Cumpleaños  ", description="  ")
        assert wishlist.title == "Cumpleaños"
        assert wishlist.description is None

    def test_blank_title_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WishlistCreate(title="   ")

    def test_title_has_maximum_length(self) -> None:
        with pytest.raises(ValidationError):
            WishlistCreate(title="a" * 101)

    def test_description_has_maximum_length(self) -> None:
        with pytest.raises(ValidationError):
            WishlistCreate(title="Lista", description="a" * 501)

    def test_update_uses_same_rules_as_create(self) -> None:
        with pytest.raises(ValidationError):
            WishlistUpdate(title="")

    def test_public_response_requires_owner_username(self) -> None:
        with pytest.raises(ValidationError):
            WishlistPublicResponse.model_validate(
                {
                    "id": 1,
                    "title": "Lista",
                    "description": None,
                    "share_id": "a" * 32,
                    "created_at": "2026-01-01T00:00:00Z",
                    "items": [],
                }
            )
