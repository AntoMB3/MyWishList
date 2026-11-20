"""Endpoints protegidos de artículos, anidados dentro de una wishlist.

`/api/wishlists/{wishlist_id}/items` deja explícita la pertenencia del
artículo y evita aceptar un `wishlist_id` manipulable en el cuerpo.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.dependencies import get_current_user, get_db
from backend.models import User, WishlistItem
from backend.schemas import ItemCreate, ItemResponse, ItemUpdate
from backend.services import item_service

router = APIRouter(
    prefix="/api/wishlists/{wishlist_id}/items",
    tags=["items"],
)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ItemResponse,
    summary="Crear un artículo dentro de una wishlist propia",
)
def create_item(
    wishlist_id: int,
    item_in: ItemCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> WishlistItem:
    return item_service.create_item(db, wishlist_id, item_in, current_user)


@router.put(
    "/{item_id}",
    response_model=ItemResponse,
    summary="Editar un artículo propio (reemplazo completo)",
)
def update_item(
    wishlist_id: int,
    item_id: int,
    item_in: ItemUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> WishlistItem:
    return item_service.update_item(db, wishlist_id, item_id, item_in, current_user)


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Eliminar un artículo propio",
)
def delete_item(
    wishlist_id: int,
    item_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    item_service.delete_item(db, wishlist_id, item_id, current_user)
