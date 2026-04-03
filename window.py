"""
window.py — всплывающее окно по левому клику.

HTML-дашборд в стиле T-Bank Invest через pywebview (Edge WebView2).
HTML загружается из файла dashboard.html через url=file:// для полной
интерактивности (inline html= блокирует JS-события в EdgeChromium).
"""
import threading
import logging
import json
import os
from datetime import datetime

import webview as _webview

log = logging.getLogger("tbank.window")

# PyInstaller onefile: ресурсы в sys._MEIPASS, иначе рядом со скриптом
import sys as _sys
_BASE_DIR  = getattr(_sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
_HTML_FILE = os.path.join(_BASE_DIR, "dashboard.html")


# ──────────────────────────────────────────────────────────────────────────────
#  JS API для pywebview
# ──────────────────────────────────────────────────────────────────────────────
class _DashboardAPI:
    def __init__(self, store, refresh_callback, cfg):
        self._store   = store
        self._refresh = refresh_callback
        self._cfg     = cfg

    def get_data(self) -> str:
        s = self._store.snapshot()
        s["theme"] = self._cfg.get("theme", "system")
        s["use_logos"] = self._cfg.get("use_logos", False)
        s["bond_horizon_days"] = self._cfg.get("bond_horizon_days", 60)
        s["app_name"] = self._cfg.get("app_name", "")
        s["use_custom_icons"] = self._cfg.get("use_custom_icons", True)
        s["show_hints"] = self._cfg.get("show_hints", False)
        s["auto_update"] = self._cfg.get("auto_update", True)
        from version import APP_VERSION, APP_NAME
        s["app_version"] = APP_VERSION
        s["app_brand"]   = APP_NAME
        def _serial(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            if isinstance(obj, set):
                return list(obj)
            raise TypeError(f"Not serializable: {type(obj)}")
        return json.dumps(s, default=_serial, ensure_ascii=False)

    def refresh(self):
        threading.Thread(target=self._refresh, daemon=True).start()

    def open_url(self, url: str):
        import webbrowser
        webbrowser.open(url)

    def set_theme(self, theme: str):
        from config import save_config
        self._cfg["theme"] = theme
        save_config(self._cfg)

    def set_use_logos(self, val: bool):
        from config import save_config
        self._cfg["use_logos"] = val
        save_config(self._cfg)

    def set_show_hints(self, val: bool):
        from config import save_config
        self._cfg["show_hints"] = val
        save_config(self._cfg)

    def set_custom_icons(self, val: bool):
        from config import save_config
        self._cfg["use_custom_icons"] = val
        save_config(self._cfg)

    def set_app_name(self, name: str):
        from config import save_config
        self._cfg["app_name"] = name
        save_config(self._cfg)

    def apply_update(self):
        """Скачать и применить обновление."""
        from updater import download_update, apply_update
        info = self._store.update_info
        if not info or not info.get("url"):
            return "no_update"
        exe_path = download_update(info["url"], info.get("asset_name", "tbank_invest.exe"))
        if not exe_path:
            return "download_failed"
        apply_update(exe_path)
        # Закрываем приложение
        import sys
        sys.exit(0)

    def set_auto_update(self, val: bool):
        from config import save_config
        self._cfg["auto_update"] = val
        save_config(self._cfg)

    def set_horizon(self, days: int):
        from config import save_config
        self._cfg["bond_horizon_days"] = days
        save_config(self._cfg)
        # Обновляем DataStore и перезагружаем облигации
        self._store.set_horizon(days, self._cfg)
        threading.Thread(target=self._refresh, daemon=True).start()


# ──────────────────────────────────────────────────────────────────────────────
#  Менеджер окна
# ──────────────────────────────────────────────────────────────────────────────
class DashboardWindow:
    """Дашборд через pywebview (Edge WebView2).

    HTML загружается из dashboard.html через url= для полной интерактивности.
    Окно создаётся скрытым при старте, toggle() показывает/скрывает.
    """

    def __init__(self, store, refresh_callback, cfg=None):
        self._store   = store
        self._refresh = refresh_callback
        self._visible = False
        self._cfg     = cfg or {}
        self._api     = _DashboardAPI(store, refresh_callback, self._cfg)

    def create_window(self):
        """Создать окно ДО webview.start(). Окно скрыто."""
        self._window = _webview.create_window(
            title            = "T-Bank Invest",
            url              = _HTML_FILE,
            js_api           = self._api,
            width            = 960,
            height           = 720,
            resizable        = True,
            easy_drag        = False,
            text_select      = True,
            hidden           = True,
            background_color = "#1c1c1e",
        )
        # Перехватываем закрытие: прячем окно вместо уничтожения
        self._window.events.closing += self._on_closing
        return self._window

    def _on_closing(self):
        """Кнопка X → прячем окно, не уничтожаем."""
        self._window.hide()
        self._visible = False
        return False  # False → closing.set() returns True → args.Cancel = True

    def toggle(self):
        """Показать/скрыть дашборд."""
        try:
            if self._visible:
                self._window.hide()
                self._visible = False
            else:
                self._visible = True
                self._window.show()
                try:
                    self._window.evaluate_js("if(typeof loadData==='function')loadData();")
                except Exception:
                    pass
        except Exception:
            log.exception("toggle failed")
            self._visible = False

    def request_quit(self):
        """Настоящее закрытие при выходе из приложения."""
        # Убираем обработчик closing чтобы destroy() не был отменён
        try:
            self._window.events.closing -= self._on_closing
        except Exception:
            pass
        try:
            self._window.destroy()
        except Exception:
            pass
