"""
Stack — GitHub Social Preview generator (v2, rich layout).

Layout:
  ┌──────────────────────────┬──────────────────────────────┐
  │  pill: T-BANK INVEST API │  ┌── window mockup ──┐       │
  │                          │  │ ● ● ● file.py     │       │
  │  Portfolio               │  │ TRAY ... TOTAL ...│       │
  │  Tray ← lime-highlighted │  │ Portfolio Pos ... │       │
  │  Monitor                 │  │ ┌──┐┌──┐┌──┐┌──┐  │       │
  │                          │  │ │  ││  ││  ││  │  │       │
  │  Subtitle...             │  │ └──┘└──┘└──┘└──┘  │       │
  │  • feature 1             │  │ TICKER QTY ... P&L│       │
  │  • feature 2             │  │ SBER  150 ... +.. │       │
  │  ...                     │  │ ...               │       │
  │  [Python][pywebview]...  │  └───────────────────┘       │
  └──────────────────────────┴──────────────────────────────┘

Renders at 2x (2560×1280) and downscales for crisp output at 1280×640.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ── Пути ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
DEFAULT_OUT = ASSETS / "github-social-preview.png"
MOCKUPS_DIR = ASSETS / "mockups"   # реальные скриншоты из приложения

sys.path.insert(0, str(ROOT))
try:
    from version import APP_VERSION, APP_NAME
except Exception:
    APP_VERSION, APP_NAME = "?", "Stack"

# ── Палитра ──────────────────────────────────────────────────────────────────
BG          = "#020306"
BG_CARD     = "#0B0E12"
BG_SOFT     = "#11151A"
BG_TITLEBAR = "#161A20"
BORDER      = "#1F2428"
BORDER_2    = "#2A2F33"
DIVIDER     = "#181C20"
TEXT        = "#F3F4F6"
TEXT_DIM    = "#D1D5DB"
MUTED       = "#6B7280"
MUTED_2     = "#4B5563"

LIME       = "#B8F34A"
LIME_DIM   = "#7A9F2A"
YELLOW     = "#FACC15"
YELLOW_DIM = "#A37D08"
GREEN      = "#4ADE80"
RED        = "#F87171"
BLUE       = "#60A5FA"
PURPLE     = "#C084FC"
TEAL       = "#5EEAD4"
ORANGE     = "#FB923C"

# Render at 2x for crisp text, then downscale.
SCALE = 2
W_OUT, H_OUT = 1280, 640
W, H = W_OUT * SCALE, H_OUT * SCALE


# ── Локализация ──────────────────────────────────────────────────────────────
# Текст исключительно про Stack — наше приложение, наши экраны, наши фичи.
LOCALES = {
    "en": {
        "brand":          APP_NAME,                         # "Stack"
        "tagline":        "Investment Tracker",
        "subtitle":       "Windows tray widget . T-Bank Invest API",
        "features": [
            ("Tray icon",        "- with live P&L color indicator"),
            ("HTML dashboard",   "- 5 tabs, dark/light themes"),
            ("Bond calendar",    "- coupons, offers, redemptions"),
            ("Excel & XML",      "- export with formulas"),
            ("Streamer mode",    "- blur all balances"),
        ],
        "brokers_label":  "BROKERS",
        "brokers": [
            {"name": "T-Bank",    "active": True},
            {"name": "Sber",      "active": False},
            {"name": "Alfa-Bank", "active": False},
            {"name": "BCS",       "active": False},
        ],
        "soon":           "soon",
        "win_title":      f"{APP_NAME} - Dashboard",
        "win_payouts_title": f"{APP_NAME} - Payouts",
        "tabs":           ["Overview", "Positions", "Payouts", "Analytics", "Settings"],
        "stat_labels":    ["TOTAL VALUE", "P&L TODAY", "ALL-TIME P&L", "POSITIONS"],
        "footer_left":    "Last update 15.04.2026 . 18:42:07",
        "footer_right":   "Connected",
        "table_headers":  ["Ticker", "Quantity", "Avg Price", "Price", "P&L", "Share"],
        "simple_headers": ["Ticker", "Qty", "Avg Price", "Price", "P&L"],
        "sb_today":       "TODAY",
        "sb_tray":        "TRAY",
        "sb_total":       "TOTAL",
        "simple_label":   "Simple mode",
        "calendar_month": "April 2026",
        "calendar_dow":   ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "upcoming_title": "Upcoming events",
        "view_all":       "View all events",
        "events": [
            ("15.04", "SBER coupon",      "+P340",  BLUE),
            ("15.04", "GAZP coupon",      "+P278",  BLUE),
            ("22.04", "SU26238RMFS6 offer", "",     ORANGE),
            ("28.04", "LKOH dividend",    "+P656",  TEAL),
            ("28.04", "RU000A104YT6 redeem", "",    PURPLE),
        ],
    },
    "ru": {
        "brand":          APP_NAME,
        "tagline":        "Инвест-трекер",
        "subtitle":       "Windows-виджет . API T-Bank Invest",
        "features": [
            ("Иконка в трее",      "- с индикатором P&L"),
            ("HTML-дашборд",       "- 5 вкладок, темы dark/light"),
            ("Календарь облигаций","- купоны, оферты, погашения"),
            ("Excel и XML",        "- экспорт с формулами"),
            ("Режим стримера",     "- размытие балансов"),
        ],
        "brokers_label":  "БРОКЕРЫ",
        "brokers": [
            {"name": "T-Bank",    "active": True},
            {"name": "Sber",      "active": False},
            {"name": "Alfa-Bank", "active": False},
            {"name": "БКС",       "active": False},
        ],
        "soon":           "скоро",
        "win_title":      f"{APP_NAME} - Дашборд",
        "win_payouts_title": f"{APP_NAME} - Выплаты",
        "tabs":           ["Обзор", "Позиции", "Выплаты", "Аналитика", "Настройки"],
        "stat_labels":    ["ПОРТФЕЛЬ", "P&L ДЕНЬ", "P&L ВСЁ ВРЕМЯ", "ПОЗИЦИИ"],
        "footer_left":    "Обновлено 15.04.2026 . 18:42:07",
        "footer_right":   "Подключено",
        "table_headers":  ["Тикер", "Кол-во", "Цена пок.", "Цена", "P&L", "Доля"],
        "simple_headers": ["Тикер", "Кол-во", "Цена пок.", "Цена", "P&L"],
        "sb_today":       "ДЕНЬ",
        "sb_tray":        "ТРЕЙ",
        "sb_total":       "ВСЕГО",
        "simple_label":   "Упрощённый",
        "calendar_month": "Апрель 2026",
        "calendar_dow":   ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"],
        "upcoming_title": "Ближайшие события",
        "view_all":       "Все события",
        "events": [
            ("15.04", "SBER купон",         "+P340", BLUE),
            ("15.04", "GAZP купон",         "+P278", BLUE),
            ("22.04", "SU26238RMFS6 оферта", "",     ORANGE),
            ("28.04", "LKOH дивиденд",      "+P656", TEAL),
            ("28.04", "RU000A104YT6 погаш.", "",     PURPLE),
        ],
    },
}


# ── Шрифты ────────────────────────────────────────────────────────────────────
def find_font(size: int, bold: bool = False, mono: bool = False) -> ImageFont.FreeTypeFont:
    """Inter/JetBrains Mono из assets/fonts → системные → default."""
    fonts_dir = ASSETS / "fonts"
    win_fonts = Path("C:/Windows/Fonts")

    if mono:
        cands = [
            fonts_dir / ("JetBrainsMono-Bold.ttf" if bold else "JetBrainsMono-Regular.ttf"),
            win_fonts / ("consolab.ttf" if bold else "consola.ttf"),
            win_fonts / "cour.ttf",
        ]
    else:
        cands = [
            fonts_dir / ("Inter-Black.ttf" if bold else "Inter-Regular.ttf"),
            fonts_dir / ("Inter-Bold.ttf"  if bold else "Inter-Medium.ttf"),
            win_fonts / ("seguibl.ttf" if bold else "segoeui.ttf"),
            win_fonts / ("segoeuib.ttf" if bold else "segoeui.ttf"),
            win_fonts / ("arialbd.ttf" if bold else "arial.ttf"),
        ]
    for p in cands:
        if p and p.exists():
            try:
                return ImageFont.truetype(str(p), size * SCALE if size <= 100 else size)
            except Exception:
                continue
    return ImageFont.load_default()


# Удобные обёртки — размер указывается в "logical" единицах (соответствует 1280-канвасу).
def fnt(size: int, bold=False, mono=False) -> ImageFont.FreeTypeFont:
    fonts_dir = ASSETS / "fonts"
    win_fonts = Path("C:/Windows/Fonts")
    if mono:
        cands = [
            fonts_dir / ("JetBrainsMono-Bold.ttf" if bold else "JetBrainsMono-Regular.ttf"),
            win_fonts / ("consolab.ttf" if bold else "consola.ttf"),
            win_fonts / "cour.ttf",
        ]
    else:
        cands = [
            fonts_dir / ("Inter-Black.ttf" if bold else "Inter-Regular.ttf"),
            fonts_dir / ("Inter-Bold.ttf"  if bold else "Inter-Medium.ttf"),
            win_fonts / ("seguibl.ttf" if bold else "segoeui.ttf"),
            win_fonts / ("segoeuib.ttf" if bold else "segoeui.ttf"),
            win_fonts / ("arialbd.ttf" if bold else "arial.ttf"),
        ]
    for p in cands:
        if p and p.exists():
            try:
                return ImageFont.truetype(str(p), size * SCALE)
            except Exception:
                continue
    return ImageFont.load_default()


def text_w(draw: ImageDraw.ImageDraw, s: str, font) -> int:
    bb = draw.textbbox((0, 0), s, font=font)
    return bb[2] - bb[0]


def text_h(draw: ImageDraw.ImageDraw, s: str, font) -> int:
    bb = draw.textbbox((0, 0), s, font=font)
    return bb[3] - bb[1]


# ── Логические координаты (×SCALE при отрисовке) ────────────────────────────
def x(v: int) -> int: return v * SCALE
def y(v: int) -> int: return v * SCALE
def s(v: int) -> int: return v * SCALE


# ── Реальные скриншоты приложения (mockups/) ─────────────────────────────────
def load_mockup(name: str) -> Image.Image | None:
    """
    Загружает реальный скриншот экрана приложения, сохранённый через dev-кнопку.
    Возвращает PIL.Image или None если файл отсутствует.
    """
    path = MOCKUPS_DIR / f"dashboard-{name}.png"
    if not path.exists():
        return None
    try:
        return Image.open(path).convert("RGBA")
    except Exception:
        return None


def paste_window_screenshot(
    img: Image.Image,
    screenshot: Image.Image,
    x: int, y: int, w: int, h: int,
    radius: int = 10,
    add_chrome: bool = True,
):
    """
    Вставляет скриншот как «окно»: добавляет тень, скруглённые углы,
    macOS traffic-lights сверху (опционально).
    Координаты x, y, w, h — в логических px (не SCALE).
    """
    px, py = x * SCALE, y * SCALE
    pw, ph = w * SCALE, h * SCALE
    pr = radius * SCALE

    # Тень
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        [px, py + s(8), px + pw, py + ph + s(8)],
        radius=pr, fill=(0, 0, 0, 160),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=s(20)))
    img.paste(shadow, (0, 0), shadow)

    # Подгоняем скриншот под размер окна (cover-style: пропорционально, кроп если надо)
    src_aspect = screenshot.width / screenshot.height
    target_aspect = pw / ph
    if src_aspect > target_aspect:
        # Скриншот шире — скейлим по высоте, кропаем по ширине
        new_h = ph
        new_w = int(new_h * src_aspect)
    else:
        new_w = pw
        new_h = int(new_w / src_aspect)
    resized = screenshot.resize((new_w, new_h), Image.LANCZOS)
    # По горизонтали центрируем, по вертикали обрезаем сверху —
    # дашборд длинный, важная часть (шапка, итоги) у верхнего края.
    cx = (new_w - pw) // 2
    cy = 0
    cropped = resized.crop((cx, cy, cx + pw, cy + ph))

    # Скруглённые углы через alpha-маску
    mask = Image.new("L", (pw, ph), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, pw, ph], radius=pr, fill=255)

    # Применяем маску
    cropped.putalpha(mask)
    img.paste(cropped, (px, py), cropped)

    # Border (без macOS traffic-lights — они закрывают часть интерфейса)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(
        [px, py, px + pw, py + ph],
        radius=pr, outline=BORDER_2, width=s(1),
    )


# ── Логотип Stack — рендерим logo.svg напрямую через resvg (с перекраской) ───
_LOGO_CACHE: dict = {}
_LOGO_SVG = ASSETS / "icons" / "logo.svg"
# Внутренний размер растрового кэша SVG (источник для последующих ресайзов).
# Большой, чтобы любой downscale выглядел чисто.
_LOGO_RENDER_W = 1024


def _load_logo_png() -> Image.Image | None:
    """Растеризует logo.svg через resvg_py один раз, кэширует на сессию."""
    if "src" in _LOGO_CACHE:
        return _LOGO_CACHE["src"]
    if not _LOGO_SVG.exists():
        return None
    try:
        import io
        import resvg_py
        # logo.svg viewBox = 278×230, сохраняем aspect
        h = int(round(_LOGO_RENDER_W * 230 / 278))
        data = resvg_py.svg_to_bytes(svg_path=str(_LOGO_SVG),
                                     width=_LOGO_RENDER_W, height=h)
        if isinstance(data, list):
            data = bytes(data)
        src = Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception:
        return None
    _LOGO_CACHE["src"] = src
    return src


def draw_logo(draw_or_img, lx: int, ly: int, size: int, color: str):
    """
    Размещает SVG-логотип Stack на canvas, перекрашенный в `color`.
    `lx, ly, size` — в логических px (умножаются на SCALE).
    Принимает ImageDraw или Image — извлекает Image из draw.
    """
    # Достаём Image из draw или принимаем напрямую
    img = draw_or_img._image if hasattr(draw_or_img, "_image") else draw_or_img

    src = _load_logo_png()
    if src is None:
        # Fallback на рисованную версию (если PNG отсутствует)
        _draw_logo_polygons(ImageDraw.Draw(img), lx, ly, size, color)
        return

    # Векторизованный recolor: solid цвет + alpha из исходного
    rgb = tuple(int(color.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
    solid = Image.new("RGBA", src.size, rgb + (0,))
    alpha = src.split()[3]
    solid.putalpha(alpha)

    # Resize с сохранением aspect ratio (логотип 1.21:1, ширина = size)
    aspect = src.width / src.height
    final_w = size * SCALE
    final_h = int(final_w / aspect)
    resized = solid.resize((final_w, final_h), Image.LANCZOS)

    img.paste(resized, (lx * SCALE, ly * SCALE), resized)


def _draw_logo_polygons(draw: ImageDraw.ImageDraw, lx: int, ly: int, size: int, color: str):
    """Старая рисованная версия — fallback если PNG-рендер недоступен."""
    px = lx * SCALE
    py = ly * SCALE
    sz = size * SCALE
    tiles = [(38, 14, 44, 18), (28, 38, 60, 18), (18, 62, 76, 18)]
    for tx, ty, tw, th in tiles:
        x1 = px + int(tx * sz / 100)
        y1 = py + int(ty * sz / 100)
        x2 = x1 + int(tw * sz / 100)
        y2 = y1 + int(th * sz / 100)
        sk = max(2, int(tw * sz * 0.07 / 100))
        pts = [(x1 + sk, y1), (x2, y1), (x2 - sk, y2), (x1, y2)]
        draw.polygon(pts, fill=color)


# ── Декоративные элементы ─────────────────────────────────────────────────────
def draw_grid(draw: ImageDraw.ImageDraw):
    """Тонкая сетка фоном — намёк на "стек/слои"."""
    step = s(40)
    color = "#0A0E12"
    for px in range(0, W + 1, step):
        draw.line([(px, 0), (px, H)], fill=color, width=1)
    for py in range(0, H + 1, step):
        draw.line([(0, py), (W, py)], fill=color, width=1)


def draw_corner_marks(draw: ImageDraw.ImageDraw):
    """4 угловых маркера-уголка (как в видоискателе)."""
    arm = s(28)
    pad = s(20)
    width = s(2)
    color = LIME_DIM

    # Top-left
    draw.line([(pad, pad), (pad + arm, pad)], fill=color, width=width)
    draw.line([(pad, pad), (pad, pad + arm)], fill=color, width=width)
    # Top-right
    draw.line([(W - pad - arm, pad), (W - pad, pad)], fill=color, width=width)
    draw.line([(W - pad, pad), (W - pad, pad + arm)], fill=color, width=width)
    # Bottom-left
    draw.line([(pad, H - pad), (pad + arm, H - pad)], fill=color, width=width)
    draw.line([(pad, H - pad - arm), (pad, H - pad)], fill=color, width=width)
    # Bottom-right
    draw.line([(W - pad - arm, H - pad), (W - pad, H - pad)], fill=color, width=width)
    draw.line([(W - pad, H - pad - arm), (W - pad, H - pad)], fill=color, width=width)


def draw_diagonal_streak(img: Image.Image):
    """Тонкая диагональная линия — "сканирующий луч"."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    # От правого верха к левому низу
    od.line([(s(720), 0), (s(560), H)], fill=(184, 243, 74, 22), width=s(1))
    od.line([(s(900), 0), (s(720), H)], fill=(250, 204, 21, 14), width=s(1))
    img.paste(overlay, (0, 0), overlay)


def draw_glow_ellipse(img: Image.Image, cx: int, cy: int, rx: int, ry: int, rgba):
    """Размытое лайм-glow пятно за заголовком."""
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=rgba)
    glow = glow.filter(ImageFilter.GaussianBlur(radius=s(40)))
    img.paste(glow, (0, 0), glow)


def draw_pill(draw: ImageDraw.ImageDraw, px: int, py: int, label: str,
              font, fg: str, border: str, dot_color: str | None = None,
              fill="transparent"):
    """Универсальная "пилюля" с обводкой."""
    pad_x, pad_y = s(14), s(8)
    tw = text_w(draw, label, font)
    th = text_h(draw, label, font)
    # дополнительная ширина под точку
    extra = s(20) if dot_color else 0
    box_w = tw + pad_x * 2 + extra
    box_h = th + pad_y * 2 + s(4)

    if fill == "transparent":
        draw.rounded_rectangle(
            [px, py, px + box_w, py + box_h],
            radius=s(8), outline=border, width=s(1),
        )
    else:
        draw.rounded_rectangle(
            [px, py, px + box_w, py + box_h],
            radius=s(8), fill=fill, outline=border, width=s(1),
        )

    cur_x = px + pad_x
    if dot_color:
        cy = py + box_h // 2
        r = s(4)
        draw.ellipse([cur_x, cy - r, cur_x + r * 2, cy + r * 2], fill=dot_color)
        cur_x += s(16)

    draw.text((cur_x, py + pad_y - s(2)), label, font=font, fill=fg)
    return box_w, box_h


# ── Левая половина: контент ──────────────────────────────────────────────────
def draw_left_panel(draw: ImageDraw.ImageDraw, img: Image.Image, loc: dict):
    """
    Композиция (логические px на канвасе 1280×640):
      y= 60: version pill (правее ничего нет)
      y=120: Stack-логотип + крупный текст "Stack" (центрированы по вертикали)
      y=235: tagline лаймом
      y=275: subtitle серым моно
      y=325: список из 5 фич (точки центрированы по cap-height текста)
      y=560: блок "Brokers" с активным T-Bank и dimmed-планами
    """
    pad_l = s(60)

    # version pill теперь рисуется отдельно в draw_version_pill (в углу).
    # T-BANK pill удалён — он визуально дублировал бы блок BROKERS внизу.

    # ── 1. БРЕНД (логотип + текст по одной геометрической оси) ──
    logo_size = 100        # логических px
    brand_top = 120        # верх логотипа
    logo_cx = pad_l + (logo_size * SCALE) // 2
    logo_cy = s(brand_top) + (logo_size * SCALE) // 2

    draw_logo(draw, lx=60, ly=brand_top, size=logo_size, color=LIME)

    # Текст "Stack" — центрируется ВЕРТИКАЛЬНО по центру логотипа.
    # Pillow textbbox даёт реальные пиксельные границы глифов.
    f_brand = fnt(86, bold=True)
    brand = loc["brand"]
    bb = draw.textbbox((0, 0), brand, font=f_brand)
    text_h_real = bb[3] - bb[1]
    text_top_offset = bb[1]   # сколько пустого пространства сверху до глифа
    brand_x = pad_l + s(logo_size) + s(22)
    brand_y = logo_cy - text_h_real // 2 - text_top_offset
    draw.text((brand_x, brand_y), brand, font=f_brand, fill=TEXT)

    # ── 2. Tagline + subtitle ──
    f_tagline = fnt(28, bold=True)
    tagline_y = s(brand_top + logo_size + 22)
    draw.text((pad_l, tagline_y), loc["tagline"], font=f_tagline, fill=LIME)

    f_sub = fnt(13, mono=True)
    sub_y = tagline_y + s(44)
    draw.text((pad_l, sub_y), loc["subtitle"], font=f_sub, fill=MUTED)

    # ── 3. Список фич (точки строго центрируем по cap-height текста) ──
    # Все точки одного цвета — фирменный лайм, без радуги.
    feature_colors = [LIME, LIME, LIME, LIME, LIME]
    f_feat_b = fnt(13, bold=True, mono=True)
    f_feat_n = fnt(13, mono=True)

    feat_y_start = sub_y + s(38)
    feat_gap = s(28)

    # cap-height = верхняя половина буквы. Используем bbox прописной буквы.
    cap_bb = draw.textbbox((0, 0), "X", font=f_feat_b)
    cap_top = cap_bb[1]
    cap_bot = cap_bb[3]
    cap_center = (cap_top + cap_bot) // 2  # центр глифа относительно (0,0)

    dot_r = s(4)  # меньше, чтобы было аккуратно круглым

    for i, (bold_part, rest) in enumerate(loc["features"]):
        c = feature_colors[i % len(feature_colors)]
        row_y = feat_y_start + i * feat_gap

        # Текст рисуем сначала
        bx = pad_l + s(22)
        draw.text((bx, row_y), bold_part, font=f_feat_b, fill=TEXT)
        bw = text_w(draw, bold_part, f_feat_b)
        draw.text((bx + bw + s(8), row_y), rest, font=f_feat_n, fill=MUTED)

        # Точка центрируется по cap-center текста
        dot_cy = row_y + cap_center
        dot_cx = pad_l + s(6)
        draw.ellipse(
            [dot_cx - dot_r, dot_cy - dot_r, dot_cx + dot_r, dot_cy + dot_r],
            fill=c,
        )

    # ── 4. Блок брокеров (заменяет tech-pills) ──
    f_section = fnt(9, bold=True)
    section_y = s(548)
    draw.text((pad_l, section_y), loc["brokers_label"], font=f_section, fill=MUTED)

    # Подчеркивающая линия справа от заголовка
    label_w = text_w(draw, loc["brokers_label"], f_section)
    line_x1 = pad_l + label_w + s(10)
    line_x2 = s(580)
    line_y = section_y + s(7)
    draw.line([(line_x1, line_y), (line_x2, line_y)], fill=BORDER_2, width=s(1))

    # Пилюли брокеров — активный T-Bank лаймом, остальные dim (без пометки "soon")
    f_brk = fnt(12, bold=True)
    px_cur = pad_l
    py_pill = s(572)

    for i, broker in enumerate(loc["brokers"]):
        name = broker["name"]
        active = broker["active"]
        if active:
            # Заливка лаймом + тёмный текст
            tw = text_w(draw, name, f_brk)
            box_w = tw + s(16) + s(20)  # padding + checkmark space
            box_h = s(28)
            draw.rounded_rectangle(
                [px_cur, py_pill, px_cur + box_w, py_pill + box_h],
                radius=s(8), fill=LIME, outline=LIME, width=s(1),
            )
            # Галочка слева
            cx = px_cur + s(12)
            cy = py_pill + box_h // 2
            draw.line(
                [(cx - s(3), cy), (cx, cy + s(3)), (cx + s(5), cy - s(4))],
                fill="#0B0D0E", width=s(2),
            )
            draw.text((px_cur + s(24), py_pill + s(6)), name, font=f_brk, fill="#0B0D0E")
            px_cur += box_w + s(8)
        else:
            tw = text_w(draw, name, f_brk)
            box_w = tw + s(20)
            box_h = s(28)
            draw.rounded_rectangle(
                [px_cur, py_pill, px_cur + box_w, py_pill + box_h],
                radius=s(8), fill="#0E1114", outline=BORDER_2, width=s(1),
            )
            draw.text((px_cur + s(10), py_pill + s(6)), name, font=f_brk, fill=MUTED)
            px_cur += box_w + s(8)


# ── Мини-мокап упрощённого режима (накладывается над основным) ──────────────
def draw_simple_mockup(draw: ImageDraw.ImageDraw, img: Image.Image, loc: dict):
    """
    Маленькое окно справа сверху — показывает упрощённый дизайн Stack:
    статус-бар + плотную таблицу. Слегка повёрнуто/смещено для эффекта стопки.
    """
    # Малое окно — верх-лево правой панели, перекрывает только title bar dashboard
    win_x, win_y = s(560), s(20)
    win_w, win_h = s(440), s(200)
    radius = s(8)

    # Тень
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        [win_x - s(2), win_y + s(6), win_x + win_w + s(2), win_y + win_h + s(6)],
        radius=radius, fill=(0, 0, 0, 130),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=s(14)))
    img.paste(shadow, (0, 0), shadow)
    draw = ImageDraw.Draw(img)

    # Корпус окна
    draw.rounded_rectangle(
        [win_x, win_y, win_x + win_w, win_y + win_h],
        radius=radius, fill=BG_CARD, outline=BORDER_2, width=s(1),
    )

    # Title bar тонкий
    tb_h = s(22)
    draw.rounded_rectangle(
        [win_x, win_y, win_x + win_w, win_y + tb_h + s(2)],
        radius=radius, fill=BG_TITLEBAR,
    )
    draw.rectangle(
        [win_x, win_y + tb_h - s(2), win_x + win_w, win_y + tb_h + s(2)],
        fill=BG_TITLEBAR,
    )
    draw.line([(win_x, win_y + tb_h), (win_x + win_w, win_y + tb_h)],
              fill=BORDER, width=s(1))

    # Traffic lights (компактные)
    tl_y = win_y + tb_h // 2
    tl_r = s(4)
    for i, color in enumerate(["#FF5F57", "#FEBC2E", "#28C840"]):
        cx = win_x + s(12) + i * s(13)
        draw.ellipse([cx - tl_r, tl_y - tl_r, cx + tl_r, tl_y + tl_r], fill=color)

    # Заголовок-метка справа: "Simple mode"
    f_label = fnt(9, bold=True)
    label = loc["simple_label"]
    lw = text_w(draw, label, f_label)
    draw.text((win_x + win_w - lw - s(12), win_y + s(6)), label, font=f_label, fill=LIME)

    # Статус-бар внутри
    sb_y = win_y + tb_h + s(12)
    f_sb_l = fnt(9, bold=True, mono=True)
    f_sb_v = fnt(10, bold=True, mono=True)

    cur_x = win_x + s(14)

    def sb_pair(label_, value_, color):
        nonlocal cur_x
        draw.text((cur_x, sb_y), label_, font=f_sb_l, fill=MUTED)
        cur_x += text_w(draw, label_, f_sb_l) + s(6)
        draw.text((cur_x, sb_y - s(1)), value_, font=f_sb_v, fill=color)
        cur_x += text_w(draw, value_, f_sb_v) + s(8)

    sb_pair(loc["sb_tray"],  "+P4 821", GREEN)
    draw.text((cur_x, sb_y), "|", font=f_sb_l, fill=BORDER_2); cur_x += s(10)
    sb_pair(loc["sb_today"], "+0.83%", GREEN)
    draw.text((cur_x, sb_y), "|", font=f_sb_l, fill=BORDER_2); cur_x += s(10)
    sb_pair(loc["sb_total"], "P581.2K", TEXT)

    # Плотная таблица: 4 строки (как на референсе)
    f_th = fnt(8, bold=True)
    f_td = fnt(10, bold=True, mono=True)

    tbl_y = sb_y + s(22)
    # 5 колонок для 440px ширины: ticker | qty | avg | price | pnl
    cols_x = [win_x + s(14), win_x + s(94), win_x + s(170), win_x + s(266), win_x + s(360)]
    headers = loc["simple_headers"][:5]
    for cx, h in zip(cols_x, headers):
        draw.text((cx, tbl_y), h, font=f_th, fill=MUTED)

    # Тонкая разделяющая линия под header
    draw.line(
        [(win_x + s(14), tbl_y + s(15)), (win_x + win_w - s(14), tbl_y + s(15))],
        fill=BORDER, width=s(1),
    )

    rows = [
        ("SBER", "150", "P271.4", "P289.1", "+P2 655", GREEN),
        ("GAZP", "80",  "P162.0", "P154.3", "-P616",   RED),
        ("LKOH", "10",  "P6 812", "P7 140", "+P3 280", GREEN),
        ("TATN", "50",  "P688.0", "P701.5", "+P675",   GREEN),
    ]
    for ri, (tk, q, ab, cur, pnl, pcol) in enumerate(rows):
        ry = tbl_y + s(20) + ri * s(17)
        draw.text((cols_x[0], ry), tk,  font=f_td, fill=TEXT)
        draw.text((cols_x[1], ry), q,   font=f_td, fill=TEXT)
        draw.text((cols_x[2], ry), ab,  font=f_td, fill=TEXT_DIM)
        draw.text((cols_x[3], ry), cur, font=f_td, fill=TEXT_DIM)
        draw.text((cols_x[4], ry), pnl, font=f_td, fill=pcol)


# ── Окно Payouts (Bond Calendar) — среднее, верх-право ───────────────────────
def draw_payouts_mockup(draw: ImageDraw.ImageDraw, img: Image.Image, loc: dict):
    """
    Среднее окно — верх-право. Показывает вкладку Payouts:
    календарь событий + список ближайших.
    Заканчивается до y где у dashboard начинаются stat-карточки.
    """
    win_x, win_y = s(860), s(80)
    win_w, win_h = s(380), s(280)
    radius = s(10)

    # Тень
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        [win_x, win_y + s(8), win_x + win_w, win_y + win_h + s(8)],
        radius=radius, fill=(0, 0, 0, 150),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=s(16)))
    img.paste(shadow, (0, 0), shadow)
    draw = ImageDraw.Draw(img)

    # Корпус
    draw.rounded_rectangle(
        [win_x, win_y, win_x + win_w, win_y + win_h],
        radius=radius, fill=BG_CARD, outline=BORDER_2, width=s(1),
    )

    # Title bar
    tb_h = s(28)
    draw.rounded_rectangle(
        [win_x, win_y, win_x + win_w, win_y + tb_h + s(2)],
        radius=radius, fill=BG_TITLEBAR,
    )
    draw.rectangle(
        [win_x, win_y + tb_h - s(2), win_x + win_w, win_y + tb_h + s(2)],
        fill=BG_TITLEBAR,
    )
    draw.line([(win_x, win_y + tb_h), (win_x + win_w, win_y + tb_h)],
              fill=BORDER, width=s(1))

    # Traffic lights
    tl_y = win_y + tb_h // 2
    tl_r = s(5)
    for i, color in enumerate(["#FF5F57", "#FEBC2E", "#28C840"]):
        cx = win_x + s(14) + i * s(15)
        draw.ellipse([cx - tl_r, tl_y - tl_r, cx + tl_r, tl_y + tl_r], fill=color)

    # Title bar: лого + название
    f_tb = fnt(10, mono=True)
    title = loc["win_payouts_title"]
    tw = text_w(draw, title, f_tb)
    mini_logo_size = 11
    composition_w = mini_logo_size * SCALE + s(7) + tw
    cx_start = win_x + (win_w - composition_w) // 2
    logo_x_logical = cx_start // SCALE
    logo_y_logical = (win_y + s(7)) // SCALE
    draw_logo(draw, lx=logo_x_logical, ly=logo_y_logical, size=mini_logo_size, color=LIME)
    draw.text((cx_start + mini_logo_size * SCALE + s(7), win_y + s(7)),
              title, font=f_tb, fill=MUTED)

    # Refresh + menu кнопки в правом углу
    btn_y = win_y + tb_h // 2 - s(6)
    for bi, sym in enumerate(["⟳", "⋯"]):
        bx = win_x + win_w - s(28) - bi * s(20)
        draw.ellipse(
            [bx - s(7), btn_y - s(1), bx + s(7), btn_y + s(13)],
            outline=BORDER, width=s(1),
        )
    # Иконки рисуем простыми символами (Pillow без эмодзи)
    f_btn = fnt(11, bold=True, mono=True)
    draw.text((win_x + win_w - s(33), btn_y - s(1)), "↻", font=f_btn, fill=MUTED)
    draw.text((win_x + win_w - s(13) - s(4), btn_y - s(1)), "⋮", font=f_btn, fill=MUTED)

    # Уровень ниже title bar — сразу видно что это Payouts (без полосы табов).
    # 5 табов в окно 380px не помещаются красиво, поэтому показываем
    # только активный лейбл с лайм-подчёркиванием.
    tabs_y = win_y + tb_h + s(10)
    f_tab = fnt(11, bold=True)
    tab_label = loc["tabs"][2]   # "Payouts"
    tw_ = text_w(draw, tab_label, f_tab)
    draw.text((win_x + s(14), tabs_y), tab_label, font=f_tab, fill=LIME)
    draw.line(
        [(win_x + s(14), tabs_y + s(17)),
         (win_x + s(14) + tw_, tabs_y + s(17))],
        fill=LIME, width=s(2),
    )
    # Тонкая линия-разделитель снизу
    draw.line(
        [(win_x + s(12), tabs_y + s(19)), (win_x + win_w - s(12), tabs_y + s(19))],
        fill=BORDER, width=s(1),
    )

    # ─── Список событий — полная ширина окна, как наш реальный bonds-tab ──
    list_x = win_x + s(14)
    list_y = tabs_y + s(28)
    list_w = win_w - s(28)

    # Заголовок "Upcoming events"
    f_lh = fnt(9, bold=True)
    draw.text((list_x, list_y), loc["upcoming_title"], font=f_lh, fill=TEXT)
    # Кнопка "View all" справа
    f_va = fnt(8, bold=True)
    va = loc["view_all"]
    vw = text_w(draw, va, f_va)
    draw.text((list_x + list_w - vw, list_y + s(2)), va, font=f_va, fill=LIME)

    # События (5 строк) — каждое = pill-метка типа + название + сумма
    f_ev_d = fnt(8, mono=True)
    f_ev_n = fnt(9)
    f_ev_a = fnt(9, bold=True, mono=True)
    f_ev_p = fnt(7, bold=True)

    pill_labels = {
        BLUE:   ("coupon",   "купон"),
        TEAL:   ("dividend", "дивиденд"),
        PURPLE: ("redeem",   "погаш."),
        ORANGE: ("offer",    "оферта"),
    }

    ev_y0 = list_y + s(18)
    ev_h = s(26)
    is_en = loc["brokers_label"] == "BROKERS"

    # Показываем только первые 4 события (5-е не помещается в окно 280px)
    for i, (date, name, amt, color) in enumerate(loc["events"][:4]):
        ry = ev_y0 + i * ev_h
        # Карточка события (мягкий фон)
        draw.rounded_rectangle(
            [list_x, ry, list_x + list_w, ry + ev_h - s(3)],
            radius=s(4), fill=BG_SOFT,
        )
        # Pill-метка типа события (полупрозрачный фон + цветной текст)
        pill_text = pill_labels[color][0 if is_en else 1]
        pill_text_w = text_w(draw, pill_text, f_ev_p)
        pill_w = pill_text_w + s(10)
        pill_h = s(12)
        pill_x = list_x + s(6)
        pill_y = ry + s(5)
        c_rgb = tuple(int(color.lstrip("#")[j:j+2], 16) for j in (0, 2, 4))
        pill_overlay = Image.new("RGBA", (pill_w, pill_h), (*c_rgb, 38))
        img.paste(pill_overlay, (pill_x, pill_y), pill_overlay)
        draw.text((pill_x + s(5), pill_y + s(1)), pill_text, font=f_ev_p, fill=color)

        # Дата
        draw.text((pill_x + pill_w + s(6), ry + s(5)), date, font=f_ev_d, fill=MUTED)
        # Имя облигации
        draw.text((pill_x + pill_w + s(6) + s(34), ry + s(5)),
                  name, font=f_ev_n, fill=TEXT)

        # Сумма справа (если есть)
        if amt:
            aw = text_w(draw, amt, f_ev_a)
            draw.text((list_x + list_w - aw - s(6), ry + s(5)),
                      amt, font=f_ev_a, fill=GREEN)


# ── Правая половина: мокап окна дашборда (нижнее, главное) ───────────────────
def draw_window_mockup(draw: ImageDraw.ImageDraw, img: Image.Image, loc: dict):
    # Основное окно — занимает большую часть правой панели.
    # Поверх него каскадом: Payouts (правый-верх) и Simple (левый-верх).
    # Stat-карточки этого окна будут на y >= 360, чтобы не перекрываться с Payouts.
    win_x, win_y = s(600), s(230)
    win_w, win_h = s(640), s(380)
    radius = s(10)

    # Тень окна — отдельный слой с blur
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        [win_x, win_y + s(8), win_x + win_w, win_y + win_h + s(8)],
        radius=radius, fill=(0, 0, 0, 160),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=s(20)))
    img.paste(shadow, (0, 0), shadow)

    # Свежая ссылка на draw после paste
    draw = ImageDraw.Draw(img)

    # Окно
    draw.rounded_rectangle(
        [win_x, win_y, win_x + win_w, win_y + win_h],
        radius=radius, fill=BG_CARD, outline=BORDER_2, width=s(1),
    )

    # Title bar
    tb_h = s(32)
    # Эмулируем «рисование с обрезкой» — рисуем только верх с фоном чуть светлее
    draw.rounded_rectangle(
        [win_x, win_y, win_x + win_w, win_y + tb_h + s(2)],
        radius=radius, fill=BG_TITLEBAR,
    )
    # Перекрываем нижнюю половину чтобы радиус остался только сверху
    draw.rectangle(
        [win_x, win_y + tb_h - s(2), win_x + win_w, win_y + tb_h + s(2)],
        fill=BG_TITLEBAR,
    )
    # Линия-разделитель
    draw.line(
        [(win_x, win_y + tb_h), (win_x + win_w, win_y + tb_h)],
        fill=BORDER, width=s(1),
    )

    # Traffic lights (macOS style)
    tl_y = win_y + tb_h // 2
    tl_r = s(6)
    for i, color in enumerate(["#FF5F57", "#FEBC2E", "#28C840"]):
        cx = win_x + s(16) + i * s(18)
        draw.ellipse([cx - tl_r, tl_y - tl_r, cx + tl_r, tl_y + tl_r], fill=color)

    # Title bar text — со Stack-меткой (мини-логотип + название)
    f_tb = fnt(11, mono=True)
    tb_text = loc["win_title"]
    tw = text_w(draw, tb_text, f_tb)
    # Центрируем композицию: лого + текст
    mini_logo_size = 12
    composition_w = mini_logo_size * SCALE + s(8) + tw
    cx_start = win_x + (win_w - composition_w) // 2
    # Мини-логотип (используем то что win_y+8 → нужно конвертить обратно)
    # draw_logo принимает logical координаты (умножает на SCALE), а у нас тут уже px
    logo_x_logical = cx_start // SCALE
    logo_y_logical = (win_y + s(8)) // SCALE
    draw_logo(draw, lx=logo_x_logical, ly=logo_y_logical, size=mini_logo_size, color=LIME)
    # Текст после логотипа
    draw.text((cx_start + mini_logo_size * SCALE + s(8), win_y + s(8)),
              tb_text, font=f_tb, fill=MUTED)

    # ─── Status bar (TRAY ... TODAY ... TOTAL ...) ───
    sb_y = win_y + tb_h + s(14)
    f_sb_l = fnt(10, bold=True, mono=True)
    f_sb_v = fnt(11, bold=True, mono=True)

    cur_x = win_x + s(20)

    def sb_pair(label: str, value: str, value_color=GREEN):
        nonlocal cur_x
        draw.text((cur_x, sb_y), label, font=f_sb_l, fill=MUTED)
        cur_x += text_w(draw, label, f_sb_l) + s(8)
        draw.text((cur_x, sb_y - s(1)), value, font=f_sb_v, fill=value_color)
        cur_x += text_w(draw, value, f_sb_v) + s(10)

    sb_pair(loc["sb_tray"],  "+P4 821.30", GREEN)
    draw.text((cur_x, sb_y), "|", font=f_sb_l, fill=BORDER_2); cur_x += s(14)
    sb_pair(loc["sb_today"], "+0.83%", GREEN)
    draw.text((cur_x, sb_y), "|", font=f_sb_l, fill=BORDER_2); cur_x += s(14)
    sb_pair(loc["sb_total"], "P581 200", TEXT)

    # ─── Tabs ───
    tabs_y = win_y + tb_h + s(48)
    f_tab = fnt(11, bold=True)
    tab_x = win_x + s(20)
    for i, name in enumerate(loc["tabs"]):
        active = (i == 0)
        color = LIME if active else MUTED
        draw.text((tab_x, tabs_y), name, font=f_tab, fill=color)
        tw = text_w(draw, name, f_tab)
        if active:
            # Underline
            draw.line(
                [(tab_x, tabs_y + s(20)), (tab_x + tw, tabs_y + s(20))],
                fill=LIME, width=s(2),
            )
        tab_x += tw + s(20)

    # Линия под табами
    draw.line(
        [(win_x + s(16), tabs_y + s(24)), (win_x + win_w - s(16), tabs_y + s(24))],
        fill=BORDER, width=s(1),
    )

    # ─── 4 stat cards ───
    # ═══════════════════════════════════════════════════════════════════════
    # ВНУТРЕННОСТИ ОКНА — точно как у нас в реальном dashboard.html:
    #   1. acc-tabs (переключатель счетов)
    #   2. bigBlock (огромное число + дельта)
    #   3. 4 stat-карточки (наши: Доходность всё / Сегодня / НКД / YTM)
    #   4. Топ позиции — список pos-item с цветной иконкой + name + price + P&L
    # ═══════════════════════════════════════════════════════════════════════

    # ─── 1. Account tabs ───
    at_y = tabs_y + s(38)
    at_h = s(28)
    at_pad = s(3)
    at_x = win_x + s(18)
    at_w = win_w - s(36)
    draw.rounded_rectangle(
        [at_x, at_y, at_x + at_w, at_y + at_h],
        radius=s(6), fill=BG_SOFT,
    )
    # Активная "Все счета" + 2 счёта
    acc_tabs = ["Все счета", "ИИС", "Брокерский"] if loc.get("brand") == "Stack" else ["All accounts", "IIS", "Brokerage"]
    if loc["brokers_label"] == "BROKERS":  # английская локаль
        acc_tabs = ["All accounts", "IIS", "Brokerage"]
    n = len(acc_tabs)
    tab_w = (at_w - at_pad * 2) // n
    f_at = fnt(10, bold=True)
    for i, name in enumerate(acc_tabs):
        tx = at_x + at_pad + i * tab_w
        active = (i == 0)
        if active:
            draw.rounded_rectangle(
                [tx, at_y + at_pad, tx + tab_w, at_y + at_h - at_pad],
                radius=s(4), fill=BG_CARD, outline=BORDER, width=s(1),
            )
        nw = text_w(draw, name, f_at)
        col = TEXT if active else MUTED
        draw.text((tx + (tab_w - nw) // 2, at_y + s(7)), name, font=f_at, fill=col)

    # ─── 2. Big block: огромное значение + дельта ───
    bb_y = at_y + at_h + s(6)
    f_big = fnt(24, bold=True)
    f_delta = fnt(12, bold=True)
    f_secondary = fnt(10)

    big_value = "P581 200"
    draw.text((win_x + s(20), bb_y), big_value, font=f_big, fill=TEXT)

    # Дельта одной строкой
    f_d_y = bb_y + s(34)
    delta1 = "+P4 821 . Today" if loc["brokers_label"] == "BROKERS" else "+P4 821 . Сегодня"
    delta2 = "+P38 740 . All-time" if loc["brokers_label"] == "BROKERS" else "+P38 740 . Всё время"
    draw.text((win_x + s(20), f_d_y), delta1, font=f_delta, fill=GREEN)
    dw = text_w(draw, delta1, f_delta)
    draw.text((win_x + s(20) + dw + s(12), f_d_y + s(2)), delta2, font=f_secondary, fill=MUTED)

    # ─── 3. Stat cards — наши 4 (как в приложении) ───
    cards_y = bb_y + s(54)
    cards_h = s(56)
    gap = s(8)
    inner_w = win_w - s(36)
    card_w = (inner_w - gap * 3) // 4

    # Наши реальные карточки из приложения
    if loc["brokers_label"] == "BROKERS":
        stat_data = [
            ("ALL-TIME RETURN", "+7.14%", LIME),
            ("TODAY", "+0.83%", GREEN),
            ("ACCRUED INT.", "P12 458", TEXT),
            ("YTM", "11.84%", LIME),
        ]
    else:
        stat_data = [
            ("ДОХОДНОСТЬ ВСЕГО", "+7.14%", LIME),
            ("ДОХОДНОСТЬ ДЕНЬ",  "+0.83%", GREEN),
            ("НКД",              "P12 458", TEXT),
            ("YTM",              "11.84%",  LIME),
        ]

    f_cl = fnt(7, bold=True)
    f_cv = fnt(15, bold=True, mono=True)

    for i, (label, value, val_color) in enumerate(stat_data):
        cx = win_x + s(18) + i * (card_w + gap)
        draw.rounded_rectangle(
            [cx, cards_y, cx + card_w, cards_y + cards_h],
            radius=s(6), fill=BG_SOFT, outline=BORDER, width=s(1),
        )
        draw.text((cx + s(8), cards_y + s(8)), label, font=f_cl, fill=MUTED)
        draw.text((cx + s(8), cards_y + s(24)), value, font=f_cv, fill=val_color)

    # ─── 4. Top positions — наш реальный список pos-item ───
    pos_y = cards_y + cards_h + s(12)
    if loc["brokers_label"] == "BROKERS":
        pos_title = "Top positions"
    else:
        pos_title = "Топ позиции"
    f_pt = fnt(9, bold=True)
    draw.text((win_x + s(18), pos_y), pos_title, font=f_pt, fill=MUTED)

    # Список из 2 позиций — компактно, чтобы влез footer
    items = [
        ("SBER", "Сбербанк",   "Акция",      "share",    "P289.1", "+P2 655", GREEN,  GREEN),
        ("GAZP", "Газпром",    "Акция",      "share",    "P154.3", "-P616",   RED,    GREEN),
    ]
    if loc["brokers_label"] == "BROKERS":
        items = [
            ("SBER", "Sberbank", "Stock", "share", "P289.1", "+P2 655", GREEN, GREEN),
            ("GAZP", "Gazprom",  "Stock", "share", "P154.3", "-P616",   RED,   GREEN),
        ]

    f_pn = fnt(11, bold=True)
    f_ps = fnt(9)
    f_pp = fnt(11, bold=True, mono=True)
    f_pd = fnt(10, bold=True, mono=True)

    item_h = s(34)
    item_y0 = pos_y + s(16)

    type_bgs = {"share": "rgba(74,222,128,0.14)", "bond": "rgba(96,165,250,0.14)", "etf": "rgba(192,132,252,0.14)"}
    type_fgs = {"share": GREEN, "bond": BLUE, "etf": PURPLE}

    for i, (tk, name, sub, itype, price, pnl, pnl_col, type_col) in enumerate(items):
        iy = item_y0 + i * (item_h + s(4))
        # Карточка строки
        draw.rounded_rectangle(
            [win_x + s(18), iy, win_x + win_w - s(18), iy + item_h],
            radius=s(6), fill=BG_SOFT,
        )
        # Цветная иконка-кружок типа
        ic_x = win_x + s(28)
        ic_y = iy + s(8)
        ic_r = s(12)
        # Hex с alpha → используем rgba конвертацию через PIL alpha-overlay
        # Для простоты — solid colored circle, dimmer вариант
        draw.ellipse(
            [ic_x, ic_y, ic_x + ic_r * 2, ic_y + ic_r * 2],
            fill=BG_CARD, outline=type_col, width=s(2),
        )
        # Первая буква типа в центре кружка
        first = tk[0]
        f_ic = fnt(11, bold=True)
        fw = text_w(draw, first, f_ic)
        draw.text((ic_x + ic_r - fw // 2, ic_y + s(4)), first, font=f_ic, fill=type_col)

        # Тикер + название
        text_x = ic_x + ic_r * 2 + s(10)
        draw.text((text_x, iy + s(6)), tk, font=f_pn, fill=TEXT)
        tw = text_w(draw, tk, f_pn)
        draw.text((text_x + tw + s(8), iy + s(8)), sub, font=f_ps, fill=MUTED)

        # Текущая цена + P&L справа
        right_x = win_x + win_w - s(28)
        pnl_w = text_w(draw, pnl, f_pd)
        draw.text((right_x - pnl_w, iy + s(20)), pnl, font=f_pd, fill=pnl_col)
        price_w = text_w(draw, price, f_pp)
        draw.text((right_x - price_w, iy + s(6)), price, font=f_pp, fill=TEXT)

    # ─── Footer ───
    foot_y = win_y + win_h - s(22)
    f_ft = fnt(9, mono=True)
    draw.text(
        (win_x + s(20), foot_y),
        loc["footer_left"],
        font=f_ft, fill=MUTED_2,
    )
    # Connected indicator (правая сторона)
    right_text = loc["footer_right"]
    rw = text_w(draw, right_text, f_ft)
    rx = win_x + win_w - s(20) - rw - s(14)
    cy = foot_y + s(6)
    r = s(3)
    draw.ellipse([rx, cy - r, rx + r * 2, cy + r * 2], fill=GREEN)
    draw.text((rx + s(10), foot_y), right_text, font=f_ft, fill=GREEN)


# ── Версия (левый-верх, единственный pill в углу — "v2.6.1") ────────────────
def draw_version_pill(draw: ImageDraw.ImageDraw):
    f = fnt(13, bold=True, mono=True)
    label = f"v{APP_VERSION}"
    tw = text_w(draw, label, f)
    th = text_h(draw, label, f)
    pad_x, pad_y = s(14), s(8)
    box_w, box_h = tw + pad_x * 2, th + pad_y * 2

    # Чуть крупнее и солиднее — стоит сам по себе
    px = s(60)
    py = s(70)
    draw.rounded_rectangle(
        [px, py, px + box_w, py + box_h],
        radius=s(8), fill=BG_CARD, outline=LIME_DIM, width=s(1),
    )
    draw.text((px + pad_x, py + pad_y - s(2)), label, font=f, fill=LIME)


# ── Сборка ────────────────────────────────────────────────────────────────────
def generate(out_path: Path, locale: str = "en"):
    if locale not in LOCALES:
        raise SystemExit(f"Unknown locale '{locale}'. Available: {list(LOCALES)}")
    loc = LOCALES[locale]

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Слои снизу вверх:
    draw_grid(draw)
    draw_corner_marks(draw)

    # Лайм-glow за заголовком (левая часть)
    draw_glow_ellipse(img, cx=s(280), cy=s(260), rx=s(360), ry=s(280),
                      rgba=(184, 243, 74, 22))
    # Жёлтый glow за акцентной строкой заголовка
    draw_glow_ellipse(img, cx=s(220), cy=s(225), rx=s(160), ry=s(80),
                      rgba=(250, 204, 21, 30))

    # Diagonal streak (после glow, до контента)
    draw_diagonal_streak(img)

    # Контент
    draw = ImageDraw.Draw(img)
    draw_left_panel(draw, img, loc)

    # Z-order справа: главный dashboard (фон) → Payouts (середина) → Simple (фронт).
    # Каждый последующий частично перекрывает предыдущий, создавая "стопку".
    # ┌──────────────────────────────────────────────────────────────────┐
    # │ Если в assets/mockups/ есть реальные скриншоты — используем их   │
    # │ (см. ui/window.py → save_screenshot, кнопка "📷 Dev" в шапке).   │
    # │ Иначе fallback на нарисованные мокапы Pillow.                    │
    # └──────────────────────────────────────────────────────────────────┘

    # Главное окно (низ-право) — обычно скриншот вкладки Обзор
    main_shot = load_mockup("overview")
    if main_shot is not None:
        paste_window_screenshot(img, main_shot, x=600, y=230, w=640, h=380)
    else:
        draw_window_mockup(draw, img, loc)
    draw = ImageDraw.Draw(img)

    # Среднее окно (верх-право) — Выплаты / Bonds tab
    payouts_shot = load_mockup("bonds") or load_mockup("payouts")
    if payouts_shot is not None:
        paste_window_screenshot(img, payouts_shot, x=860, y=80, w=380, h=280)
    else:
        draw_payouts_mockup(draw, img, loc)
    draw = ImageDraw.Draw(img)

    # Малое окно (верх-лево) — Упрощённый режим
    simple_shot = load_mockup("simple")
    if simple_shot is not None:
        paste_window_screenshot(img, simple_shot, x=560, y=20, w=440, h=200)
    else:
        draw_simple_mockup(draw, img, loc)
    draw = ImageDraw.Draw(img)

    draw_version_pill(draw)

    # Лог: какие окна были взяты из реальных скриншотов
    sources = []
    if main_shot:    sources.append("overview")
    if payouts_shot: sources.append("bonds")
    if simple_shot:  sources.append("simple")
    if sources:
        print(f"     Used real screenshots: {', '.join(sources)}")
    else:
        print(f"     Used Pillow-drawn mockups (no screenshots in {MOCKUPS_DIR.relative_to(ROOT)})")

    # Downscale 2x → 1x (resampling LANCZOS — резкие шрифты)
    final = img.resize((W_OUT, H_OUT), Image.LANCZOS)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    final.save(out_path, "PNG", optimize=True)

    size_kb = out_path.stat().st_size / 1024
    print(f"[OK] Generated: {out_path}")
    print(f"     Locale:     {locale}")
    print(f"     Resolution: {W_OUT}x{H_OUT} (rendered at {W}x{H}, downscaled)")
    print(f"     File size:  {size_kb:.1f} KB")
    print()
    print("     Upload at: GitHub repo -> Settings -> Options -> Social preview")


def main():
    p = argparse.ArgumentParser(description="Generate GitHub social preview PNG for Stack.")
    p.add_argument("--out", type=Path, default=DEFAULT_OUT,
                   help=f"Output path (default: {DEFAULT_OUT.relative_to(ROOT)})")
    p.add_argument("--locale", choices=list(LOCALES), default="en",
                   help="Language for labels (default: en)")
    p.add_argument("--all", action="store_true",
                   help="Generate one PNG per locale (suffix added before extension)")
    args = p.parse_args()

    if args.all:
        for loc_code in LOCALES:
            stem = args.out.stem
            ext = args.out.suffix
            out_localized = args.out.with_name(f"{stem}-{loc_code}{ext}")
            generate(out_localized, loc_code)
            print()
    else:
        generate(args.out, args.locale)


if __name__ == "__main__":
    main()
