"""Endpoints de imágenes de artículos.

- `POST /api/media/unfurl`: intenta sacar la imagen del enlace del producto.
- `POST /api/media`: sube una foto, la comprime y la guarda.
- `GET /media/{filename}`: sirve las fotos propias ya almacenadas.

Solo la descarga de fotos es pública (quien tenga el enlace de la wishlist
debe ver las tarjetas). Publicar y consultar metadatos exige autenticación.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from backend.dependencies import get_current_user
from backend.models import User
from backend.rate_limit import authenticated_rate_limit
from backend.schemas import (
    MediaUploadResponse,
    UnfurlRequest,
    UnfurlResponse,
)
from backend.services import media_service

router = APIRouter(prefix="/api/media", tags=["media"])
media_router = APIRouter(tags=["media"])


@router.post(
    "/unfurl",
    response_model=UnfurlResponse,
    summary="Buscar la imagen principal del enlace de un producto",
    dependencies=[
        Depends(authenticated_rate_limit("unfurl", "rate_limit_unfurl_per_minute", 60))
    ],
)
def unfurl_image(
    payload: UnfurlRequest,
    _current_user: Annotated[User, Depends(get_current_user)],
) -> UnfurlResponse:
    image_url = media_service.fetch_product_image(str(payload.url))
    return UnfurlResponse(image_url=image_url)


@router.post(
    "",
    response_model=MediaUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Subir una foto del producto (se comprime a WebP)",
    dependencies=[
        Depends(authenticated_rate_limit("media", "rate_limit_media_per_minute", 60))
    ],
)
async def upload_image(
    _current_user: Annotated[User, Depends(get_current_user)],
    file: Annotated[UploadFile, File(description="Imagen JPEG, PNG o WebP")],
) -> MediaUploadResponse:
    data = await file.read(media_service.MAX_UPLOAD_BYTES + 1)
    return MediaUploadResponse(image_url=media_service.store_image(data))


@media_router.get(
    "/media/{filename}",
    response_class=FileResponse,
    summary="Servir una foto almacenada",
)
def get_media(filename: str) -> FileResponse:
    path = media_service.media_path(filename)
    if path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Imagen no encontrada.",
        )
    return FileResponse(
        path,
        media_type="image/webp",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
