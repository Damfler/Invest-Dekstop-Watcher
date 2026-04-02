"""
icons.py — генерация иконок для трея.
Приоритет: пользовательский файл из icons/ → нарисованная иконка.
"""
import os
import sys
from PIL import Image, ImageDraw, ImageFont

BASE_DIR       = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
ICONS_DIR      = os.path.join(BASE_DIR, "icons")
ICON_POS_FILE  = os.path.join(ICONS_DIR, "positive.png")
ICON_NEG_FILE  = os.path.join(ICONS_DIR, "negative.png")
ICON_WARN_FILE = os.path.join(ICONS_DIR, "warn.png")
ICON_CRIT_FILE = os.path.join(ICONS_DIR, "crit.png")

ICON_SIZE = 64


def _load_custom(path: str) -> Image.Image | None:
    try:
        img = Image.open(path).convert("RGBA")
        return img.resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS)
    except Exception:
        return None


def _draw_icon(bg: tuple, symbol: str,
               fg: tuple = (255, 255, 255)) -> Image.Image:
    img  = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([0, 0, ICON_SIZE - 1, ICON_SIZE - 1],
                            radius=14, fill=bg)
    font_size = 26 if len(symbol) > 1 else 36
    try:
        font = ImageFont.truetype("arialbd.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), symbol, font=font)
    tw   = bbox[2] - bbox[0]
    th   = bbox[3] - bbox[1]
    draw.text(
        ((ICON_SIZE - tw) / 2 - bbox[0],
         (ICON_SIZE - th) / 2 - bbox[1]),
        symbol, font=font, fill=fg,
    )
    return img


def make_icon_normal(delta: float, use_custom: bool) -> Image.Image:
    if use_custom:
        path = ICON_POS_FILE if delta >= 0 else ICON_NEG_FILE
        img  = _load_custom(path)
        if img:
            return img
    bg = (34, 197, 94) if delta >= 0 else (239, 68, 68)
    return _draw_icon(bg, "+" if delta >= 0 else "−")


def make_icon_warn(use_custom: bool) -> Image.Image:
    if use_custom:
        img = _load_custom(ICON_WARN_FILE)
        if img:
            return img
    return _draw_icon((234, 128, 0), "⚠")


def make_icon_crit(bright: bool, use_custom: bool) -> Image.Image:
    if use_custom:
        img = _load_custom(ICON_CRIT_FILE)
        if img:
            if not bright:
                img = img.point(lambda p: int(p * 0.35))
            return img
    bg = (220, 30, 30) if bright else (120, 0, 0)
    return _draw_icon(bg, "!!", fg=(255, 230, 50))
