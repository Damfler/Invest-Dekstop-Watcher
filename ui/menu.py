"""
menu.py — построитель меню трея.

КЛЮЧЕВОЕ РЕШЕНИЕ для заморозки:
  pystray поддерживает menu=pystray.Menu(callable).
  Callable вызывается в момент открытия меню, а не при обновлении данных.
  Фоновый поток меняет только данные в DataStore — меню он НЕ трогает.
  Это полностью устраняет заморозку при обновлении API.

Структура меню (подменю):
  📅 Переключатель режима
  ─────────────
  💼 Портфель ▸         (итого, счета)
  📊 Аналитика ▸        (НКД, купоны вперёд, муверы, аллокация, YTM)
  🚨 Алерт-баннер       (если есть)
  📋 Облигации ▸        (купоны, оферты, call, погашения)
  ─────────────
  ⚙ Настройки ▸         (горизонт, сортировка, автозапуск)
  ─────────────
  Обновлено / Обновить / Выйти
"""
import webbrowser
import pystray

from utils import autostart
from utils import analytics as an
from utils.formatting import (fmt_total, fmt_delta, fmt_money, fmt_date,
                   fmt_days, days_until)
from core.data_store import DataStore
from constants import ALERT_NONE, ALERT_WARN, ALERT_CRIT
from api.endpoints import TBANK_PORTFOLIO_URL, TBANK_BONDS_URL


class MenuBuilder:
    """Строит меню на каждый вызов из свежего снапшота данных."""

    def __init__(self, store: DataStore, app_callbacks: dict, cfg: dict = None):
        self._store      = store
        self._cb         = app_callbacks
        self._max_events = (cfg or {}).get("max_bond_events", 50)

    # ── Точка входа — callable для pystray ──────────────────
    def __call__(self) -> tuple:
        """pystray вызывает это при каждом открытии меню."""
        s = self._store.snapshot()
        return tuple(self._build(s))

    # ──────────────────────────────────────────────────────
    def _build(self, s: dict) -> list:
        items = []
        mode      = s["show_mode"]
        al        = s["alert_level"]
        horizon   = s["bond_horizon"]
        bond_sort = s["bond_sort"]

        # ── Переключатель режима ──────────────────────────
        mode_label = ("📅 За сегодня  [→ за всё время]"
                      if mode == "day" else
                      "📈 За всё время  [→ за сегодня]")
        items.append(pystray.MenuItem(mode_label, self._cb["toggle_mode"]))
        items.append(pystray.Menu.SEPARATOR)

        # ── 💼 Портфель (подменю) ────────────────────────
        items.append(pystray.MenuItem(
            "💼 Портфель", pystray.Menu(*self._portfolio_section(s))))

        # ── 📊 Аналитика (подменю) ───────────────────────
        analytics_items = self._analytics_section(s)
        if analytics_items:
            items.append(pystray.MenuItem(
                "📊 Аналитика", pystray.Menu(*analytics_items)))

        items.append(pystray.Menu.SEPARATOR)

        # ── Алерт-баннер (top-level) ─────────────────────
        items += self._alert_banner(s)

        # ── 📋 Облигации (подменю) ───────────────────────
        bond_items = self._bond_section(s)
        if bond_items:
            items.append(pystray.MenuItem(
                "📋 Облигации", pystray.Menu(*bond_items)))

        items.append(pystray.Menu.SEPARATOR)

        # ── ⚙ Настройки (подменю) ────────────────────────
        items.append(pystray.MenuItem(
            "⚙ Настройки", pystray.Menu(*self._settings_section(horizon, bond_sort))))

        items.append(pystray.Menu.SEPARATOR)

        # ── Футер ────────────────────────────────────────
        update_info = s.get("update_info", {})
        if update_info.get("available"):
            ver = update_info.get("version", "?")
            items.append(pystray.MenuItem(
                f"⬆ Доступно обновление v{ver} — скачать и установить",
                self._cb.get("download_update"),
            ))
        items.append(pystray.MenuItem("🔄 Обновить сейчас", self._cb["refresh"]))
        items.append(pystray.MenuItem("❌ Выйти", self._cb["quit"]))

        return items

    # ──────────────────────────────────────────────────────
    #  Подменю: Портфель
    # ──────────────────────────────────────────────────────
    def _portfolio_section(self, s: dict) -> list:
        items = []
        if s["error"]:
            items.append(pystray.MenuItem(
                f"⚠ Ошибка: {s['error']}", None, enabled=False))
            return items
        if not s["portfolios"]:
            items.append(pystray.MenuItem("Загрузка…", None, enabled=False))
            return items

        mode = s["show_mode"]
        portfolios = s["portfolios"]
        total_all  = sum(p["total"] for p in portfolios)
        delta_all  = sum(
            p["day_delta"] if mode == "day" else p["alltime_delta"]
            for p in portfolios
        )
        mode_str = "сегодня" if mode == "day" else "за всё время"
        arrow    = "▲" if delta_all >= 0 else "▼"
        items.append(pystray.MenuItem(
            f"Итого: {fmt_total(total_all)}   {arrow} {fmt_delta(delta_all)} {mode_str}",
            None, enabled=False,
        ))
        items.append(pystray.Menu.SEPARATOR)
        for p in portfolios:
            delta = p["day_delta"] if mode == "day" else p["alltime_delta"]
            arrow = "▲" if delta >= 0 else "▼"
            items.append(pystray.MenuItem(
                f"{p['name']}:  {fmt_total(p['total'])}   {arrow} {fmt_delta(delta)}",
                lambda _, aid=p["account_id"]: webbrowser.open(TBANK_PORTFOLIO_URL),
            ))
        return items

    # ──────────────────────────────────────────────────────
    #  Подменю: Аналитика (НКД, купоны вперёд, муверы, аллокация, YTM)
    # ──────────────────────────────────────────────────────
    def _analytics_section(self, s: dict) -> list:
        items = []

        # НКД
        bond_nkd    = s["bond_nkd"]
        bond_events = s["bond_events"]
        if bond_nkd:
            total_nkd = sum(v["nkd_total"] for v in bond_nkd.values())
            if total_nkd > 0:
                items.append(pystray.MenuItem(
                    f"📎 НКД накоплено: {fmt_money(total_nkd)}", None, enabled=False))

            parts = []
            for d in (30, 90):
                s_val = an.coupon_sum_horizon(bond_events, d)
                if s_val > 0:
                    parts.append(f"{d} дн.: {fmt_money(s_val)}")
            if parts:
                items.append(pystray.MenuItem(
                    "📆 Купоны вперёд:  " + "   |   ".join(parts),
                    None, enabled=False,
                ))
            if items:
                items.append(pystray.Menu.SEPARATOR)

        # Топ-3 муверы
        pos = s["positions_extra"]
        if pos:
            gainers, losers = an.top_movers(pos, n=3)
            if gainers:
                items.append(pystray.MenuItem("📈 Лучшие за день:", None, enabled=False))
                for p in gainers:
                    items.append(pystray.MenuItem(
                        f"   {p['name']}   +{fmt_money(p['day_delta'])}",
                        lambda _, i=p.get("isin", ""): self._open_bond(i) if i else webbrowser.open(TBANK_PORTFOLIO_URL)
                    ))
            if losers:
                items.append(pystray.MenuItem("📉 Худшие за день:", None, enabled=False))
                for p in losers:
                    items.append(pystray.MenuItem(
                        f"   {p['name']}   {fmt_money(p['day_delta'])}",
                        lambda _, i=p.get("isin", ""): self._open_bond(i) if i else webbrowser.open(TBANK_PORTFOLIO_URL)
                    ))
            if gainers or losers:
                items.append(pystray.Menu.SEPARATOR)

        # Аллокация
        if pos:
            alloc = an.compute_allocation(pos)
            line  = an.fmt_allocation(alloc)
            if line:
                items.append(pystray.MenuItem(
                    f"🗂 Аллокация: {line}", None, enabled=False))
                items.append(pystray.Menu.SEPARATOR)

        # YTM
        ytm = an.compute_portfolio_ytm(s["bond_analytics"])
        if ytm is not None:
            items.append(pystray.MenuItem(
                f"📊 Средний YTM: {ytm:.2f}%", None, enabled=False))

        return items

    # ──────────────────────────────────────────────────────
    #  Алерт-баннер (top-level)
    # ──────────────────────────────────────────────────────
    def _alert_banner(self, s: dict) -> list:
        al = s["alert_level"]
        if al == ALERT_CRIT:
            return [
                pystray.MenuItem("🚨 ОФЕРТА СЕГОДНЯ! Требует вашего решения!",
                                 None, enabled=False),
                pystray.Menu.SEPARATOR,
            ]
        if al == ALERT_WARN:
            return [
                pystray.MenuItem(
                    "✅ Прочитано — скрыть предупреждение",
                    self._cb["dismiss_warnings"],
                ),
                pystray.Menu.SEPARATOR,
            ]
        return []

    # ──────────────────────────────────────────────────────
    #  Подменю: Облигации (события)
    # ──────────────────────────────────────────────────────
    def _bond_section(self, s: dict) -> list:
        items = []
        events    = s["bond_events"]
        bond_nkd  = s["bond_nkd"]
        bond_sort = s["bond_sort"]
        horizon   = s["bond_horizon"]

        from datetime import timezone, timedelta
        from datetime import datetime as _dt
        now    = _dt.now(timezone.utc)
        hor_dt = now + timedelta(days=horizon)

        def in_horizon(e):
            dt = e["date"]
            if dt is None:
                return False
            dt_utc = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            return dt_utc <= hor_dt

        events = [e for e in events if in_horizon(e)]

        coupons    = [e for e in events if e["type"] == "coupon"]
        offers     = [e for e in events if e["type"] == "offer"]
        calls      = [e for e in events if e["type"] == "call"]
        maturities = [e for e in events if e["type"] == "maturity"]

        if not (coupons or offers or calls or maturities):
            items.append(pystray.MenuItem(
                f"Нет событий в ближайшие {horizon} дн.",
                None, enabled=False,
            ))
            return items

        if bond_sort == "amount":
            coupons.sort(
                key=lambda e: (e.get("amount") or e.get("amount_est") or 0) * e["qty"],
                reverse=True
            )

        # Купоны
        if coupons:
            items.append(pystray.MenuItem("💰 Ближайшие купоны:", None, enabled=False))
            for e in coupons[:self._max_events]:
                d       = days_until(e["date"])
                tip     = fmt_days(d)
                nkd_inf = bond_nkd.get(e["figi"])
                nkd_str = (f"  НКД: {fmt_money(nkd_inf['nkd_per'])}"
                           if nkd_inf and nkd_inf["nkd_per"] > 0 else "")
                amount  = e.get("amount")
                est     = e.get("amount_est")

                if amount:
                    total_p = amount * e["qty"]
                    line = (f"   {e['name']}  [{e['isin']}]  —  "
                            f"{fmt_date(e['date'])} ({tip})"
                            f"   {fmt_money(amount)}/бум x {e['qty']} = {fmt_money(total_p)}"
                            f"{nkd_str}")
                elif est:
                    total_p = est * e["qty"]
                    line = (f"   {e['name']}  [{e['isin']}]  —  "
                            f"{fmt_date(e['date'])} ({tip})"
                            f"   ~ {fmt_money(est)}/бум x {e['qty']} = ~ {fmt_money(total_p)}"
                            f"  (по НКД){nkd_str}")
                else:
                    line = (f"   {e['name']}  [{e['isin']}]  —  "
                            f"{fmt_date(e['date'])} ({tip}){nkd_str}")

                items.append(pystray.MenuItem(
                    line, lambda _, i=e["isin"]: self._open_bond(i)))

            if len(coupons) > self._max_events:
                items.append(pystray.MenuItem(
                    f"   ... ещё {len(coupons) - self._max_events} купонов",
                    None, enabled=False))
            items.append(pystray.Menu.SEPARATOR)

        for ev_list, header in [(offers, "📌 Оферты (put):"),
                                (calls,  "📞 Оферты (call):"),
                                (maturities, "🏁 Погашения:")]:
            if not ev_list:
                continue
            items.append(pystray.MenuItem(header, None, enabled=False))
            for e in ev_list[:self._max_events]:
                d = days_until(e["date"])
                items.append(pystray.MenuItem(
                    f"   {e['name']}  [{e['isin']}]  —  "
                    f"{fmt_date(e['date'])} ({fmt_days(d)})",
                    lambda _, i=e["isin"]: self._open_bond(i),
                ))
            items.append(pystray.Menu.SEPARATOR)

        return items

    # ──────────────────────────────────────────────────────
    #  Подменю: Настройки (горизонт, сортировка, автозапуск)
    # ──────────────────────────────────────────────────────
    def _settings_section(self, horizon: int, bond_sort: str) -> list:
        items = []

        # Горизонт
        def _make_horizon_cb(d):
            return lambda icon, item: self._cb["set_horizon"](d)

        items.append(pystray.MenuItem("⏳ Горизонт событий:", None, enabled=False))
        for days in (30, 60, 90):
            mark = "✓ " if days == horizon else "   "
            items.append(pystray.MenuItem(
                f"{mark}{days} дней",
                _make_horizon_cb(days),
            ))
        items.append(pystray.Menu.SEPARATOR)

        # Сортировка
        sort_lbl = ("⬇ Сортировка: по дате  [→ по сумме]"
                    if bond_sort == "date" else
                    "⬇ Сортировка: по сумме  [→ по дате]")
        items.append(pystray.MenuItem(sort_lbl, self._cb["toggle_bond_sort"]))

        items.append(pystray.Menu.SEPARATOR)

        # Автозапуск
        auto_lbl = ("🟢 Автозапуск: включён  [→ выключить]"
                    if autostart.is_enabled() else
                    "⚫ Автозапуск: выключен  [→ включить]")
        items.append(pystray.MenuItem(auto_lbl, self._cb["toggle_autostart"]))

        return items

    # ──────────────────────────────────────────────────────
    @staticmethod
    def _open_bond(isin: str):
        webbrowser.open(
            TBANK_BONDS_URL.format(ticker=isin) if isin else TBANK_PORTFOLIO_URL
        )
