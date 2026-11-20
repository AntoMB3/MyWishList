"""Servicios de artículos de wishlist.

Contratos consumidos por `backend.routers.items`. La implementación real de
las consultas llega en la Fase 3.
"""

from sqlalchemy.orm import Session

from backend.models import User, WishlistItem
from backend.schemas import ItemCreate, ItemUpdate


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
    raise NotImplementedError("TODO(Fase 3): implementar la creación de artículos.")


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
    raise NotImplementedError("TODO(Fase 3): implementar la edición de artículos.")


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
    raise NotImplementedError("TODO(Fase 3): implementar el borrado de artículos.")
