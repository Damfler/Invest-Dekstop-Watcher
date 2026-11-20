import unittest
from datetime import datetime
from unittest.mock import patch

from utils import moex_iss


class MoexTests(unittest.TestCase):
    def test_registry_date_is_not_a_payment_date(self):
        response = {"dividends": {
            "columns": ["registryclosedate", "value", "currencyid"],
            "data": [["2026-11-21", 10, "RUB"]],
        }}
        with patch.object(moex_iss, "_get", return_value=response):
            result = moex_iss.dividends("SBER", from_dt=datetime(2026, 11, 1), to_dt=datetime(2026, 12, 1))
        self.assertEqual(result, [])

    def test_dividend_payment_keeps_explicit_currency(self):
        response = {"dividends": {
            "columns": ["paymentdate", "value", "currencyid"],
            "data": [["2026-11-21", 10, "USD"]],
        }}
        with patch.object(moex_iss, "_get", return_value=response):
            result = moex_iss.dividends("SHARE", from_dt=datetime(2026, 11, 1), to_dt=datetime(2026, 12, 1))
        self.assertEqual(result[0]["dividendNet"], {"units": 10, "nano": 0, "currency": "USD"})

    def test_coupon_currency_is_preserved_or_left_unknown(self):
        response = {"coupons": {
            "columns": ["coupondate", "value", "faceunit"],
            "data": [["2026-11-21", 10, "USD"], ["2026-11-22", 20, None]],
        }}
        with patch.object(moex_iss, "_get", return_value=response):
            result = moex_iss.bond_coupons("BOND", from_dt=datetime(2026, 11, 1), to_dt=datetime(2026, 12, 1))
        self.assertEqual([p["payOneBond"]["currency"] for p in result], ["USD", ""])


if __name__ == "__main__":
    unittest.main()
