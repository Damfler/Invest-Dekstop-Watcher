import copy
import json
import sys
import threading
import types
import unittest
from unittest.mock import Mock, patch

with patch.dict(sys.modules, {'webview': types.ModuleType('webview')}):
    from ui import window as window_module
_DashboardAPI = window_module._DashboardAPI
from core.config import DEFAULT_CONFIG


class WindowTests(unittest.TestCase):
    def setUp(self):
        self.cfg = copy.deepcopy(DEFAULT_CONFIG)
        self.store = Mock()
        self.store.snapshot.return_value = {}
        self.store._lock = threading.RLock()
        self.store.update_info = {}
        self.api = _DashboardAPI(self.store, Mock(), self.cfg)
        self.saved = patch('core.config.save_config').start()
        self.addCleanup(patch.stopall)

    def test_snapshot_exposes_notification_settings_and_thresholds(self):
        data = json.loads(self.api.get_data())
        self.assertEqual(data['notifications'], self.cfg['notifications'])
        self.assertEqual(data['notify_offer_days'], 2)
        self.assertEqual(data['notify_move_pct'], 1.0)
        self.assertNotIn('connections', data)

    def test_toggle_saves_without_losing_other_notification_settings(self):
        self.api.set_notification('coupon_today', False)
        self.assertFalse(self.cfg['notifications']['coupon_today'])
        self.assertTrue(self.cfg['notifications']['dividend_today'])
        self.assertEqual(self.saved.call_args.args[0]['notifications'], self.cfg['notifications'])

    def test_unknown_toggle_or_non_boolean_is_rejected(self):
        for key, value in [('token', True), ('coupon_today', 'false'), ('coupon_today', 0)]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.api.set_notification(key, value)
        self.saved.assert_not_called()

    def test_threshold_validation_and_success(self):
        for days, pct in [(-1, 1), (1.5, 1), (True, 1), (2, 0), (2, float('nan')),
                          (2, float('inf')), (2, True), (2, '1')]:
            with self.subTest(days=days, pct=pct), self.assertRaises(ValueError):
                self.api.set_notification_thresholds(days, pct)
        self.saved.assert_not_called()
        self.api.set_notification_thresholds(0, 0.5)
        self.assertEqual((self.cfg['notify_offer_days'], self.cfg['notify_move_pct']), (0, 0.5))
        self.saved.assert_called_once()

    def test_failed_persistence_keeps_notification_state(self):
        before = copy.deepcopy(self.cfg)
        self.saved.side_effect = OSError('denied')
        with self.assertLogs('stack.window', level='ERROR'), self.assertRaises(RuntimeError):
            self.api.set_notification('coupon_today', False)
        self.assertEqual(self.cfg, before)

    def test_manual_update_check_publishes_info_but_keeps_previous_on_error(self):
        available = dict(available=True, version='9.0', url='https://example.test/update')
        with patch('utils.updater.check_for_update', return_value=available):
            result = self.api.check_update()
        self.assertTrue(result['available'])
        self.assertEqual(self.store.update_info, available)
        with patch('utils.updater.check_for_update', return_value={'available': False, 'error': 'offline'}):
            self.assertEqual(self.api.check_update()['error'], 'offline')
        self.assertEqual(self.store.update_info, available)
        with patch('utils.updater.check_for_update', return_value={'available': False}):
            self.api.check_update()
        self.assertFalse(self.store.update_info['available'])

    def test_failed_update_install_keeps_application_running(self):
        self.store.update_info = dict(available=True, url='https://example.test/update', asset_name='Stack.exe')
        with patch('utils.updater.download_update', return_value='fake.exe'), \
             patch('utils.updater.apply_update', return_value=False), patch.object(window_module.os, '_exit') as exit_process:
            self.assertEqual(self.api.apply_update(), 'apply_failed')
        exit_process.assert_not_called()

    def test_horizon_delegates_once_and_failed_save_does_not_refresh(self):
        with patch.object(window_module.threading, 'Thread') as thread:
            self.api.set_horizon(90)
            self.store.set_horizon.assert_called_once_with(90, self.cfg)
            self.saved.assert_not_called()
            thread.return_value.start.assert_called_once()
            thread.reset_mock()
            self.store.set_horizon.side_effect = OSError('denied')
            with self.assertRaisesRegex(RuntimeError, 'Не удалось сохранить'):
                self.api.set_horizon(180)
            thread.assert_not_called()


if __name__ == '__main__':
    unittest.main()
