import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from core.data_store import DataStore, _annual_coupon_from_bond
from api.client import TBankAPIError


def money(value):
    return {"units": value, "nano": 0}


class DataStoreTests(unittest.TestCase):
    def setUp(self):
        for target, value in (
            ("load_cache", None), ("load_history", []), ("load_dismissed", set()),
        ):
            patcher = patch(f"core.data_store.{target}", return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch("core.data_store._time.sleep")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.api = Mock()
        self.api.get_dividends.return_value = [{
            "paymentDate": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            "dividendNet": money(10),
        }]
        self.store = DataStore([("bank", self.api)], {})

    def share(self, qty, connection="bank"):
        return {"instrumentType": "share", "figi": "SHARE", "qty": qty,
                "connection_name": connection}

    def test_share_only_portfolio_gets_dividends(self):
        self.store.positions_extra = [self.share(5)]
        self.store.fetch_bond_events()
        self.assertEqual([(e["type"], e["qty"], e["amount"])
                          for e in self.store.bond_events], [("dividend", 5, 10)])

    def test_empty_portfolio_clears_old_events_and_analytics(self):
        self.store.bond_events = [{"type": "coupon"}]
        self.store.bond_analytics = [{"figi": "SOLD"}]
        self.store.fetch_bond_events()
        self.assertEqual(self.store.bond_events, [])
        self.assertEqual(self.store.bond_analytics, [])
        self.assertIsNotNone(self.store.last_bond_update)

    def test_todays_offer_call_and_maturity_remain_in_calendar(self):
        midnight = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
        self.store.bond_positions = {"BOND": {"name": "Bond", "qty": 2}}
        self.api.get_bond_by_figi.return_value = {
            "maturityDate": midnight.isoformat(), "putDate": midnight.isoformat(),
            "callDate": midnight.isoformat(),
        }
        self.api.get_bond_coupons.return_value = []
        self.store.fetch_bond_events()
        self.assertEqual({e["type"] for e in self.store.bond_events}, {"offer", "call", "maturity"})
        from constants import ALERT_CRIT
        self.assertEqual(self.store.compute_alert(), ALERT_CRIT)

    def test_changed_share_and_bond_holdings_invalidate_calendar(self):
        self.api.get_accounts.return_value = [{"id": "a"}]
        for instrument_type in ("share", "bond"):
            for qty in (2, 3, 0):
                with self.subTest(instrument_type=instrument_type, qty=qty):
                    self.store.last_bond_update = datetime.now(timezone.utc)
                    self.api.get_portfolio.return_value = {
                        "totalAmountPortfolio": money(100),
                        "positions": ([{"figi": "instrument", "instrumentType": instrument_type,
                                        "quantity": money(qty)}] if qty else []),
                    }
                    self.store.fetch_portfolio()
                    self.assertIsNone(self.store.last_bond_update)

    def test_unchanged_holdings_keep_calendar_timestamp(self):
        self.api.get_accounts.return_value = [{"id": "a"}]
        self.api.get_portfolio.return_value = {
            "totalAmountPortfolio": money(100),
            "positions": [{"figi": "instrument", "instrumentType": "share", "quantity": money(2)}],
        }
        self.store.fetch_portfolio()
        stamp = self.store.last_bond_update = datetime.now(timezone.utc)
        self.store.fetch_portfolio()
        self.assertEqual(self.store.last_bond_update, stamp)

    def test_registry_date_is_not_used_as_dividend_payment(self):
        self.store.positions_extra = [self.share(5)]
        self.api.get_dividends.return_value = [{
            "recordDate": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            "dividendNet": money(10),
        }]
        self.store.fetch_bond_events()
        self.assertEqual(self.store.bond_events, [])

    def test_payout_events_keep_amount_and_currency(self):
        tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        self.store.bond_positions = {"BOND": {"name": "Bond", "qty": 2, "connection_name": "bank"}}
        self.store.positions_extra = [self.share(5)]
        self.api.get_bond_by_figi.return_value = {
            "maturityDate": tomorrow, "nominal": {**money(1000), "currency": "usd"},
        }
        self.api.get_bond_coupons.return_value = [{
            "couponDate": tomorrow, "payOneBond": {**money(25), "currency": "usd"},
        }]
        self.api.get_dividends.return_value = [{
            "paymentDate": tomorrow, "dividendNet": {**money(10), "currency": "eur"},
        }]
        self.store.fetch_bond_events()
        self.assertEqual({e["type"]: (e["amount"], e["currency"]) for e in self.store.bond_events},
                         {"maturity": (1000, "usd"), "coupon": (25, "usd"), "dividend": (10, "eur")})
        self.assertEqual({e["connection_name"] for e in self.store.bond_events}, {"bank"})

    def test_dividends_sum_accounts_and_keep_connection_routing(self):
        other = Mock()
        other.get_dividends.return_value = [{
            "paymentDate": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            "dividendNet": money(20),
        }]
        self.store = DataStore([("bank", self.api), ("other", other)], {})
        self.store.positions_extra = [self.share(2), self.share(3), self.share(7, "other")]
        self.store.fetch_bond_events()
        self.assertEqual(sorted((e["qty"], e["amount"]) for e in self.store.bond_events),
                         [(5, 10), (7, 20)])

    def test_partial_failure_does_not_append_incomplete_history(self):
        self.api.get_accounts.return_value = [{"id": "a"}]
        self.api.get_portfolio.return_value = {"totalAmountPortfolio": money(100)}
        offline = Mock()
        offline.get_accounts.side_effect = TBankAPIError("offline")
        self.store = DataStore([("bank", self.api), ("offline", offline)], {})
        self.store.portfolio_history = [{"ts": "previous", "value": 300}]
        self.store.fetch_portfolio()
        self.assertEqual(self.store.portfolio_history, [{"ts": "previous", "value": 300}])
        self.assertIsNotNone(self.store.error)

    def test_successful_refresh_still_records_history(self):
        self.api.get_accounts.return_value = [{"id": "a"}]
        self.api.get_portfolio.return_value = {"totalAmountPortfolio": money(100)}
        self.store.fetch_portfolio()
        self.assertEqual(self.store.portfolio_history[-1]["value"], 100)

    def test_incomplete_snapshot_preserves_cache_but_saves_history(self):
        self.store.error = "offline broker"
        self.store.portfolio_history = [{"ts": "previous", "value": 300}]
        with patch("core.data_store.save_cache") as save_cache, \
                patch("core.data_store.save_history") as save_history:
            self.store.save_to_cache()
        save_cache.assert_not_called()
        save_history.assert_called_once_with([{"ts": "previous", "value": 300}])

    def test_complete_snapshot_saves_cache_and_history(self):
        with patch("core.data_store.save_cache") as save_cache, \
                patch("core.data_store.save_history") as save_history:
            self.store.save_to_cache()
        save_cache.assert_called_once()
        save_history.assert_called_once_with([])

    def test_annual_coupon_rate_is_percentage_independent_of_frequency(self):
        for rate, frequency, expected in ((12, 4, 120), (0.5, 2, 5), (1, 12, 10)):
            with self.subTest(rate=rate):
                self.assertEqual(_annual_coupon_from_bond({
                    "nominal": money(1000), "couponRate": rate,
                    "couponQuantityPerYear": frequency,
                }), expected)

    def test_coupon_payment_takes_precedence_over_rate(self):
        self.assertEqual(_annual_coupon_from_bond({
            "nominal": money(1000), "coupon": money(30),
            "couponQuantityPerYear": 4, "couponRate": 10,
        }), 120)

    def test_setting_save_failure_keeps_config_and_store_unchanged(self):
        for method, args in (("set_horizon", (30,)), ("toggle_bond_sort", ())):
            with self.subTest(method=method):
                cfg = {"bond_horizon_days": 365, "bond_sort": "date"}
                with patch("core.config.save_config", side_effect=OSError("disk full")):
                    with self.assertRaises(OSError):
                        getattr(self.store, method)(*args, cfg)
                self.assertEqual(cfg, {"bond_horizon_days": 365, "bond_sort": "date"})
                self.assertEqual(self.store.bond_horizon, 365)
                self.assertEqual(self.store.bond_sort, "date")

    def test_setting_save_success_updates_config_and_store(self):
        cfg = {}
        with patch("core.config.save_config"):
            self.store.set_horizon(30, cfg)
            self.store.toggle_bond_sort(cfg)
        self.assertEqual(cfg, {"bond_horizon_days": 30, "bond_sort": "amount"})
        self.assertEqual(self.store.bond_horizon, 30)
        self.assertEqual(self.store.bond_sort, "amount")


if __name__ == "__main__":
    unittest.main()
