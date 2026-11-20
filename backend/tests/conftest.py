from collections.abc import Iterator

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend import models  # noqa: F401  (registra las tablas en Base.metadata)
from backend.database import Base, create_db_engine


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
