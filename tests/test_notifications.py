import json
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from utils.notifications import NotificationManager, toast


class NotificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "notifications.json"
        self.cfg = {"notifications": {key: True for key in (
            "coupon_today", "coupon_tomorrow", "dividend_today", "dividend_tomorrow",
            "maturity_today", "maturity_tomorrow", "offer_warn", "offer_crit", "portfolio_move")}}
        self.manager = NotificationManager(self.cfg, self.path)
        self.send = patch("utils.notifications.toast", return_value=True).start()
        self.addCleanup(patch.stopall)

    def event(self, kind="coupon", days=1, **overrides):
        value = dict(type=kind, name="Облигация", isin="RU123", date=datetime.now() + timedelta(days=days),
                     qty=3, amount=10.5, currency="rub")
        value.update(overrides)
        return value

    def fire(self, events=(), portfolios=(), dismissed=None):
        self.manager.fire(list(events), dismissed or set(), list(portfolios), 2)

    def test_all_payout_types_today_and_tomorrow_have_date_quantity_amount(self):
        for kind in ("coupon", "dividend", "maturity"):
            for days in (0, 1):
                with self.subTest(kind=kind, days=days):
                    self.send.reset_mock()
                    event = self.event(kind, days)
                    self.fire([event])
                    title, message = self.send.call_args.args
                    self.assertIn("Плановые выплаты", title)
                    self.assertIn(event["date"].strftime("%d.%m"), message)
                    self.assertIn("3 шт.", message)
                    self.assertIn("31.50 ₽", message)
                    self.assertNotIn("зачислен", message)

    def test_dedup_survives_restart_and_today_is_a_new_stage(self):
        self.fire([self.event()])
        self.manager = NotificationManager(self.cfg, self.path)
        self.fire([self.event()])
        self.assertEqual(self.send.call_count, 1)
        self.fire([self.event(days=0)])
        self.assertEqual(self.send.call_count, 2)

    def test_settings_and_threshold_changes_take_effect(self):
        self.cfg["notifications"] = {"coupon_tomorrow": False, "portfolio_move": True}
        self.fire([self.event()])
        self.assertFalse(self.send.called)
        self.cfg["notifications"]["coupon_tomorrow"] = True
        self.fire([self.event()])
        self.assertEqual(self.send.call_count, 1)
        self.cfg["notify_move_pct"] = 5
        self.fire(portfolios=[dict(total=100, day_delta=2)])
        self.assertEqual(self.send.call_count, 1)
        self.cfg["notify_move_pct"] = 1
        self.fire(portfolios=[dict(total=100, day_delta=2)])
        self.fire(portfolios=[dict(total=100, day_delta=3)])
        self.assertEqual(self.send.call_count, 2)

    def test_many_events_are_one_digest_and_deduplicated(self):
        events = [self.event(isin=f"RU{i}") for i in range(12)]
        self.fire(events)
        self.assertEqual(self.send.call_count, 1)
        self.assertIn("Ещё событий", self.send.call_args.args[1])
        self.fire(events)
        self.assertEqual(self.send.call_count, 1)

    def test_multiple_connections_combine_quantity_and_new_source_is_not_suppressed(self):
        events = [self.event(connection_name='A'), self.event(connection_name='B', qty=2)]
        self.fire(events)
        message = self.send.call_args.args[1]
        self.assertEqual(message.count('Купон:'), 1)
        self.assertIn('5 шт.', message)
        self.assertIn('52.50 ₽', message)
        self.fire(events)
        self.assertEqual(self.send.call_count, 1)
        self.fire(events + [self.event(connection_name='C', qty=1)])
        self.assertEqual(self.send.call_count, 2)
        self.assertIn('6 шт.', self.send.call_args.args[1])

    def test_foreign_unknown_and_estimated_amounts(self):
        for kwargs, expected in ((dict(currency="USD"), "31.50 USD"),
                                 (dict(amount=None, amount_est=4), "≈12.00 ₽"),
                                 (dict(amount=None), "сумма уточняется"),
                                 (dict(currency=None), "валюта ?")):
            with self.subTest(kwargs=kwargs):
                text = self.manager._event_text(self.event(**kwargs))
                self.assertIn(expected, text)

    def test_dismissal_only_suppresses_warning_and_calls_are_distinct(self):
        event = self.event("offer")
        from utils.formatting import alert_key
        self.fire([event], dismissed={alert_key(event)})
        self.assertFalse(self.send.called)
        self.fire([self.event("offer", 0), self.event("call", 0)])
        self.assertEqual(self.send.call_count, 1)
        self.assertIn("Put-оферта", self.send.call_args.args[1])
        self.assertIn("Call-оферта", self.send.call_args.args[1])

    def test_failed_delivery_retries_and_bad_history_does_not_break_startup(self):
        self.send.return_value = False
        self.fire([self.event()])
        self.send.return_value = True
        self.fire([self.event()])
        self.assertEqual(self.send.call_count, 2)
        self.path.write_text("broken", encoding="utf-8")
        self.assertEqual(NotificationManager(self.cfg, self.path)._notified, {})

    def test_history_is_bounded(self):
        old = time.time() - 91 * 86400
        self.path.write_text(json.dumps({"old": old, **{str(i): time.time() for i in range(1100)}}))
        manager = NotificationManager(self.cfg, self.path)
        self.assertEqual(len(manager._notified), 1000)
        self.assertNotIn("old", manager._notified)

    def test_toast_obeys_windows_limits(self):
        with patch("utils.notifications._plyer") as backend:
            self.assertTrue(toast("a" * 80, "b" * 400))
            kwargs = backend.notify.call_args.kwargs
            self.assertEqual(len(kwargs["title"]), 64)
            self.assertEqual(len(kwargs["message"]), 256)


if __name__ == "__main__":
    unittest.main()
