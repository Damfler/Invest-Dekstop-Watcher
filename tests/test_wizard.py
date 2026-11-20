import ast
import copy
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


class WizardTests(unittest.TestCase):
    def submit(self, verify):
        tree = ast.parse((Path(__file__).parents[1] / 'ui' / 'wizard.py').read_text(encoding='utf-8'))
        submit = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == '_submit')
        queue = []
        worker = []
        namespace = {
            'spinner': {'active': False}, 'broker_var': Mock(), 'token_var': Mock(),
            'status_var': Mock(), 'status_lbl': Mock(), 'entry': Mock(),
            'start_btn': Mock(), '_spin': Mock(), 'C': lambda x: x,
            'RED': 'red', 'PINK': 'pink', '_save': Mock(),
            'root': SimpleNamespace(after=lambda delay, callback: queue.append(callback), update=Mock()),
            'threading': SimpleNamespace(Thread=lambda target, **kw: SimpleNamespace(start=lambda: worker.append(target))),
        }
        namespace['broker_var'].get.return_value = 'tbank'
        namespace['token_var'].get.return_value = 'verified-token'
        exec(compile(ast.Module(body=[submit], type_ignores=[]), 'wizard.py', 'exec'), namespace)
        namespace['_submit']()
        namespace['broker_var'].get.return_value = 'bcs'
        namespace['token_var'].get.return_value = 'changed-token'
        with patch('api.factory.verify_connection', verify):
            worker[0]()
        queue[0]()
        return namespace

    def test_saves_exact_verified_broker_and_token(self):
        verify = Mock(return_value=2)
        namespace = self.submit(verify)
        self.assertEqual(verify.call_args.args, ('tbank', 'verified-token'))
        namespace['_save'].assert_called_once_with('verified-token', 2, 'tbank')

    def test_deferred_error_survives_exception_scope(self):
        namespace = self.submit(Mock(side_effect=ValueError('rejected')))
        namespace['status_var'].set.assert_called_with('Ошибка: rejected')
        namespace['_save'].assert_not_called()

    def test_failed_save_does_not_return_token_or_close_wizard(self):
        from core import config
        tree = ast.parse((Path(__file__).parents[1] / 'ui' / 'wizard.py').read_text(encoding='utf-8'))
        save = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == '_save')
        with tempfile.TemporaryDirectory() as directory:
            root = Mock()
            namespace = {
                'CONFIG_FILE': str(Path(directory) / 'config.json'),
                'os': os, 'deepcopy': copy.deepcopy, 'BROKERS': {'bcs': 'БКС'},
                'status_var': Mock(), 'status_lbl': Mock(), 'start_btn': Mock(),
                'root': root, 'result': {'token': None}, 'auto_var': Mock(),
                'GREEN': 'green', 'RED': 'red', 'PINK': 'pink',
            }
            exec(compile(ast.Module(body=[save], type_ignores=[]), 'wizard.py', 'exec'), namespace)
            with patch.object(config, 'save_config', side_effect=OSError('disk full')):
                namespace['_save']('token', 1, 'bcs')
            self.assertIsNone(namespace['result']['token'])
            root.after.assert_not_called()
            namespace['status_var'].set.assert_called_with('Ошибка: disk full')


if __name__ == '__main__':
    unittest.main()
