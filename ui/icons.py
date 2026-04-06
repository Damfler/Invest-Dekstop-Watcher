"""
icons_gen.py — генерация иконок для трея.
Приоритет: пользовательский файл из icons/ → нарисованная иконка.
v2: красивые стрелки вместо символов +/−
"""
import os
import sys
from PIL import Image, ImageDraw, ImageFont

BASE_DIR       = getattr(sys, '_MEIPASS', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ICONS_DIR      = os.path.join(BASE_DIR, "assets", "icons")

# Для .exe: пользовательские иконки в AppData
if getattr(sys, 'frozen', False):
    _USER_ICONS = os.path.join(
        os.environ.get("APPDATA", os.path.dirname(sys.executable)),
        "InvestDesktopWatcher", "icons")
else:
    _USER_ICONS = ICONS_DIR

ICON_SIZE = 64
R = 14  # радиус скругления


def _load_custom(name: str) -> Image.Image | None:
    """Попытка загрузить пользовательскую иконку."""
    for d in (_USER_ICONS, ICONS_DIR):
        p = os.path.join(d, name)
        try:
            img = Image.open(p).convert("RGBA")
            return img.resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS)
        except Exception:
            continue
    return None


def _draw_arrow_up(draw, color):
    """Стрелка вверх (рост)."""
    cx, cy = ICON_SIZE // 2, ICON_SIZE // 2
    # Треугольник вверх
    pts = [(cx, cy - 16), (cx + 14, cy + 8), (cx - 14, cy + 8)]
    draw.polygon(pts, fill=color)
    # Ножка
    draw.rectangle([cx - 4, cy + 6, cx + 4, cy + 18], fill=color)


def _draw_arrow_down(draw, color):
    """Стрелка вниз (падение)."""
    cx, cy = ICON_SIZE // 2, ICON_SIZE // 2
    pts = [(cx, cy + 16), (cx + 14, cy - 8), (cx - 14, cy - 8)]
    draw.polygon(pts, fill=color)
    draw.rectangle([cx - 4, cy - 18, cx + 4, cy - 6], fill=color)


def _draw_icon(bg, draw_fn, fg=(255, 255, 255)):
    """Рисует иконку с фоном и символом."""
    img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([0, 0, ICON_SIZE - 1, ICON_SIZE - 1],
                            radius=R, fill=bg)
    draw_fn(draw, fg)
    return img


def _draw_text(symbol):
    """Возвращает функцию рисования текстового символа."""
    def fn(draw, fg):
        fs = 26 if len(symbol) > 1 else 36
        try:
            font = ImageFont.truetype("arialbd.ttf", fs)
        except Exception:
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), symbol, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(
            ((ICON_SIZE - tw) / 2 - bbox[0],
             (ICON_SIZE - th) / 2 - bbox[1]),
            symbol, font=font, fill=fg)
    return fn


def make_icon_normal(delta: float, use_custom: bool) -> Image.Image:
    if use_custom:
        name = "positive.png" if delta >= 0 else "negative.png"
        img = _load_custom(name) or _load_custom("icon.png")
        if img:
            return img
    if delta >= 0:
        return _draw_icon((34, 180, 80), _draw_arrow_up)
    else:
        return _draw_icon((220, 50, 50), _draw_arrow_down)


def make_icon_warn(use_custom: bool) -> Image.Image:
    if use_custom:
        img = _load_custom("warn.png") or _load_custom("icon.png")
        if img:
            return img
    return _draw_icon((234, 128, 0), _draw_text("!"))


def make_icon_crit(bright: bool, use_custom: bool) -> Image.Image:
    if use_custom:
        img = _load_custom("crit.png")
        if img:
            if not bright:
                img = img.point(lambda p: int(p * 0.35))
            return img
    bg = (220, 30, 30) if bright else (120, 0, 0)
    return _draw_icon(bg, _draw_text("!!"), fg=(255, 230, 50))
