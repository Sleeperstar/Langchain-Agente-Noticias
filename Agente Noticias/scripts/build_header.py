"""Builds the static email header banner `agente_noticias/assets/header_noticias_ia.png`.

The header is an image (not an orange `bgcolor` cell) because Outlook on the web in
dark mode rewrites light background colors (#FF5A0A becomes a dark red) but never
recolors images. Layout at 2x (shown at 600x110 in the email):

    WIN orange background, transparent rounded top corners (matches the 12px container),
    white WIN logo on the left, "NOTICIAS IA" in white bold caps on the right.

Saved as a PNG under `card_images.MAX_CARD_BYTES` (Outlook web drops larger inline
images): full color when it fits, palette-quantized otherwise. Re-run after changing the logo or the brand colors:

    uv run python scripts/build_header.py
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from PIL import Image, ImageChops, ImageDraw  # noqa: E402

from agente_noticias.card_images import (  # noqa: E402
    MAX_CARD_BYTES,
    ORANGE,
    SUPERSAMPLE,
    bold_font,
    save_card_png,
)
from agente_noticias.config import HEADER_PATH, LOGO_PATH  # noqa: E402

# Geometry (2x of the 600x110 display size).
HEADER_SIZE = (1200, 220)
TOP_RADIUS = 24
PAD_X = 48
LOGO_HEIGHT = 114  # 57 px displayed, as the previous HTML header
LABEL = "NOTICIAS IA"
LABEL_FONT_SIZE = 40  # ~13 px on a 390 px wide phone
LABEL_TRACKING = 7 # extra px between letters (letter-spacing)
WHITE = (255, 255, 255, 255)


def _round_top_corners(img: Image.Image, radius: int) -> None:
    """Makes the top-left/top-right corners transparent (bottom stays square)."""
    w, h = img.size
    s = SUPERSAMPLE
    mask = Image.new("L", (w * s, h * s), 0)
    r = radius * s
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w * s - 1, h * s + r), radius=r, fill=255)
    mask = mask.resize((w, h), Image.LANCZOS)
    img.putalpha(ImageChops.multiply(img.getchannel("A"), mask))


def _draw_tracked_text(img: Image.Image, text: str, right: int, center_y: int) -> None:
    """Draws `text` right-aligned at `right` with LABEL_TRACKING letter-spacing."""
    font = bold_font(LABEL_FONT_SIZE)
    draw = ImageDraw.Draw(img)
    widths = [draw.textlength(ch, font=font) for ch in text]
    total = sum(widths) + LABEL_TRACKING * (len(text) - 1)
    x = right - total
    for ch, w in zip(text, widths):
        draw.text((x, center_y), ch, font=font, fill=WHITE, anchor="lm")
        x += w + LABEL_TRACKING


def build_header(logo_path: Path = LOGO_PATH) -> Image.Image:
    w, h = HEADER_SIZE
    img = Image.new("RGBA", HEADER_SIZE, ORANGE + (255,))
    logo = Image.open(logo_path).convert("RGBA")
    logo_w = max(1, round(logo.width * LOGO_HEIGHT / logo.height))
    logo = logo.resize((logo_w, LOGO_HEIGHT), Image.LANCZOS)
    img.alpha_composite(logo, (PAD_X, (h - LOGO_HEIGHT) // 2))
    _draw_tracked_text(img, LABEL, right=w - PAD_X, center_y=h // 2)
    _round_top_corners(img, TOP_RADIUS)
    return img


def save_header_png(img: Image.Image, out_path: Path) -> int:
    """Full-color PNG (exact brand orange, clean alpha) if it fits the budget, else palette."""
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    if buf.tell() <= MAX_CARD_BYTES:
        out_path.write_bytes(buf.getvalue())
        return buf.tell()
    return save_card_png(img, out_path)


def main() -> int:
    HEADER_PATH.parent.mkdir(parents=True, exist_ok=True)
    size = save_header_png(build_header(), HEADER_PATH)
    print(f"{HEADER_PATH} ({HEADER_SIZE[0]}x{HEADER_SIZE[1]}, {size / 1000:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
