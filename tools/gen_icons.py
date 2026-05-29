"""
gen_icons.py — генератор иконок Stack из реального SVG-логотипа.

Рендерит `assets/icons/logo.svg` через resvg_py (нативный Rust-рендерер,
не требует cairo), перекрашивает силуэт по альфа-каналу и кладёт его
на цветной squircle-фон. Из получившегося `icon.png` генерируется
многоразмерный `icon.ico` для PyInstaller.

Палитра:
  icon      — лаймовый squircle + чёрный логотип (бренд)
  positive  — зелёный   + чёрный (рост портфеля)
  negative  — красный   + чёрный (просадка)
  neutral   — серый     + чёрный (без изменений)
  warn      — оранжевый + чёрный (оферта скоро)
  crit      — красный   + белый  (оферта сегодня)

Использование:
    python tools/gen_icons.py             # сгенерировать всё
    python tools/gen_icons.py --states    # только positive/negative/...
    python tools/gen_icons.py --brand     # только icon.png + icon.ico
    python tools/gen_icons.py --ico       # только icon.ico из icon.png
"""
from __future__ import annotations

import argparse
import io
from pathlib import Path

import resvg_py
from PIL import Image, ImageDraw

ROOT     = Path(__file__).resolve().parent.parent
ICONS    = ROOT / "assets" / "icons"
LOGO_SVG = ICONS / "logo.svg"

# ── Палитра (RGBA) ────────────────────────────────────────────────────────────
LIME   = (199, 250,  56, 255)   # #C7FA38 — бренд Stack
DARK   = ( 28,  28,  30, 255)   # #1c1c1e
GREEN  = ( 52, 199,  89, 255)   # #34c759
RED    = (255,  59,  48, 255)   # #ff3b30
GREY   = (142, 142, 147, 255)   # #8e8e93
ORANGE = (255, 149,   0, 255)   # #ff9500
WHITE  = (255, 255, 255, 255)
BLACK  = (  0,   0,   0, 255)

# ── Геометрия ─────────────────────────────────────────────────────────────────
ICON_SIZE       = 512    # сторона генерируемых PNG
SQUIRCLE_RATIO  = 0.22   # радиус скругления (доля от стороны)
LOGO_PAD_RATIO  = 0.13   # внутренний отступ от squircle до логотипа


# ── Рендер SVG ────────────────────────────────────────────────────────────────
def _render_svg(width: int, height: int) -> Image.Image:
    """Растеризует logo.svg через resvg в RGBA-PIL."""
    data = resvg_py.svg_to_bytes(
        svg_path=str(LOGO_SVG),
        width=width,
        height=height,
    )
    if isinstance(data, list):
        data = bytes(data)
    return Image.open(io.BytesIO(data)).convert("RGBA")


def render_logo(box: int, fg: tuple) -> Image.Image:
    """
    Рендерит логотип в квадрат `box×box` с заданным цветом.
    Силуэт центрируется по короткой стороне с сохранением aspect ratio SVG.
    """
    # logo.svg viewBox = 278×230 (шире, чем выше)
    aspect = 278 / 230
    if aspect >= 1:
        w = box
        h = int(round(box / aspect))
    else:
        h = box
        w = int(round(box * aspect))

    raw = _render_svg(w, h)

    # Перекрашиваем: заменяем чёрный на fg, сохраняем альфу как маску.
    _, _, _, alpha = raw.split()
    recolored = Image.new("RGBA", raw.size, fg)
    recolored.putalpha(alpha)

    canvas = Image.new("RGBA", (box, box), (0, 0, 0, 0))
    canvas.alpha_composite(recolored, ((box - w) // 2, (box - h) // 2))
    return canvas


def make_icon(size: int, fg: tuple, bg: tuple) -> Image.Image:
    """Squircle-фон `bg` + центрированный логотип цвета `fg`."""
    ss = 2  # super-sampling для гладких углов squircle
    rsize = size * ss
    img = Image.new("RGBA", (rsize, rsize), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle(
        [0, 0, rsize - 1, rsize - 1],
        radius=int(rsize * SQUIRCLE_RATIO),
        fill=bg,
    )

    inner = rsize - 2 * int(rsize * LOGO_PAD_RATIO)
    logo  = render_logo(inner, fg)
    img.alpha_composite(
        logo,
        ((rsize - inner) // 2, (rsize - inner) // 2),
    )
    return img.resize((size, size), Image.LANCZOS)


# ── Пресеты ──────────────────────────────────────────────────────────────────
# Под ТЁМНЫЙ taskbar Windows (default) — цветной squircle + чёрный логотип
PRESETS: dict[str, dict] = {
    "icon":     {"bg": LIME,   "fg": BLACK},  # бренд
    "positive": {"bg": GREEN,  "fg": BLACK},
    "negative": {"bg": RED,    "fg": BLACK},
    "neutral":  {"bg": GREY,   "fg": BLACK},
    "warn":     {"bg": ORANGE, "fg": BLACK},
    "crit":     {"bg": RED,    "fg": WHITE},
}

# Под СВЕТЛЫЙ taskbar Windows — тёмный squircle + цветной логотип
# (так иконка остаётся читаемой, не сливается с белым фоном таскбара)
PRESETS_LIGHT: dict[str, dict] = {
    "icon":     {"bg": DARK,   "fg": LIME},
    "positive": {"bg": DARK,   "fg": GREEN},
    "negative": {"bg": DARK,   "fg": RED},
    "neutral":  {"bg": DARK,   "fg": GREY},
    "warn":     {"bg": DARK,   "fg": ORANGE},
    "crit":     {"bg": DARK,   "fg": RED},
}

STATE_NAMES = ("positive", "negative", "neutral", "warn", "crit")


def generate(names: list[str], variant: str = "dark") -> list[Path]:
    """variant: 'dark' — для тёмного taskbar (без суффикса);
               'light' — для светлого taskbar (суффикс -light)."""
    out = []
    presets = PRESETS_LIGHT if variant == "light" else PRESETS
    suffix  = "-light" if variant == "light" else ""
    for name in names:
        preset = presets[name]
        img = make_icon(ICON_SIZE, fg=preset["fg"], bg=preset["bg"])
        path = ICONS / f"{name}{suffix}.png"
        img.save(path, "PNG")
        out.append(path)
    return out


def regenerate_ico(
    src_png: Path = ICONS / "icon.png",
    out_ico: Path = ICONS / "icon.ico",
) -> Path:
    img = Image.open(src_png).convert("RGBA")
    img.save(
        out_ico,
        format="ICO",
        sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
    )
    return out_ico


def main():
    ap = argparse.ArgumentParser(description="Stack icons generator (resvg)")
    ap.add_argument("--ico",    action="store_true", help="только icon.ico")
    ap.add_argument("--brand",  action="store_true", help="только icon.png + icon.ico")
    ap.add_argument("--states", action="store_true", help="только state-иконки")
    args = ap.parse_args()

    do_all = not (args.ico or args.brand or args.states)

    if args.brand or do_all:
        for variant in ("dark", "light"):
            for p in generate(["icon"], variant=variant):
                print(f"  [ok] {p.relative_to(ROOT)}")

    if args.states or do_all:
        for variant in ("dark", "light"):
            for p in generate(list(STATE_NAMES), variant=variant):
                print(f"  [ok] {p.relative_to(ROOT)}")

    if args.ico or args.brand or do_all:
        ico = regenerate_ico()
        print(f"  [ok] {ico.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
