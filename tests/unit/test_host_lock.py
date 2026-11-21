"""Host locking tests use ordinary subprocesses, never native tools."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools.release.host_lock import ENV, host_lock


class HostLockTests(unittest.TestCase):
    def child(self, path, env):
        script = ('import sys; from tools.release.host_lock import host_lock; '
                  '\nwith host_lock("child", sys.argv[1]): print("acquired")')
        return subprocess.run([sys.executable, '-B', '-c', script, str(path)],
                              env=env, capture_output=True, text=True, timeout=10)

    def test_refusal_and_descendant_reentry(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'host.lock'
            with host_lock('friendcycle', path):
                record = json.loads(path.read_text())
                self.assertEqual(record['holder'], 'friendcycle')
                self.assertEqual(record['pid'], os.getpid())
                self.assertIn('started', record)
                self.assertEqual(self.child(path, dict(os.environ)).returncode, 0)
                env = dict(os.environ)
                env.pop(ENV)
                result = self.child(path, env)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('holder=friendcycle', result.stderr)
            self.assertEqual(self.child(path, env).returncode, 0)

    def test_exception_and_crash_release(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'host.lock'
            with self.assertRaises(RuntimeError):
                with host_lock('test', path):
                    raise RuntimeError()
            with host_lock('test', path):
                pass
            script = ('import os,sys; from tools.release.host_lock import host_lock; '
                      '\nwith host_lock("test", sys.argv[1]): os._exit(4)')
            subprocess.run([sys.executable, '-B', '-c', script, str(path)], check=False, timeout=10)
            with host_lock('test', path):
                pass

    def test_forged_environment_cannot_bypass_holder(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'host.lock'
            path.write_text(json.dumps(dict(holder='test', pid=99999999, started='old')))
            with patch.dict(os.environ, {ENV: path.read_text()}):
                with host_lock('new', path):
                    self.assertEqual(json.loads(path.read_text())['holder'], 'new')
