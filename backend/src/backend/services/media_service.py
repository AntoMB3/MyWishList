"""Obtención y almacenamiento de imágenes de artículos.

Dos capas:

1. `fetch_product_image`: lee el HTML del enlace del producto y busca su
   imagen en Open Graph, Twitter Cards o JSON-LD. Solo devuelve la URL; la
   imagen la carga el navegador, no se descarga ni se rehospeda.
2. `store_image`: recibe una foto subida por la persona, la comprime a WebP y
   la guarda en `MEDIA_DIR` con un nombre opaco.

Todo lo que consulta URLs escritas por el usuario pasa por `_assert_public_url`
para evitar peticiones a la red interna (SSRF).
"""

from __future__ import annotations

import ipaddress
import json
import re
import socket
import uuid
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from fastapi import HTTPException, status
from PIL import Image, ImageOps, UnidentifiedImageError

from backend.config import settings
from backend.schemas import MEDIA_URL_PATTERN

MAX_HTML_BYTES = 1_000_000
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_IMAGE_SIDE = 512
WEBP_QUALITY = 60
MAX_STORED_IMAGE_BYTES = 40 * 1024
# Se intenta conservar el tamaño y, si no se alcanza el objetivo de peso,
# se reduce la dimensión y la calidad de forma progresiva.
IMAGE_SIDE_STEPS = tuple(
    dict.fromkeys(
        side
        for side in (MAX_IMAGE_SIDE, 448, 384, 320, 256, 192, 128, 96, 64)
        if side <= MAX_IMAGE_SIDE
    )
)
IMAGE_QUALITY_STEPS = tuple(
    dict.fromkeys(
        quality
        for quality in (WEBP_QUALITY, 50, 40, 30, 20)
        if quality <= WEBP_QUALITY
    )
)
UNFURL_TIMEOUT = httpx.Timeout(5.0, connect=3.0)
MAX_REDIRECTS = 3
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 MyWishList/1.0"
)
_MEDIA_NAME_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.webp$"
)

_INVALID_IMAGE = HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail="El archivo no es una imagen válida.",
)
_IMAGE_TOO_LARGE = HTTPException(
    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
    detail=f"La imagen no puede pesar más de {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
)


class _MetaParser(HTMLParser):
    """Extrae etiquetas `<meta>` y bloques JSON-LD del `<head>`."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.json_ld: list[str] = []
        self._in_json_ld = False
        self._buffer: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        values = {key: value for key, value in attrs}
        if tag == "meta":
            key = values.get("property") or values.get("name")
            content = values.get("content")
            if key and content:
                self.meta.setdefault(key.strip().lower(), content.strip())
        elif tag == "script":
            script_type = (values.get("type") or "").lower()
            if script_type == "application/ld+json":
                self._in_json_ld = True
                self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._in_json_ld:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._in_json_ld:
            self._in_json_ld = False
            block = "".join(self._buffer).strip()
            if block:
                self.json_ld.append(block)
            self._buffer = []


def _assert_public_url(url: str) -> None:
    """Rechaza destinos locales, privados o de metadata de cloud."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("URL no válida.")

    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 80)
    except socket.gaierror as exc:
        raise ValueError("No se pudo resolver el dominio.") from exc

    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise ValueError("El destino no es una dirección pública.")


def _download_html(url: str) -> tuple[str, str]:
    """Descarga como máximo `MAX_HTML_BYTES` siguiendo redirecciones seguras.

    Devuelve `(html, url_final)` para poder resolver imágenes relativas.
    """
    current = url
    with httpx.Client(
        timeout=UNFURL_TIMEOUT,
        follow_redirects=False,
        headers={
            "User-Agent": _USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "es,en;q=0.8",
        },
    ) as client:
        for _ in range(MAX_REDIRECTS + 1):
            _assert_public_url(current)
            with client.stream("GET", current) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise ValueError("Redirección sin destino.")
                    current = urljoin(current, location)
                    continue

                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                if "html" not in content_type.lower():
                    raise ValueError("El destino no es una página HTML.")

                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_HTML_BYTES:
                        raise ValueError("La página es demasiado grande.")
                    chunks.append(chunk)
                return b"".join(chunks).decode(response.encoding or "utf-8", "replace"), current

    raise ValueError("Demasiadas redirecciones.")


def _first_json_ld_image(value: object) -> str | None:
    """Busca recursivamente una URL de imagen en un documento JSON-LD."""
    if isinstance(value, str):
        return value if value.strip() else None
    if isinstance(value, list):
        for entry in value:
            found = _first_json_ld_image(entry)
            if found:
                return found
        return None
    if not isinstance(value, dict):
        return None

    image = value.get("image")
    if isinstance(image, dict):
        image = image.get("url")
    if isinstance(image, str) and image.strip():
        return image.strip()

    for key in ("@graph", "itemListElement", "item"):
        if key in value:
            found = _first_json_ld_image(value[key])
            if found:
                return found
    return None


def _normalize_image_url(candidate: str | None, base_url: str) -> str | None:
    """Convierte referencias relativas y descarta esquemas no web."""
    if not candidate:
        return None
    candidate = candidate.strip()
    if not candidate:
        return None
    absolute = urljoin(base_url, candidate)
    parsed = urlparse(absolute)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return absolute


def extract_image_url(html: str, base_url: str) -> str | None:
    """Devuelve la imagen principal declarada en el HTML, si existe."""
    parser = _MetaParser()
    try:
        parser.feed(html)
    except Exception:  # HTML mal formado: se usa lo ya recolectado.
        pass

    for key in ("og:image", "og:image:url", "og:image:secure_url"):
        image = _normalize_image_url(parser.meta.get(key), base_url)
        if image:
            return image

    for key in ("twitter:image", "twitter:image:src"):
        image = _normalize_image_url(parser.meta.get(key), base_url)
        if image:
            return image

    for block in parser.json_ld:
        data = _parse_json(block)
        if data is None:
            continue
        image = _normalize_image_url(_first_json_ld_image(data), base_url)
        if image:
            return image

    return None


def _parse_json(raw: str) -> object | None:
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


def fetch_product_image(url: str) -> str | None:
    """Intenta obtener la imagen del producto desde su enlace público."""
    try:
        html, final_url = _download_html(url)
    except (ValueError, httpx.HTTPError, OSError):
        return None
    return extract_image_url(html, final_url)


def _media_dir() -> Path:
    path = Path(settings.media_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _encode_webp(image: Image.Image, side: int, quality: int) -> bytes:
    """Codifica una copia redimensionada de la imagen como WebP."""
    candidate = image.copy()
    candidate.thumbnail((side, side), Image.Resampling.LANCZOS)
    output = BytesIO()
    candidate.save(output, format="WEBP", quality=quality, method=6)
    return output.getvalue()


def store_image(data: bytes) -> str:
    """Comprime la imagen recibida y devuelve su ruta pública `/media/...`."""
    if len(data) > MAX_UPLOAD_BYTES:
        raise _IMAGE_TOO_LARGE

    try:
        image = Image.open(BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise _INVALID_IMAGE from exc

    if image.format not in ALLOWED_FORMATS:
        raise _INVALID_IMAGE

    image = ImageOps.exif_transpose(image)
    if image.mode in {"RGBA", "LA"} or (
        image.mode == "P" and "transparency" in image.info
    ):
        image = image.convert("RGBA")
    else:
        image = image.convert("RGB")

    compressed: bytes | None = None
    for side in IMAGE_SIDE_STEPS:
        for quality in IMAGE_QUALITY_STEPS:
            candidate = _encode_webp(image, side, quality)
            if len(candidate) <= MAX_STORED_IMAGE_BYTES:
                compressed = candidate
                break
        if compressed is not None:
            break

    if compressed is None:
        compressed = _encode_webp(
            image,
            IMAGE_SIDE_STEPS[-1],
            IMAGE_QUALITY_STEPS[-1],
        )

    filename = f"{uuid.uuid4()}.webp"
    (_media_dir() / filename).write_bytes(compressed)
    return f"/media/{filename}"


def delete_stored_image(image_url: str | None) -> None:
    """Borra un archivo propio; ignora URLs externas y archivos ausentes."""
    if not image_url or not re.fullmatch(MEDIA_URL_PATTERN, image_url):
        return
    filename = image_url.rsplit("/", 1)[-1]
    if not _MEDIA_NAME_RE.fullmatch(filename):
        return
    (_media_dir() / filename).unlink(missing_ok=True)


def media_path(filename: str) -> Path | None:
    """Resuelve un nombre de archivo propio, sin permitir rutas arbitrarias."""
    if not _MEDIA_NAME_RE.fullmatch(filename):
        return None
    path = _media_dir() / filename
    return path if path.is_file() else None
