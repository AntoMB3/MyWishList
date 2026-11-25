# ==========================================================================
# MyWishList — Dockerfile de producción (FastAPI + Frontend estático)
# ==========================================================================
FROM python:3.14-slim

# Instalar uv desde la imagen oficial
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PORT=8000 \
    DATABASE_URL=sqlite:////data/whishlist.db \
    MEDIA_DIR=/data/media

WORKDIR /app

# 1. Instalar dependencias primero para aprovechar la caché de capas de Docker
COPY backend/pyproject.toml backend/uv.lock ./backend/
WORKDIR /app/backend
RUN uv sync --frozen --no-dev --no-install-project

# 2. Copiar el código fuente del backend y el frontend
WORKDIR /app
COPY backend ./backend
COPY frontend ./frontend

# 3. Instalar el paquete backend en el entorno virtual
WORKDIR /app/backend
RUN uv sync --frozen --no-dev --no-editable

# Directorio persistente para la base de datos SQLite y usuario no-root
RUN mkdir -p /data/media && \
    adduser --disabled-password --gecos "" appuser && \
    chown -R appuser:appuser /app /data

USER appuser

VOLUME ["/data"]

EXPOSE 8000

# Usa $PORT (compatible con Fly.io, Railway, Render y Docker local)
# Detrás de un proxy inverso hay que definir FORWARDED_ALLOW_IPS con la IP del
# proxy (o * si el contenedor solo es accesible a través de él) para que el
# limitador de tasa use la IP real del cliente y no la del proxy.
CMD ["sh", "-c", "uv run --no-sync uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips \"${FORWARDED_ALLOW_IPS:-127.0.0.1}\""]
