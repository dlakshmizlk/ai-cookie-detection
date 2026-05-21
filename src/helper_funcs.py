"""Small utility helpers used across the scraper."""

from __future__ import annotations

import base64
import re
from io import BytesIO
from urllib.parse import urlparse

from PIL import Image


def normalize_url(url: str) -> str:
    """Strip whitespace and ensure the URL has an http(s):// scheme."""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def b64_to_pil(b64_string: str) -> Image.Image:
    """Decode a base64 string (or data URL) into a PIL Image."""
    if b64_string.startswith("data:"):
        b64_string = b64_string.split(",", 1)[1]
    image_bytes = base64.b64decode(b64_string)
    return Image.open(BytesIO(image_bytes))


_NON_SLUG_CHARS = re.compile(r"[^a-z0-9.-]+")


def hostname_slug(url: str, max_len: int = 48) -> str:
    """Produce a filesystem-safe slug from the URL's hostname.

    Examples:
        https://www.lg.com/us/      -> "lg.com"
        https://cricut.com          -> "cricut.com"
        https://kinolorber.com/shop -> "kinolorber.com"
        (invalid)                   -> "unknown"

    Any leading ``www.`` is dropped (cosmetic — fewer near-duplicate
    folder names). Characters outside ``[a-z0-9.-]`` are replaced
    with ``_``. The result is truncated to ``max_len`` characters to
    keep folder names well-behaved.
    """
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        host = ""
    if host.startswith("www."):
        host = host[4:]
    host = _NON_SLUG_CHARS.sub("_", host)
    host = host.strip("._-")
    return host[:max_len] or "unknown"
