import sys
import threading
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

# GUI backends are irrelevant to the refresh and updater orchestration tests.
with patch.dict(sys.modules, {"pystray": Mock(), "webview": Mock()}):
    from core import app as app_module


class AppTests(unittest.TestCase):
    def setUp(self):
        self.store = Mock()
        self.store._lock = threading.Lock()
        self.store.last_bond_update = datetime.now(timezone.utc)
        self.store.snapshot.return_value = {
            "error": None, "bond_events": [], "dismissed": set(), "portfolios": [],
        }
        with patch.object(app_module, "DashboardWindow"), patch.object(app_module, "NotificationManager"), patch.object(app_module, "MenuBuilder"):
            self.app = app_module.StackTrayApp({}, self.store)

    def test_parallel_refreshes_only_fetch_and_notify_once(self):
        entered, release = threading.Event(), threading.Event()
        def fetch():
            entered.set()
            if not release.wait(2):
                raise TimeoutError("test did not release refresh")
        self.store.fetch_portfolio.side_effect = fetch
        first = threading.Thread(target=self.app._do_refresh)
        first.start()
        try:
            self.assertTrue(entered.wait(2))
            second = threading.Thread(target=self.app._do_refresh)
            second.start()
            second.join(0.5)
            self.assertFalse(second.is_alive(), "duplicate refresh should return immediately")
            self.assertEqual(self.store.fetch_portfolio.call_count, 1)
        finally:
            release.set()
            first.join(2)
        self.assertFalse(first.is_alive())
        self.assertEqual(self.store.fetch_portfolio.call_count, 1)
        self.app._notif.fire.assert_called_once()

    def test_refresh_lock_releases_after_failure(self):
        self.store.fetch_portfolio.side_effect = [RuntimeError("offline"), None]
        with self.assertRaises(RuntimeError):
            self.app._do_refresh()
        self.app._do_refresh()
        self.assertEqual(self.store.fetch_portfolio.call_count, 2)
        self.app._notif.fire.assert_called_once()

    def test_partial_snapshot_does_not_send_notifications(self):
        self.store.snapshot.return_value["error"] = "offline broker"
        self.app._do_refresh()
        self.app._notif.fire.assert_not_called()

    def test_invalidated_calendar_refreshes_immediately(self):
        self.store.last_bond_update = None
        self.app._do_refresh()
        self.store.fetch_bond_events.assert_called_once()

    def test_update_metadata_and_exit_follow_apply_result(self):
        self.store.update_info = {"available": True, "url": "https://example.org/Stack.exe",
                                  "asset_name": "Stack.exe", "size": 123, "digest": "sha256:abc"}
        for applied in (False, True):
            with self.subTest(applied=applied), \
                    patch("utils.updater.download_update", return_value="update.exe") as download, \
                    patch("utils.updater.apply_update", return_value=applied), patch("os._exit") as exit_process:
                self.app._download_and_apply_update()
                download.assert_called_once_with("https://example.org/Stack.exe", "Stack.exe",
                                                 size=123, digest="sha256:abc")
                self.assertEqual(exit_process.call_count, int(applied))

    def test_check_update_keeps_negative_and_error_results(self):
        for info in ({"available": False}, {"available": False, "error": "offline"}):
            with self.subTest(info=info), patch("utils.updater.check_for_update", return_value=info):
                self.app._check_update()
                self.assertEqual(self.store.update_info, info)
        with patch("utils.updater.check_for_update", side_effect=RuntimeError("offline")):
            self.app._check_update()
        self.assertEqual(self.store.update_info, {"available": False, "error": "offline"})


if __name__ == "__main__":
    unittest.main()
