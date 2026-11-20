"""Servicios de wishlists.

Contratos consumidos por `backend.routers.wishlists`. Toda la lógica de
acceso a datos y las comprobaciones de autoría viven aquí, de modo que los
routers solo se ocupen de HTTP.
"""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from backend.models import User, Wishlist
from backend.schemas import (
    ItemResponse,
    WishlistCreate,
    WishlistPublicResponse,
    WishlistUpdate,
)

_WISHLIST_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Wishlist no encontrada.",
)

_WISHLIST_FORBIDDEN = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="No tienes permiso para modificar esta wishlist.",
)


def get_owned_wishlist(
    db: Session,
    wishlist_id: int,
    current_user: User,
) -> Wishlist:
    """Devuelve una wishlist propia o lanza el error HTTP adecuado.

    Contrato: `404` si no existe y `403` si pertenece a otro usuario.
    Reutilizado por `item_service` para validar la autoría del contenedor.
    """
    wishlist = db.get(Wishlist, wishlist_id)
    if wishlist is None:
        raise _WISHLIST_NOT_FOUND
    if wishlist.user_id != current_user.id:
        raise _WISHLIST_FORBIDDEN
    return wishlist


def list_own_wishlists(db: Session, current_user: User) -> list[Wishlist]:
    """Devuelve todas las wishlists del usuario autenticado."""
    statement = (
        select(Wishlist)
        .where(Wishlist.user_id == current_user.id)
        .order_by(Wishlist.created_at.desc(), Wishlist.id.desc())
    )
    return list(db.scalars(statement))


def create_wishlist(
    db: Session,
    wishlist_in: WishlistCreate,
    current_user: User,
) -> Wishlist:
    """Crea una wishlist asignándola al usuario autenticado."""
    wishlist = Wishlist(**wishlist_in.model_dump(), user_id=current_user.id)
    db.add(wishlist)
    db.commit()
    db.refresh(wishlist)
    return wishlist


def get_wishlist_by_share_id(db: Session, share_id: str) -> WishlistPublicResponse:
    """Devuelve la wishlist compartida con ese `share_id`.

    Contrato: lanza `HTTPException(404)` si no existe ninguna wishlist con
    ese identificador.
    """
    statement = (
        select(Wishlist)
        .options(
            joinedload(Wishlist.owner),
            selectinload(Wishlist.items),
        )
        .where(Wishlist.share_id == share_id)
    )
    wishlist = db.scalar(statement)
    if wishlist is None:
        raise _WISHLIST_NOT_FOUND

    return WishlistPublicResponse(
        id=wishlist.id,
        title=wishlist.title,
        description=wishlist.description,
        share_id=wishlist.share_id,
        owner_username=wishlist.owner.username,
        created_at=wishlist.created_at,
        items=[ItemResponse.model_validate(item) for item in wishlist.items],
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
    wishlist = get_owned_wishlist(db, wishlist_id, current_user)

    wishlist.title = wishlist_in.title
    wishlist.description = wishlist_in.description
    db.commit()
    db.refresh(wishlist)
    return wishlist


def delete_wishlist(db: Session, wishlist_id: int, current_user: User) -> None:
    """Elimina una wishlist y, en cascada, sus artículos.

    Contrato: lanza `HTTPException(404)` si la wishlist no existe y
    `HTTPException(403)` si pertenece a otro usuario.
    """
    wishlist = get_owned_wishlist(db, wishlist_id, current_user)

    db.delete(wishlist)
    db.commit()
