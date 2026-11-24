from typing import Any

from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.config import settings

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _enable_sqlite_foreign_keys(
    dbapi_connection: Any,
    connection_record: Any,
) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_db_engine(database_url: str, **engine_kwargs: Any) -> Engine:
    is_sqlite = database_url.startswith("sqlite")
    db_engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False} if is_sqlite else {},
        pool_pre_ping=True,
        **engine_kwargs,
    )
    if is_sqlite:
        event.listen(db_engine, "connect", _enable_sqlite_foreign_keys)
    return db_engine


engine = create_db_engine(settings.database_url)

SessionLocal = sessionmaker(bind=engine, class_=Session, autoflush=False, expire_on_commit=False)


def migrate_image_url_nullable(db_engine: Engine) -> None:
    """Quita el `NOT NULL` de `wishlist_items.image_url` en bases ya creadas.

    `create_all` no modifica columnas existentes. SQLite no permite cambiar
    una restricción con `ALTER COLUMN`, así que se copia el valor a una
    columna temporal y se reemplaza la original (SQLite >= 3.35).
    """
    if db_engine.dialect.name != "sqlite":
        return

    with db_engine.begin() as connection:
        columns = connection.exec_driver_sql(
            "PRAGMA table_info(wishlist_items)"
        ).mappings().all()
        target = next((row for row in columns if row["name"] == "image_url"), None)
        if target is None or not target["notnull"]:
            return

        connection.exec_driver_sql(
            "ALTER TABLE wishlist_items ADD COLUMN image_url_tmp VARCHAR(2048)"
        )
        connection.exec_driver_sql(
            "UPDATE wishlist_items SET image_url_tmp = image_url"
        )
        connection.exec_driver_sql("ALTER TABLE wishlist_items DROP COLUMN image_url")
        connection.exec_driver_sql(
            "ALTER TABLE wishlist_items RENAME COLUMN image_url_tmp TO image_url"
        )