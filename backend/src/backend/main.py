from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend import models  # noqa: F401  (registra las tablas en Base.metadata)
from backend.config import BASE_DIR
from backend.database import Base, engine
from backend.routers import auth, items, wishlists

FRONTEND_DIR = BASE_DIR.parent / "frontend"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="MyWishList API",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(wishlists.router)
app.include_router(items.router)

# El frontend se sirve desde el mismo origen que la API. El montaje va al
# final para que las rutas /api, /docs y /openapi.json tengan prioridad.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


def main() -> None:
    import uvicorn

    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
