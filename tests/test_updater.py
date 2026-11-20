import hashlib
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from utils import updater


class UpdaterTests(unittest.TestCase):
    def test_latest_release_selects_stack_and_keeps_integrity_metadata(self):
        response = Mock(status_code=200)
        response.json.return_value = {
            'tag_name': 'v99.0.0', 'assets': [
                {'name': 'other.exe', 'browser_download_url': 'https://example.org/other'},
                {'name': 'Stack.exe', 'browser_download_url': 'https://example.org/Stack.exe',
                 'size': 5, 'digest': 'sha256:abc'},
            ]}
        with patch.object(updater.sys, 'frozen', True, create=True), patch.object(updater.requests, 'get', return_value=response):
            result = updater.check_for_update()
        self.assertEqual(result['asset_name'], 'Stack.exe')
        self.assertEqual(result['size'], 5)
        self.assertEqual(result['digest'], 'sha256:abc')

    def test_network_failure_is_visible(self):
        with patch.object(updater.sys, 'frozen', True, create=True), patch.object(updater.requests, 'get', side_effect=OSError('offline')):
            self.assertIn('error', updater.check_for_update())

    def test_download_validates_and_rejects_corruption(self):
        content = b'MZfake executable'
        response = Mock()
        response.iter_content.return_value = [content]
        with tempfile.TemporaryDirectory() as directory, patch.object(updater, '_UPDATE_DIR', directory), patch.object(updater.requests, 'get', return_value=response):
            path = updater.download_update('https://example.org/Stack.exe', size=len(content), digest='sha256:' + hashlib.sha256(content).hexdigest())
            self.assertEqual(Path(path).read_bytes(), content)
            response.iter_content.return_value = [b'MZbroken']
            self.assertIsNone(updater.download_update('https://example.org/Stack.exe', size=len(content)))
            self.assertEqual(Path(path).read_bytes(), content)
            self.assertFalse(Path(path + '.part').exists())

    def test_download_rejects_unsafe_asset_name(self):
        with patch.object(updater.requests, 'get') as request:
            self.assertIsNone(updater.download_update('https://example.org/x', '../Stack.exe'))
            request.assert_not_called()

    def test_apply_launches_unicode_safe_hidden_helper(self):
        with tempfile.TemporaryDirectory(prefix='Stack тест ') as directory:
            current = Path(directory) / 'current.exe'
            new = Path(directory) / 'new.exe'
            current.write_bytes(b'MZold')
            new.write_bytes(b'MZnew')
            with patch.object(updater, '_UPDATE_DIR', directory), patch.object(updater.sys, 'frozen', True, create=True), patch.object(updater.sys, 'executable', str(current)), patch.object(updater.subprocess, 'Popen') as spawn:
                self.assertTrue(updater.apply_update(str(new)))
            script = (Path(directory) / '_update.ps1').read_text(encoding='utf-8-sig')
            self.assertIn('[System.IO.File]::Replace', script)
            self.assertIn('WaitForExit', script)
            self.assertIn('-WindowStyle Hidden', script)
            self.assertIn('-File', spawn.call_args.args[0])
            self.assertEqual(spawn.call_args.kwargs['env']['PYINSTALLER_RESET_ENVIRONMENT'], '1')

    @unittest.skipUnless(os.name == 'nt', 'Windows update helper')
    def test_windows_helper_restores_previous_executable_when_new_one_cannot_start(self):
        with tempfile.TemporaryDirectory() as directory:
            current = Path(directory) / 'Stack.exe'
            source = Path(directory) / 'new.exe'
            code = 'using System.IO; class App { static void Main() { File.WriteAllText(System.Reflection.Assembly.GetExecutingAssembly().Location + ".started", "ok"); } }'
            subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
                            f"Add-Type -TypeDefinition '{code}' -OutputAssembly '{current}' -OutputType ConsoleApplication"],
                           check=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            original = current.read_bytes()
            source.write_bytes(b'MZinvalid executable')
            helpers = []
            real_spawn = subprocess.Popen
            def spawn(*args, **kwargs):
                helper = real_spawn(*args, **kwargs)
                helpers.append(helper)
                return helper
            with patch.object(updater, '_UPDATE_DIR', directory), patch.object(updater.sys, 'frozen', True, create=True), patch.object(updater.sys, 'executable', str(current)), patch.object(updater.os, 'getpid', return_value=2147483647), patch.object(updater.subprocess, 'Popen', side_effect=spawn):
                self.assertTrue(updater.apply_update(str(source)))
            marker = Path(str(current) + '.started')
            for _ in range(80):
                if marker.exists():
                    break
                time.sleep(0.1)
            helpers[0].wait(timeout=10)
            self.assertTrue(marker.exists(), 'Previous version did not restart')
            self.assertEqual(current.read_bytes(), original)
            self.assertEqual(Path(str(current) + '.failed').read_bytes(), source.read_bytes())


if __name__ == '__main__':
    unittest.main()
