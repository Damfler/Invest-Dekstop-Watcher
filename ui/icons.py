"""
icons.py — генератор иконок трея Stack.

Рисует логотип Stack (3 наклонных слоя с округлёнными углами) поверх
цветного squircle-фона. Цвет фона определяется состоянием портфеля:
  positive — зелёный, negative — красный, neutral — серый,
  warn — оранжевый, crit — красный с белым силуэтом и миганием.

Если в `assets/icons/` или `%APPDATA%\\Stack\\icons\\` есть PNG
с соответствующим именем (positive.png и т.д.) — он имеет приоритет,
но только при config["use_custom_icons"] == True.
"""
import os
import sys
from PIL import Image, ImageDraw

BASE_DIR  = getattr(sys, '_MEIPASS', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ICONS_DIR = os.path.join(BASE_DIR, "assets", "icons")

if getattr(sys, 'frozen', False):
    _USER_ICONS = os.path.join(
        os.environ.get("APPDATA", os.path.dirname(sys.executable)),
        "Stack", "icons")
else:
    _USER_ICONS = ICONS_DIR

ICON_SIZE = 64

# Палитра (RGBA)
_GREEN     = ( 52, 199,  89, 255)
_RED       = (255,  59,  48, 255)
_RED_DIM   = (120,   0,   0, 255)
_GREY      = (142, 142, 147, 255)
_ORANGE    = (255, 149,   0, 255)
_BLACK     = (  0,   0,   0, 255)
_WHITE     = (255, 255, 255, 255)
_WHITE_DIM = (180, 180, 180, 255)


def _load_custom(name: str) -> Image.Image | None:
    """Ищет PNG в %APPDATA%\\Stack\\icons или в assets/icons."""
    for d in (_USER_ICONS, ICONS_DIR):
        p = os.path.join(d, name)
        try:
            img = Image.open(p).convert("RGBA")
            return img.resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS)
        except Exception:
            continue
    return None


def _draw_stack(fg: tuple, bg: tuple, size: int = ICON_SIZE, ss: int = 4) -> Image.Image:
    """Логотип Stack: 3 наклонных слоя `fg` поверх squircle-фона `bg`.

    Геометрия повторяет `assets/icons/banks/stack.svg`.
    Рендер при ss-кратном размере для антиалиасинга, затем downsample.
    """
    s = size * ss
    img  = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * 0.22), fill=bg)

    bar_w  = int(s * 0.55)
    bar_h  = int(s * 0.135)
    slant  = int(s * 0.10)
    gap    = int(s * 0.05)
    step_x = int(s * 0.075)
    bar_r  = int(bar_h * 0.40)
    canvas_w = bar_w + slant

    bar = Image.new("RGBA", (canvas_w, bar_h), (0, 0, 0, 0))
    ImageDraw.Draw(bar).rounded_rectangle(
        [0, 0, bar_w - 1, bar_h - 1], radius=bar_r, fill=fg)
    sheared = bar.transform(
        (canvas_w, bar_h), Image.AFFINE,
        (1, slant / bar_h, -slant, 0, 1, 0),
        resample=Image.BICUBIC,
    )

    total_h = 3 * bar_h + 2 * gap
    y0 = (s - total_h) // 2
    x_center = (s - canvas_w) // 2
    for i in range(3):
        x = x_center + (1 - i) * step_x
        y = y0 + i * (bar_h + gap)
        img.alpha_composite(sheared, (x, y))

    return img.resize((size, size), Image.LANCZOS)


def make_icon_normal(delta: float, use_custom: bool) -> Image.Image:
    if use_custom:
        if delta > 0:
            name = "positive.png"
        elif delta < 0:
            name = "negative.png"
        else:
            name = "neutral.png"
        img = _load_custom(name) or _load_custom("icon.png")
        if img:
            return img
    if delta > 0:
        return _draw_stack(_BLACK, _GREEN)
    if delta < 0:
        return _draw_stack(_BLACK, _RED)
    return _draw_stack(_BLACK, _GREY)


def make_icon_warn(use_custom: bool) -> Image.Image:
    if use_custom:
        img = _load_custom("warn.png") or _load_custom("icon.png")
        if img:
            return img
    return _draw_stack(_BLACK, _ORANGE)


def make_icon_crit(bright: bool, use_custom: bool) -> Image.Image:
    if use_custom:
        img = _load_custom("crit.png")
        if img:
            if not bright:
                img = img.point(lambda p: int(p * 0.35))
            return img
    bg = _RED if bright else _RED_DIM
    fg = _WHITE if bright else _WHITE_DIM
    return _draw_stack(fg, bg)
