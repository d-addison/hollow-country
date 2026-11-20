"""#142: bundle-apply on a Windows friend server (synthetic; no Windows host is used here).

Two Windows-only failures were reported from the friend runbook:
1. the existing-CE guard refused the tool's own forward-slash folder because Path() on Windows
   rewrote it with backslashes;
2. os.fsync on a read-only descriptor raises EBADF on Windows (_commit needs a writable handle).
"""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

from tools.package import ce_coverage, loot_boost, optional_overlays


class ExistingCeRelative(unittest.TestCase):
    def test_forward_slash_folder_survives_windows_path_flavour(self):
        # Simulate Windows: the module's Path becomes the Windows flavour.
        with mock.patch.object(optional_overlays, 'Path', pathlib.PureWindowsPath):
            self.assertEqual(optional_overlays._ce_relative('hollow-country-optional-packs/ce', 'types.xml'),
                             'hollow-country-optional-packs/ce/types.xml')

    def test_unsafe_declarations_still_refused(self):
        for folder, name in (('a\\b', 'types.xml'), ('/abs', 'types.xml'), ('a/../..', 'types.xml'),
                             ('C:/x', 'types.xml'), ('ok', '..\\types.xml')):
            with self.subTest(folder=folder, name=name):
                with self.assertRaisesRegex(ValueError, 'unsafe existing CE declaration'):
                    optional_overlays._ce_relative(folder, name)


class SyncFileWritableOnWindows(unittest.TestCase):
    def _flags_used(self, module, os_name):
        seen = []
        real_open = os.open

        def recording_open(path, flags, *args, **kwargs):
            seen.append(flags)
            return real_open(path, flags, *args, **kwargs)

        with tempfile.TemporaryDirectory() as root:
            target = os.path.join(root, 'f.xml')
            with open(target, 'w') as stream:
                stream.write('<x/>')
            with mock.patch.object(module.os, 'name', os_name), mock.patch.object(module.os, 'open', recording_open):
                module._sync_file(target)
        return seen

    def test_windows_opens_read_write_posix_stays_read_only(self):
        for module in (loot_boost, ce_coverage):
            with self.subTest(module=module.__name__):
                windows = self._flags_used(module, 'nt')
                posix = self._flags_used(module, 'posix')
                self.assertTrue(windows and windows[0] & os.O_RDWR, windows)
                self.assertTrue(posix and not posix[0] & (os.O_RDWR | os.O_WRONLY), posix)


class DefaultPackGateIgnoresPlanReceipts(unittest.TestCase):
    """Boot-052 friend-path install: plan() also appends the HC-32 receipt line, which
    has no loaded= suffix; the default-pack gate must judge only the pack lines."""

    PACKS = ['[HollowCountry] V2 optional pack %s loaded=1' % name
             for name in ('AmbientAnimals', 'Bicycles', 'Navigation', 'RaGVehicles')]
    HC32 = '[HC Plan] HC-32 vehicle_families=8 optional=1 refused=runtime_pending state=authored runtime=PENDING'

    def test_all_packs_loaded_with_a_plan_receipt_is_accepted(self):
        self.assertEqual([], optional_overlays.unloaded_default_packs(self.PACKS + [self.HC32]))

    def test_an_unloaded_pack_is_named(self):
        lines = self.PACKS[:2] + ['[HollowCountry] V2 optional pack Navigation loaded=0', self.PACKS[3], self.HC32]
        self.assertEqual(['Navigation'], optional_overlays.unloaded_default_packs(lines))

    def test_no_pack_lines_at_all_is_refused(self):
        self.assertEqual(['<none reported>'], optional_overlays.unloaded_default_packs([self.HC32]))


if __name__ == '__main__':
    unittest.main()
