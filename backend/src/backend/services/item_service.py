"""Servicios de artículos de wishlist.

Contratos consumidos por `backend.routers.items`. La autoría se valida
siempre a través de la wishlist: un artículo solo es accesible si pertenece
a una lista del usuario autenticado.
"""

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models import User, WishlistItem
from backend.schemas import ItemCreate, ItemUpdate
from backend.services.media_service import delete_stored_image
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
    image_url = values.get("image_url")
    values["image_url"] = str(image_url) if image_url else None
    return values


def create_item(
    db: Session,
    wishlist_id: int,
    item_in: ItemCreate,
    current_user: User,
) -> WishlistItem:
    """Crea un artículo dentro de una wishlist del usuario autenticado.

    Contrato: lanza `HTTPException(404)` si la wishlist no existe,
    `HTTPException(403)` si pertenece a otro usuario y `HTTPException(409)`
    si la wishlist ya alcanzó el límite de artículos.
    """
    wishlist = get_owned_wishlist(db, wishlist_id, current_user)

    item_count = db.scalar(
        select(func.count(WishlistItem.id)).where(
            WishlistItem.wishlist_id == wishlist.id
        )
    ) or 0
    if item_count >= settings.max_items_per_wishlist:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Has alcanzado el límite de {settings.max_items_per_wishlist} "
                "artículos por wishlist."
            ),
        )

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

    previous_image = item.image_url
    for field, value in _item_values(item_in).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)

    if previous_image != item.image_url:
        delete_stored_image(previous_image)
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

    previous_image = item.image_url
    db.delete(item)
    db.commit()
    delete_stored_image(previous_image)
