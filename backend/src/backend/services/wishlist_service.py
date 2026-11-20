"""Servicios de wishlists.

Contratos consumidos por `backend.routers.wishlists`. La implementación real
de las consultas llega en la Fase 3.
"""

from sqlalchemy.orm import Session

from backend.models import User, Wishlist
from backend.schemas import (
    WishlistCreate,
    WishlistPublicResponse,
    WishlistUpdate,
)


def list_own_wishlists(db: Session, current_user: User) -> list[Wishlist]:
    """Devuelve todas las wishlists del usuario autenticado."""
    raise NotImplementedError(
        "TODO(Fase 3): implementar el listado de wishlists propias."
    )


def create_wishlist(
    db: Session,
    wishlist_in: WishlistCreate,
    current_user: User,
) -> Wishlist:
    """Crea una wishlist asignándola al usuario autenticado."""
    raise NotImplementedError(
        "TODO(Fase 3): implementar la creación de wishlists."
    )


def get_wishlist_by_share_id(db: Session, share_id: str) -> WishlistPublicResponse:
    """Devuelve la wishlist compartida con ese `share_id`.

    Contrato: lanza `HTTPException(404)` si no existe ninguna wishlist con
    ese identificador.
    """
    raise NotImplementedError(
        "TODO(Fase 3): implementar la consulta de wishlist por share_id."
    )


def update_wishlist(
    db: Session,
    wishlist_id: int,
    wishlist_in: WishlistUpdate,
    current_user: User,
) -> Wishlist:
    """Reemplaza el título y la descripción de una wishlist.

    Contrato: lanza `HTTPException(404)` si la wishlist no existe y
    `HTTPException(403)` si pertenece a otro usuario.
    """
    raise NotImplementedError(
        "TODO(Fase 3): implementar la edición de wishlists."
    )


def delete_wishlist(db: Session, wishlist_id: int, current_user: User) -> None:
    """Elimina una wishlist y, en cascada, sus artículos.

    Contrato: lanza `HTTPException(404)` si la wishlist no existe y
    `HTTPException(403)` si pertenece a otro usuario.
    """
    raise NotImplementedError(
        "TODO(Fase 3): implementar el borrado de wishlists."
    )
