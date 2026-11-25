"""Tests de la configuración sensible: clave JWT y publicación de /docs."""

import pytest
from pydantic import SecretStr

from backend.config import (
    DEFAULT_DEV_SECRET_KEY,
    assert_secure_secret_key,
    settings,
)

CUSTOM_SECRET_KEY = "clave-personalizada-de-al-menos-32-caracteres"


class TestAssertSecureSecretKey:
    def test_rejects_default_development_key(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            settings, "secret_key", SecretStr(DEFAULT_DEV_SECRET_KEY)
        )

        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            assert_secure_secret_key()

    @pytest.mark.parametrize(
        "placeholder",
        [
            "cambia-esta-clave-secreta-por-una-de-al-menos-32-caracteres",
            "cambia-esto-por-un-secreto-largo-y-aleatorio",
        ],
    )
    def test_rejects_placeholder_keys(
        self,
        monkeypatch: pytest.MonkeyPatch,
        placeholder: str,
    ) -> None:
        monkeypatch.setattr(settings, "secret_key", SecretStr(placeholder))

        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            assert_secure_secret_key()

    def test_accepts_custom_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "secret_key", SecretStr(CUSTOM_SECRET_KEY))

        assert_secure_secret_key()  # No debe lanzar.


class TestDocsEnabled:
    def test_enabled_by_default_in_development(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "enable_docs", None)
        monkeypatch.setattr(
            settings, "secret_key", SecretStr(DEFAULT_DEV_SECRET_KEY)
        )

        assert settings.docs_enabled is True

    def test_disabled_with_custom_key(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "enable_docs", None)
        monkeypatch.setattr(settings, "secret_key", SecretStr(CUSTOM_SECRET_KEY))

        assert settings.docs_enabled is False

    def test_explicit_override_wins(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "secret_key", SecretStr(CUSTOM_SECRET_KEY))
        monkeypatch.setattr(settings, "enable_docs", True)
        assert settings.docs_enabled is True

        monkeypatch.setattr(settings, "enable_docs", False)
        assert settings.docs_enabled is False
