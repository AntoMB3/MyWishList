"""DTOs (esquemas Pydantic) que definen el contrato de entrada y salida de la API.

Desacoplan los modelos ORM de lo que se expone en JSON: `hashed_password`
nunca forma parte de ningún esquema de respuesta.
"""

import re
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    TypeAdapter,
    UrlConstraints,
    field_validator,
)

USERNAME_PATTERN = r"^[a-zA-Z0-9_-]{3,30}$"
SHARE_ID_PATTERN = r"^[0-9a-f]{32}$"
SHARE_ID_LENGTH = 32
MAX_URL_LENGTH = 2048
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
# Archivos propios servidos por la API (`GET /media/<uuid>.webp`).
MEDIA_URL_PATTERN = r"^/media/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.webp$"

# HttpUrl ya restringe los esquemas a http/https (bloquea vectores como
# `javascript:`); limitamos además la longitud a la de las columnas de la BD.
ArticleUrl = Annotated[
    HttpUrl,
    UrlConstraints(max_length=MAX_URL_LENGTH, allowed_schemes=["http", "https"]),
]

_ArticleUrlAdapter = TypeAdapter(ArticleUrl)


class UserBase(BaseModel):
    """Campos comunes de usuario."""

    username: str = Field(min_length=3, max_length=30, pattern=USERNAME_PATTERN)

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: object) -> object:
        """Normaliza el username para que las URLs sean limpias y estables."""
        return value.strip().lower() if isinstance(value, str) else value


class UserCreate(UserBase):
    """Payload de `POST /api/auth/register`."""

    password: str = Field(
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_LENGTH,
    )


class UserLogin(UserBase):
    """Payload JSON opcional de `POST /api/auth/login`.

    El endpoint también acepta `application/x-www-form-urlencoded` para que
    funcione el botón *Authorize* de Swagger UI.
    """

    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class UserResponse(BaseModel):
    """Representación pública de un usuario (sin `hashed_password`)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    created_at: datetime


class TokenResponse(BaseModel):
    """Respuesta de un login exitoso."""

    access_token: str
    token_type: str = "bearer"


class ItemBase(BaseModel):
    """Campos comunes de un artículo de la wishlist."""

    title: str = Field(min_length=1, max_length=150)
    price: Decimal = Field(ge=Decimal("0"), max_digits=10, decimal_places=2)
    description: str | None = Field(default=None, max_length=2000)
    url: ArticleUrl
    image_url: str | None = Field(default=None, max_length=MAX_URL_LENGTH)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("El título no puede estar vacío.")
        return value

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("image_url")
    @classmethod
    def validate_image_url(cls, value: str | None) -> str | None:
        """Acepta una URL externa http(s) o una ruta local `/media/...`."""
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        if re.fullmatch(MEDIA_URL_PATTERN, value):
            return value
        return str(_ArticleUrlAdapter.validate_python(value))


class ItemCreate(ItemBase):
    """Payload de `POST /api/items`."""


class ItemUpdate(ItemBase):
    """Payload de `PUT /api/items/{item_id}` (reemplazo completo)."""


class ItemResponse(BaseModel):
    """Representación pública de un artículo."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    price: Decimal
    description: str | None
    url: str
    image_url: str | None
    wishlist_id: int
    created_at: datetime


class WishlistBase(BaseModel):
    """Campos editables de una wishlist."""

    title: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("El título no puede estar vacío.")
        return value

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class WishlistCreate(WishlistBase):
    """Payload de `POST /api/wishlists`."""


class WishlistUpdate(WishlistBase):
    """Payload de `PUT /api/wishlists/{wishlist_id}` (reemplazo completo)."""


class WishlistResponse(BaseModel):
    """Wishlist tal como la ve su dueño (incluye el enlace para compartir)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    share_id: str
    item_count: int = 0
    created_at: datetime


class WishlistPublicResponse(BaseModel):
    """Wishlist compartida, accesible conociendo su `share_id`."""

    id: int
    title: str
    description: str | None
    share_id: str
    owner_username: str
    created_at: datetime
    items: list[ItemResponse]


class UnfurlRequest(BaseModel):
    """Enlace del producto del que se intentará extraer la imagen."""

    url: ArticleUrl


class UnfurlResponse(BaseModel):
    """Imagen encontrada en el enlace, o `None` si no se pudo obtener."""

    image_url: str | None


class MediaUploadResponse(BaseModel):
    """Imagen propia ya comprimida y almacenada en el servidor."""

    image_url: str
