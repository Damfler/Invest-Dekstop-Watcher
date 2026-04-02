"""
notifications.py — логика toast-уведомлений Windows
"""
import logging
from datetime import datetime

from utils import days_until, fmt_money, fmt_total, fmt_delta, fmt_date, alert_key

log = logging.getLogger("tbank.notify")

try:
    from plyer import notification as _plyer
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False
    log.debug("plyer недоступен, toast-уведомления отключены")


def toast(title: str, message: str):
    if not _AVAILABLE:
        return
    try:
        _plyer.notify(title=title, message=message,
                      app_name="T-Bank Invest", timeout=8)
    except Exception as e:
        log.debug("toast failed: %s", e)


class NotificationManager:
    def __init__(self, cfg: dict):
        self._cfg      = cfg.get("notifications", {})
        self._move_pct = float(cfg.get("notify_move_pct", 1.0))
        self._notified: set = set()
        self._prev_total    = 0.0

    def fire(self, bond_events: list, dismissed: set,
             portfolios: list, offer_warn_days: int):
        """Вызывается после каждого обновления данных."""
        notified  = set(self._notified)
        curr_total = sum(p["total"] for p in portfolios)

        # 1. Оферта СЕГОДНЯ
        if self._cfg.get("offer_crit"):
            for e in bond_events:
                if e["type"] in ("offer", "call") and days_until(e["date"]) == 0:
                    key = f"crit_{alert_key(e)}"
                    if key not in notified:
                        toast("🚨 Оферта СЕГОДНЯ!",
                              f"{e['name']}\nТребует решения!\nОткройте меню виджета.")
                        notified.add(key)

        # 2. Оферта скоро (настраиваемый порог)
        if self._cfg.get("offer_warn"):
            for e in bond_events:
                if e["type"] in ("offer", "call"):
                    d   = days_until(e["date"])
                    key = f"warn_{alert_key(e)}"
                    if (1 <= d <= offer_warn_days
                            and key not in notified
                            and alert_key(e) not in dismissed):
                        from utils import fmt_days
                        toast("⚠ Оферта скоро",
                              f"{e['name']}\n{fmt_days(d)} — {fmt_date(e['date'])}")
                        notified.add(key)

        # 3. Купон завтра
        if self._cfg.get("coupon_tomorrow"):
            for e in bond_events:
                if e["type"] == "coupon" and days_until(e["date"]) == 1:
                    key = f"coupon_{alert_key(e)}"
                    if key not in notified:
                        payout = (e["amount"] or e.get("amount_est") or 0) * e["qty"]
                        toast("💰 Купон завтра",
                              f"{e['name']}\n{fmt_money(payout)} → ваш счёт")
                        notified.add(key)

        # 4. Крупное движение портфеля
        if (self._cfg.get("portfolio_move")
                and self._prev_total > 0 and curr_total > 0):
            pct = abs(curr_total - self._prev_total) / self._prev_total * 100
            if pct >= self._move_pct:
                day_delta = sum(p["day_delta"] for p in portfolios)
                direction = "вырос" if day_delta >= 0 else "упал"
                key       = f"move_{datetime.now().strftime('%Y%m%d%H')}"
                if key not in notified:
                    toast(f"📊 Портфель {direction} на {pct:.1f}%",
                          f"Итого: {fmt_total(curr_total)}\n"
                          f"За день: {fmt_delta(day_delta)}")
                    notified.add(key)

        self._notified  = notified
        self._prev_total = curr_total
