"""Servicios de artículos de wishlist.

Contratos consumidos por `backend.routers.items`. La autoría se valida
siempre a través de la wishlist: un artículo solo es accesible si pertenece
a una lista del usuario autenticado.
"""

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import User, WishlistItem
from backend.schemas import ItemCreate, ItemUpdate
from backend.services.wishlist_service import get_owned_wishlist

_ITEM_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Artículo no encontrado.",
)


def _item_values(item_in: ItemCreate | ItemUpdate) -> dict[str, Any]:
    """Convierte el DTO en valores listos para el ORM.

    `HttpUrl` no hereda de `str`, así que las URLs se serializan antes de
    pasarlas a SQLAlchemy. El precio se mantiene como `Decimal`.
    """
    values = item_in.model_dump()
    values["url"] = str(values["url"])
    values["image_url"] = str(values["image_url"])
    return values


def create_item(
    db: Session,
    wishlist_id: int,
    item_in: ItemCreate,
    current_user: User,
) -> WishlistItem:
    """Crea un artículo dentro de una wishlist del usuario autenticado.

    Contrato: lanza `HTTPException(404)` si la wishlist no existe y
    `HTTPException(403)` si pertenece a otro usuario.
    """
    wishlist = get_owned_wishlist(db, wishlist_id, current_user)

    item = WishlistItem(**_item_values(item_in), wishlist_id=wishlist.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _get_item(db: Session, wishlist_id: int, item_id: int) -> WishlistItem:
    """Busca el artículo dentro de la wishlist indicada."""
    statement = select(WishlistItem).where(
        WishlistItem.id == item_id,
        WishlistItem.wishlist_id == wishlist_id,
    )
    item = db.scalar(statement)
    if item is None:
        raise _ITEM_NOT_FOUND
    return item


def update_item(
    db: Session,
    wishlist_id: int,
    item_id: int,
    item_in: ItemUpdate,
    current_user: User,
) -> WishlistItem:
    """Reemplaza un artículo existente.

    Contrato: lanza `HTTPException(404)` si la wishlist o el artículo no
    existen y `HTTPException(403)` si la wishlist pertenece a otro usuario.
    """
    get_owned_wishlist(db, wishlist_id, current_user)
    item = _get_item(db, wishlist_id, item_id)

    for field, value in _item_values(item_in).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


def delete_item(
    db: Session,
    wishlist_id: int,
    item_id: int,
    current_user: User,
) -> None:
    """Elimina un artículo existente.

    Contrato: lanza `HTTPException(404)` si la wishlist o el artículo no
    existen y `HTTPException(403)` si la wishlist pertenece a otro usuario.
    """
    get_owned_wishlist(db, wishlist_id, current_user)
    item = _get_item(db, wishlist_id, item_id)

    db.delete(item)
    db.commit()
