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
import hashlib

log = logging.getLogger("stack.updater")

from version import APP_VERSION
from constants import GITHUB_REPO

GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

if getattr(sys, 'frozen', False):
    _UPDATE_DIR = os.path.join(
        os.environ.get("APPDATA", os.path.dirname(sys.executable)),
        "Stack", "update")
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
            result["error"] = f"GitHub: HTTP {r.status_code}. Проверьте сеть и лимит запросов."
            log.warning(result["error"])
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
            if name.lower() == "stack.exe":
                result["available"] = True
                result["version"] = tag.lstrip("vV")
                result["url"] = asset.get("browser_download_url", "")
                result["asset_name"] = name
                result["changelog"] = data.get("body", "")[:500]
                result["size"] = asset.get("size")
                result["digest"] = asset.get("digest")
                log.info("Доступно обновление: %s → %s", APP_VERSION, result["version"])
                return result

        result["error"] = f"В релизе {tag} отсутствует Stack.exe."
        log.warning(result["error"])

    except Exception as e:
        result["error"] = "Не удалось проверить обновление. Проверьте подключение к GitHub."
        log.warning("Ошибка проверки обновлений: %s", e)

    return result


def download_update(url: str, asset_name: str = "Stack.exe", *,
                    size: int | None = None, digest: str | None = None) -> str | None:
    """
    Скачивает новый .exe в папку update/.
    Возвращает путь к скачанному файлу или None.
    """
    if asset_name.lower() != "stack.exe":
        log.error("Неожиданное имя файла обновления")
        return None
    partial = os.path.join(_UPDATE_DIR, asset_name + ".part")
    try:
        os.makedirs(_UPDATE_DIR, exist_ok=True)
        dest = os.path.join(_UPDATE_DIR, asset_name)

        log.info("Скачиваю обновление: %s", url)
        r = requests.get(url, stream=True, timeout=(10, 120))
        try:
            r.raise_for_status()
            sha = hashlib.sha256()
            with open(partial, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    f.write(chunk)
                    sha.update(chunk)
        finally:
            r.close()
        if size is not None and os.path.getsize(partial) != size:
            raise ValueError("Размер обновления не совпадает с релизом")
        if digest and digest != "sha256:" + sha.hexdigest():
            raise ValueError("Контрольная сумма обновления не совпадает с релизом")
        with open(partial, "rb") as f:
            if f.read(2) != b"MZ":
                raise ValueError("Скачанный файл не является Windows .exe")
        os.replace(partial, dest)

        size_mb = os.path.getsize(dest) / 1048576
        log.info("Скачано: %s (%.1f МБ)", dest, size_mb)
        return dest

    except Exception as e:
        log.error("Ошибка скачивания обновления: %s", e)
        return None
    finally:
        if os.path.exists(partial):
            os.remove(partial)


def apply_update(new_exe_path: str) -> bool:
    """
    Запускает скрытый помощник: ждёт выхода, атомарно заменяет .exe и перезапускает.
    Ошибки помощника сохраняются в update.log; предыдущая версия — в .bak.
    """
    if not getattr(sys, 'frozen', False):
        log.warning("apply_update: не в режиме .exe")
        return False

    current_exe = sys.executable
    script_path = os.path.join(_UPDATE_DIR, "_update.ps1")
    # Single-quoted PowerShell literals preserve Unicode and paths with shell metacharacters.
    current = current_exe.replace("'", "''")
    source = os.path.abspath(new_exe_path).replace("'", "''")
    script = f'''$ErrorActionPreference = 'Stop'
$current = '{current}'
$source = '{source}'
$staged = $current + '.update-new'
$backup = $current + '.bak'
$log = Join-Path $PSScriptRoot 'update.log'
$replaced = $false
try {{
    $process = Get-Process -Id {os.getpid()} -ErrorAction SilentlyContinue
    if ($process -and -not $process.WaitForExit(60000)) {{ throw 'Application did not exit in 60 seconds' }}
    Copy-Item -LiteralPath $source -Destination $staged -Force
    for ($attempt = 0; $attempt -lt 60; $attempt++) {{
        try {{
            [System.IO.File]::Replace($staged, $current, $backup)
            $replaced = $true
            break
        }} catch {{
            if ($attempt -eq 59) {{ throw }}
            Start-Sleep -Milliseconds 500
        }}
    }}
    Start-Process -FilePath $current -WindowStyle Hidden
    Remove-Item -LiteralPath $source -Force
    'Update installed successfully' | Out-File -LiteralPath $log -Encoding utf8
}} catch {{
    $_ | Out-File -LiteralPath $log -Encoding utf8
    if ($replaced) {{ [System.IO.File]::Replace($backup, $current, $current + '.failed') }}
    if (Test-Path -LiteralPath $current) {{ Start-Process -FilePath $current -WindowStyle Hidden }}
}} finally {{
    if (Test-Path -LiteralPath $staged) {{ Remove-Item -LiteralPath $staged -Force }}
}}
'''
    try:
        if os.path.samefile(new_exe_path, current_exe):
            raise ValueError("Обновление совпадает с запущенным файлом")
        # Check access before asking the running app to exit.
        with tempfile.NamedTemporaryFile(dir=os.path.dirname(current_exe)):
            pass
        os.makedirs(_UPDATE_DIR, exist_ok=True)
        with open(script_path, "w", encoding="utf-8-sig") as f:
            f.write(script)
        subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", script_path],
            creationflags=subprocess.CREATE_NO_WINDOW,
            close_fds=True,
            env={**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"},
        )
        return True
    except Exception:
        log.exception("Не удалось запустить обновление. Проверьте права записи в папку приложения.")
        return False
