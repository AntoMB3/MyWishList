"""Servicios de autenticación: registro, credenciales y cambio de contraseña."""

from fastapi import HTTPException, status
from pwdlib.exceptions import PwdlibError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.models import User
from backend.schemas import PasswordChange, TokenResponse, UserCreate
from backend.security import create_access_token, hash_password, verify_password

# Hash de relleno: si el usuario no existe verificamos igualmente una contraseña
# para que el tiempo de respuesta no revele qué usernames están registrados.
_DUMMY_PASSWORD_HASH = hash_password("dummy-password-for-timing")

_USERNAME_TAKEN = HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail="El nombre de usuario ya está registrado.",
)

_INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Usuario o contraseña incorrectos.",
    headers={"WWW-Authenticate": "Bearer"},
)

_WRONG_CURRENT_PASSWORD = HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail="La contraseña actual es incorrecta.",
)

_SAME_PASSWORD = HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail="La nueva contraseña debe ser diferente de la actual.",
)


def register_user(db: Session, user_in: UserCreate) -> User:
    """Crea un usuario nuevo con la contraseña hasheada.

    Lanza `HTTPException(400)` si el username ya está registrado.
    """
    username = user_in.username.strip().lower()
    if db.scalar(select(User.id).where(User.username == username)) is not None:
        raise _USERNAME_TAKEN

    user = User(
        username=username,
        hashed_password=hash_password(user_in.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Condición de carrera: otra petición registró el mismo username.
        db.rollback()
        raise _USERNAME_TAKEN from None

    db.refresh(user)
    return user


def authenticate_user(db: Session, username: str, password: str) -> TokenResponse:
    """Verifica las credenciales y emite un JWT de acceso.

    Lanza `HTTPException(401)` si el usuario no existe o la contraseña no
    coincide (mismo mensaje en ambos casos para no filtrar qué usernames
    existen).
    """
    user = db.scalar(select(User).where(User.username == username.strip().lower()))
    if user is None:
        verify_password(password, _DUMMY_PASSWORD_HASH)
        raise _INVALID_CREDENTIALS

    try:
        password_matches = verify_password(password, user.hashed_password)
    except PwdlibError:
        password_matches = False

    if not password_matches:
        raise _INVALID_CREDENTIALS

    return TokenResponse(
        access_token=create_access_token(
            user.id,
            token_version=user.token_version,
        )
    )


def change_user_password(
    db: Session,
    user: User,
    password_in: PasswordChange,
) -> TokenResponse:
    """Cambia la contraseña de un usuario que ya está autenticado.

    Se exige la contraseña actual para que un token robado o una sesión
    abierta sin supervisión no baste para apropiarse de la cuenta. Lanza
    `HTTPException(400)` si la contraseña actual no coincide o si la nueva es
    idéntica a la anterior.

    Al cambiar la contraseña se incrementa `token_version`, lo que invalida
    todos los JWT emitidos antes (incluidas otras sesiones). Se devuelve un
    token nuevo para que la sesión que hizo el cambio siga activa.
    """
    try:
        current_matches = verify_password(
            password_in.current_password,
            user.hashed_password,
        )
    except PwdlibError:
        current_matches = False

    if not current_matches:
        raise _WRONG_CURRENT_PASSWORD

    if password_in.new_password == password_in.current_password:
        raise _SAME_PASSWORD

    user.hashed_password = hash_password(password_in.new_password)
    user.token_version = (user.token_version or 0) + 1
    db.commit()

    return TokenResponse(
        access_token=create_access_token(
            user.id,
            token_version=user.token_version,
        )
    )

