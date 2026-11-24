"""Endpoints de `/api/auth`: registro, login y datos del usuario actual."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.dependencies import get_current_user, get_db
from backend.models import User
from backend.schemas import (
    PasswordChange,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)
from backend.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])

LOGIN_OPENAPI_EXTRA = {
    "requestBody": {
        "required": True,
        "content": {
            "application/x-www-form-urlencoded": {
                "schema": {
                    "type": "object",
                    "required": ["username", "password"],
                    "properties": {
                        "username": {"type": "string"},
                        "password": {"type": "string", "format": "password"},
                    },
                }
            },
            "application/json": {"schema": UserLogin.model_json_schema()},
        },
    }
}


async def login_credentials(request: Request) -> UserLogin:
    """Extrae las credenciales del login aceptando JSON o form-data.

    - `application/json`: usado por el frontend (`fetch`).
    - `application/x-www-form-urlencoded`: usado por el botón *Authorize*
      de Swagger UI (`OAuth2PasswordRequestForm`).
    """
    content_type = request.headers.get("content-type", "")
    try:
        if content_type.startswith("application/json"):
            payload = await request.json()
            if not isinstance(payload, dict):
                raise RequestValidationError(
                    [
                        {
                            "type": "model_attributes_type",
                            "loc": ("body",),
                            "msg": "El cuerpo debe ser un objeto JSON.",
                            "input": payload,
                        }
                    ]
                )
            return UserLogin.model_validate(payload)

        form = await request.form()
        return UserLogin(
            username=str(form.get("username", "")),
            password=str(form.get("password", "")),
        )
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=UserResponse,
    summary="Registrar un usuario",
)
def register(
    user_in: UserCreate,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    return auth_service.register_user(db, user_in)


@router.post(
    "/login",
    response_model=TokenResponse,
    openapi_extra=LOGIN_OPENAPI_EXTRA,
    summary="Autenticar y obtener un token JWT",
)
def login(
    credentials: Annotated[UserLogin, Depends(login_credentials)],
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    return auth_service.authenticate_user(
        db,
        username=credentials.username,
        password=credentials.password,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Datos del usuario autenticado",
)
def read_current_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    return current_user


@router.post(
    "/change-password",
    response_model=TokenResponse,
    summary="Cambiar la contraseña del usuario autenticado",
)
def change_password(
    password_in: PasswordChange,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    return auth_service.change_user_password(db, current_user, password_in)
