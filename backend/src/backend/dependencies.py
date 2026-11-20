from collections.abc import Iterator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models import User
from backend.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="No se pudieron validar las credenciales.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Resuelve el usuario autenticado a partir del Bearer token."""
    try:
        payload = decode_access_token(token)
        subject = payload["sub"]
        user_id = int(subject)
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise CREDENTIALS_EXCEPTION from None

    user = db.get(User, user_id)
    if user is None:
        raise CREDENTIALS_EXCEPTION
    return user
