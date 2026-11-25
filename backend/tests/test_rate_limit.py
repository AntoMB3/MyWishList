"""Tests del limitador de tasa (unidad y endpoints protegidos)."""

from collections.abc import Iterator
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from backend.config import settings
from backend.dependencies import get_current_user, get_db
from backend.main import app
from backend.models import User
from backend.rate_limit import SlidingWindowLimiter
from backend.services import media_service

PASSWORD = "contraseña-segura"


class FakeClock:
    """Reloj controlable para probar la ventana sin dormir en los tests."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _user() -> User:
    return User(
        id=1,
        username="alex",
        hashed_password="hash",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (32, 32), (10, 80, 160)).save(buffer, format="PNG")
    return buffer.getvalue()


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
def authenticated_client(client: TestClient) -> TestClient:
    app.dependency_overrides[get_current_user] = lambda: _user()
    return client


@pytest.fixture()
def media_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "media_dir", tmp_path)
    return tmp_path


class TestSlidingWindowLimiter:
    def test_allows_up_to_the_limit(self) -> None:
        limiter = SlidingWindowLimiter(clock=FakeClock())

        assert limiter.check("clave", 2, 60) is None
        assert limiter.check("clave", 2, 60) is None

    def test_blocks_over_the_limit_and_reports_retry_after(self) -> None:
        clock = FakeClock()
        limiter = SlidingWindowLimiter(clock=clock)
        limiter.check("clave", 2, 60)
        limiter.check("clave", 2, 60)

        retry_after = limiter.check("clave", 2, 60)

        assert retry_after is not None
        assert 1 <= retry_after <= 60

    def test_allows_again_when_the_window_expires(self) -> None:
        clock = FakeClock()
        limiter = SlidingWindowLimiter(clock=clock)
        limiter.check("clave", 1, 60)
        assert limiter.check("clave", 1, 60) is not None

        clock.now += 61

        assert limiter.check("clave", 1, 60) is None

    def test_keys_are_independent(self) -> None:
        limiter = SlidingWindowLimiter(clock=FakeClock())
        assert limiter.check("ana", 1, 60) is None
        assert limiter.check("luis", 1, 60) is None

    def test_clear_resets_the_state(self) -> None:
        limiter = SlidingWindowLimiter(clock=FakeClock())
        limiter.check("clave", 1, 60)
        assert limiter.check("clave", 1, 60) is not None

        limiter.clear()

        assert limiter.check("clave", 1, 60) is None


class TestLoginRateLimit:
    def test_blocks_after_repeated_failures(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "rate_limit_login_per_minute", 2)

        first = client.post(
            "/api/auth/login", json={"username": "alex", "password": "mala"}
        )
        second = client.post(
            "/api/auth/login", json={"username": "alex", "password": "mala"}
        )
        third = client.post(
            "/api/auth/login", json={"username": "alex", "password": "mala"}
        )

        assert first.status_code == 401
        assert second.status_code == 401
        assert third.status_code == 429
        assert "Retry-After" in third.headers
        assert int(third.headers["Retry-After"]) >= 1


class TestRegisterRateLimit:
    def test_blocks_mass_account_creation(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "rate_limit_register_per_hour", 2)

        def register(username: str):
            return client.post(
                "/api/auth/register",
                json={"username": username, "password": PASSWORD},
            )

        assert register("usuario1").status_code == 201
        assert register("usuario2").status_code == 201

        blocked = register("usuario3")

        assert blocked.status_code == 429
        assert "Retry-After" in blocked.headers


class TestMediaRateLimit:
    def test_upload_is_limited(
        self,
        authenticated_client: TestClient,
        media_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "rate_limit_media_per_minute", 2)
        files = {"file": ("foto.png", _png_bytes(), "image/png")}

        assert authenticated_client.post("/api/media", files=files).status_code == 201
        assert authenticated_client.post("/api/media", files=files).status_code == 201

        blocked = authenticated_client.post("/api/media", files=files)

        assert blocked.status_code == 429

    def test_unfurl_is_limited(
        self,
        authenticated_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "rate_limit_unfurl_per_minute", 2)
        monkeypatch.setattr(
            media_service, "fetch_product_image", lambda url: None
        )
        payload = {"url": "https://tienda.com/producto"}

        assert (
            authenticated_client.post("/api/media/unfurl", json=payload).status_code
            == 200
        )
        assert (
            authenticated_client.post("/api/media/unfurl", json=payload).status_code
            == 200
        )

        blocked = authenticated_client.post("/api/media/unfurl", json=payload)

        assert blocked.status_code == 429


class TestEndpointsWithoutLimit:
    def test_public_config_is_not_limited(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "rate_limit_login_per_minute", 1)
        monkeypatch.setattr(settings, "rate_limit_register_per_hour", 1)

        responses = [client.get("/api/config") for _ in range(5)]

        assert all(response.status_code == 200 for response in responses)
