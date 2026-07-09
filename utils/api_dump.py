"""
api_dump.py — сохранение сырых ответов API в файлы для отладки.

Папка:
  - .exe: %APPDATA%\\Stack\\api_dump\\
  - dev:  ./api_dump/

Включение:
  set STACK_API_DUMP=1

Важно:
  - дампы перезаписываются на каждом обновлении
  - потенциально чувствительные поля (token/Authorization) редактируются
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import threading
from datetime import datetime, timezone

log = logging.getLogger("stack.api_dump")

_lock = threading.Lock()
_dump_dir: str | None = None

_README = """\
Stack — дампы ответов API
========================

Сюда Stack сохраняет последние сырые ответы брокерских API (JSON) для отладки.
Файлы перезаписываются при каждом обновлении.

Как включить:
  set STACK_API_DUMP=1

Что внутри JSON:
  - dumped_at: UTC timestamp
  - broker/connection: источник данных
  - op: логическое имя операции (get_accounts/get_portfolio/...)
  - args: параметры вызова (если есть)
  - body: ответ сервера как есть (с редактированием токенов)
  - error: текст ошибки (если было исключение)
"""


def enabled() -> bool:
    v = (os.environ.get("STACK_API_DUMP") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.join(
            os.environ.get("APPDATA", os.path.dirname(sys.executable)), "Stack",
        )
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def dump_dir() -> str:
    global _dump_dir
    if _dump_dir is None:
        _dump_dir = os.path.join(_base_dir(), "api_dump")
        os.makedirs(_dump_dir, exist_ok=True)
        readme = os.path.join(_dump_dir, "README.txt")
        if not os.path.exists(readme):
            with open(readme, "w", encoding="utf-8") as f:
                f.write(_README)
    return _dump_dir


def _safe_name(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^\w\-]+", "_", s).strip("_")
    s = re.sub(r"_+", "_", s)
    return (s[:140] or "dump") + ".json"


def _redact(obj):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            lk = str(k).lower()
            if lk in ("token", "access_token", "refresh_token", "authorization"):
                out[k] = "***REDACTED***" if v else v
            else:
                out[k] = _redact(v)
        return out
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    return obj


def dump(*, filename: str, payload: dict) -> str:
    """
    Сохраняет payload в JSON-файл. Возвращает путь к файлу.
    """
    if not enabled():
        return ""
    path = os.path.join(dump_dir(), _safe_name(filename))
    with _lock:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    log.info("API dump → %s", path)
    return path


def dump_call(
    *,
    broker: str,
    connection: str,
    op: str,
    args: dict | None = None,
    body=None,
    error: str | None = None,
) -> str:
    if not enabled():
        return ""
    payload = {
        "dumped_at":  datetime.now(timezone.utc).isoformat(),
        "broker":     broker,
        "connection": connection,
        "op":         op,
        "args":       args or {},
        "error":      error,
        "body":       _redact(body),
    }
    fname = f"{broker}_{connection}_{op}"
    return dump(filename=fname, payload=payload)

