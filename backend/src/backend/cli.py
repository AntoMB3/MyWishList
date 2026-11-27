"""Comandos de administración de MyWishList.

MyWishList no recoge correo electrónico ni teléfono, así que la recuperación
de contraseña la realiza quien administra la instancia: genera una contraseña
temporal, se la comunica al usuario por un canal de confianza y el usuario la
cambia desde la aplicación.

Uso:
    uv run reset-password <usuario>
    uv run reset-password <usuario> --password "nueva-contraseña"

En Docker:
    docker exec -it <contenedor> uv run --no-sync reset-password <usuario>
"""

import argparse
import secrets
import string
import sys
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import (
    Base,
    SessionLocal,
    create_db_engine,
    engine,
    migrate_image_url_nullable,
    migrate_users_token_version,
)
from backend.models import User, Wishlist, WishlistItem
from backend.schemas import PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH
from backend.security import hash_password

TEMP_PASSWORD_LENGTH = 14
TEMP_PASSWORD_ALPHABET = string.ascii_letters + string.digits


def generate_temporary_password(length: int = TEMP_PASSWORD_LENGTH) -> str:
    """Devuelve una contraseña aleatoria criptográficamente segura."""
    return "".join(secrets.choice(TEMP_PASSWORD_ALPHABET) for _ in range(length))


def reset_user_password(
    db: Session,
    username: str,
    new_password: str,
) -> User | None:
    """Reemplaza el hash de la contraseña del usuario indicado.

    El `username` se normaliza igual que en el registro y el login. Devuelve
    `None` si el usuario no existe y lanza `ValueError` si la contraseña no
    cumple la longitud permitida.
    """
    if not PASSWORD_MIN_LENGTH <= len(new_password) <= PASSWORD_MAX_LENGTH:
        raise ValueError(
            f"La contraseña debe tener entre {PASSWORD_MIN_LENGTH} y "
            f"{PASSWORD_MAX_LENGTH} caracteres."
        )

    user = db.scalar(select(User).where(User.username == username.strip().lower()))
    if user is None:
        return None

    user.hashed_password = hash_password(new_password)
    # Invalida cualquier JWT emitido antes del reseteo.
    user.token_version = (user.token_version or 0) + 1
    db.commit()
    return user


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reset-password",
        description=(
            "Genera una contraseña temporal para un usuario de MyWishList. "
            "Comunícasela por un canal de confianza y pídele que la cambie "
            "al iniciar sesión."
        ),
    )
    parser.add_argument("username", help="Nombre de usuario (sin distinguir mayúsculas).")
    parser.add_argument(
        "--password",
        "-p",
        default=None,
        help=(
            "Contraseña concreta en lugar de una temporal aleatoria. "
            f"Debe tener entre {PASSWORD_MIN_LENGTH} y {PASSWORD_MAX_LENGTH} caracteres."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada del comando `reset-password`."""
    args = _build_parser().parse_args(argv)
    new_password = args.password or generate_temporary_password()

    # Garantiza que las tablas y columnas existan aunque el servidor aún no se
    # haya arrancado contra esta base de datos.
    Base.metadata.create_all(bind=engine)
    migrate_users_token_version(engine)

    with SessionLocal() as db:
        try:
            user = reset_user_password(db, args.username, new_password)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2

    if user is None:
        print(f'Error: el usuario "{args.username}" no existe.', file=sys.stderr)
        return 1

    print(f"Contraseña actualizada para @{user.username}.")
    print(f"Contraseña temporal: {new_password}")
    print("El usuario debe cambiarla desde la aplicación tras iniciar sesión.")
    return 0


def migrate_database_data(
    source_engine: Engine,
    target_engine: Engine,
) -> dict[str, int]:
    """Copia usuarios, wishlists y artículos de una base de datos a otra.

    Exige que la base de datos destino esté vacía para evitar conflictos de
    claves primarias o duplicados accidentales.
    """
    migrate_users_token_version(source_engine)
    migrate_image_url_nullable(source_engine)

    Base.metadata.create_all(bind=target_engine)
    migrate_users_token_version(target_engine)
    migrate_image_url_nullable(target_engine)

    with Session(source_engine) as src, Session(target_engine) as dst:
        if (dst.scalar(select(func.count(User.id))) or 0) > 0:
            raise ValueError(
                "La base de datos destino no está vacía. Usa una base limpia para migrar."
            )

        users = list(src.scalars(select(User).order_by(User.id)))
        wishlists = list(src.scalars(select(Wishlist).order_by(Wishlist.id)))
        items = list(src.scalars(select(WishlistItem).order_by(WishlistItem.id)))

        for user in users:
            dst.add(
                User(
                    id=user.id,
                    username=user.username,
                    hashed_password=user.hashed_password,
                    token_version=user.token_version,
                    created_at=user.created_at,
                )
            )
        dst.flush()

        for wishlist in wishlists:
            dst.add(
                Wishlist(
                    id=wishlist.id,
                    title=wishlist.title,
                    description=wishlist.description,
                    share_id=wishlist.share_id,
                    user_id=wishlist.user_id,
                    created_at=wishlist.created_at,
                )
            )
        dst.flush()

        for item in items:
            dst.add(
                WishlistItem(
                    id=item.id,
                    title=item.title,
                    price=item.price,
                    description=item.description,
                    url=item.url,
                    image_url=item.image_url,
                    wishlist_id=item.wishlist_id,
                    created_at=item.created_at,
                )
            )
        dst.commit()

    if target_engine.dialect.name == "postgresql":
        with target_engine.begin() as conn:
            for table in ("users", "wishlists", "wishlist_items"):
                conn.exec_driver_sql(
                    f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM {table}), 1), "
                    f"(SELECT COUNT(*) > 0 FROM {table}))"
                )

    return {
        "users": len(users),
        "wishlists": len(wishlists),
        "wishlist_items": len(items),
    }


def _build_migrate_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="migrate-db",
        description=(
            "Migra los datos de MyWishList entre bases de datos "
            "(por ejemplo, de SQLite a PostgreSQL o MySQL)."
        ),
    )
    parser.add_argument(
        "--from",
        dest="source_url",
        required=True,
        help="URL de la base de datos origen (ej. sqlite:///./whishlist.db).",
    )
    parser.add_argument(
        "--to",
        dest="target_url",
        default=None,
        help="URL de la base de datos destino (por defecto usa DATABASE_URL).",
    )
    return parser


def migrate_db_main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada del comando `migrate-db`."""
    args = _build_migrate_parser().parse_args(argv)
    target_url = args.target_url or settings.database_url

    if args.source_url == target_url:
        print(
            "Error: la base de datos origen y destino son la misma.",
            file=sys.stderr,
        )
        return 2

    source_engine = create_db_engine(args.source_url)
    target_engine = create_db_engine(target_url)
    try:
        counts = migrate_database_data(source_engine, target_engine)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        source_engine.dispose()
        target_engine.dispose()

    print(
        f"Migración completada: {counts['users']} usuarios, "
        f"{counts['wishlists']} wishlists, "
        f"{counts['wishlist_items']} artículos."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
