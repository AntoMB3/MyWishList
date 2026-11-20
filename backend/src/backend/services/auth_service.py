"""Servicios de autenticación.

Contratos consumidos por `backend.routers.auth`. La implementación real
(hashing de contraseñas y emisión/validación de JWT) llega en la Fase 2
junto con `backend.security`.
"""

from sqlalchemy.orm import Session

from backend.models import User
from backend.schemas import TokenResponse, UserCreate


def register_user(db: Session, user_in: UserCreate) -> User:
    """Crea un usuario nuevo.

    Contrato: lanza `HTTPException(400)` si el username ya está registrado.
    """
    raise NotImplementedError(
        "TODO(Fase 2): implementar registro con hashing de contraseña."
    )


def authenticate_user(db: Session, username: str, password: str) -> TokenResponse:
    """Verifica las credenciales y emite el par de tokens.

    Contrato: lanza `HTTPException(401)` si el usuario no existe o la
    contraseña es incorrecta.
    """
    raise NotImplementedError(
        "TODO(Fase 2): implementar verificación de credenciales y emisión de JWT."
    )
