"""Limitador de tasa en memoria para los endpoints sensibles.

Protege el login y el registro frente a fuerza bruta y creación masiva de
cuentas, y limita la subida de fotos y la consulta de imágenes remotas
(`unfurl`), que consumen CPU y ancho de banda del servidor.

El despliegue Docker usa un único worker de uvicorn, así que el estado en
memoria del proceso es suficiente. Si en el futuro se escala a varios
workers o réplicas, habrá que compartir el estado (por ejemplo, con Redis).
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status

from backend.config import settings
from backend.dependencies import get_current_user
from backend.models import User

# Cada cuántas comprobaciones se descartan las claves ya inactivas.
_PRUNE_EVERY = 512
# Ninguna ventana configurada supera esta duración.
_MAX_WINDOW_SECONDS = 3600.0

_RETRY_DETAIL = "Demasiadas peticiones. Espera unos segundos e inténtalo de nuevo."


class SlidingWindowLimiter:
    """Ventana deslizante por clave con reloj inyectable (para los tests)."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._checks = 0

    def check(self, key: str, limit: int, window: float) -> float | None:
        """Registra un intento para `key`.

        Devuelve los segundos que faltan para poder reintentar si se superó
        el límite, o `None` si la petición está permitida.
        """
        now = self._clock()
        with self._lock:
            self._checks += 1
            if self._checks % _PRUNE_EVERY == 0:
                self._prune(now)

            events = self._events.get(key)
            if events is None:
                events = deque()
                self._events[key] = events
            else:
                cutoff = now - window
                while events and events[0] <= cutoff:
                    events.popleft()

            if len(events) >= limit:
                return max(events[0] + window - now, 1.0)

            events.append(now)
            return None

    def clear(self) -> None:
        """Vacía el estado; los tests lo usan para aislarse entre casos."""
        with self._lock:
            self._events.clear()
            self._checks = 0

    def _prune(self, now: float) -> None:
        """Descarta claves sin actividad reciente para no crecer sin límite."""
        for key, events in list(self._events.items()):
            if not events or now - events[-1] > _MAX_WINDOW_SECONDS:
                del self._events[key]


_limiter = SlidingWindowLimiter()


def reset_rate_limiter() -> None:
    """Vacía el estado del limitador; pensado para aislar los tests."""
    _limiter.clear()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "desconocido"


def _enforce(key: str, limit: int, window: float) -> None:
    retry_after = _limiter.check(key, limit, window)
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=_RETRY_DETAIL,
            headers={"Retry-After": str(int(retry_after) + 1)},
        )


def anonymous_rate_limit(
    scope: str,
    setting_name: str,
    window: float,
) -> Callable[..., None]:
    """Dependencia de FastAPI que limita por IP (endpoints anónimos).

    El límite se lee de `settings` en cada petición para que pueda
    ajustarse por entorno y monkeyparchearse en los tests.
    """

    def dependency(request: Request) -> None:
        limit = int(getattr(settings, setting_name))
        _enforce(f"{scope}:{_client_ip(request)}", limit, window)

    return dependency


def authenticated_rate_limit(
    scope: str,
    setting_name: str,
    window: float,
) -> Callable[..., None]:
    """Dependencia de FastAPI que limita por usuario autenticado."""

    def dependency(current_user: User = Depends(get_current_user)) -> None:
        limit = int(getattr(settings, setting_name))
        _enforce(f"{scope}:user:{current_user.id}", limit, window)

    return dependency
