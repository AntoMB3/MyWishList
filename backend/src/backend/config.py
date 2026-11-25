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

# Claves de ejemplo publicadas en el repositorio. Arrancar con cualquiera de
# ellas permitiría forjar tokens JWT, así que también se rechazan.
INSECURE_SECRET_KEYS = frozenset(
    {
        DEFAULT_DEV_SECRET_KEY,
        "cambia-esta-clave-secreta-por-una-de-al-menos-32-caracteres",
        "cambia-esto-por-un-secreto-largo-y-aleatorio",
    }
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = f"sqlite:///{BASE_DIR / 'whishlist.db'}"
    media_dir: Path = BASE_DIR / "media"
    secret_key: SecretStr = SecretStr(DEFAULT_DEV_SECRET_KEY)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 24 * 60
    max_wishlists_per_user: int = 5
    max_items_per_wishlist: int = 20
    # `None` = automático: Swagger UI solo se publica en desarrollo (cuando la
    # clave es la de por defecto). En producción se oculta salvo que se ponga
    # ENABLE_DOCS=1 de forma explícita.
    enable_docs: bool | None = None
    # Límites de peticiones para los endpoints sensibles (ver `rate_limit.py`).
    rate_limit_login_per_minute: int = 10
    rate_limit_register_per_hour: int = 5
    rate_limit_media_per_minute: int = 10
    rate_limit_unfurl_per_minute: int = 10

    @property
    def uses_default_secret_key(self) -> bool:
        return self.secret_key.get_secret_value() == DEFAULT_DEV_SECRET_KEY

    @property
    def uses_insecure_secret_key(self) -> bool:
        """Indica si la clave es una de las claves de ejemplo del repositorio."""
        return self.secret_key.get_secret_value() in INSECURE_SECRET_KEYS

    @property
    def docs_enabled(self) -> bool:
        """Indica si se publica `/docs` y el esquema OpenAPI."""
        if self.enable_docs is not None:
            return self.enable_docs
        return self.uses_default_secret_key


settings = Settings()


def assert_secure_secret_key() -> None:
    """Impide arrancar con una clave JWT de ejemplo del repositorio.

    Sin esta comprobación, desplegar sin definir `SECRET_KEY` (o copiando el
    valor de `.env.example` sin cambiarlo) deja la aplicación firmando tokens
    con una clave conocida: cualquiera podría forjar un JWT válido de
    cualquier usuario.
    """
    if settings.uses_insecure_secret_key:
        raise RuntimeError(
            "SECRET_KEY no está configurada con un valor propio: se está "
            "usando una clave de ejemplo del repositorio, con la que se "
            "pueden forjar tokens JWT de cualquier usuario. Define SECRET_KEY "
            "en el entorno antes de arrancar (por ejemplo: "
            "`openssl rand -hex 32`)."
        )
