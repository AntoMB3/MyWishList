"""Configuración pública que el frontend necesita para la interfaz.

Los límites reales se validan siempre en el backend; este endpoint solo
permite que la UI muestre contadores y deshabilite botones sin duplicar
números mágicos en JavaScript.
"""

from fastapi import APIRouter

from backend.config import settings
from backend.schemas import AppConfigResponse
from backend.services import media_service

router = APIRouter(prefix="/api", tags=["config"])


@router.get(
    "/config",
    response_model=AppConfigResponse,
    summary="Límites públicos de la aplicación",
)
def read_config() -> AppConfigResponse:
    return AppConfigResponse(
        max_wishlists_per_user=settings.max_wishlists_per_user,
        max_items_per_wishlist=settings.max_items_per_wishlist,
        max_upload_bytes=media_service.MAX_UPLOAD_BYTES,
        max_image_side=media_service.MAX_IMAGE_SIDE,
        max_stored_image_bytes=media_service.MAX_STORED_IMAGE_BYTES,
    )
