from typing import Any

from sqlalchemy import MetaData, create_engine, event, inspect
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


def normalize_database_url(database_url: str) -> str:
    """Adapta esquemas comunes de proveedores cloud al driver instalado."""
    if database_url.startswith("postgres://"):
        return "postgresql+psycopg://" + database_url.removeprefix("postgres://")
    if database_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + database_url.removeprefix("postgresql://")
    if database_url.startswith("mysql://"):
        return "mysql+pymysql://" + database_url.removeprefix("mysql://")
    return database_url


def create_db_engine(database_url: str, **engine_kwargs: Any) -> Engine:
    normalized_url = normalize_database_url(database_url)
    is_sqlite = normalized_url.startswith("sqlite")
    db_engine = create_engine(
        normalized_url,
        connect_args={"check_same_thread": False} if is_sqlite else {},
        pool_pre_ping=True,
        **engine_kwargs,
    )
    if is_sqlite:
        event.listen(db_engine, "connect", _enable_sqlite_foreign_keys)
    return db_engine


engine = create_db_engine(settings.database_url)

SessionLocal = sessionmaker(bind=engine, class_=Session, autoflush=False, expire_on_commit=False)


def migrate_users_token_version(db_engine: Engine) -> None:
    """Añade `users.token_version` a bases creadas antes de este campo.

    `create_all` no modifica tablas existentes. El valor por defecto `0`
    mantiene válidos los tokens emitidos antes de la actualización: solo se
    invalidan cuando el usuario cambia su contraseña.
    """
    inspector = inspect(db_engine)
    if not inspector.has_table("users"):
        return
    if any(col["name"] == "token_version" for col in inspector.get_columns("users")):
        return

    with db_engine.begin() as connection:
        connection.exec_driver_sql(
            "ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0"
        )


def migrate_image_url_nullable(db_engine: Engine) -> None:
    """Quita el `NOT NULL` de `wishlist_items.image_url` en bases ya creadas.

    `create_all` no modifica columnas existentes. SQLite no permite cambiar
    una restricción con `ALTER COLUMN`, así que se copia el valor a una
    columna temporal y se reemplaza la original (SQLite >= 3.35).
    """
    inspector = inspect(db_engine)
    if not inspector.has_table("wishlist_items"):
        return
    target = next(
        (col for col in inspector.get_columns("wishlist_items") if col["name"] == "image_url"),
        None,
    )
    if target is None or target["nullable"]:
        return

    dialect = db_engine.dialect.name
    with db_engine.begin() as connection:
        if dialect == "sqlite":
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
        elif dialect == "postgresql":
            connection.exec_driver_sql(
                "ALTER TABLE wishlist_items ALTER COLUMN image_url DROP NOT NULL"
            )
        elif dialect in {"mysql", "mariadb"}:
            connection.exec_driver_sql(
                "ALTER TABLE wishlist_items MODIFY COLUMN image_url VARCHAR(2048) NULL"
            )