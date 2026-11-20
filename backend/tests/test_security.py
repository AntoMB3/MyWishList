from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.config import settings
from backend.dependencies import get_db
from backend.main import app
from backend.models import User
from backend.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

PASSWORD = "secreto123"


class TestPasswordHashing:
    def test_hash_is_not_plaintext(self) -> None:
        hashed = hash_password(PASSWORD)
        assert hashed != PASSWORD
        assert hashed.startswith("$argon2")

    def test_verify_correct_password(self) -> None:
        assert verify_password(PASSWORD, hash_password(PASSWORD)) is True

    def test_verify_wrong_password(self) -> None:
        assert verify_password("otra-cosa", hash_password(PASSWORD)) is False

    def test_each_hash_uses_a_different_salt(self) -> None:
        assert hash_password(PASSWORD) != hash_password(PASSWORD)


class TestJwt:
    def test_token_roundtrip(self) -> None:
        token = create_access_token(42)
        payload = decode_access_token(token)
        assert payload["sub"] == "42"
        assert "exp" in payload
        assert "iat" in payload

    def test_subject_is_stored_as_string(self) -> None:
        assert decode_access_token(create_access_token(7))["sub"] == "7"

    def test_expired_token_is_rejected(self) -> None:
        token = create_access_token(1, expires_delta=timedelta(minutes=-1))
        with pytest.raises(jwt.ExpiredSignatureError):
            decode_access_token(token)

    def test_token_signed_with_another_secret_is_rejected(self) -> None:
        now = datetime.now(UTC)
        foreign_token = jwt.encode(
            {"sub": "1", "iat": now, "exp": now + timedelta(minutes=5)},
            "otro-secreto-que-no-es-el-nuestro-0123456789",
            algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(jwt.InvalidSignatureError):
            decode_access_token(foreign_token)

    def test_tampered_token_is_rejected(self) -> None:
        token = create_access_token(1)
        tampered = f"{token[:-3]}abc"
        with pytest.raises(jwt.InvalidTokenError):
            decode_access_token(tampered)


@pytest.fixture()
def client(session: Session) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        yield session

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        test_client.close()
        app.dependency_overrides.clear()


@pytest.fixture()
def user(session: Session) -> User:
    db_user = User(username="alex", hashed_password=hash_password(PASSWORD))
    session.add(db_user)
    session.commit()
    return db_user


class TestGetCurrentUser:
    def test_valid_token_resolves_user(self, client: TestClient, user: User) -> None:
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {create_access_token(user.id)}"},
        )
        assert response.status_code == 200
        assert response.json()["username"] == "alex"

    def test_unknown_user_is_rejected(self, client: TestClient) -> None:
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {create_access_token(999)}"},
        )
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"

    def test_invalid_token_is_rejected(self, client: TestClient) -> None:
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer esto-no-es-un-jwt"},
        )
        assert response.status_code == 401

    def test_expired_token_is_rejected(self, client: TestClient, user: User) -> None:
        expired = create_access_token(user.id, expires_delta=timedelta(minutes=-1))
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {expired}"},
        )
        assert response.status_code == 401

    def test_token_with_non_numeric_subject_is_rejected(
        self,
        client: TestClient,
    ) -> None:
        now = datetime.now(UTC)
        weird_token = jwt.encode(
            {"sub": "alex", "iat": now, "exp": now + timedelta(minutes=5)},
            settings.secret_key.get_secret_value(),
            algorithm=settings.jwt_algorithm,
        )
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {weird_token}"},
        )
        assert response.status_code == 401
