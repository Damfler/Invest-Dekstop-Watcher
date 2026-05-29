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
import logging
from PIL import Image, ImageDraw

log = logging.getLogger("stack.icons")

BASE_DIR  = getattr(sys, '_MEIPASS', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ICONS_DIR = os.path.join(BASE_DIR, "assets", "icons")

if getattr(sys, 'frozen', False):
    _USER_ICONS = os.path.join(
        os.environ.get("APPDATA", os.path.dirname(sys.executable)),
        "Stack", "icons")
else:
    _USER_ICONS = ICONS_DIR

# Один раз при загрузке модуля логируем где ищем иконки —
# это поможет диагностировать почему PNG не находится в .exe.
log.info("Icons resolver: BASE_DIR=%s  ICONS_DIR=%s  USER_ICONS=%s",
         BASE_DIR, ICONS_DIR, _USER_ICONS)
if os.path.isdir(ICONS_DIR):
    try:
        _icon_files = sorted(os.listdir(ICONS_DIR))
        log.info("Icons resolver: bundled assets/icons/ contains %d files: %s",
                 len(_icon_files), _icon_files[:20])
    except Exception:
        pass
else:
    log.warning("Icons resolver: ICONS_DIR DOES NOT EXIST — программный fallback гарантирован")

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


# Чтобы не спамить лог одинаковыми записями при каждой перерисовке трея,
# логируем результат для каждого имени иконки только один раз.
_logged_load: set = set()


def _is_light_taskbar() -> bool:
    """True, если у Windows установлена СВЕТЛАЯ тема панели задач.
    Читаем `SystemUsesLightTheme` из реестра."""
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as k:
            val, _ = winreg.QueryValueEx(k, "SystemUsesLightTheme")
            return val == 1
    except Exception:
        return False  # по умолчанию считаем dark


# Кэшируем результат — реестр читаем 1 раз за процесс
_TASKBAR_LIGHT = _is_light_taskbar()
log.info("Windows taskbar theme: %s", "LIGHT" if _TASKBAR_LIGHT else "DARK")


def _variant_name(name: str) -> str:
    """positive.png -> positive-light.png при светлом taskbar."""
    if _TASKBAR_LIGHT and name.endswith(".png"):
        return name[:-4] + "-light.png"
    return name


def _load_custom(name: str) -> Image.Image | None:
    """Ищет PNG в %APPDATA%\\Stack\\icons или в assets/icons.

    Автоматически выбирает вариант под тему Windows taskbar:
    - тёмный taskbar (default) → positive.png
    - светлый taskbar → positive-light.png (с fallback на positive.png).
    """
    candidates = []
    variant = _variant_name(name)
    if variant != name:
        candidates.append(variant)  # под Windows-тему — приоритет
    candidates.append(name)         # базовый вариант — fallback

    for cn in candidates:
        for d in (_USER_ICONS, ICONS_DIR):
            p = os.path.join(d, cn)
            if not os.path.exists(p):
                continue
            try:
                img = Image.open(p).convert("RGBA")
                res = img.resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS)
                if name not in _logged_load:
                    log.info("Tray icon %s -> loaded from %s", name, p)
                    _logged_load.add(name)
                return res
            except Exception as e:
                log.warning("Cannot load icon %s: %s", p, e)
                continue
    if name not in _logged_load:
        log.warning("Tray icon %s NOT FOUND (tried %s) — fallback на стрелки",
                    name, candidates)
        _logged_load.add(name)
    return None


def _squircle(size: int, bg: tuple, ss: int = 4) -> Image.Image:
    """Skoraz squircle нужного цвета (используется fallback-иконками)."""
    s = size * ss
    img  = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle(
        [0, 0, s - 1, s - 1], radius=int(s * 0.22), fill=bg)
    return img, s, ss


def _draw_arrow_up(fg: tuple, bg: tuple, size: int = ICON_SIZE) -> Image.Image:
    """Стрелка вверх — fallback для роста, когда логотип не загрузился."""
    img, s, _ = _squircle(size, bg)
    draw = ImageDraw.Draw(img)
    cx, cy = s // 2, s // 2
    # Треугольник + ножка
    head = int(s * 0.18)
    stem_w = int(s * 0.10)
    stem_h = int(s * 0.18)
    pts = [(cx, cy - head), (cx + head, cy + head // 2), (cx - head, cy + head // 2)]
    draw.polygon(pts, fill=fg)
    draw.rectangle(
        [cx - stem_w // 2, cy + head // 2 - 2, cx + stem_w // 2, cy + head // 2 + stem_h],
        fill=fg)
    return img.resize((size, size), Image.LANCZOS)


def _draw_arrow_down(fg: tuple, bg: tuple, size: int = ICON_SIZE) -> Image.Image:
    """Стрелка вниз — fallback для просадки."""
    img, s, _ = _squircle(size, bg)
    draw = ImageDraw.Draw(img)
    cx, cy = s // 2, s // 2
    head = int(s * 0.18)
    stem_w = int(s * 0.10)
    stem_h = int(s * 0.18)
    pts = [(cx, cy + head), (cx + head, cy - head // 2), (cx - head, cy - head // 2)]
    draw.polygon(pts, fill=fg)
    draw.rectangle(
        [cx - stem_w // 2, cy - head // 2 - stem_h, cx + stem_w // 2, cy - head // 2 + 2],
        fill=fg)
    return img.resize((size, size), Image.LANCZOS)


def _draw_dash(fg: tuple, bg: tuple, size: int = ICON_SIZE) -> Image.Image:
    """Тире — fallback для нейтрального состояния."""
    img, s, _ = _squircle(size, bg)
    draw = ImageDraw.Draw(img)
    cx, cy = s // 2, s // 2
    w, h = int(s * 0.36), int(s * 0.10)
    draw.rounded_rectangle(
        [cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2],
        radius=h // 2, fill=fg)
    return img.resize((size, size), Image.LANCZOS)


def _draw_bang(fg: tuple, bg: tuple, size: int = ICON_SIZE) -> Image.Image:
    """Восклицательный знак — fallback для warn/crit."""
    img, s, _ = _squircle(size, bg)
    draw = ImageDraw.Draw(img)
    cx, cy = s // 2, s // 2
    w = int(s * 0.10)
    bar_h = int(s * 0.32)
    gap = int(s * 0.06)
    dot_r = int(w * 0.55)
    draw.rounded_rectangle(
        [cx - w // 2, cy - bar_h // 2 - gap // 2, cx + w // 2, cy + bar_h // 2 - gap // 2],
        radius=w // 2, fill=fg)
    cyd = cy + bar_h // 2 + gap
    draw.ellipse([cx - dot_r, cyd - dot_r, cx + dot_r, cyd + dot_r], fill=fg)
    return img.resize((size, size), Image.LANCZOS)


def make_icon_normal(delta: float, use_custom: bool = True) -> Image.Image:
    """Иконка обычного состояния (роста/просадки/нейтраль).

    use_custom — legacy-параметр, игнорируется. Логика: всегда сначала пробуем
    PNG (positive/negative/neutral → icon.png), и только если ни один не нашли —
    рисуем стрелочки программно.
    """
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
        return _draw_arrow_up(_BLACK, _GREEN)
    if delta < 0:
        return _draw_arrow_down(_BLACK, _RED)
    return _draw_dash(_BLACK, _GREY)


def make_icon_warn(use_custom: bool = True) -> Image.Image:
    img = _load_custom("warn.png") or _load_custom("icon.png")
    if img:
        return img
    return _draw_bang(_BLACK, _ORANGE)


def make_icon_crit(bright: bool, use_custom: bool = True) -> Image.Image:
    img = _load_custom("crit.png")
    if img:
        if not bright:
            img = img.point(lambda p: int(p * 0.35))
        return img
    bg = _RED if bright else _RED_DIM
    fg = _WHITE if bright else _WHITE_DIM
    return _draw_bang(fg, bg)
