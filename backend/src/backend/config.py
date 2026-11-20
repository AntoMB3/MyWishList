from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]

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
