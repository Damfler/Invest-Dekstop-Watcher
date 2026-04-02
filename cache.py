"""
cache.py — сохранение и загрузка последних данных портфеля на диск.
При старте показываем кэш мгновенно, API загружается в фоне.
Максимальный возраст кэша — 24 часа.
"""
import json
import os
import sys
import logging
from datetime import datetime, timezone

log = logging.getLogger("tbank.cache")

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.join(os.environ.get("APPDATA", os.path.dirname(sys.executable)), "TBankWatcher")
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(BASE_DIR, exist_ok=True)
CACHE_FILE    = os.path.join(BASE_DIR, "cache.json")
HISTORY_FILE  = os.path.join(BASE_DIR, "history.json")
MAX_AGE_H     = 24   # часов
MAX_HISTORY   = 5000  # макс. точек истории (~17 дней при 5-мин интервале)


def save_cache(portfolios: list, bond_events: list,
               bond_nkd: dict, positions_extra: list):
    """Сохраняет текущее состояние в cache.json."""
    def _dt(v):
        return v.isoformat() if isinstance(v, datetime) else v

    def _ev(e: dict) -> dict:
        return {**e, "date": _dt(e["date"])}

    payload = {
        "saved_at":       datetime.now(timezone.utc).isoformat(),
        "portfolios":     portfolios,
        "bond_events":    [_ev(e) for e in bond_events],
        "bond_nkd":       bond_nkd,
        "positions_extra": positions_extra,
    }
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        log.debug("Кэш сохранён")
    except Exception as e:
        log.warning("Не удалось сохранить кэш: %s", e)


def save_history(points: list[dict]):
    """Сохраняет историю портфеля в отдельный файл (без лимита по возрасту)."""
    try:
        trimmed = points[-MAX_HISTORY:]
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(trimmed, f, ensure_ascii=False)
    except Exception as e:
        log.warning("Не удалось сохранить историю: %s", e)


def load_history() -> list[dict]:
    """Загружает историю портфеля из файла."""
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.warning("Ошибка чтения истории: %s", e)
        return []


def load_cache() -> dict | None:
    """
    Возвращает данные из кэша или None если кэш отсутствует / устарел.
    """
    if not os.path.exists(CACHE_FILE):
        return None
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            data = json.load(f)

        saved_at = datetime.fromisoformat(data["saved_at"])
        age_h    = (datetime.now(timezone.utc) - saved_at).total_seconds() / 3600
        if age_h > MAX_AGE_H:
            log.info("Кэш устарел (%.1f ч > %d ч), игнорируем", age_h, MAX_AGE_H)
            return None

        # Восстанавливаем datetime в событиях
        from utils import parse_ts
        for e in data.get("bond_events", []):
            if isinstance(e.get("date"), str):
                e["date"] = parse_ts(e["date"])

        log.info("Загружен кэш (возраст %.1f ч)", age_h)
        return data

    except Exception as e:
        log.warning("Ошибка чтения кэша: %s", e)
        return None
