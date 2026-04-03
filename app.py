"""
app.py — главный класс TBankTrayApp.
Координирует DataStore, MenuBuilder, иконки и фоновые потоки.
"""
import threading
import time
import logging

import pystray

import autostart
from icons_gen import (make_icon_normal, make_icon_warn, make_icon_crit)
from data_store import DataStore, ALERT_NONE, ALERT_WARN, ALERT_CRIT
from menu import MenuBuilder
from notifications import NotificationManager
from window import DashboardWindow

log = logging.getLogger("tbank.app")

REFRESH_SECONDS    = 60
BOND_REFRESH_HOURS = 6
BLINK_INTERVAL     = 0.6


_WM_LBUTTONUP = 0x0202   # Win32 WM_LBUTTONUP
_WM_NOTIFY    = 1035     # pystray custom WM_NOTIFY (WM_USER + 11)


class TBankTrayApp:
    def __init__(self, cfg: dict, store: DataStore):
        self._cfg        = cfg
        self._store      = store
        self._notif      = NotificationManager(cfg)

        self._blink_state  = False
        self._blink_thread: threading.Thread | None = None

        self._icon: pystray.Icon | None = None
        self._dashboard = DashboardWindow(store, self._do_refresh, cfg)

        # MenuBuilder получает ссылки на действия приложения
        self._menu = MenuBuilder(store, {
            "toggle_mode":      self._toggle_mode,
            "refresh":          self._refresh_now,
            "quit":             self._quit,
            "toggle_autostart": self._toggle_autostart,
            "dismiss_warnings": self._dismiss_warnings,
            "toggle_bond_sort": self._toggle_bond_sort,
            "set_horizon":      self._set_horizon,
        }, cfg=cfg)

    # ──────────────────────────────────────────
    #  Действия из меню
    # ──────────────────────────────────────────
    def _toggle_mode(self, icon=None, item=None):
        self._store.toggle_mode()
        self._update_icon_and_tooltip()

    def _toggle_autostart(self, icon=None, item=None):
        autostart.toggle()

    def _dismiss_warnings(self, icon=None, item=None):
        self._store.dismiss_warnings()
        self._update_icon_and_tooltip()

    def _toggle_bond_sort(self, icon=None, item=None):
        self._store.toggle_bond_sort(self._cfg)

    def _set_horizon(self, days: int):
        self._store.set_horizon(days, self._cfg)
        threading.Thread(target=self._do_refresh,
                         kwargs={"force_bonds": True}, daemon=True).start()

    def _refresh_now(self, icon=None, item=None):
        threading.Thread(target=self._do_refresh, daemon=True).start()

    def _quit(self, icon=None, item=None):
        log.info("Выход...")
        self._store.save_to_cache()
        if self._icon:
            self._icon.stop()
        self._dashboard.request_quit()

    # ──────────────────────────────────────────
    #  Обновление данных
    # ──────────────────────────────────────────
    def _do_refresh(self, force_bonds: bool = False):
        self._store.fetch_portfolio()

        s = self._store.snapshot()
        need_bond = (
            force_bonds
            or self._store.last_bond_update is None
            or (
                __import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ) - self._store.last_bond_update
            ).total_seconds() > BOND_REFRESH_HOURS * 3600
        )
        if need_bond:
            self._store.fetch_bond_events()

        # Обновляем уровень алерта
        al = self._store.compute_alert()
        with self._store._lock:
            self._store.alert_level = al

        # Уведомления
        s = self._store.snapshot()
        self._notif.fire(
            bond_events    = s["bond_events"],
            dismissed      = s["dismissed"],
            portfolios     = s["portfolios"],
            offer_warn_days = self._cfg.get("notify_offer_days", 2),
        )

        self._update_icon_and_tooltip()

        # Сохраняем кэш после каждого успешного обновления
        self._store.save_to_cache()

    def _refresh_loop(self):
        self._do_refresh(force_bonds=True)
        while True:
            time.sleep(REFRESH_SECONDS)
            self._do_refresh()

    # ──────────────────────────────────────────
    #  Иконка и тултип (не трогает меню!)
    # ──────────────────────────────────────────
    def _update_icon_and_tooltip(self):
        if not self._icon:
            return

        s  = self._store.snapshot()
        al = s["alert_level"]
        mode = s["show_mode"]

        # Иконка
        if al == ALERT_CRIT:
            self._icon.icon = make_icon_crit(bright=True,
                                             use_custom=self._cfg.get("use_custom_icons", True))
            self._blink_state = True
            self._ensure_blink_thread()
        elif al == ALERT_WARN:
            self._icon.icon = make_icon_warn(use_custom=self._cfg.get("use_custom_icons", True))
        else:
            delta = sum(
                p["day_delta"] if mode == "day" else p["alltime_delta"]
                for p in s["portfolios"]
            ) if s["portfolios"] else 0
            self._icon.icon = make_icon_normal(
                0 if s["error"] else delta,
                use_custom=self._cfg.get("use_custom_icons", True),
            )

        # Тултип
        if s["error"]:
            tip = f"T-Bank Invest ⚠ {s['error']}"
        elif s["portfolios"]:
            from utils import fmt_total, fmt_money, fmt_date
            from analytics import coupon_sum_horizon
            total = sum(p["total"] for p in s["portfolios"])
            delta = sum(
                p["day_delta"] if mode == "day" else p["alltime_delta"]
                for p in s["portfolios"]
            )
            mode_str = "сегодня" if mode == "day" else "за всё время"
            sign     = "+" if delta >= 0 else ""

            nkd_t = sum(v["nkd_total"] for v in s["bond_nkd"].values())
            nkd_tip = f"\n📎 НКД: {fmt_money(nkd_t)}" if nkd_t > 0 else ""

            coupons = [e for e in s["bond_events"] if e["type"] == "coupon"]
            coup_tip = ""
            if coupons:
                nxt = coupons[0]
                coup_tip = f"\n💰 Купон: {nxt['name']} — {fmt_date(nxt['date'])}"

            alert_tip = ""
            if al == ALERT_CRIT:
                alert_tip = "\n🚨 ОФЕРТА СЕГОДНЯ!"
            elif al == ALERT_WARN:
                alert_tip = f"\n⚠ Оферта через 1–{self._cfg.get('notify_offer_days',2)} дня!"

            tip = (f"T-Bank Invest\n{fmt_total(total)}\n"
                   f"{mode_str.capitalize()}: {sign}{delta:,.0f} ₽"
                   f"{nkd_tip}{coup_tip}{alert_tip}")
        else:
            tip = "T-Bank Invest — загрузка…"

        self._icon.title = tip

    def _ensure_blink_thread(self):
        if self._blink_thread and self._blink_thread.is_alive():
            return
        self._blink_thread = threading.Thread(
            target=self._blink_loop, daemon=True)
        self._blink_thread.start()

    def _blink_loop(self):
        while True:
            time.sleep(BLINK_INTERVAL)
            al = self._store.compute_alert()
            if al != ALERT_CRIT:
                break
            self._blink_state = not self._blink_state
            if self._icon:
                self._icon.icon = make_icon_crit(
                    self._blink_state, self._cfg.get("use_custom_icons", True))

    # ──────────────────────────────────────────
    #  Запуск
    # ──────────────────────────────────────────
    def run(self):
        import webview as _webview
        log.info("Запуск T-Bank Invest Tray")

        # Создаём окно дашборда ДО start() (скрытым).
        # pywebview требует минимум одно окно перед start().
        self._dashboard.create_window()

        # Главный поток = pywebview event loop.
        # func= запускается pywebview в фоновом потоке ПОСЛЕ старта GUI loop.
        _webview.start(func=self._background_init)

    def _background_init(self):
        """Инициализация в фоновом потоке (вызывается pywebview после старта)."""
        # Создаём pystray Icon
        self._icon = pystray.Icon(
            name  = "tbank_invest",
            icon  = make_icon_normal(0, self._cfg.get("use_custom_icons", True)),
            title = "T-Bank Invest — загрузка…",
            menu  = pystray.Menu(self._menu),
        )

        # Monkey-patch: перехватываем ЛКМ на иконке трея.
        # pystray Win32 хранит обработчики в dict _message_handlers,
        # диспетчер вызывает их по ключу. Патчим запись в dict.
        _orig_on_notify = self._icon._message_handlers[_WM_NOTIFY]
        def _patched_on_notify(wparam, lparam):
            if lparam == _WM_LBUTTONUP:
                self._on_left_click()
                return 0
            return _orig_on_notify(wparam, lparam)
        self._icon._message_handlers[_WM_NOTIFY] = _patched_on_notify

        # Refresh loop в отдельном потоке
        threading.Thread(target=self._refresh_loop, daemon=True).start()

        # Проверка обновлений в фоне
        if self._cfg.get("auto_update", True):
            threading.Thread(target=self._check_update, daemon=True).start()

        # pystray в своём потоке (run_detached), главный = webview
        self._icon.run_detached()

    def _check_update(self):
        """Проверяет обновления через GitHub Releases."""
        try:
            from updater import check_for_update
            info = check_for_update()
            if info.get("available"):
                self._store.update_info = info
        except Exception as e:
            log.debug("Ошибка проверки обновлений: %s", e)

    def _on_left_click(self):
        self._dashboard.toggle()
