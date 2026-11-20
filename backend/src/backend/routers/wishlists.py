"""Endpoints de `/api/wishlists`.

- Las wishlists propias se gestionan con autenticación (`/mine` y CRUD).
- Cualquier visita puede leer una wishlist concreta conociendo su `share_id`.
- No existe (a propósito) un listado global de wishlists.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.orm import Session

from backend.dependencies import get_current_user, get_db
from backend.models import User, Wishlist
from backend.schemas import (
    SHARE_ID_LENGTH,
    SHARE_ID_PATTERN,
    WishlistCreate,
    WishlistPublicResponse,
    WishlistResponse,
    WishlistUpdate,
)
from backend.services import wishlist_service

router = APIRouter(prefix="/api/wishlists", tags=["wishlists"])

ShareId = Annotated[
    str,
    Path(min_length=SHARE_ID_LENGTH, max_length=SHARE_ID_LENGTH, pattern=SHARE_ID_PATTERN),
]


@router.get(
    "/mine",
    response_model=list[WishlistResponse],
    summary="Listar las wishlists propias",
)
def read_own_wishlists(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[Wishlist]:
    return wishlist_service.list_own_wishlists(db, current_user)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=WishlistResponse,
    summary="Crear una wishlist propia",
)
def create_wishlist(
    wishlist_in: WishlistCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Wishlist:
    return wishlist_service.create_wishlist(db, wishlist_in, current_user)


@router.get(
    "/{share_id}",
    response_model=WishlistPublicResponse,
    summary="Wishlist compartida (pública por enlace)",
)
def read_shared_wishlist(
    share_id: ShareId,
    db: Annotated[Session, Depends(get_db)],
) -> WishlistPublicResponse:
    return wishlist_service.get_wishlist_by_share_id(db, share_id)


@router.put(
    "/{wishlist_id}",
    response_model=WishlistResponse,
    summary="Editar una wishlist propia (reemplazo completo)",
)
def update_wishlist(
    wishlist_id: int,
    wishlist_in: WishlistUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Wishlist:
    return wishlist_service.update_wishlist(db, wishlist_id, wishlist_in, current_user)


@router.delete(
    "/{wishlist_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Eliminar una wishlist propia y sus artículos",
)
def delete_wishlist(
    wishlist_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    wishlist_service.delete_wishlist(db, wishlist_id, current_user)
