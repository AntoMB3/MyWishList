"""Hashing de contraseñas y firma/validación de tokens JWT.

- Contraseñas: Argon2 mediante `pwdlib` (nunca se almacena texto plano).
- Tokens: JWT firmados con HS256 usando `SECRET_KEY` del entorno.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash

from backend.config import settings

password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Devuelve el hash Argon2 de `password`."""
    return password_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Comprueba si `plain_password` corresponde al hash almacenado."""
    return password_hasher.verify(plain_password, hashed_password)


def create_access_token(
    subject: int | str,
    expires_delta: timedelta | None = None,
    token_version: int = 0,
) -> str:
    """Firma un JWT con el `sub` indicado (normalmente el id del usuario).

    `ver` guarda la versión de credenciales del usuario: al cambiar la
    contraseña se incrementa en la base de datos y todos los tokens emitidos
    antes dejan de ser válidos.
    """
    now = datetime.now(UTC)
    expires_at = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload = {
        "sub": str(subject),
        "ver": token_version,
        "iat": now,
        "exp": expires_at,
    }
    return jwt.encode(
        payload,
        settings.secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """Valida la firma y la expiración del token y devuelve su payload.

    Lanza `jwt.InvalidTokenError` (o una subclase) si el token no es válido.
    """
    return jwt.decode(
        token,
        settings.secret_key.get_secret_value(),
        algorithms=[settings.jwt_algorithm],
    )
