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

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database import Base, SessionLocal, engine, migrate_users_token_version
from backend.models import User
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


if __name__ == "__main__":
    raise SystemExit(main())
