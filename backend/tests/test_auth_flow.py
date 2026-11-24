"""Pruebas de integración del flujo real de autenticación (sin mocks)."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.dependencies import get_db
from backend.main import app
from backend.models import User
from backend.security import decode_access_token

PASSWORD = "secreto123"


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


def _register(client: TestClient, username: str = "Alex") -> None:
    response = client.post(
        "/api/auth/register",
        json={"username": username, "password": PASSWORD},
    )
    assert response.status_code == 201


def _login(client: TestClient, username: str = "alex", password: str = PASSWORD) -> str:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


class TestRegister:
    def test_creates_user_with_hashed_password(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        _register(client)

        user = session.scalar(select(User).where(User.username == "alex"))
        assert user is not None
        assert user.hashed_password != PASSWORD
        assert user.hashed_password.startswith("$argon2")

    def test_username_is_normalized(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        _register(client, username="  Alex_01 ")

        assert session.scalar(select(User).where(User.username == "alex_01")) is not None

    def test_duplicate_username_returns_400(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        _register(client)

        response = client.post(
            "/api/auth/register",
            json={"username": "alex", "password": PASSWORD},
        )
        assert response.status_code == 400
        assert "registrado" in response.json()["detail"]
        assert session.scalar(select(User)) is not None

    def test_duplicate_username_is_case_insensitive(
        self,
        client: TestClient,
    ) -> None:
        _register(client)

        response = client.post(
            "/api/auth/register",
            json={"username": "ALEX", "password": PASSWORD},
        )
        assert response.status_code == 400

    def test_two_different_users_can_register(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        _register(client, username="alex")
        _register(client, username="maria")

        usernames = set(session.scalars(select(User.username)))
        assert usernames == {"alex", "maria"}


class TestLogin:
    def test_returns_bearer_token_for_the_user(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        _register(client)
        user = session.scalar(select(User).where(User.username == "alex"))

        response = client.post(
            "/api/auth/login",
            json={"username": "alex", "password": PASSWORD},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        assert decode_access_token(body["access_token"])["sub"] == str(user.id)

    def test_username_is_case_insensitive(
        self,
        client: TestClient,
    ) -> None:
        _register(client, username="alex")
        assert _login(client, username="ALEX")

    def test_accepts_form_data(
        self,
        client: TestClient,
    ) -> None:
        _register(client)

        response = client.post(
            "/api/auth/login",
            data={"username": "alex", "password": PASSWORD},
        )

        assert response.status_code == 200
        assert response.json()["token_type"] == "bearer"

    def test_wrong_password_returns_401(
        self,
        client: TestClient,
    ) -> None:
        _register(client)

        response = client.post(
            "/api/auth/login",
            json={"username": "alex", "password": "incorrecta"},
        )

        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"

    def test_unknown_user_returns_401_with_same_message(
        self,
        client: TestClient,
    ) -> None:
        _register(client)

        wrong_password = client.post(
            "/api/auth/login",
            json={"username": "alex", "password": "incorrecta"},
        )
        unknown_user = client.post(
            "/api/auth/login",
            json={"username": "nadie", "password": PASSWORD},
        )

        assert wrong_password.status_code == unknown_user.status_code == 401
        assert wrong_password.json()["detail"] == unknown_user.json()["detail"]


class TestAuthenticatedFlow:
    def test_register_login_and_read_me(
        self,
        client: TestClient,
    ) -> None:
        _register(client)
        token = _login(client)

        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        assert response.json()["username"] == "alex"

    def test_token_of_one_user_does_not_impersonate_another(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        _register(client, username="alex")
        _register(client, username="maria")
        token = _login(client, username="alex")

        me = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert me.status_code == 200
        assert me.json()["username"] == "alex"


class TestChangePassword:
    NEW_PASSWORD = "nuevaClave456"

    def test_requires_authentication(self, client: TestClient) -> None:
        response = client.post(
            "/api/auth/change-password",
            json={
                "current_password": PASSWORD,
                "new_password": self.NEW_PASSWORD,
            },
        )

        assert response.status_code == 401

    def test_changes_password_and_allows_login_with_new_one(
        self,
        client: TestClient,
    ) -> None:
        _register(client)
        token = _login(client)

        response = client.post(
            "/api/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "current_password": PASSWORD,
                "new_password": self.NEW_PASSWORD,
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        assert decode_access_token(body["access_token"])["ver"] == 1

        assert _login(client, password=self.NEW_PASSWORD)

        old_password = client.post(
            "/api/auth/login",
            json={"username": "alex", "password": PASSWORD},
        )
        assert old_password.status_code == 401

    def test_previous_token_stops_being_valid(
        self,
        client: TestClient,
    ) -> None:
        _register(client)
        old_token = _login(client)

        response = client.post(
            "/api/auth/change-password",
            headers={"Authorization": f"Bearer {old_token}"},
            json={
                "current_password": PASSWORD,
                "new_password": self.NEW_PASSWORD,
            },
        )
        new_token = response.json()["access_token"]

        stale = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {old_token}"},
        )
        fresh = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {new_token}"},
        )

        assert stale.status_code == 401
        assert fresh.status_code == 200

    def test_other_sessions_are_invalidated(
        self,
        client: TestClient,
    ) -> None:
        _register(client)
        first_token = _login(client)
        second_token = _login(client)

        client.post(
            "/api/auth/change-password",
            headers={"Authorization": f"Bearer {first_token}"},
            json={
                "current_password": PASSWORD,
                "new_password": self.NEW_PASSWORD,
            },
        )

        for token in (first_token, second_token):
            response = client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 401

    def test_wrong_current_password_returns_400(
        self,
        client: TestClient,
    ) -> None:
        _register(client)
        token = _login(client)

        response = client.post(
            "/api/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "current_password": "incorrecta",
                "new_password": self.NEW_PASSWORD,
            },
        )

        assert response.status_code == 400
        assert "actual" in response.json()["detail"]
        assert _login(client, password=PASSWORD)

    def test_wrong_current_password_keeps_session_alive(
        self,
        client: TestClient,
    ) -> None:
        _register(client)
        token = _login(client)

        client.post(
            "/api/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "current_password": "incorrecta",
                "new_password": self.NEW_PASSWORD,
            },
        )

        me = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me.status_code == 200

    def test_same_password_is_rejected(
        self,
        client: TestClient,
    ) -> None:
        _register(client)
        token = _login(client)

        response = client.post(
            "/api/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "current_password": PASSWORD,
                "new_password": PASSWORD,
            },
        )

        assert response.status_code == 400
        assert "diferente" in response.json()["detail"]

    def test_short_new_password_returns_422(
        self,
        client: TestClient,
    ) -> None:
        _register(client)
        token = _login(client)

        response = client.post(
            "/api/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "current_password": PASSWORD,
                "new_password": "corta",
            },
        )

        assert response.status_code == 422
