"""
Генерация иконок через Pillow (для pystray)
"""
from PIL import Image, ImageDraw, ImageFont


def _make(color: str) -> Image.Image:
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Круг заданного цвета
    d.ellipse([4, 4, size - 4, size - 4], fill=color)
    # Буква A
    try:
        font = ImageFont.truetype("arial.ttf", 28)
    except Exception:
        font = ImageFont.load_default()
    d.text((size // 2, size // 2), "A", fill="white", font=font, anchor="mm")
    return img


def online() -> Image.Image:
    return _make("#16a34a")   # зелёный


def offline() -> Image.Image:
    return _make("#dc2626")   # красный


def pending() -> Image.Image:
    return _make("#64748b")   # серый
