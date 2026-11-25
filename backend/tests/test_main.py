"""Tests de la app: cabeceras de seguridad y publicación de la documentación."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.main import SECURITY_HEADERS, app

CSP_HEADER = "Content-Security-Policy"


@pytest.fixture()
def client() -> Iterator[TestClient]:
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        test_client.close()


class TestSecurityHeaders:
    def test_html_frontend_has_all_headers(self, client: TestClient) -> None:
        response = client.get("/")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        for name in SECURITY_HEADERS:
            assert name in response.headers

    def test_api_json_has_all_headers(self, client: TestClient) -> None:
        response = client.get("/api/config")

        assert response.status_code == 200
        for name in SECURITY_HEADERS:
            assert name in response.headers

    def test_media_response_has_all_headers(
        self,
        client: TestClient,
    ) -> None:
        # Un archivo inexistente sigue pasando por el middleware (404).
        response = client.get("/media/inexistente.webp")

        assert response.status_code == 404
        for name in SECURITY_HEADERS:
            assert name in response.headers

    def test_csp_blocks_inline_scripts(self, client: TestClient) -> None:
        csp = client.get("/").headers[CSP_HEADER]

        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "unsafe-inline" not in csp

    def test_docs_skips_csp_but_keeps_other_headers(
        self,
        client: TestClient,
    ) -> None:
        # En los tests la app se construye sin `.env` (clave de desarrollo),
        # así que /docs está disponible. Swagger UI carga su JS desde un CDN
        # y no debe recibir la CSP del frontend.
        response = client.get("/docs")

        assert response.status_code == 200
        assert CSP_HEADER not in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"


class TestDocsPublication:
    def test_docs_enabled_with_development_settings(self) -> None:
        # `app` se construye en import-time con la configuración de desarrollo.
        assert app.docs_url == "/docs"
        assert app.openapi_url == "/openapi.json"

    def test_openapi_schema_is_served(self, client: TestClient) -> None:
        response = client.get("/openapi.json")

        assert response.status_code == 200
        assert response.json()["info"]["title"] == "MyWishList API"
