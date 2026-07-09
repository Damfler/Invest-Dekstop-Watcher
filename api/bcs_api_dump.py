"""
bcs_api_dump.py — сохранение сырых ответов BCS Trade API в файлы для отладки.

Папка: %APPDATA%\\Stack\\bcs_api_dump\\  (или ./bcs_api_dump/ в dev)
По одному JSON на метод/эндпоинт (перезаписывается при каждом запросе).
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import threading
from datetime import datetime, timezone

log = logging.getLogger("stack.bcs.dump")

_lock = threading.Lock()
_dump_dir: str | None = None


def enabled() -> bool:
    """
    В боевой среде дампы по умолчанию выключены.
    Включение: set BCS_API_DUMP=1  (или STACK_API_DUMP=1 как общий флаг)
    """
    v = (os.environ.get("BCS_API_DUMP") or os.environ.get("STACK_API_DUMP") or "").strip().lower()
    return v in ("1", "true", "yes", "on")

_README = """\
BCS Trade API — дампы ответов
=============================

Сюда Stack сохраняет последние сырые ответы BCS API (JSON).
Файлы перезаписываются при каждом обновлении портфеля.

Примеры файлов:
  GET_portfolio.json          — портфель
  GET_limits.json             — лимиты / остатки (depoLimit, moneyLimits)
  POST_oauth_token.json       — OAuth (токены замазаны)
  GET_instrument_TQBR_SBER.json — справочник по тикеру

Поле body — ответ сервера как есть.
"""


def _base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.join(
            os.environ.get("APPDATA", os.path.dirname(sys.executable)), "Stack",
        )
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def dump_dir() -> str:
    global _dump_dir
    if not enabled():
        return ""
    if _dump_dir is None:
        _dump_dir = os.path.join(_base_dir(), "bcs_api_dump")
        os.makedirs(_dump_dir, exist_ok=True)
        readme = os.path.join(_dump_dir, "README.txt")
        if not os.path.exists(readme):
            with open(readme, "w", encoding="utf-8") as f:
                f.write(_README)
    return _dump_dir


def _safe_name(label: str, method: str, url: str, params: dict | None) -> str:
    parts: list[str] = []
    m = (method or "GET").upper()
    if m:
        parts.append(m)
    tag = (label or "").strip()
    if tag:
        tag = re.sub(r"[^\w\-]+", "_", tag).strip("_")
        parts.append(tag)
    if params:
        cc = params.get("classCode") or params.get("class_code")
        ticker = params.get("ticker")
        if cc:
            parts.append(str(cc))
        if ticker:
            parts.append(str(ticker))
    if len(parts) <= 1:
        tail = url.rstrip("/").split("/")[-1]
        if tail:
            parts.append(tail)
    name = "_".join(p for p in parts if p).lower()
    return re.sub(r"_+", "_", name)[:120] or "response"


def _redact(obj):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in ("access_token", "refresh_token") and v:
                out[k] = "***REDACTED***"
            else:
                out[k] = _redact(v)
        return out
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    return obj


def _parse_body(text: str):
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"_raw_text": text}


def dump_api_response(
    *,
    label: str,
    method: str,
    url: str,
    params: dict | None = None,
    status_code: int | None = None,
    body_text: str = "",
    error: str | None = None,
    redact_tokens: bool = False,
) -> str:
    """
    Сохраняет ответ в JSON-файл. Возвращает путь к файлу.
    """
    if not enabled():
        return ""
    body = _parse_body(body_text)
    if redact_tokens:
        body = _redact(body)

    payload = {
        "dumped_at":   datetime.now(timezone.utc).isoformat(),
        "label":       label,
        "method":      method.upper(),
        "url":         url,
        "params":      params or {},
        "status_code": status_code,
        "error":       error,
        "body":        body,
    }

    fname = _safe_name(label, method, url, params) + ".json"
    base = dump_dir()
    if not base:
        return ""
    path = os.path.join(base, fname)

    with _lock:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    log.info("BCS API dump → %s", path)
    return path
