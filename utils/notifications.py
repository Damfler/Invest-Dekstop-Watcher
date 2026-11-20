"""Native reminders for scheduled events; delivery is not confirmation of payment."""
import json
import logging
import os
import threading
import time
from datetime import datetime

from utils.formatting import days_until, fmt_total, fmt_delta, alert_key
from version import APP_NAME

log = logging.getLogger("tbank.notify")
try:
    from plyer import notification as _plyer
except ImportError:
    _plyer = None


def toast(title: str, message: str) -> bool:
    if _plyer is None:
        return False
    try:
        _plyer.notify(title=title[:64], message=message[:256],
                      app_name=APP_NAME, timeout=8)
        return True
    except Exception as e:
        log.debug("toast failed: %s", e)
        return False


class NotificationManager:
    def __init__(self, cfg: dict, state_file=None):
        self._cfg = cfg
        self._lock = threading.Lock()
        if state_file is None:
            from core.config import BASE_DIR
            state_file = os.path.join(BASE_DIR, "notifications.json")
        self._state_file = os.fspath(state_file)
        self._notified = {}
        try:
            with open(self._state_file, encoding="utf-8") as f:
                saved = json.load(f)
            if isinstance(saved, dict):
                self._notified = {k: v for k, v in saved.items()
                                  if isinstance(v, (int, float))}
        except (OSError, ValueError):
            pass
        self._prune()

    def _prune(self):
        cutoff = time.time() - 90 * 86400
        recent = [(k, v) for k, v in self._notified.items() if v >= cutoff]
        self._notified = dict(sorted(recent, key=lambda item: item[1])[-1000:])

    def _save(self):
        self._prune()
        try:
            with open(self._state_file + ".tmp", "w", encoding="utf-8") as f:
                json.dump(self._notified, f)
            os.replace(self._state_file + ".tmp", self._state_file)
        except OSError as e:
            log.warning("Cannot save notification history: %s", e)

    def _digest(self, title, rows):
        if not rows:
            return
        # Windows notifications have a 256-character message limit.
        visible = rows[:2]
        message = "\n".join(text[:104] for _, text in visible)
        if len(rows) > 2:
            message += f"\nЕщё событий: {len(rows) - 2}. См. дашборд."
        if toast(title, message):
            now = time.time()
            self._notified.update((key, now) for key, _ in rows)

    @staticmethod
    def _event_key(event, stage):
        identity = event.get("isin") or event.get("figi") or event.get("name", "")
        return f"{event['type']}:{identity}:{event['date'].date()}:{stage}:{event.get('currency', '')}:{event.get('_connections', '')}"

    @staticmethod
    def _event_text(event):
        name = str(event.get("name") or event.get("isin") or "Инструмент")[:24]
        qty = event.get("qty", 0)
        amount = event.get("amount")
        estimated = amount is None
        if estimated:
            amount = event.get("amount_est")
        currency = str(event.get("currency") or "").upper()
        currency = "₽" if currency == "RUB" else currency
        payout = (f"{'≈' if estimated else ''}{amount * qty:,.2f} {currency or '(валюта ?)'}"
                  .replace(",", " ") if amount is not None else "сумма уточняется")
        label = {"coupon": "Купон", "dividend": "Див.", "maturity": "Погаш.",
                 "offer": "Put-оферта", "call": "Call-оферта"}[event["type"]]
        detail = f"{event['date']:%d.%m} {label}: {name}, {qty:g} шт."
        return detail if event["type"] in ("offer", "call") else f"{detail}, {payout}"

    def fire(self, bond_events: list, dismissed: set,
             portfolios: list, offer_warn_days: int):
        """At most one payout digest, one offer digest and one move toast per refresh."""
        with self._lock:
            before = dict(self._notified)
            self._prune()
            settings = self._cfg.get("notifications", {})
            payouts, offers = [], []
            grouped = {}
            for event in bond_events:
                if not isinstance(event.get("date"), datetime):
                    continue
                identity = event.get("isin") or event.get("figi") or event.get("name", "")
                group = (event.get("type"), identity, event["date"].date(),
                         event.get("currency"), event.get("amount"), event.get("amount_est"))
                if group not in grouped:
                    grouped[group] = dict(event, qty=0, _sources=set())
                grouped[group]["qty"] += event.get("qty", 0)
                grouped[group]["_sources"].add(event.get("connection_name", ""))
            for event in grouped.values():
                event["_connections"] = tuple(sorted(event.pop("_sources")))
                kind = event.get("type")
                days = days_until(event["date"])
                if kind in ("offer", "call"):
                    stage = "crit" if days == 0 else "warn"
                    enabled = settings.get("offer_" + stage, False)
                    if not enabled or not 0 <= days <= offer_warn_days:
                        continue
                    if days and alert_key(event) in dismissed:
                        continue
                    rows = offers
                elif kind in ("coupon", "dividend", "maturity") and days in (0, 1):
                    stage = "today" if days == 0 else "tomorrow"
                    if not settings.get(kind + "_" + stage, False):
                        continue
                    rows = payouts
                else:
                    continue
                key = self._event_key(event, stage)
                if key not in self._notified:
                    rows.append((key, self._event_text(event)))
            self._digest("Плановые выплаты · даты и суммы по данным брокера", payouts)
            self._digest("Оферты · проверьте условия и срок подачи поручения", offers)

            total = sum(p.get("total", 0) for p in portfolios)
            delta = sum(p.get("day_delta", 0) for p in portfolios)
            threshold = float(self._cfg.get("notify_move_pct", 1.0))
            if settings.get("portfolio_move") and total > 0:
                pct = abs(delta) / total * 100
                direction = "вырос" if delta >= 0 else "снизился"
                key = f"move:{datetime.now():%Y-%m-%d}:{'up' if delta >= 0 else 'down'}"
                if pct >= threshold and key not in self._notified:
                    if toast(f"Портфель {direction} на {pct:.1f}% за день",
                             f"{datetime.now():%d.%m.%Y} · Итого: {fmt_total(total)}\n"
                             f"Изменение за день: {fmt_delta(delta)}"):
                        self._notified[key] = time.time()
            if self._notified != before:
                self._save()
