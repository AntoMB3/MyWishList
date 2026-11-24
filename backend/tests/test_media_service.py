from io import BytesIO
from pathlib import Path

import pytest
from fastapi import HTTPException
from PIL import Image

from backend.config import settings
from backend.services import media_service


@pytest.fixture()
def media_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "media_dir", tmp_path)
    return tmp_path


def _image_bytes(
    size: tuple[int, int] = (1600, 1200),
    image_format: str = "PNG",
) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, (20, 120, 200)).save(buffer, format=image_format)
    return buffer.getvalue()


class TestExtractImageUrl:
    def test_reads_open_graph_image(self) -> None:
        html = '<meta property="og:image" content="https://cdn.example.com/foto.jpg">'
        assert (
            media_service.extract_image_url(html, "https://tienda.com/p/1")
            == "https://cdn.example.com/foto.jpg"
        )

    def test_resolves_relative_open_graph_image(self) -> None:
        html = '<meta property="og:image" content="/media/foto.jpg">'
        assert (
            media_service.extract_image_url(html, "https://tienda.com/producto/1")
            == "https://tienda.com/media/foto.jpg"
        )

    def test_falls_back_to_twitter_image(self) -> None:
        html = '<meta name="twitter:image" content="https://cdn.example.com/tw.jpg">'
        assert (
            media_service.extract_image_url(html, "https://tienda.com/p/1")
            == "https://cdn.example.com/tw.jpg"
        )

    def test_reads_json_ld_image_object(self) -> None:
        html = (
            '<script type="application/ld+json">'
            '{"@type": "Product", "image": {"url": "/img/producto.webp"}}'
            "</script>"
        )
        assert (
            media_service.extract_image_url(html, "https://tienda.com/p/1")
            == "https://tienda.com/img/producto.webp"
        )

    def test_ignores_non_http_image(self) -> None:
        html = '<meta property="og:image" content="javascript:alert(1)">'
        assert media_service.extract_image_url(html, "https://tienda.com") is None

    def test_returns_none_without_declared_image(self) -> None:
        html = "<html><head><title>Sin imagen</title></head></html>"
        assert media_service.extract_image_url(html, "https://tienda.com") is None

    def test_survives_broken_json_ld(self) -> None:
        html = '<script type="application/ld+json">{no es json}</script>'
        assert media_service.extract_image_url(html, "https://tienda.com") is None


class TestPublicUrlGuard:
    @pytest.mark.parametrize(
        "url",
        [
            "http://127.0.0.1/admin",
            "http://localhost/admin",
            "http://169.254.169.254/latest/meta-data",
            "http://10.0.0.5/",
            "ftp://example.com/archivo",
        ],
    )
    def test_rejects_non_public_destinations(self, url: str) -> None:
        with pytest.raises(ValueError):
            media_service._assert_public_url(url)


class TestStoreImage:
    def test_compresses_and_stores_webp(self, media_dir: Path) -> None:
        image_url = media_service.store_image(_image_bytes())

        assert image_url.startswith("/media/")
        assert image_url.endswith(".webp")

        stored = media_dir / image_url.rsplit("/", 1)[-1]
        assert stored.is_file()
        with Image.open(stored) as image:
            assert image.format == "WEBP"
            assert max(image.size) <= media_service.MAX_IMAGE_SIDE

    def test_rejects_non_image_bytes(self, media_dir: Path) -> None:
        with pytest.raises(HTTPException) as exc_info:
            media_service.store_image(b"no soy una imagen")

        assert exc_info.value.status_code == 400

    def test_rejects_file_over_the_limit(self, media_dir: Path) -> None:
        oversized = b"0" * (media_service.MAX_UPLOAD_BYTES + 1)

        with pytest.raises(HTTPException) as exc_info:
            media_service.store_image(oversized)

        assert exc_info.value.status_code == 413

    def test_deletes_only_own_files(self, media_dir: Path) -> None:
        image_url = media_service.store_image(_image_bytes())
        stored = media_dir / image_url.rsplit("/", 1)[-1]

        media_service.delete_stored_image("https://example.com/foto.jpg")
        assert stored.is_file()

        media_service.delete_stored_image(image_url)
        assert not stored.exists()

    def test_media_path_rejects_traversal(self, media_dir: Path) -> None:
        assert media_service.media_path("../whishlist.db") is None
        assert media_service.media_path("no-existe.webp") is None
