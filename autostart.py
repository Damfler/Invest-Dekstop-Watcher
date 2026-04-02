"""
autostart.py — управление автозапуском через реестр Windows
"""
import sys
import os
import logging

log = logging.getLogger("tbank.autostart")

try:
    import winreg
    _WINREG_OK = True
except ImportError:
    _WINREG_OK = False   # не Windows

REG_KEY   = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME  = "TBankInvestTray"


def _cmd() -> str:
    pythonw = sys.executable.replace("python.exe", "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable
    script = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "main.py")
    )
    return f'"{pythonw}" "{script}"'


def is_enabled() -> bool:
    if not _WINREG_OK:
        return False
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0,
                             winreg.KEY_READ)
        winreg.QueryValueEx(key, APP_NAME)
        winreg.CloseKey(key)
        return True
    except Exception:
        return False


def enable() -> bool:
    if not _WINREG_OK:
        return False
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0,
                             winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _cmd())
        winreg.CloseKey(key)
        log.info("Автозапуск включён")
        return True
    except Exception as e:
        log.error("Ошибка включения автозапуска: %s", e)
        return False


def disable() -> bool:
    if not _WINREG_OK:
        return False
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0,
                             winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, APP_NAME)
        winreg.CloseKey(key)
        log.info("Автозапуск выключен")
        return True
    except FileNotFoundError:
        return True
    except Exception as e:
        log.error("Ошибка выключения автозапуска: %s", e)
        return False


def toggle() -> bool:
    """Переключает состояние. Возвращает новое состояние."""
    if is_enabled():
        disable()
        return False
    else:
        enable()
        return True
