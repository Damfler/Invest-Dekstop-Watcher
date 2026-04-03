"""
config.py — загрузка и сохранение конфигурации.
Токен берётся из .env (для разработки) или config.json (для пользователя).
"""
import json
import os
import sys

# Пользовательские файлы в %APPDATA%/TBankWatcher/ (для .exe)
# или рядом со скриптом (для разработки)
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.join(os.environ.get("APPDATA", os.path.dirname(sys.executable)), "TBankWatcher")
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(BASE_DIR, exist_ok=True)
CONFIG_FILE    = os.path.join(BASE_DIR, "config.json")
DISMISSED_FILE = os.path.join(BASE_DIR, "dismissed.json")

DEFAULT_CONFIG: dict = {
    "token": "YOUR_TBANK_API_TOKEN_HERE",
    "use_sandbox": False,

    "use_custom_icons": True,

    # Горизонт событий облигаций (дни). Переключается в меню.
    "bond_horizon_days": 60,

    # Сортировка событий: "date" | "amount"
    "bond_sort": "date",

    # Максимальное количество событий облигаций в меню
    "max_bond_events": 50,

    # Тема дашборда: "dark" | "light" | "system"
    "theme": "system",

    # Показывать логотипы инструментов (True) или иконки (False)
    "use_logos": False,

    # Пользовательское название приложения
    "app_name": "",

    # Показывать подсказки (концентрация и т.д.)
    "show_hints": False,

    # Автообновление через GitHub Releases
    "auto_update": True,

    "notifications": {
        "offer_warn":       True,
        "offer_crit":       True,
        "coupon_tomorrow":  True,
        "portfolio_move":   True,
    },

    # Настраиваемые пороги
    "notify_move_pct":   1.0,   # % изменения портфеля для уведомления
    "notify_offer_days": 2,     # за сколько дней предупреждать об оферте
}


def load_config() -> dict:
    if not os.path.exists(CONFIG_FILE):
        _write_default()
        print("Создан config.json — вставьте токен и перезапустите.")
        sys.exit(0)

    raw = ""
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            raw = f.read()
        cfg = json.loads(raw)

    except json.JSONDecodeError as e:
        # Показываем конкретную проблемную строку
        lines = raw.splitlines()
        bad_line = lines[e.lineno - 1] if e.lineno <= len(lines) else ""
        backup   = CONFIG_FILE + ".bak"

        print("=" * 60)
        print("ОШИБКА: config.json содержит невалидный JSON.")
        print(f"  Строка {e.lineno}, позиция {e.colno}: {e.msg}")
        print(f"  → {bad_line!r}")
        print()
        print("Возможные причины:")
        print("  • Случайно добавлен текст/комментарий в файл")
        print("  • Файл сохранён с неверной кодировкой")
        print("  • Незакрытая кавычка или лишняя запятая")
        print()

        # Пробуем спасти токен из сломанного файла
        import re
        token_match = re.search(r'"token"\s*:\s*"([^"]{10,})"', raw)
        saved_token = token_match.group(1) if token_match else None

        # Сохраняем бэкап сломанного файла
        try:
            import shutil
            shutil.copy2(CONFIG_FILE, backup)
            print(f"Сломанный файл сохранён как: {backup}")
        except Exception:
            pass

        # Создаём чистый конфиг
        _write_default(token=saved_token)
        if saved_token:
            print(f"Токен из старого файла сохранён: {saved_token[:8]}…")
            print("Создан новый config.json — перезапустите приложение.")
        else:
            print("Создан новый config.json — вставьте токен и перезапустите.")
        print("=" * 60)
        sys.exit(1)

    # Мягкое слияние: добавляем новые ключи не ломая старый конфиг
    def _merge(dst: dict, src: dict):
        for k, v in src.items():
            if k not in dst:
                dst[k] = v
            elif isinstance(v, dict) and isinstance(dst.get(k), dict):
                _merge(dst[k], v)

    _merge(cfg, DEFAULT_CONFIG)

    # Валидация
    cfg["notify_move_pct"]   = max(0.1, float(cfg.get("notify_move_pct",   1.0)))
    cfg["notify_offer_days"] = max(0,   int(cfg.get("notify_offer_days",   2)))
    cfg["bond_horizon_days"] = int(cfg.get("bond_horizon_days", 60))
    if cfg.get("bond_sort") not in ("date", "amount"):
        cfg["bond_sort"] = "date"

    # .env — перезаписывает токен из config.json (для разработки)
    _env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(_env_file):
        try:
            with open(_env_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, val = line.split("=", 1)
                        if key.strip() == "TBANK_TOKEN" and val.strip():
                            cfg["token"] = val.strip()
        except Exception:
            pass

    return cfg


def _write_default(token: str | None = None):
    """Записывает дефолтный конфиг, опционально подставляя токен."""
    cfg = dict(DEFAULT_CONFIG)
    if token:
        cfg["token"] = token
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def save_config(cfg: dict):
    """Сохраняет только изменяемые пользователем поля."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def load_dismissed() -> set:
    try:
        with open(DISMISSED_FILE, encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()


def save_dismissed(keys: set):
    try:
        with open(DISMISSED_FILE, "w", encoding="utf-8") as f:
            json.dump(list(keys), f)
    except Exception:
        pass
