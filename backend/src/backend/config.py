from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def _resolve_base_dir() -> Path:
    """Devuelve el directorio del proyecto backend.

    En instalaciones editables con layout ``src/`` el módulo vive en
    ``<backend>/src/backend/config.py``. En instalaciones no editables (por
    ejemplo, la imagen Docker con ``uv sync --no-editable``) el paquete se
    copia a ``site-packages``, así que se busca hacia arriba el directorio
    que contiene tanto ``backend/`` como ``frontend/``.
    """
    package_dir = Path(__file__).resolve().parent
    if package_dir.parent.name == "src":
        return package_dir.parent.parent
    for parent in package_dir.parents:
        if (parent / "backend").is_dir() and (parent / "frontend").is_dir():
            return parent / "backend"
    return package_dir.parent


BASE_DIR = _resolve_base_dir()

# Solo se usa si no existe `.env`; en producción SIEMPRE definir SECRET_KEY.
DEFAULT_DEV_SECRET_KEY = "dev-secret-key-change-me-0123456789abcdef"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = f"sqlite:///{BASE_DIR / 'whishlist.db'}"
    secret_key: SecretStr = SecretStr(DEFAULT_DEV_SECRET_KEY)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 24 * 60

    @property
    def uses_default_secret_key(self) -> bool:
        return self.secret_key.get_secret_value() == DEFAULT_DEV_SECRET_KEY


settings = Settings()
