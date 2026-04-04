"""
updater.py — автообновление через GitHub Releases.

Проверяет наличие новой версии, скачивает .exe, применяет обновление.
Работает только в режиме .exe (sys.frozen), в Python-режиме пропускает.
"""
import os
import sys
import logging
import requests
import subprocess
import tempfile

log = logging.getLogger("tbank.updater")

from version import APP_VERSION
from constants import GITHUB_REPO

GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

if getattr(sys, 'frozen', False):
    _UPDATE_DIR = os.path.join(
        os.environ.get("APPDATA", os.path.dirname(sys.executable)),
        "InvestDesktopWatcher", "update")
else:
    _UPDATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_update")


def _parse_version(v: str) -> tuple:
    """'v2.1.3' → (2, 1, 3), '2.1' → (2, 1, 0)"""
    v = v.strip().lstrip("vV")
    parts = []
    for p in v.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            break
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def check_for_update() -> dict:
    """
    Проверяет GitHub Releases.
    Возвращает: {available, version, url, changelog, asset_name}
    """
    result = {"available": False, "version": "", "url": "", "changelog": "", "asset_name": ""}

    if not getattr(sys, 'frozen', False):
        log.debug("Пропуск проверки обновлений (не .exe)")
        return result

    try:
        r = requests.get(GITHUB_API, timeout=10, headers={"Accept": "application/json"})
        if r.status_code != 200:
            log.debug("GitHub API: %d", r.status_code)
            return result

        data = r.json()
        tag = data.get("tag_name", "")
        remote_ver = _parse_version(tag)
        local_ver  = _parse_version(APP_VERSION)

        if remote_ver <= local_ver:
            log.debug("Версия актуальна: %s >= %s", APP_VERSION, tag)
            return result

        # Ищем .exe в assets
        for asset in data.get("assets", []):
            name = asset.get("name", "")
            if name.lower().endswith(".exe"):
                result["available"] = True
                result["version"] = tag.lstrip("vV")
                result["url"] = asset.get("browser_download_url", "")
                result["asset_name"] = name
                result["changelog"] = data.get("body", "")[:500]
                log.info("Доступно обновление: %s → %s", APP_VERSION, result["version"])
                return result

        log.debug("В релизе %s нет .exe", tag)

    except Exception as e:
        log.debug("Ошибка проверки обновлений: %s", e)

    return result


def download_update(url: str, asset_name: str = "tbank_invest.exe") -> str | None:
    """
    Скачивает новый .exe в папку update/.
    Возвращает путь к скачанному файлу или None.
    """
    try:
        os.makedirs(_UPDATE_DIR, exist_ok=True)
        dest = os.path.join(_UPDATE_DIR, asset_name)

        log.info("Скачиваю обновление: %s", url)
        r = requests.get(url, stream=True, timeout=120)
        r.raise_for_status()

        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                f.write(chunk)

        size_mb = os.path.getsize(dest) / 1048576
        log.info("Скачано: %s (%.1f МБ)", dest, size_mb)
        return dest

    except Exception as e:
        log.error("Ошибка скачивания обновления: %s", e)
        return None


def apply_update(new_exe_path: str):
    """
    Заменяет текущий .exe на новый и перезапускает.
    Создаёт .bat скрипт который:
    1. Ждёт завершения текущего процесса
    2. Копирует new.exe → current.exe
    3. Запускает обновлённый .exe
    4. Удаляет себя и new.exe
    """
    if not getattr(sys, 'frozen', False):
        log.warning("apply_update: не в режиме .exe")
        return

    current_exe = sys.executable
    bat_path = os.path.join(_UPDATE_DIR, "_update.bat")

    from version import APP_NAME
    bat_content = f'''@echo off
echo Обновление {APP_NAME}...
timeout /t 2 /nobreak >nul
copy /y "{new_exe_path}" "{current_exe}" >nul
if errorlevel 1 (
    echo Ошибка копирования. Попробуйте обновить вручную.
    pause
    exit /b 1
)
start "" "{current_exe}"
del /f /q "{new_exe_path}" >nul 2>&1
del /f /q "%~f0" >nul 2>&1
'''

    with open(bat_path, "w", encoding="cp866") as f:
        f.write(bat_content)

    log.info("Запуск обновления: %s", bat_path)
    subprocess.Popen(
        ["cmd", "/c", bat_path],
        creationflags=subprocess.CREATE_NO_WINDOW,
        close_fds=True,
    )
