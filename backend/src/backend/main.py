from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles

from backend import models  # noqa: F401  (registra las tablas en Base.metadata)
from backend.config import BASE_DIR, assert_secure_secret_key, settings
from backend.database import Base, engine, migrate_image_url_nullable, migrate_users_token_version
from backend.routers import auth, config, items, media, wishlists

FRONTEND_DIR = BASE_DIR.parent / "frontend"

# Cabeceras que se añaden a todas las respuestas. La CSP es estricta: el
# frontend carga scripts y estilos propios (sin inline) y las imágenes de los
# artículos pueden ser https externas o rutas /media propias.
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; "
        "img-src 'self' https: data:; "
        "style-src 'self'; "
        "script-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Cross-Origin-Opener-Policy": "same-origin",
}

# Rutas que quedan fuera de la CSP: Swagger UI carga sus recursos desde un CDN
# y solo se publica en desarrollo (ver `settings.docs_enabled`).
_CSP_EXEMPT_PREFIXES = ("/docs", "/redoc", "/openapi.json")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    assert_secure_secret_key()
    Base.metadata.create_all(bind=engine)
    migrate_users_token_version(engine)
    migrate_image_url_nullable(engine)
    yield


app = FastAPI(
    title="MyWishList API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)


@app.middleware("http")
async def disable_static_html_cache(request: Request, call_next) -> Response:
    response: Response = await call_next(request)
    if not request.url.path.startswith(("/api", "/media")):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.middleware("http")
async def add_security_headers(request: Request, call_next) -> Response:
    response: Response = await call_next(request)
    for name, value in SECURITY_HEADERS.items():
        if name == "Content-Security-Policy" and request.url.path.startswith(
            _CSP_EXEMPT_PREFIXES
        ):
            continue
        response.headers[name] = value
    return response


app.include_router(auth.router)
app.include_router(config.router)
app.include_router(wishlists.router)
app.include_router(items.router)
app.include_router(media.router)
app.include_router(media.media_router)

# El frontend se sirve desde el mismo origen que la API. El montaje va al
# final para que las rutas /api, /docs y /openapi.json tengan prioridad.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


def main() -> None:
    import uvicorn

    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
