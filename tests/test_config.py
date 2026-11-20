import copy
import json
import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import config


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'config.json'
        for name, value in [('BASE_DIR', self.temp.name), ('CONFIG_FILE', str(self.path))]:
            p = patch.object(config, name, value)
            p.start()
            self.addCleanup(p.stop)

    def test_first_run_returns_independent_defaults(self):
        cfg = config.load_config()
        self.assertTrue(self.path.exists())
        cfg['connections'][0]['token'] = 'changed'
        cfg['notifications']['coupon_today'] = False
        self.assertEqual(config.DEFAULT_CONFIG['connections'][0]['token'], config.TOKEN_STUB)
        self.assertTrue(config.DEFAULT_CONFIG['notifications']['coupon_today'])

    def test_env_keeps_both_brokers(self):
        (Path(self.temp.name) / '.env').write_text(
            'TBANK_TOKEN=test-tbank\nBCS_REFRESH_TOKEN=test-bcs\n', encoding='utf-8')
        cfg = config.load_config()
        self.assertEqual({c['broker']: c['token'] for c in cfg['connections']},
                         {'tbank': 'test-tbank', 'bcs': 'test-bcs'})

    def test_failed_write_preserves_previous_file_and_reports_error(self):
        config.save_config({'theme': 'light'})
        original = self.path.read_bytes()
        with patch.object(config.os, 'replace', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                config.save_config({'theme': 'dark'})
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(Path(self.temp.name).iterdir()), [self.path])
        with self.assertRaises(TypeError):
            config.save_config({'invalid': object()})
        self.assertEqual(self.path.read_bytes(), original)

    def test_merged_defaults_do_not_share_nested_values(self):
        self.path.write_text('{"connections": []}', encoding='utf-8')
        cfg = config.load_config()
        cfg['notifications']['coupon_today'] = False
        self.assertTrue(config.DEFAULT_CONFIG['notifications']['coupon_today'])

    def test_dashboard_save_failure_keeps_memory_and_returns_failure(self):
        import sys
        import types
        with patch.dict(sys.modules, {'webview': types.ModuleType('webview')}):
            from ui.window import _DashboardAPI
        cfg = copy.deepcopy(config.DEFAULT_CONFIG)
        api = _DashboardAPI(None, None, cfg)
        original = copy.deepcopy(cfg)
        with self.assertLogs('stack.window', level='ERROR'), patch.object(config, 'save_config', side_effect=OSError('denied')):
            with self.assertRaisesRegex(RuntimeError, 'Не удалось сохранить'):
                api.set_theme('light')
            with patch('api.factory.verify_connection'):
                result = api.add_connection('BCS', 'bcs', 'test-refresh-token')
            self.assertFalse(result['ok'])
            with self.assertRaises(RuntimeError):
                api.toggle_connection(0)
            cfg['connections'].append(copy.deepcopy(cfg['connections'][0]))
            before_remove = copy.deepcopy(cfg)
            with self.assertRaises(RuntimeError):
                api.remove_connection(0)
            self.assertEqual(cfg, before_remove)
            cfg['connections'].pop()
        self.assertEqual(cfg, original)

    def test_logging_routes_both_namespaces_once(self):
        import main
        with patch.object(main, 'LOG_FILE', str(Path(self.temp.name) / 'log.txt')):
            main.setup_logging()
            main.setup_logging()
            logging.getLogger('stack.updater').info('stack message')
            logging.getLogger('tbank.api').info('tbank message')
            handlers = set()
            for name in ('stack', 'tbank'):
                logger = logging.getLogger(name)
                handlers.update(logger.handlers)
                logger.handlers.clear()
            for handler in handlers:
                handler.close()
        content = (Path(self.temp.name) / 'log.txt').read_text(encoding='utf-8')
        self.assertEqual(content.count('stack message'), 1)
        self.assertEqual(content.count('tbank message'), 1)


if __name__ == '__main__':
    unittest.main()
