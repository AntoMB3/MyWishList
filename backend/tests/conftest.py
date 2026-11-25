from collections.abc import Iterator

import pytest
from pydantic import SecretStr
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend import models  # noqa: F401  (registra las tablas en Base.metadata)
from backend.config import settings
from backend.database import Base, create_db_engine
from backend.rate_limit import reset_rate_limiter

TEST_SECRET_KEY = "clave-de-test-para-firmar-tokens-jwt-0123456789"


@pytest.fixture(autouse=True)
def _secure_test_secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Evita que el guard de producción detenga los tests de lifespan.

    `assert_secure_secret_key` rechaza arrancar con la clave pública de
    desarrollo; los tests no definen `SECRET_KEY`, así que se inyecta una.
    """
    monkeypatch.setattr(settings, "secret_key", SecretStr(TEST_SECRET_KEY))


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> Iterator[None]:
    """Aísla los tests: cada uno empieza con el limitador vacío."""
    reset_rate_limiter()
    yield
    reset_rate_limiter()


@pytest.fixture()
def engine() -> Iterator[Engine]:
    """Engine SQLite en memoria con la misma configuración que producción."""
    test_engine = create_db_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(test_engine)
    yield test_engine
    test_engine.dispose()


@pytest.fixture()
def session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as db_session:
        yield db_session
