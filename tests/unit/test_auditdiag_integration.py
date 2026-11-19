"""Reviewable Z-owned fixture edits, applied ONLY to a temporary test-tree copy.

Run explicitly with python3 -B -m tests.unit.test_auditdiag_integration.
No shared fixture is modified in the worktree. No full unittest discovery.
The replacements below are the exact integration requests for report item 4.
"""
from pathlib import Path
import difflib
import os
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]

# All substitutions are fixture syntax/ports or the explicitly renamed unit label.
# No authored decision body or behavioral assertion is bypassed.
EDITS = {
    'test_hc_recovery.py': [
        ("self.env['HCGroupIO'] = N(WriteNew=self.write, HCReadRaw=self.read)",
         "self.env['HCGroupIO'] = N(WriteNew=self.write, HCReadRaw=self.read, HC_RAW_READ_CAP=self.io.HC_RAW_READ_CAP)"),
    ],
    'test_ecology_runtime.py': [
        ('self.e.update(archive_read=archive_read, read_file=read_file,',
         'self.e.update(HCGroupIO=SimpleNamespace(HC_RAW_READ_CAP=native.io.HC_RAW_READ_CAP),\n                      archive_read=archive_read, read_file=read_file,'),
    ],
    'test_hc_cellars.py': [
        ('HCGroupJson=N(Load=lambda path, limit, target: loaded.append((path, limit)) or True))',
         'HCGroupJson=N(Load=lambda path, limit, target: loaded.append((path, limit)) or True),\n                           HCGroupIO=N(HC_RAW_READ_CAP=1048576))'),
    ],
    'test_hc48_habitat_boot.py': [('manifest_bytes', 'manifest_chars')],
    'test_admin_start_refusals.py': [
        ('env = base_scope(GetGame=lambda: game,',
         'env = base_scope(HCAdminPermissionAdapter=lambda: N(HCStart=lambda: None), GetGame=lambda: game,'),
    ],
    'test_map_layers.py': [
        ("service = NS(m_Running=True, m_Admins=NS(PlainIds=EArray(['synthetic-admin'])))",
         "service = NS(m_Running=True, m_Permissions=None, m_Admins=NS(PlainIds=EArray(['synthetic-admin'])))"),
        ("'bool HCAuthorized(', 'sender', {})",
         "'bool HCAuthorized(', 'sender', {'GetGame': lambda: NS(IsServer=lambda: True)})"),
    ],
    'test_ops_admin_controls.py': [
        ("owner = NS(m_Running=True, m_Admins=NS(PlainIds=EArray(['operator'])),",
         "owner = NS(m_Running=True, m_Permissions=None, m_Admins=NS(PlainIds=EArray(['operator'])),"),
        ('m_CommandAt=[0.0], m_Identities=[None], m_Tickets=[0],',
         'm_CommandAt=[0.0], m_SnapshotAt=[0.0], m_Identities=EArray([None]), m_Tickets=[0],'),
        ('owner.HCAuthorized = lambda sender: authorized(owner, sender)',
         "owner.HCAuthorized = lambda sender: authorized(owner, sender)\n        auth_slot = compile_authored(module, 'HCAdminModule', 'HCAuthSlot', scope,\n                                     ('HCAuthorized',), modded=False)\n        owner.HCAuthSlot = lambda sender: auth_slot(owner, sender)"),
        ("('HCAuthorized', 'HCRefused', 'HCKnown', 'HCReply'), modded=False)",
         "('HCAuthorized', 'HCAuthSlot', 'HCRefused', 'HCKnown', 'HCReply'), modded=False)"),
    ],
}


def run():
    readers = subprocess.run(['rg', '-l', 'HCPersistenceDisposition|HCCellarsModule|HCAdminSnapshotWire|HCAdminModule|HCEcologyNative|HCAITrade',
                              'tests/unit'], cwd=ROOT, text=True, capture_output=True, check=True)
    modules = sorted({p.removesuffix('.py').replace('/', '.') for p in readers.stdout.splitlines()
                      if p.endswith('.py')})
    patches = []
    with tempfile.TemporaryDirectory(prefix='auditdiag-fixtures-') as temporary:
        copy_root = Path(temporary)
        shutil.copytree(ROOT / 'tests', copy_root / 'tests', ignore=shutil.ignore_patterns('__pycache__'))
        # All production sources/data stay read-only in this isolated fixture tree.
        for name in ('mods', 'mission', 'config', 'tools', 'docs', 'README.md'):
            (copy_root / name).symlink_to(ROOT / name, target_is_directory=(ROOT / name).is_dir())
        for name, replacements in EDITS.items():
            path = copy_root / 'tests/unit' / name
            original = path.read_text()
            updated = original
            for old, new in replacements:
                assert old in updated, (name, old)
                updated = updated.replace(old, new)
            path.write_text(updated)
            patches.extend(difflib.unified_diff(original.splitlines(True), updated.splitlines(True),
                           fromfile='a/tests/unit/' + name, tofile='b/tests/unit/' + name))
        # Historical diagnostic overview is Z-owned too; request its label edit.
        doc = 'docs/OUTSTANDING.md'
        old_doc = (ROOT / doc).read_text()
        new_doc = old_doc.replace('`manifest_bytes`/`manifest_cap`', '`manifest_chars`/`manifest_cap`')
        patches.extend(difflib.unified_diff(old_doc.splitlines(True), new_doc.splitlines(True),
                       fromfile='a/' + doc, tofile='b/' + doc))
        (ROOT / '.banso-writer/auditdiag-fixtures.patch').write_text(''.join(patches))
        print('Temporary-copy focused command: python3 -B -m unittest ' + ' '.join(modules) + ' -v', flush=True)
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(copy_root))
        return subprocess.run(['python3', '-B', '-m', 'unittest', *modules, '-v'],
                              cwd=copy_root, env=env).returncode


if __name__ == '__main__':
    raise SystemExit(run())
