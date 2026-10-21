"""Newsletter card images: illustration + baked-in company badge (DataCamp-like cards).

Each card is a 528x370 PNG (shown at 264x185 in the email) built as:

1. Base image, first that works of:
   a. AI illustration via OpenRouter's image API (`POST /api/v1/images`, response
      `data[0].b64_json`), house style in `prompts.CARD_IMAGE_PROMPT`.
   b. The article's source image (`Article.image_url`) or its `og:image`/`twitter:image`.
   c. A branded placeholder drawn with Pillow (dark gradient with orange/yellow glow).
2. Cover-crop to 528x370, white badge tab at the bottom-left (logo + company name,
   rounded top-right corner) and rounded image corners baked into the alpha channel
   (Outlook ignores CSS border-radius).

Nothing here raises to the caller for a bad image source: every failure logs a
warning and falls through to the next option.
"""
from __future__ import annotations

import base64
import hashlib
import io
import os
import random
import re
import sys
import time
import unicodedata
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

import httpx
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps

from agente_noticias.config import get_image_model, get_image_quality, images_enabled
from agente_noticias.logos import display_name, logo_path
from agente_noticias.prompts import CARD_IMAGE_PROMPT

# Geometry (2x of the 264x185 display size).
CARD_SIZE = (528, 370)
CORNER_RADIUS = 16
BADGE_HEIGHT = 64
BADGE_RADIUS = 20
BADGE_PAD_LEFT = 18
BADGE_PAD_RIGHT = 22
BADGE_GAP = 10
# Outlook on the web silently drops large inline (CID) images: verified 2026-10-21 that
# ~43 KB cards render while a 283 KB full-color PNG shows as a blank 1x1 placeholder.
MAX_CARD_BYTES = 100_000
CARD_PALETTE_STEPS = (192, 128, 64, 32)
LOGO_HEIGHT = 36
BADGE_FONT_SIZE = 26
SUPERSAMPLE = 4

# WIN palette.
DARK = (15, 9, 8)  # #0F0908
NAVY = (12, 22, 48)
ORANGE = (255, 90, 10)  # #FF5A0A
YELLOW = (255, 194, 0)  # #FFC200
BADGE_TEXT = DARK

OPENROUTER_IMAGES_URL = "https://openrouter.ai/api/v1/images"
IMAGE_TIMEOUT = 120.0
HTTP_TIMEOUT = 15.0
MAX_HTML_BYTES = 1_500_000
MAX_IMAGE_BYTES = 12_000_000
MIN_SOURCE_SIZE = (200, 120)
MAX_SOURCE_PIXELS = 40_000_000  # reject decompression bombs before decoding
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/141.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,image/avif,image/webp,image/*,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
}

_FONTS_DIR = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
_FONT_CANDIDATES = (_FONTS_DIR / "segoeuib.ttf", _FONTS_DIR / "arialbd.ttf")
_META_IMAGE_KEYS = (
    "og:image",
    "og:image:secure_url",
    "og:image:url",
    "twitter:image",
    "twitter:image:src",
)


class ImageGenerationError(RuntimeError):
    """The OpenRouter image call failed (message carries status + provider error)."""


def _warn(message: str) -> None:
    print(f"[card_images] WARNING: {message}", file=sys.stderr)


# --------------------------------------------------------------------------- #
# Base image sources
# --------------------------------------------------------------------------- #
def _open_image(data: bytes) -> Image.Image:
    """Decodes image bytes, rejecting tiny images (icons, tracking pixels)."""
    img = Image.open(io.BytesIO(data))
    if img.width < MIN_SOURCE_SIZE[0] or img.height < MIN_SOURCE_SIZE[1]:
        raise ValueError(f"image too small ({img.width}x{img.height})")
    if img.width * img.height > MAX_SOURCE_PIXELS:
        raise ValueError(f"image too large ({img.width}x{img.height})")
    img.load()
    return img


def decode_image_response(payload: dict) -> Image.Image:
    """Extracts the first image of an OpenRouter `/api/v1/images` response."""
    items = payload.get("data") or []
    if not items:
        raise ImageGenerationError(f"response has no images: {str(payload)[:300]}")
    first = items[0]
    data = first.get("b64_json") or ""
    if not data and str(first.get("url", "")).startswith("data:"):
        data = first["url"]
    if data:
        if data.startswith("data:"):
            data = data.split(",", 1)[1]
        return _open_image(base64.b64decode(data))
    if first.get("url"):
        return download_image(first["url"])
    raise ImageGenerationError("response image has neither b64_json nor url")


def _error_message(resp: httpx.Response) -> str:
    try:
        body = resp.json()
        err = body.get("error") if isinstance(body, dict) else None
        if isinstance(err, dict):
            return str(err.get("message") or err)[:300]
        return str(body)[:300]
    except ValueError:
        return resp.text[:300]


def generate_illustration(
    subject: str,
    *,
    model: str | None = None,
    quality: str | None = None,
    api_key: str | None = None,
    timeout: float = IMAGE_TIMEOUT,
) -> Image.Image:
    """Generates the card illustration with OpenRouter (1 retry on network/5xx/429)."""
    api_key = api_key or os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise ImageGenerationError("OPENROUTER_API_KEY is not set")
    payload = {
        "model": model or get_image_model(),
        "prompt": CARD_IMAGE_PROMPT.format(subject=subject.strip()),
        "aspect_ratio": "3:2",
        "quality": quality or get_image_quality(),
        "n": 1,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    last_error: ImageGenerationError | None = None
    for attempt in range(2):
        if attempt:
            time.sleep(3)
        try:
            resp = httpx.post(OPENROUTER_IMAGES_URL, json=payload, headers=headers, timeout=timeout)
        except httpx.HTTPError as exc:
            last_error = ImageGenerationError(f"request failed: {type(exc).__name__}: {exc}")
            continue
        if resp.status_code == 429 or resp.status_code >= 500:
            last_error = ImageGenerationError(f"HTTP {resp.status_code}: {_error_message(resp)}")
            continue
        if resp.status_code >= 400:
            raise ImageGenerationError(f"HTTP {resp.status_code}: {_error_message(resp)}")
        try:
            payload_json = resp.json()
        except ValueError as exc:
            raise ImageGenerationError(f"non-JSON response: {resp.text[:200]!r}") from exc
        if not isinstance(payload_json, dict):
            raise ImageGenerationError(f"unexpected response: {str(payload_json)[:300]}")
        try:
            return decode_image_response(payload_json)
        except ImageGenerationError:
            raise
        except Exception as exc:  # noqa: BLE001 - bad base64 / undecodable image
            raise ImageGenerationError(f"undecodable image: {type(exc).__name__}: {exc}") from exc
    assert last_error is not None
    raise last_error


def _http_get(url: str, max_bytes: int, *, truncate: bool) -> bytes:
    """GET with a browser-like UA and a size cap (truncate HTML, reject huge images)."""
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"unsupported URL: {url[:100]}")
    with httpx.Client(follow_redirects=True, timeout=HTTP_TIMEOUT, headers=BROWSER_HEADERS) as client:
        with client.stream("GET", url) as resp:
            resp.raise_for_status()
            declared = resp.headers.get("Content-Length", "")
            if not truncate and declared.isdigit() and int(declared) > max_bytes:
                raise ValueError(f"response larger than {max_bytes} bytes")
            buf = bytearray()
            for chunk in resp.iter_bytes():
                buf.extend(chunk)
                if len(buf) > max_bytes:
                    if truncate:
                        break
                    raise ValueError(f"response larger than {max_bytes} bytes")
            return bytes(buf)


def download_image(url: str) -> Image.Image:
    """Downloads and validates an image URL."""
    return _open_image(_http_get(url, MAX_IMAGE_BYTES, truncate=False))


class _MetaImageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.found: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "meta":
            return
        attr = {k.lower(): (v or "").strip() for k, v in attrs}
        key = (attr.get("property") or attr.get("name") or "").lower()
        if key in _META_IMAGE_KEYS and attr.get("content"):
            self.found.setdefault(key, attr["content"])


def parse_og_image(html: str, base_url: str = "") -> str | None:
    """Returns the absolute og:image (or twitter:image) URL declared in `html`."""
    parser = _MetaImageParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # noqa: BLE001 - malformed HTML: use whatever was found
        pass
    for key in _META_IMAGE_KEYS:
        if key in parser.found:
            url = urljoin(base_url, parser.found[key])
            if url.startswith(("http://", "https://")):
                return url
    return None


def fetch_og_image(page_url: str) -> Image.Image | None:
    """Downloads the article page and its og:image; None if the page declares none."""
    html = _http_get(page_url, MAX_HTML_BYTES, truncate=True).decode("utf-8", errors="replace")
    image_url = parse_og_image(html, page_url)
    return download_image(image_url) if image_url else None


def _glow(size: tuple[int, int], color: tuple[int, int, int], strength: float) -> Image.Image:
    """Soft radial glow layer (RGBA) of the given size."""
    # radial_gradient: 0 at the centre, 181 at the edge midpoints, 255 at the corners.
    # Fade to exactly 0 at the inscribed circle so the square layer leaves no edges.
    mask = Image.radial_gradient("L").resize(size, Image.BICUBIC)
    mask = mask.point(lambda v: int(255 * strength * max(0.0, 1 - v / 181) ** 2.2))
    layer = Image.new("RGBA", size, color + (0,))
    layer.putalpha(mask)
    return layer


def placeholder_image(seed: str = "") -> Image.Image:
    """Branded fallback: dark gradient with an orange and a yellow glow."""
    w, h = CARD_SIZE
    rnd = random.Random(seed)
    gradient = Image.linear_gradient("L").rotate(90).resize((w, h))
    img = Image.composite(
        Image.new("RGBA", (w, h), NAVY + (255,)),
        Image.new("RGBA", (w, h), DARK + (255,)),
        gradient,
    )
    for color, scale, strength in ((ORANGE, 1.25, 0.85), (YELLOW, 0.6, 0.7)):
        size = int(h * scale)
        cx = rnd.uniform(0.45, 0.8) * w
        cy = rnd.uniform(0.25, 0.6) * h
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        layer.paste(_glow((size, size), color, strength), (int(cx - size / 2), int(cy - size / 2)))
        img.alpha_composite(layer)
    return img


# --------------------------------------------------------------------------- #
# Composition
# --------------------------------------------------------------------------- #
def bold_font(size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    """Bold sans font: Segoe UI Bold, then Arial Bold, then DejaVu / Pillow default."""
    for path in _FONT_CANDIDATES:
        if path.is_file():
            try:
                return ImageFont.truetype(str(path), size)
            except OSError:
                continue
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
    except OSError:
        return ImageFont.load_default(size)


def _load_logo(company: str, logos_dir: Path | None) -> Image.Image | None:
    path = logo_path(company, logos_dir)
    if path is None:
        return None
    try:
        logo = Image.open(path).convert("RGBA")
    except Exception as exc:  # noqa: BLE001
        _warn(f"unreadable logo {path.name}: {exc}")
        return None
    width = max(1, round(logo.width * LOGO_HEIGHT / logo.height))
    return logo.resize((width, LOGO_HEIGHT), Image.LANCZOS)


def _draw_badge(img: Image.Image, company: str, logos_dir: Path | None) -> None:
    """White tab at the bottom-left with the logo + company name."""
    w, h = img.size
    name = display_name(company)
    font = bold_font(BADGE_FONT_SIZE)
    draw = ImageDraw.Draw(img)
    logo = _load_logo(company, logos_dir)

    content_w = int(draw.textlength(name, font=font))
    if logo is not None:
        content_w += logo.width + BADGE_GAP
    badge_w = min(w, BADGE_PAD_LEFT + content_w + BADGE_PAD_RIGHT)
    top = h - BADGE_HEIGHT

    # Supersampled shape; only the top-right corner is rounded (the others fall
    # outside the canvas, and the bottom-left is clipped by the image corner).
    s = SUPERSAMPLE
    r = BADGE_RADIUS * s
    mask = Image.new("L", (badge_w * s, BADGE_HEIGHT * s), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (-r, 0, badge_w * s - 1, BADGE_HEIGHT * s + r), radius=r, fill=255
    )
    mask = mask.resize((badge_w, BADGE_HEIGHT), Image.LANCZOS)
    img.paste((255, 255, 255, 255), (0, top, badge_w, h), mask)

    x = BADGE_PAD_LEFT
    if logo is not None:
        img.alpha_composite(logo, (x, top + (BADGE_HEIGHT - logo.height) // 2))
        x += logo.width + BADGE_GAP
    draw.text((x, top + BADGE_HEIGHT / 2), name, font=font, fill=BADGE_TEXT + (255,), anchor="lm")


def _round_corners(img: Image.Image, radius: int) -> None:
    w, h = img.size
    s = SUPERSAMPLE
    mask = Image.new("L", (w * s, h * s), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w * s - 1, h * s - 1), radius=radius * s, fill=255)
    mask = mask.resize((w, h), Image.LANCZOS)
    img.putalpha(ImageChops.multiply(img.getchannel("A"), mask))


def compose_card(
    base: Image.Image, company: str | None, logos_dir: Path | None = None
) -> Image.Image:
    """Cover-crops `base` to the card size, adds the badge (if any) and rounds corners."""
    fitted = ImageOps.fit(base.convert("RGBA"), CARD_SIZE, Image.LANCZOS)
    card = Image.new("RGBA", CARD_SIZE, DARK + (255,))
    card.alpha_composite(fitted)
    if company:
        _draw_badge(card, company, logos_dir)
    _round_corners(card, CORNER_RADIUS)
    return card


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def card_filename(title: str, url: str = "") -> str:
    """Filesystem-safe `<slug>-<hash>.png` for an article."""
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-")[:60].rstrip("-")
    digest = hashlib.sha1((url or title).encode("utf-8")).hexdigest()[:8]
    return f"{slug or 'noticia'}-{digest}.png"


def _illustration_subject(title: str, summary: str, visual_subject: str) -> str:
    if visual_subject.strip():
        return visual_subject.strip()
    return f"An abstract visual metaphor for this news: {title}. {summary}"[:500]


def save_card_png(card: Image.Image, out_path: Path) -> int:
    """Save the card as PNG under MAX_CARD_BYTES, keeping alpha corners.

    Full color first (smooth gradients like the placeholder band when quantized), then
    palette PNGs with fewer colors until the file fits; returns the final size in bytes.
    """
    buf = io.BytesIO()
    card.save(buf, "PNG", optimize=True)
    data = buf.getvalue()
    for colors in CARD_PALETTE_STEPS if len(data) > MAX_CARD_BYTES else ():
        quantized = card.convert("RGBA").quantize(colors=colors, method=Image.Quantize.FASTOCTREE)
        buf = io.BytesIO()
        quantized.save(buf, "PNG", optimize=True)
        data = buf.getvalue()
        if len(data) <= MAX_CARD_BYTES:
            break
    if len(data) > MAX_CARD_BYTES:
        _warn(
            f"{out_path.name} is {len(data) // 1024} KB (> {MAX_CARD_BYTES // 1000} KB): "
            "Outlook on the web may show it blank"
        )
    out_path.write_bytes(data)
    return len(data)


def build_card_image(
    *,
    out_path: Path,
    title: str,
    summary: str = "",
    visual_subject: str = "",
    company: str | None = None,
    image_url: str | None = None,
    article_url: str | None = None,
    generate: bool | None = None,
) -> Path:
    """Builds and saves one card PNG. Never fails because of an image source."""
    if generate is None:
        generate = images_enabled()

    base: Image.Image | None = None
    source = "placeholder"
    if generate:
        try:
            base = generate_illustration(_illustration_subject(title, summary, visual_subject))
            source = "ai"
        except Exception as exc:  # noqa: BLE001
            _warn(f"AI illustration failed for '{title[:60]}': {exc}")

    fallbacks = (
        ("image_url", lambda: download_image(image_url) if image_url else None),
        ("og:image", lambda: fetch_og_image(article_url) if article_url else None),
    )
    for label, fetch in fallbacks:
        if base is not None:
            break
        try:
            base = fetch()
            if base is not None:
                source = label
        except Exception as exc:  # noqa: BLE001
            _warn(f"{label} fallback failed for '{title[:60]}': {exc}")

    if base is None:
        base = placeholder_image(seed=article_url or title)

    card = compose_card(base, company)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    save_card_png(card, out_path)
    print(f"[card_images] {out_path.name} ({source}, company={company or '-'})")
    return out_path
