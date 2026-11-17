"""Behavior tests for tools/setup/local_test_session.py on synthetic temp-dir fixtures.

Every server, mission, profile, mod and installer here is synthetic and explicit. The existing
gameplay/economy/acceptance-marker tools are replaced by recording fakes in most tests (the contract
under test is how the session orchestrates them), and exercised for real in one guarded integration
test that skips when those sibling tools are absent. Offline tests never establish DayZ behavior.
"""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from tools.package import pbo
from tools.setup import local_test_session as lts

ROOT = Path(__file__).resolve().parents[2]

SYNTHETIC_PASSWORD = 'synthetic-join-secret'
SYNTHETIC_ADMIN = 'synthetic-admin-secret'
CFG = (
    'hostname = "HC synthetic";   // name\r\n'
    'password = "%s";\r\n'
    'passwordAdmin = "%s";\r\n'
    'disable3rdPerson=1;\r\n'
    'serverTimeAcceleration = 6; // keep this comment\r\n'
    'BattlEye = 1;\r\n'
    'verifySignatures = 2;\r\n'
    'forceSameBuild = 1;\r\n'
    'class Missions\r\n'
    '{\r\n'
    '    class DayZ\r\n'
    '    {\r\n'
    '        template="dayzOffline.chernarusplus";\r\n'
    '        serverTimeAcceleration = 99;\r\n'
    '    };\r\n'
    '};\r\n') % (SYNTHETIC_PASSWORD, SYNTHETIC_ADMIN)



def vanilla_usage_vocabulary(mission):
    """SYNTHETIC: give the fixture mission the vanilla usage names, because the default
    economy delta now carries the datamined rows (for example Hunting)."""
    from tests.unit import test_datamined_items
    names = sorted(test_datamined_items.VOCAB)
    (mission / 'cfglimitsdefinition.xml').write_text(
        '<lists><usageflags>' + ''.join('<usage name="%s"/>' % n for n in names) + '</usageflags></lists>')
    # SYNTHETIC unspawned stock entries for every datamined row the shipped list marks present.
    import xml.etree.ElementTree as ET
    types_path = mission / 'db' / 'types.xml'
    types = ET.fromstring(types_path.read_text())
    for element in test_datamined_items.stock_for(test_datamined_items.dm.load_rows()).values():
        types.append(element)
    types_path.write_bytes(ET.tostring(types))

class FakeGameplay:
    MANAGED = 'hollow-country-gameplay'

    def __init__(self, log, fail_install=False, fail_rollback=False):
        self.log, self.fail_install, self.fail_rollback = log, fail_install, fail_rollback

    @staticmethod
    def parse(data):
        return json.loads(data)

    def generate(self, source, profile, preset):
        self.log.append(('gameplay.generate', str(source)))
        return {'cfggameplay.delta.json': b'{}'}

    def write_delta(self, stage, files):
        Path(stage).mkdir(parents=True)
        for name, data in files.items():
            (Path(stage) / name).write_bytes(data)

    def install(self, stage, target, dry_run=False):
        self.log.append(('gameplay.install', str(target)))
        if self.fail_install:
            raise ValueError('synthetic installer failure')
        (Path(target) / self.MANAGED).mkdir()
        (Path(target) / self.MANAGED / 'receipt.json').write_text('{}')

    def rollback(self, target, dry_run=False):
        self.log.append(('gameplay.rollback', str(target)))
        if (Path(target) / self.MANAGED / 'receipt.json').read_text() != '{}':
            raise ValueError('installed spawn preset drift; inspect before rollback')
        if self.fail_rollback and 'hc-rollback-trial' not in str(target):  # only the real run fails
            raise ValueError('synthetic late gameplay refusal')
        shutil.rmtree(Path(target) / self.MANAGED)


class FakeEconomy:
    MANAGED = 'hollow-country'

    def __init__(self, log):
        self.log = log

    def generate(self, source, profile):
        self.log.append(('economy.generate', profile['name']))
        return {'ce/types.xml': b'<types/>'}

    def write_delta(self, stage, files):
        Path(stage).mkdir(parents=True)

    def install_delta(self, stage, target):
        # The launcher must use the manifest-driven install so datamined and firearms rows keep their permissions.
        self.log.append(('economy.install_delta', str(target)))
        (Path(target) / self.MANAGED).mkdir()
        (Path(target) / self.MANAGED / 'receipt.json').write_text('{}')

    def rollback(self, target):
        self.log.append(('economy.rollback', str(target)))
        if (Path(target) / self.MANAGED / 'receipt.json').read_text() != '{}':
            raise ValueError('installed delta drift; inspect before rollback')
        shutil.rmtree(Path(target) / self.MANAGED)


class FakeMarkers:
    class RefusedDestination(ValueError):
        pass

    NAMES = ('fuel_siphon', 'atmosphere', 'events')

    def __init__(self, log):
        self.log = log

    def scan_tree(self, root):
        self.log.append(('markers.scan', str(root)))
        return {'markers': [{'kind': 'profile_marker', 'name': name} for name in self.NAMES]}

    def plan_profile(self, result, destination, repo, only=None):
        names = sorted(self.NAMES if not only else only)
        unknown = sorted(set(names) - set(self.NAMES))
        if unknown:
            raise self.RefusedDestination('unknown marker name(s): ' + ', '.join(unknown))
        base = Path(destination) / 'HollowCountry' / 'acceptance'
        return {'destination': str(destination), 'applied': False, 'files': [
            {'name': n, 'path': str(base / (n + '.enable')),
             'action': 'exists' if (base / (n + '.enable')).exists() else 'create'} for n in names]}

    def apply_plan(self, plan):
        for item in plan['files']:
            if item['action'] == 'create':
                Path(item['path']).parent.mkdir(parents=True, exist_ok=True)
                with open(item['path'], 'x'):
                    pass
        plan['applied'] = True
        return plan


class SessionCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hc-synthetic-session-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.log = []
        self.fail_install = False
        self.fail_rollback = False
        # Synthetic repository root: only the committed profiles the session reads.
        self.repo = self.base / 'repo'
        for rel, text in ((lts.GAMEPLAY_PROFILE, '{"name": "gp"}'), (lts.GAMEPLAY_PRESET, '{"name": "kit"}'),
                          (lts.ECONOMY_PROFILES + 'contextual-pilot.json', '{"name": "contextual-pilot"}'),
                          (lts.ECONOMY_PROFILES + 'baseline.json', '{"name": "baseline"}')):
            (self.repo / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / rel).write_text(text)
        self.world = self.base / 'world'
        self.server = self.world / 'server'
        self.mission = self.world / 'mission'
        self.profiles = self.world / 'profiles'
        self.built = self.world / 'built' / '@HollowCountry'
        self.snafu = self.world / '@SNAFU'
        self.tf = self.world / '@TacticalFlava'
        for directory in (self.server, self.mission, self.profiles, self.snafu / 'addons'):
            directory.mkdir(parents=True)
        self.cfg = self.server / 'serverDZ.cfg'
        self.cfg.write_bytes(CFG.encode())
        (self.mission / 'cfggameplay.json').write_text('{"version": 1}')
        (self.mission / 'cfgeconomycore.xml').write_text('<economycore/>')
        (self.snafu / 'addons' / 'snafu_synthetic.pbo').write_bytes(b'synthetic third-party bytes')
        (self.tf / 'addons').mkdir(parents=True)
        (self.tf / 'keys').mkdir()
        (self.tf / 'addons' / 'tf_synthetic.pbo').write_bytes(b'synthetic tactical flava bytes')
        (self.tf / 'keys' / 'Wayward.bikey').write_bytes(b'synthetic wayward public key')
        self.pbo_blob = pbo.pack({'config.cpp': b'synthetic'})
        self.make_built(signed=True)
        self.dest = self.world / 'session' / '@HollowCountry'
        self.dest.parent.mkdir()
        patcher = mock.patch.object(lts, 'load_tool', self.load_tool)
        patcher.start()
        self.addCleanup(patcher.stop)

    def make_built(self, signed):
        shutil.rmtree(self.built.parent, ignore_errors=True)
        (self.built / 'addons').mkdir(parents=True)
        (self.built / 'addons' / 'hollowcountry.pbo').write_bytes(self.pbo_blob)
        (self.built / 'mod.cpp').write_text('name = "Hollow Country";\n')
        if signed:
            (self.built / 'addons' / 'hollowcountry.pbo.synthetic.bisign').write_bytes(b'synthetic signature')
            (self.built / 'keys').mkdir()
            (self.built / 'keys' / 'synthetic.bikey').write_bytes(b'synthetic public key')

    def load_tool(self, name):
        if name == 'gameplay':
            return FakeGameplay(self.log, self.fail_install, self.fail_rollback)
        if name == 'economy':
            return FakeEconomy(self.log)
        return FakeMarkers(self.log)

    def args(self, command='plan', *extra):
        return [command, '--server-root', str(self.server), '--mission', str(self.mission),
                '--profiles', str(self.profiles), '--mod', str(self.built), '--mod-dest', str(self.dest), *extra]

    def run_cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(err):
            code = lts.main(argv, repo=self.repo, out=out)
        return code, out.getvalue(), err.getvalue()

    def tree(self, *roots):
        found = {}
        for root in roots:
            for path in sorted(Path(root).rglob('*')):
                found[str(path)] = path.read_bytes() if path.is_file() and not path.is_symlink() else None
        return found

    state = property(lambda self: self.server / lts.STATE_NAME)


class CfgEdit(unittest.TestCase):
    def values(self, **kw):
        return lts.desired_values(kw.get('time', 4), kw.get('night', 8))

    def test_only_the_five_managed_keys_change_and_everything_else_is_byte_identical(self):
        new, changes = lts.edit_cfg(CFG, self.values())
        old_lines, new_lines = CFG.splitlines(True), new.splitlines(True)
        changed = [line for line in new_lines if line not in old_lines]
        self.assertEqual(sorted(line.split('=')[0].strip() for line in changed),
                         ['disable3rdPerson', 'enableCfgGameplayFile', 'serverNightTimeAcceleration',
                          'serverTimeAcceleration', 'thirdPersonView'])
        for kept in ('hostname = "HC synthetic";   // name\r\n', 'password = "%s";\r\n' % SYNTHETIC_PASSWORD,
                     'passwordAdmin = "%s";\r\n' % SYNTHETIC_ADMIN, 'BattlEye = 1;\r\n', 'verifySignatures = 2;\r\n',
                     'forceSameBuild = 1;\r\n', '        serverTimeAcceleration = 99;\r\n'):
            self.assertIn(kept, new_lines)
        self.assertIn('disable3rdPerson=0;\r\n', new_lines)  # original spacing kept
        self.assertIn('serverTimeAcceleration = 4; // keep this comment\r\n', new_lines)  # comment kept
        self.assertTrue(all(line.endswith('\r\n') for line in new_lines))  # CRLF preserved for inserts
        self.assertLess(new.index('thirdPersonView = 2;'), new.index('class Missions'))
        self.assertEqual({c['key']: c['action'] for c in changes}['thirdPersonView'], 'insert')

    def test_equal_values_are_left_alone_and_numeric_forms_compare_equal(self):
        text = 'thirdPersonView = 2;\ndisable3rdPerson = 0;\nserverTimeAcceleration = 4.0;\n' \
               'serverNightTimeAcceleration = 8;\nenableCfgGameplayFile = 1;\n'
        new, changes = lts.edit_cfg(text, self.values())
        self.assertEqual(new, text)
        self.assertEqual({c['action'] for c in changes}, {'unchanged'})

    def test_duplicate_top_level_key_is_refused_but_a_class_scoped_key_is_ignored(self):
        with self.assertRaises(lts.Refused):
            lts.edit_cfg('disable3rdPerson = 1;\ndisable3rdPerson = 0;\n', self.values())
        new, changes = lts.edit_cfg(CFG, self.values())
        self.assertEqual(new.count('serverTimeAcceleration'), 2)

    def test_defensive_check_refuses_a_change_to_a_protected_or_unmanaged_line(self):
        with self.assertRaises(lts.Refused):
            lts.check_only_managed(CFG, CFG.replace('verifySignatures = 2;', 'verifySignatures = 0;'))
        with self.assertRaises(lts.Refused):
            lts.check_only_managed(CFG, CFG.replace('BattlEye = 1;', 'BattlEye = 0;'))
        with self.assertRaises(lts.Refused):
            lts.check_only_managed(CFG, CFG.replace(SYNTHETIC_PASSWORD, 'other'))

    def test_acceleration_overrides_are_bounded(self):
        self.assertEqual(lts.desired_values(12, 1.5)['serverTimeAcceleration'], '12')
        for bad in (0, -1, 65, float('nan'), float('inf')):
            with self.subTest(bad=bad), self.assertRaises(lts.Refused):
                lts.desired_values(bad, 8)

    def lines_of(self, text, key):
        return [line for line in text.splitlines(True) if line.lstrip('\ufeff').lower().startswith(key.lower())]

    def assertProtectedIdentical(self, before, after):
        for key in ('password', 'passwordAdmin', 'BattlEye', 'verifySignatures', 'hostname'):
            self.assertEqual(self.lines_of(before, key), self.lines_of(after, key), key)

    def test_bom_prefixed_first_line_is_replaced_not_duplicated_and_the_bom_is_kept(self):
        text = '\ufeffthirdPersonView=1;\r\npassword = "%s";\r\nBattlEye = 1;\r\n' % SYNTHETIC_PASSWORD
        new, changes = lts.edit_cfg(text, self.values())
        self.assertTrue(new.startswith('\ufeffthirdPersonView=2;\r\n'))
        self.assertEqual(new.lower().count('thirdpersonview'), 1)
        self.assertEqual({c['key']: c['action'] for c in changes}['thirdPersonView'], 'replace')
        self.assertEqual(new.count('\ufeff'), 1)
        self.assertProtectedIdentical(text, new)

    def test_bom_before_a_protected_first_line_is_untouched(self):
        text = '\ufeffpassword = "%s";\nBattlEye = 1;\n' % SYNTHETIC_PASSWORD
        new, _ = lts.edit_cfg(text, self.values())
        self.assertTrue(new.startswith('\ufeffpassword = "%s";\nBattlEye = 1;\n' % SYNTHETIC_PASSWORD))
        self.assertEqual(new.count('\ufeff'), 1)

    def test_braces_semicolons_and_comment_markers_inside_quotes_are_not_syntax(self):
        text = ('hostname = "see http://example.invalid/a // not a comment";\r\n'
                'password="{";\r\n'
                'passwordAdmin = "a;b";\r\n'
                'thirdPersonView=1;\r\n'
                'serverTimeAcceleration = 6;\r\n'
                'BattlEye = 1;\r\n'
                'class Missions\r\n{\r\n    serverTimeAcceleration = 99;\r\n};\r\n')
        new, changes = lts.edit_cfg(text, self.values())
        self.assertEqual(new.lower().count('thirdpersonview'), 1)  # replaced, not inserted a second time
        self.assertIn('thirdPersonView=2;\r\n', new)
        self.assertIn('serverTimeAcceleration = 4;\r\n', new)
        self.assertIn('    serverTimeAcceleration = 99;\r\n', new)  # class scope still recognised
        self.assertLess(new.index('enableCfgGameplayFile'), new.index('class Missions'))
        self.assertProtectedIdentical(text, new)

    def test_a_leading_inline_block_comment_is_kept_and_does_not_crash(self):
        text = '/* local note */ thirdPersonView = 1; // tail\r\n/*a*/ /*b*/disable3rdPerson=1;\r\nBattlEye=1;\r\n'
        new, _ = lts.edit_cfg(text, self.values())
        self.assertIn('/* local note */ thirdPersonView = 2; // tail\r\n', new)
        self.assertIn('/*a*/ /*b*/disable3rdPerson=0;\r\n', new)
        self.assertEqual(new.lower().count('thirdpersonview'), 1)
        self.assertIn('BattlEye=1;\r\n', new)

    def test_a_key_inside_a_multi_line_block_comment_is_not_configuration(self):
        text = '/*\nthirdPersonView=1;\npassword = "{";\n*/\nBattlEye = 1;\nclass A\n{\n};\n'
        new, changes = lts.edit_cfg(text, self.values())
        self.assertIn('/*\nthirdPersonView=1;\npassword = "{";\n*/\n', new)
        self.assertEqual({c['key']: c['action'] for c in changes}['thirdPersonView'], 'insert')
        self.assertLess(new.index('thirdPersonView = 2;'), new.index('class A'))

    def test_several_statements_on_one_line_are_refused_rather_than_guessed(self):
        with self.assertRaises(lts.Refused):
            lts.edit_cfg('thirdPersonView=1; password="x";\n', self.values())

    def test_defensive_check_accepts_a_comment_prefixed_managed_line_change(self):
        before = '/* c */ thirdPersonView=1;\nBattlEye = 1;\n'
        lts.check_only_managed(before, before.replace('=1;\nB', '=2;\nB'))
        with self.assertRaises(lts.Refused):
            lts.check_only_managed(before, before.replace('BattlEye = 1', 'BattlEye = 0'))

    def test_windows_paths_and_powershell_quoting(self):
        self.assertEqual(lts.to_windows('/mnt/d/HollowCountryLocal/@HollowCountry'),
                         ('D:\\HollowCountryLocal\\@HollowCountry', True))
        self.assertEqual(lts.to_windows('/tmp/x'), ('/tmp/x', False))
        self.assertEqual(lts.ps_quote("D:\\it's"), "'D:\\it''s'")


class Plan(SessionCase):
    def test_plan_is_the_default_and_writes_nothing(self):
        before = self.tree(self.world, self.repo)
        code, out, err = self.run_cli(self.args('plan')[1:])  # no subcommand at all
        self.assertEqual((code, err), (0, ''))
        self.assertIn('PLAN, no changes written', out)
        self.assertEqual(before, self.tree(self.world, self.repo))
        self.assertEqual(self.log.count(('gameplay.install', str(self.mission))), 0)

    def test_plan_prints_launch_commands_with_snafu_and_the_confirm_annotation(self):
        code, out, err = self.run_cli(self.args('plan', '--snafu', str(self.snafu)))
        self.assertEqual(code, 0, err)
        self.assertIn('-config=', out)
        self.assertIn('-profiles=%s' % self.profiles, out)
        self.assertIn("-mod=%s;%s" % (self.snafu, self.dest), out)  # dependency first, same list on both sides
        self.assertEqual(out.count('-mod=%s;%s' % (self.snafu, self.dest)), 2)  # server and client
        self.assertIn('-connect=127.0.0.1:2302:27016', out)
        self.assertIn('thirdPersonView: (absent) -> 2', out)
        self.assertIn('"value to confirm in session"', out)
        self.assertIn('World.c:301', out)
        self.assertIn('DayZPlayerImplement.c:2918', out)
        self.assertIn('disable3rdPerson: 1 -> 0', out)
        self.assertIn('serverTimeAcceleration: 6 -> 4', out)
        self.assertIn('serverNightTimeAcceleration: (absent) -> 8', out)
        self.assertIn('enableCfgGameplayFile: (absent) -> 1', out)

    def test_night_pace_is_stated_as_a_product_not_as_a_value_to_confirm(self):
        code, out, err = self.run_cli(self.args('plan'))
        self.assertEqual(code, 0, err)
        self.assertIn('x32', out)  # 4 * 8
        self.assertIn('serverTimeAcceleration * serverNightTimeAcceleration', out)
        self.assertIn('about 17 real minutes', out)  # 9 h / 32
        for line in out.splitlines():
            if 'serverNightTimeAcceleration:' in line:
                self.assertNotIn('confirm', line)
        code, out, err = self.run_cli(self.args('plan', '--time-accel', '6', '--night-accel', '3'))
        self.assertIn('x18', out)
        self.assertIn('about 30 real minutes', out)

    def test_plan_without_snafu_omits_it_and_flags_override_the_accelerations(self):
        code, out, err = self.run_cli(self.args('plan', '--time-accel', '12', '--night-accel', '2'))
        self.assertEqual(code, 0, err)
        self.assertNotIn('SNAFU', out)
        self.assertIn('serverTimeAcceleration: 6 -> 12', out)
        self.assertIn('serverNightTimeAcceleration: (absent) -> 2', out)

    def test_credentials_are_never_printed_and_the_password_is_only_flagged(self):
        code, out, err = self.run_cli(self.args('plan'))
        self.assertIn('-password=<yours>', out)
        outputs = [out, err]
        for argv in (self.args('apply'), ['rollback', '--server-root', str(self.server), '--dry-run'],
                     self.args('apply')):  # the last apply is refused (session exists): errors stay clean too
            code, out, err = self.run_cli(argv)
            outputs += [out, err]
        for text in outputs:
            self.assertNotIn(SYNTHETIC_PASSWORD, text)
            self.assertNotIn(SYNTHETIC_ADMIN, text)
        self.assertNotIn(SYNTHETIC_PASSWORD, (self.state / lts.RECEIPT_NAME).read_text())

    def test_unsigned_artifact_warns_and_never_edits_signature_verification(self):
        self.make_built(signed=False)
        code, out, err = self.run_cli(self.args('plan'))
        self.assertEqual(code, 0, err)
        self.assertIn('Unsigned mod', out)
        self.assertNotIn('verifySignatures:', out)  # reported as a note only, never as a change

    def test_a_bare_pbo_is_accepted_as_unsigned_and_a_half_signed_dir_is_not_treated_as_signed(self):
        bare = self.world / 'hollowcountry.pbo'
        bare.write_bytes(self.pbo_blob)
        code, out, err = self.run_cli(self.args('plan')[:7] + ['--mod', str(bare)] + self.args('plan')[9:])
        self.assertEqual(code, 0, err)
        self.assertIn('unsigned', out)
        (self.built / 'keys' / 'synthetic.bikey').unlink()
        code, out, err = self.run_cli(self.args('plan'))
        self.assertEqual(code, 0, err)
        self.assertIn('unsigned', out)
        self.assertNotIn('.bisign', out)

    def test_markers_all_none_and_named(self):
        code, out, _ = self.run_cli(self.args('plan', '--markers', 'all'))
        self.assertEqual([out.count(n + '.enable') for n in FakeMarkers.NAMES], [1, 1, 1])
        code, out, _ = self.run_cli(self.args('plan', '--markers', 'none'))
        self.assertNotIn('.enable', out)
        code, out, _ = self.run_cli(self.args('plan', '--markers', 'fuel_siphon,events'))
        self.assertIn('fuel_siphon.enable', out)
        self.assertIn('events.enable', out)
        self.assertNotIn('atmosphere.enable', out)
        for bad in ('nope', '../x', ''):
            code, out, err = self.run_cli(self.args('plan', '--markers', bad))
            self.assertEqual(code, 2, bad)

    def test_a_pbo_that_fails_the_existing_structural_check_is_refused(self):
        (self.built / 'addons' / 'hollowcountry.pbo').write_bytes(b'not a pbo' * 20)
        code, out, err = self.run_cli(self.args('plan'))
        self.assertEqual(code, 2)
        self.assertIn('structural', err)


class TacticalFlava(SessionCase):
    """--tactical-flava mirrors --snafu: read-only, loaded before HC, its own keys/*.bikey optionally installed."""

    def test_load_order_is_snafu_then_tactical_flava_then_hollow_country_on_both_commands(self):
        code, out, err = self.run_cli(self.args('plan', '--snafu', str(self.snafu), '--tactical-flava', str(self.tf)))
        self.assertEqual(code, 0, err)
        mods = '-mod=%s;%s;%s' % (self.snafu, self.tf, self.dest)
        self.assertEqual(out.count(mods), 2)  # server and client carry the same list
        self.assertIn('Tactical Flava (read-only, optional dependency): %s' % self.tf, out)

    def test_tactical_flava_alone_goes_before_hollow_country(self):
        code, out, err = self.run_cli(self.args('plan', '--tactical-flava', str(self.tf)))
        self.assertEqual(code, 0, err)
        self.assertEqual(out.count('-mod=%s;%s' % (self.tf, self.dest)), 2)
        self.assertNotIn('SNAFU', out)

    def test_without_install_key_a_note_says_signature_checks_need_the_wayward_key(self):
        code, out, err = self.run_cli(self.args('apply', '--tactical-flava', str(self.tf)))
        self.assertEqual(code, 0, err)
        note = [line for line in out.splitlines() if line.startswith('NOTE:') and 'Wayward.bikey' in line]
        self.assertEqual(len(note), 1, out)
        self.assertIn('signature', note[0])
        self.assertIn('--install-key', note[0])
        self.assertFalse((self.server / 'keys').exists())

    def test_install_key_copies_the_tactical_flava_key_with_intent_receipt_and_rollback_removes_it(self):
        (self.server / 'keys').mkdir()
        (self.server / 'keys' / 'vanilla.bikey').write_bytes(b'someone elses key')
        tf_before = self.tree(self.tf)
        code, out, err = self.run_cli(self.args('apply', '--tactical-flava', str(self.tf), '--install-key'))
        self.assertEqual(code, 0, err)
        self.assertNotIn('Wayward.bikey are not', out)
        self.assertEqual((self.server / 'keys' / 'Wayward.bikey').read_bytes(), b'synthetic wayward public key')
        self.assertEqual((self.server / 'keys' / 'synthetic.bikey').read_bytes(), b'synthetic public key')
        receipt = json.loads((self.state / lts.RECEIPT_NAME).read_text())
        self.assertEqual(sorted(Path(k['path']).name for k in receipt['server_keys']), ['Wayward.bikey', 'synthetic.bikey'])
        self.assertEqual({k['state'] for k in receipt['server_keys']}, {'created'})
        # read-only and never copied into our mod folder
        self.assertEqual(tf_before, self.tree(self.tf))
        self.assertEqual(sorted(p.name for p in (self.dest / 'addons').iterdir()),
                         ['hollowcountry.pbo', 'hollowcountry.pbo.synthetic.bisign'])
        self.assertEqual(self.run_cli(['rollback', '--server-root', str(self.server)])[0], 0)
        self.assertEqual(sorted(p.name for p in (self.server / 'keys').iterdir()), ['vanilla.bikey'])
        self.assertEqual(tf_before, self.tree(self.tf))

    def test_install_key_works_for_an_unsigned_mod_when_only_the_tactical_flava_key_exists(self):
        self.make_built(signed=False)
        code, out, err = self.run_cli(self.args('apply', '--tactical-flava', str(self.tf), '--install-key'))
        self.assertEqual(code, 0, err)
        self.assertEqual([p.name for p in (self.server / 'keys').iterdir()], ['Wayward.bikey'])

    def test_an_identical_key_already_on_the_server_is_left_alone_and_needs_no_note(self):
        (self.server / 'keys').mkdir()
        (self.server / 'keys' / 'Wayward.bikey').write_bytes(b'synthetic wayward public key')
        code, out, err = self.run_cli(self.args('apply', '--tactical-flava', str(self.tf), '--install-key'))
        self.assertEqual(code, 0, err)
        self.assertNotIn('Wayward.bikey are not', out)
        self.assertEqual(self.run_cli(['rollback', '--server-root', str(self.server)])[0], 0)
        self.assertEqual((self.server / 'keys' / 'Wayward.bikey').read_bytes(), b'synthetic wayward public key')

    def test_a_different_key_with_the_same_name_is_refused_and_so_is_a_name_clash_with_our_key(self):
        (self.server / 'keys').mkdir()
        (self.server / 'keys' / 'Wayward.bikey').write_bytes(b'a different key')
        code, out, err = self.run_cli(self.args('plan', '--tactical-flava', str(self.tf)))
        self.assertEqual(code, 2)
        self.assertIn('different content', err)
        (self.server / 'keys' / 'Wayward.bikey').unlink()
        (self.tf / 'keys' / 'synthetic.bikey').write_bytes(b'clashes with the HC key name')
        code, out, err = self.run_cli(self.args('plan', '--tactical-flava', str(self.tf)))
        self.assertEqual(code, 2)
        self.assertIn('both', err)

    def test_a_tactical_flava_dir_without_keys_says_so(self):
        shutil.rmtree(self.tf / 'keys')
        code, out, err = self.run_cli(self.args('plan', '--tactical-flava', str(self.tf)))
        self.assertEqual(code, 0, err)
        self.assertIn('no keys/*.bikey', out)

    def test_bad_tactical_flava_inputs_are_refused_before_anything_is_written(self):
        before = self.tree(self.world, self.repo)
        shutil.rmtree(self.tf / 'addons')
        code, out, err = self.run_cli(self.args('apply', '--tactical-flava', str(self.tf)))
        self.assertEqual((code, 'no addons folder' in err), (2, True), err)
        (self.tf / 'addons').mkdir()
        inside = self.repo / '@TacticalFlava'
        shutil.copytree(self.tf, inside)
        code, out, err = self.run_cli(self.args('apply', '--tactical-flava', str(inside)))
        self.assertEqual((code, 'inside the repository' in err), (2, True), err)
        shutil.rmtree(inside)
        (self.tf / 'keys' / 'Wayward.bikey').unlink()
        elsewhere = self.world / 'elsewhere.bikey'
        elsewhere.write_bytes(b'k')
        (self.tf / 'keys' / 'Wayward.bikey').symlink_to(elsewhere)
        code, out, err = self.run_cli(self.args('apply', '--tactical-flava', str(self.tf)))
        self.assertEqual((code, 'symlink' in err), (2, True), err)
        (self.tf / 'keys' / 'Wayward.bikey').unlink()
        (self.tf / 'keys' / 'Wayward.bikey').write_bytes(b'synthetic wayward public key')
        self.assertFalse(self.state.exists())
        self.assertFalse(self.dest.exists())
        after = self.tree(self.world, self.repo)
        after.pop(str(elsewhere), None)
        before.pop(str(elsewhere), None)
        self.assertEqual({k: v for k, v in before.items() if '@TacticalFlava' not in k},
                         {k: v for k, v in after.items() if '@TacticalFlava' not in k})


class Safety(SessionCase):
    def assertRefused(self, argv, text):
        before = self.tree(self.world, self.repo)
        code, out, err = self.run_cli(argv)
        self.assertEqual(code, 2, out + err)
        self.assertIn(text, err)
        self.assertEqual(before, self.tree(self.world, self.repo))  # nothing written on refusal

    def test_destinations_inside_the_repo_or_a_git_checkout_are_refused(self):
        inside = self.repo / 'dest'
        inside.mkdir()
        self.dest = inside / '@HollowCountry'
        self.assertRefused(self.args('apply'), 'inside the repository')
        self.dest = self.world / 'session' / '@HollowCountry'
        checkout = self.world / 'checkout'
        (checkout / '.git').mkdir(parents=True)
        self.dest = checkout / '@HollowCountry'
        self.assertRefused(self.args('apply'), 'git checkout')
        self.dest = self.world / 'session' / '@HollowCountry'
        shutil.copytree(self.profiles, checkout / 'profiles')
        argv = self.args('apply')
        argv[argv.index('--profiles') + 1] = str(checkout / 'profiles')
        self.assertRefused(argv, 'git checkout')

    def test_symlinked_and_hard_linked_server_config_are_refused(self):
        real = self.world / 'real.cfg'
        real.write_bytes(CFG.encode())
        self.cfg.unlink()
        self.cfg.symlink_to(real)
        self.assertRefused(self.args('apply'), 'symlink')
        self.cfg.unlink()
        self.cfg.write_bytes(CFG.encode())
        os.link(self.cfg, self.world / 'alias.cfg')
        self.assertRefused(self.args('apply'), 'hard links')

    def test_symlinked_or_hard_linked_built_files_are_refused(self):
        pbo_path = self.built / 'addons' / 'hollowcountry.pbo'
        target = self.world / 'elsewhere.pbo'
        shutil.move(pbo_path, target)
        pbo_path.symlink_to(target)
        self.assertRefused(self.args('apply'), 'symlink')
        pbo_path.unlink()
        shutil.move(target, pbo_path)
        os.link(pbo_path, self.world / 'second-name.pbo')
        self.assertRefused(self.args('apply'), 'hard links')

    def test_symlinked_directories_in_a_destination_path_are_refused(self):
        link = self.world / 'profiles-link'
        link.symlink_to(self.profiles, target_is_directory=True)
        argv = self.args('apply')
        argv[argv.index('--profiles') + 1] = str(link)
        self.assertRefused(argv, 'symlink')
        (self.profiles / 'HollowCountry').symlink_to(self.world, target_is_directory=True)
        self.assertRefused(self.args('apply'), 'symlink')

    def other_checkout(self):
        other = self.world / 'other-checkout'
        (other / '.git').mkdir(parents=True)
        (other / 'acc').mkdir()
        return other

    def test_an_acceptance_directory_symlinked_into_another_checkout_is_refused_and_nothing_is_written(self):
        other = self.other_checkout()
        (self.profiles / 'HollowCountry').mkdir()
        (self.profiles / 'HollowCountry' / 'acceptance').symlink_to(other / 'acc', target_is_directory=True)
        code, out, err = self.run_cli(self.args('apply'))
        self.assertEqual(code, 2, out)
        self.assertIn('symlink', err)
        self.assertEqual(list((other / 'acc').iterdir()), [])
        self.assertFalse(self.state.exists())
        self.assertFalse(self.dest.exists())

    def test_a_symlinked_marker_file_is_refused(self):
        other = self.other_checkout()
        base = self.profiles / 'HollowCountry' / 'acceptance'
        base.mkdir(parents=True)
        (base / 'events.enable').symlink_to(other / 'acc' / 'target.enable')
        code, out, err = self.run_cli(self.args('apply', '--markers', 'events'))
        self.assertEqual(code, 2, out)
        self.assertIn('symlink', err)
        self.assertEqual(list((other / 'acc').iterdir()), [])

    def test_the_marker_path_is_validated_again_immediately_before_the_write(self):
        other = self.other_checkout()
        args = lts.build_parser().parse_args(self.args('apply'))
        plan = lts.build_plan(args, self.repo)  # passes: nothing is linked yet
        (self.profiles / 'HollowCountry').mkdir()
        (self.profiles / 'HollowCountry' / 'acceptance').symlink_to(other / 'acc', target_is_directory=True)
        with self.assertRaises(lts.Refused):
            lts.apply_plan(plan, args)
        self.assertEqual(list((other / 'acc').iterdir()), [])
        self.assertEqual(self.run_cli(['rollback', '--server-root', str(self.server)])[0], 0)
        self.assertEqual(list((other / 'acc').iterdir()), [])

    def test_existing_mod_destination_and_steam_mission_and_missing_inputs_are_refused(self):
        self.dest.mkdir()
        self.assertRefused(self.args('apply'), 'already exists')
        self.dest = self.world / 'session' / '@HollowCountry'
        steam = self.world / 'steamapps' / 'mission'
        steam.mkdir(parents=True)
        (steam / 'cfggameplay.json').write_text('{}')
        argv = self.args('apply')
        argv[argv.index('--mission') + 1] = str(steam)
        self.assertRefused(argv, 'steamapps')
        self.cfg.unlink()
        self.assertRefused(self.args('apply'), 'serverDZ.cfg does not exist')

    def test_refuses_to_overwrite_without_a_receipt_and_never_opens_an_existing_file(self):
        victim = self.world / 'victim.txt'
        victim.write_text('keep')
        with self.assertRaises(lts.Refused):
            lts.write_new(victim, b'overwritten')
        self.assertEqual(victim.read_text(), 'keep')
        link = self.world / 'link.txt'
        link.symlink_to(victim)
        with self.assertRaises(lts.Refused):
            lts.write_new(link, b'overwritten')
        self.assertEqual(victim.read_text(), 'keep')

    def test_unmanaged_cfg_never_gets_a_second_session(self):
        self.assertEqual(self.run_cli(self.args('apply'))[0], 0)
        code, out, err = self.run_cli(self.args('apply'))
        self.assertEqual(code, 2)
        self.assertIn('run rollback first', err)


class Apply(SessionCase):
    def test_apply_does_all_five_steps_with_backup_and_receipt_first(self):
        original = self.cfg.read_bytes()
        code, out, err = self.run_cli(self.args('apply', '--snafu', str(self.snafu)))
        self.assertEqual(code, 0, err)
        self.assertIn('APPLIED', out)
        # 1. mod folder: addons plus keys because signed, hashes equal the source
        self.assertEqual((self.dest / 'addons' / 'hollowcountry.pbo').read_bytes(), self.pbo_blob)
        self.assertEqual((self.dest / 'keys' / 'synthetic.bikey').read_bytes(), b'synthetic public key')
        self.assertTrue((self.dest / 'addons' / 'hollowcountry.pbo.synthetic.bisign').is_file())
        # 2. config: backup is byte-exact, receipt records both hashes, only the managed keys changed
        self.assertEqual((self.state / lts.BACKUP_NAME).read_bytes(), original)
        receipt = json.loads((self.state / lts.RECEIPT_NAME).read_text())
        self.assertEqual(receipt['status'], 'applied')
        self.assertEqual(receipt['cfg']['before_sha256'], lts.sha(original))
        self.assertEqual(receipt['cfg']['after_sha256'], lts.sha(self.cfg.read_bytes()))
        lts.check_only_managed(original.decode(), self.cfg.read_bytes().decode())
        text = self.cfg.read_bytes().decode()
        self.assertIn('thirdPersonView = 2;', text)
        self.assertIn('enableCfgGameplayFile = 1;', text)
        # 3. the existing installers ran, gameplay then economy, on the mission only
        calls = [name for name, _ in self.log if name.endswith(('install', 'install_delta', 'generate'))]
        self.assertEqual(calls, ['gameplay.generate', 'economy.generate', 'gameplay.generate', 'gameplay.install',
                                 'economy.generate', 'economy.install_delta'])
        self.assertTrue((self.mission / 'hollow-country-gameplay').is_dir())
        self.assertTrue((self.mission / 'hollow-country').is_dir())
        # 4. markers
        base = self.profiles / 'HollowCountry' / 'acceptance'
        self.assertEqual(sorted(p.name for p in base.iterdir()), ['atmosphere.enable', 'events.enable', 'fuel_siphon.enable'])
        self.assertEqual(sorted(Path(p).name for p in receipt['markers']['created']),
                         ['atmosphere.enable', 'events.enable', 'fuel_siphon.enable'])
        # SNAFU is read-only
        self.assertEqual([p.name for p in self.snafu.rglob('*')], ['addons', 'snafu_synthetic.pbo'])

    def test_apply_markers_none_and_named_and_skipping_the_deltas(self):
        code, _, err = self.run_cli(self.args('apply', '--markers', 'fuel_siphon', '--no-gameplay',
                                              '--economy-profile', 'none'))
        self.assertEqual(code, 0, err)
        self.assertEqual([p.name for p in (self.profiles / 'HollowCountry' / 'acceptance').iterdir()], ['fuel_siphon.enable'])
        self.assertFalse((self.mission / 'hollow-country-gameplay').exists())
        self.assertFalse((self.mission / 'hollow-country').exists())
        self.assertEqual(self.run_cli(['rollback', '--server-root', str(self.server)])[0], 0)
        self.assertEqual(self.run_cli(self.args('apply', '--markers', 'none'))[0], 0)
        self.assertFalse((self.profiles / 'HollowCountry').exists())

    def test_an_installer_failure_stops_the_session_and_rollback_still_undoes_the_completed_steps(self):
        original = self.cfg.read_bytes()
        self.fail_install = True
        code, out, err = self.run_cli(self.args('apply'))
        self.assertEqual(code, 2)
        self.assertIn('synthetic installer failure', err)
        self.assertIn('rollback --server-root', err)
        receipt = json.loads((self.state / lts.RECEIPT_NAME).read_text())
        self.assertEqual(receipt['status'], 'in-progress')
        self.assertEqual(receipt['steps']['cfg'], 'done')
        self.assertEqual(receipt['steps']['gameplay'], 'started')
        self.assertNotIn('economy', receipt['steps'])
        self.fail_install = False
        code, out, err = self.run_cli(['rollback', '--server-root', str(self.server)])
        self.assertEqual(code, 0, err)
        self.assertEqual(self.cfg.read_bytes(), original)
        self.assertFalse(self.dest.exists())
        self.assertFalse(self.state.exists())

    def test_install_key_copies_the_public_key_and_rollback_removes_only_that_copy(self):
        (self.server / 'keys').mkdir()
        (self.server / 'keys' / 'vanilla.bikey').write_bytes(b'someone elses key')
        code, out, err = self.run_cli(self.args('apply', '--install-key'))
        self.assertEqual(code, 0, err)
        self.assertEqual((self.server / 'keys' / 'synthetic.bikey').read_bytes(), b'synthetic public key')
        self.assertEqual(self.run_cli(['rollback', '--server-root', str(self.server)])[0], 0)
        self.assertFalse((self.server / 'keys' / 'synthetic.bikey').exists())
        self.assertEqual((self.server / 'keys' / 'vanilla.bikey').read_bytes(), b'someone elses key')

    def test_a_signed_mod_without_the_key_on_the_server_is_advised_and_a_different_key_is_refused(self):
        code, out, err = self.run_cli(self.args('plan'))
        self.assertIn('are not in <server root>\\keys', out)
        (self.server / 'keys').mkdir()
        (self.server / 'keys' / 'synthetic.bikey').write_bytes(b'a different key')
        code, out, err = self.run_cli(self.args('plan'))
        self.assertEqual(code, 2)
        self.assertIn('different content', err)

    def test_install_key_without_a_signed_artifact_is_refused(self):
        self.make_built(signed=False)
        code, out, err = self.run_cli(self.args('apply', '--install-key'))
        self.assertEqual(code, 2)
        self.assertFalse(self.state.exists())


class Rollback(SessionCase):
    def applied(self):
        self.original = self.cfg.read_bytes()
        self.assertEqual(self.run_cli(self.args('apply'))[0], 0)

    def test_rollback_restores_the_config_byte_exact_and_calls_both_installer_rollbacks(self):
        self.applied()
        self.log.clear()
        code, out, err = self.run_cli(['rollback', '--server-root', str(self.server)])
        self.assertEqual(code, 0, err)
        self.assertEqual(self.cfg.read_bytes(), self.original)
        # each installer ran once on a scratch copy (the preflight) and once for real, economy first
        self.assertEqual([name for name, target in self.log if name.endswith('rollback') and target == str(self.mission)],
                         ['economy.rollback', 'gameplay.rollback'])
        self.assertEqual(sum('hc-rollback-trial' in target for _, target in self.log), 2)
        self.assertFalse(self.dest.exists())
        self.assertFalse(self.state.exists())
        self.assertFalse((self.mission / 'hollow-country').exists())
        self.assertFalse((self.profiles / 'HollowCountry').exists())
        self.assertEqual(self.run_cli(self.args('apply'))[0], 0)  # a fresh session is possible again

    def test_rollback_dry_run_changes_nothing(self):
        self.applied()
        before = self.tree(self.world)
        code, out, err = self.run_cli(['rollback', '--server-root', str(self.server), '--dry-run'])
        self.assertEqual(code, 0, err)
        self.assertIn('would serverDZ.cfg: restore', out)
        self.assertEqual(before, self.tree(self.world))

    def test_rollback_refuses_config_drift_and_changes_nothing(self):
        self.applied()
        self.cfg.write_bytes(self.cfg.read_bytes() + b'// operator edit\r\n')
        before = self.tree(self.world)
        code, out, err = self.run_cli(['rollback', '--server-root', str(self.server)])
        self.assertEqual(code, 2)
        self.assertIn('drifted', err)
        self.assertEqual(before, self.tree(self.world))

    def test_rollback_leaves_a_file_the_operator_changed_in_place_and_undoes_the_rest(self):
        self.applied()
        pbo = self.dest / 'addons' / 'hollowcountry.pbo'
        pbo.write_bytes(b'edited after apply')
        code, out, err = self.run_cli(['rollback', '--server-root', str(self.server)])
        self.assertEqual((code, err), (0, ''))
        self.assertIn('left in place: not provably ours (%s)' % pbo, out)
        self.assertEqual(pbo.read_bytes(), b'edited after apply')
        self.assertEqual(self.cfg.read_bytes(), self.original)
        self.assertFalse(self.state.exists())

    def test_rollback_refuses_a_marker_the_operator_filled(self):
        self.applied()
        marker = self.profiles / 'HollowCountry' / 'acceptance' / 'events.enable'
        marker.write_text('operator content')
        code, out, err = self.run_cli(['rollback', '--server-root', str(self.server)])
        self.assertEqual(code, 2)
        self.assertIn('no longer empty', err)

    def test_rollback_refuses_a_tampered_receipt_and_a_missing_session(self):
        code, out, err = self.run_cli(['rollback', '--server-root', str(self.server)])
        self.assertEqual(code, 2)
        self.applied()
        path = self.state / lts.RECEIPT_NAME
        data = json.loads(path.read_text())
        data['markers']['created'].append(str(self.world / 'elsewhere' / 'passwd'))
        path.write_text(json.dumps(data))
        code, out, err = self.run_cli(['rollback', '--server-root', str(self.server)])
        self.assertEqual(code, 2)
        self.assertIn('outside the acceptance directory', err)

    def test_a_refusing_installer_stops_rollback_before_anything_changes_and_a_retry_succeeds(self):
        self.applied()
        drift = self.mission / 'hollow-country-gameplay' / 'receipt.json'
        drift.write_text('{"edited": true}')
        before = self.tree(self.world)
        code, out, err = self.run_cli(['rollback', '--server-root', str(self.server)])
        self.assertEqual(code, 2)
        self.assertIn('drift', err)
        self.assertEqual(before, self.tree(self.world))  # markers, economy, config and mod all still in place
        drift.write_text('{}')
        code, out, err = self.run_cli(['rollback', '--server-root', str(self.server)])
        self.assertEqual((code, err), (0, ''))
        self.assertEqual(self.cfg.read_bytes(), self.original)
        self.assertFalse(self.dest.exists())
        self.assertFalse(self.state.exists())
        self.assertFalse((self.mission / 'hollow-country').exists())
        self.assertFalse((self.mission / 'hollow-country-gameplay').exists())
        self.assertFalse((self.profiles / 'HollowCountry').exists())

    def test_rollback_dry_run_runs_the_installer_preflights_too(self):
        self.applied()
        (self.mission / 'hollow-country').joinpath('receipt.json').write_text('{"edited": true}')
        before = self.tree(self.world)
        code, out, err = self.run_cli(['rollback', '--server-root', str(self.server), '--dry-run'])
        self.assertEqual(code, 2)
        self.assertIn('drift', err)
        self.assertEqual(before, self.tree(self.world))

    def test_a_late_refusal_keeps_progress_and_the_retry_resumes_without_repeating_done_steps(self):
        self.applied()
        self.fail_rollback = True
        self.log.clear()
        code, out, err = self.run_cli(['rollback', '--server-root', str(self.server)])
        self.assertEqual(code, 2)
        self.assertIn('synthetic late gameplay refusal', err)
        receipt = json.loads((self.state / lts.RECEIPT_NAME).read_text())
        self.assertEqual(receipt['rollback']['steps'].get('markers'), 'done')
        self.assertEqual(receipt['rollback']['steps'].get('economy'), 'done')
        self.assertNotEqual(receipt['rollback']['steps'].get('gameplay'), 'done')
        self.assertFalse((self.mission / 'hollow-country').exists())
        self.fail_rollback = False
        self.log.clear()
        code, out, err = self.run_cli(['rollback', '--server-root', str(self.server)])
        self.assertEqual((code, err), (0, ''))
        self.assertNotIn('economy.rollback', [name for name, _ in self.log])  # neither trialled nor repeated
        self.assertEqual(self.cfg.read_bytes(), self.original)
        self.assertFalse(self.dest.exists())
        self.assertFalse(self.state.exists())

    def test_rollback_refuses_when_an_installer_refuses_and_keeps_the_receipt(self):
        self.applied()
        (self.mission / 'hollow-country-gameplay').rename(self.mission / 'moved-away')
        code, out, err = self.run_cli(['rollback', '--server-root', str(self.server)])
        self.assertEqual(code, 2)
        self.assertTrue((self.state / lts.RECEIPT_NAME).exists())


class Crash(BaseException):
    """A simulated kill: not an Exception, so no handler in the tool swallows it."""


class Interrupted(SessionCase):
    """apply is killed at a chosen creation; the receipt must already know about the file."""

    def killing(self, selector, when='after', partial=False):
        real = lts.write_new

        def write_new(path, data, mode=0o600, stage=None):
            if selector(Path(path)):
                if when == 'before':
                    raise Crash()
                real(path, data[:len(data) // 2] if partial else data, mode)  # a direct, non-atomic write
                raise Crash()
            return real(path, data, mode, stage=stage)
        return mock.patch.object(lts, 'write_new', write_new)

    def apply_killed(self, patcher, *extra):
        self.original = self.cfg.read_bytes()
        with patcher, self.assertRaises(Crash):
            self.run_cli(self.args('apply', *extra))

    def receipt(self):
        return json.loads((self.state / lts.RECEIPT_NAME).read_text())

    def rollback_ok(self):
        code, out, err = self.run_cli(['rollback', '--server-root', str(self.server)])
        self.assertEqual((code, err), (0, ''))
        self.assertEqual(self.cfg.read_bytes(), self.original)
        self.assertFalse(self.state.exists())
        self.assertFalse(self.dest.exists())
        self.assertEqual(sorted(p.name for p in self.server.iterdir()), ['serverDZ.cfg'])

    def server_key(self, path):
        return path == self.server / 'keys' / 'synthetic.bikey'

    def test_a_kill_right_after_the_server_key_is_written_still_lets_rollback_remove_it(self):
        self.apply_killed(self.killing(self.server_key), '--install-key')
        self.assertEqual([Path(k['path']).name for k in self.receipt()['server_keys']], ['synthetic.bikey'])
        self.assertTrue((self.server / 'keys' / 'synthetic.bikey').exists())
        self.rollback_ok()

    def test_a_kill_before_the_server_key_exists_leaves_an_intent_for_a_file_that_is_not_there(self):
        self.apply_killed(self.killing(self.server_key, when='before'), '--install-key')
        self.assertEqual(len(self.receipt()['server_keys']), 1)
        self.assertFalse((self.server / 'keys' / 'synthetic.bikey').exists())
        self.rollback_ok()

    def rollback_leaving(self, path, content):
        """Rollback finishes everything else, reports the path and leaves the file exactly as found."""
        code, out, err = self.run_cli(['rollback', '--server-root', str(self.server)])
        self.assertEqual((code, err), (0, ''))
        self.assertIn('left in place: not provably ours (%s)' % path, out)
        self.assertEqual(Path(path).read_bytes(), content)
        self.assertEqual(self.cfg.read_bytes(), self.original)
        self.assertFalse(self.state.exists())

    def test_a_short_file_at_an_intent_path_is_not_deleted_even_when_it_is_a_true_prefix(self):
        self.apply_killed(self.killing(self.server_key, partial=True), '--install-key')
        key = self.server / 'keys' / 'synthetic.bikey'
        self.assertEqual(key.read_bytes(), b'synthetic ')  # a true prefix of the expected key
        self.rollback_leaving(key, b'synthetic ')

    def test_an_operator_file_created_after_an_interrupted_apply_is_never_deleted(self):
        self.apply_killed(self.killing(self.server_key, when='before'), '--install-key')
        key = self.server / 'keys' / 'synthetic.bikey'
        key.parent.mkdir(exist_ok=True)
        key.write_bytes(b'operator')  # shorter than the expected key, not a prefix of it
        self.rollback_leaving(key, b'operator')

    def test_a_dry_run_reports_the_file_it_would_leave_in_place(self):
        self.apply_killed(self.killing(self.server_key, when='before'), '--install-key')
        key = self.server / 'keys' / 'synthetic.bikey'
        key.parent.mkdir(exist_ok=True)
        key.write_bytes(b'operator')
        code, out, err = self.run_cli(['rollback', '--server-root', str(self.server), '--dry-run'])
        self.assertEqual(code, 0)
        self.assertIn('left in place: not provably ours (%s)' % key, out)
        self.assertEqual(key.read_bytes(), b'operator')
        self.assertTrue(self.state.exists())

    def test_a_symlink_at_an_intent_path_is_left_in_place_and_the_rest_is_rolled_back(self):
        self.apply_killed(self.killing(self.server_key, when='before'), '--install-key')
        key = self.server / 'keys' / 'synthetic.bikey'
        key.parent.mkdir(exist_ok=True)
        elsewhere = self.server.parent / 'elsewhere.bin'
        elsewhere.write_bytes(b'operator')
        key.symlink_to(elsewhere)
        code, out, err = self.run_cli(['rollback', '--server-root', str(self.server)])
        self.assertEqual((code, err), (0, ''))
        self.assertIn('left in place: not provably ours', out)
        self.assertTrue(key.is_symlink())
        self.assertEqual(elsewhere.read_bytes(), b'operator')
        self.assertFalse(self.dest.exists())
        self.assertEqual(self.cfg.read_bytes(), self.original)

    def test_a_kill_before_the_atomic_rename_never_leaves_a_partial_file_at_the_final_path(self):
        self.original = self.cfg.read_bytes()
        with mock.patch.object(lts.os, 'link', side_effect=Crash()), self.assertRaises(Crash):
            self.run_cli(self.args('apply', '--install-key'))
        self.assertFalse((self.server / 'keys' / 'synthetic.bikey').exists())
        self.rollback_ok()

    def test_a_key_that_appeared_before_our_exclusive_create_is_never_deleted(self):
        real = lts.write_new

        def write_new(path, data, mode=0o600, stage=None):
            if self.server_key(Path(path)):
                Path(path).write_bytes(b'foreign key')
            return real(path, data, mode, stage=stage)
        self.original = self.cfg.read_bytes()
        with mock.patch.object(lts, 'write_new', write_new):
            code, out, err = self.run_cli(self.args('apply', '--install-key'))
        self.assertEqual(code, 2)
        self.assertEqual(self.receipt()['server_keys'][0]['state'], 'skipped')
        self.assertEqual(self.run_cli(['rollback', '--server-root', str(self.server)])[0], 0)
        self.assertEqual((self.server / 'keys' / 'synthetic.bikey').read_bytes(), b'foreign key')
        self.assertEqual(self.cfg.read_bytes(), self.original)

    def test_a_kill_while_a_tactical_flava_key_is_written_is_covered_the_same_way(self):
        self.apply_killed(self.killing(lambda p: p == self.server / 'keys' / 'Wayward.bikey'),
                          '--install-key', '--tactical-flava', str(self.tf))
        self.assertIn('Wayward.bikey', [Path(k['path']).name for k in self.receipt()['server_keys']])
        self.rollback_ok()
        self.assertEqual(list(self.tf.rglob('*.pbo'))[0].read_bytes(), b'synthetic tactical flava bytes')

    def test_a_half_written_mod_file_is_left_in_place_by_rollback_and_the_rest_is_removed(self):
        self.apply_killed(self.killing(lambda p: p.name == 'hollowcountry.pbo' and self.dest in p.parents, partial=True))
        pbo = self.dest / 'addons' / 'hollowcountry.pbo'
        self.rollback_leaving(pbo, pbo.read_bytes())
        self.assertEqual([p.name for p in self.dest.rglob('*') if p.is_file()], ['hollowcountry.pbo'])

    def killed_after_the_link(self, *extra, only_keys=False):
        """apply is killed right after os.link succeeded and before the staged link is removed."""
        real = lts.os.link

        def link(source, destination, *args, **kwargs):
            real(source, destination, *args, **kwargs)
            if not only_keys or Path(destination).parent == self.server / 'keys':
                raise Crash()
        self.original = self.cfg.read_bytes()
        with mock.patch.object(lts.os, 'link', link), self.assertRaises(Crash):
            self.run_cli(self.args('apply', *extra))

    def staged_links(self):
        return sorted(p for p in self.state.iterdir() if p.name.startswith('.stage-'))

    def test_a_kill_between_the_key_link_and_the_staged_unlink_is_fully_rolled_back(self):
        self.killed_after_the_link('--install-key', only_keys=True)
        key = self.server / 'keys' / 'synthetic.bikey'
        self.assertEqual(key.stat().st_nlink, 2)  # the final path and our staging link
        self.assertEqual(len(self.staged_links()), 1)
        self.rollback_ok()  # the key, its folder and the staging link are all gone

    def test_a_kill_between_a_mod_file_link_and_the_staged_unlink_is_fully_rolled_back(self):
        self.killed_after_the_link()
        linked = [p for p in self.dest.rglob('*') if p.is_file()]
        self.assertEqual(len(linked), 1)
        self.assertEqual(linked[0].stat().st_nlink, 2)
        self.rollback_ok()

    def test_a_staged_link_that_is_not_the_same_file_keeps_the_recovery_state_and_refuses(self):
        self.killed_after_the_link('--install-key', only_keys=True)
        key = self.server / 'keys' / 'synthetic.bikey'
        staged = self.staged_links()[0]
        staged.unlink()
        staged.write_bytes(b'something else')  # not our link to the key any more
        code, out, err = self.run_cli(['rollback', '--server-root', str(self.server)])
        self.assertEqual(code, 2)
        self.assertNotIn('Rollback complete', out)
        self.assertTrue((self.state / lts.RECEIPT_NAME).exists())
        self.assertTrue(key.exists())
        self.assertEqual(staged.read_bytes(), b'something else')
        self.assertEqual(self.cfg.read_bytes(), self.original)

    def test_a_staged_link_with_other_content_keeps_the_recovery_state_and_refuses(self):
        self.killed_after_the_link('--install-key', only_keys=True)
        key = self.server / 'keys' / 'synthetic.bikey'
        with open(key, 'r+b') as stream:  # both names are the same inode, now with different bytes
            stream.write(b'X')
        code, out, err = self.run_cli(['rollback', '--server-root', str(self.server)])
        self.assertEqual(code, 2)
        self.assertTrue((self.state / lts.RECEIPT_NAME).exists())
        self.assertTrue(key.exists())
        self.assertEqual(len(self.staged_links()), 1)

    def test_a_kill_before_the_atomic_rename_of_a_mod_file_never_leaves_a_partial_file_in_the_mod_folder(self):
        self.original = self.cfg.read_bytes()
        with mock.patch.object(lts.os, 'link', side_effect=Crash()), self.assertRaises(Crash):
            self.run_cli(self.args('apply'))
        self.assertEqual([p for p in self.dest.rglob('*') if p.is_file()], [])
        self.rollback_ok()

    def test_a_kill_after_the_first_mod_file_is_removed_by_rollback(self):
        self.apply_killed(self.killing(lambda p: p.name == 'hollowcountry.pbo' and self.dest in p.parents))
        self.rollback_ok()

    def test_a_half_written_config_backup_does_not_block_rollback_because_the_config_is_untouched(self):
        self.apply_killed(self.killing(lambda p: p.name == lts.BACKUP_NAME, partial=True))
        self.assertNotEqual((self.state / lts.BACKUP_NAME).read_bytes(), self.original)
        self.assertEqual(self.cfg.read_bytes(), self.original)
        self.rollback_ok()

    def test_a_kill_after_the_config_switch_but_before_it_is_recorded_done_is_restored(self):
        real = lts.Receipt.step

        def step(receipt, name, state):
            if (name, state) == ('cfg', 'done'):
                raise Crash()
            return real(receipt, name, state)
        self.apply_killed(mock.patch.object(lts.Receipt, 'step', step))
        self.assertNotEqual(self.cfg.read_bytes(), self.original)
        self.assertEqual(sorted(p.name for p in self.server.iterdir() if p.name.startswith('.')), [])
        self.rollback_ok()

    def test_a_kill_between_two_markers_is_undone_including_the_directories_it_created(self):
        original_apply = FakeMarkers.apply_plan

        def apply_plan(marker_tool, plan):
            first = plan['files'][0]
            Path(first['path']).parent.mkdir(parents=True, exist_ok=True)
            Path(first['path']).touch()
            raise Crash()
        self.original = self.cfg.read_bytes()
        with mock.patch.object(FakeMarkers, 'apply_plan', apply_plan), self.assertRaises(Crash):
            self.run_cli(self.args('apply'))
        self.assertEqual(len(self.receipt()['markers']['created']), 3)  # intent covers all three
        self.rollback_ok()
        self.assertFalse((self.profiles / 'HollowCountry').exists())
        self.assertIs(FakeMarkers.apply_plan, original_apply)


@unittest.skipUnless(all((ROOT / p).is_file() for p in (
    'tools/package/gameplay.py', 'tools/audit/acceptance_markers.py', lts.GAMEPLAY_PROFILE, lts.GAMEPLAY_PRESET,
    lts.ECONOMY_PROFILES + 'baseline.json')), 'sibling gameplay/acceptance tools or committed profiles absent')
class RealInstallers(unittest.TestCase):
    """The actual gameplay.py, economy.py and acceptance_markers.py on a synthetic mission copy."""

    def test_apply_and_rollback_leave_the_mission_and_profile_byte_identical(self):
        from tests.unit import test_economy_contract, test_gameplay_delta
        with tempfile.TemporaryDirectory(prefix='hc-synthetic-real-') as t:
            base = Path(t)
            mission, server, profiles = base / 'mission', base / 'server', base / 'profiles'
            mission.mkdir()
            test_economy_contract.synthetic(mission)
            vanilla_usage_vocabulary(mission)
            test_gameplay_delta.synthetic_source(base / 'gp')
            shutil.copy(base / 'gp' / 'cfggameplay.json', mission / 'cfggameplay.json')
            server.mkdir()
            profiles.mkdir()
            (server / 'serverDZ.cfg').write_bytes(CFG.encode())
            built = base / 'built' / '@HollowCountry'
            (built / 'addons').mkdir(parents=True)
            (built / 'addons' / 'hollowcountry.pbo').write_bytes(pbo.pack({'config.cpp': b'synthetic'}))
            before = {p: p.read_bytes() for p in list(mission.rglob('*')) + list(server.rglob('*')) if p.is_file()}
            argv = ['--server-root', str(server), '--mission', str(mission), '--profiles', str(profiles),
                    '--mod', str(built), '--mod-dest', str(base / 'out' / '@HollowCountry'),
                    '--economy-profile', 'baseline']
            (base / 'out').mkdir()
            out = io.StringIO()
            self.assertEqual(lts.main(['apply'] + argv, out=out), 0, out.getvalue())
            self.assertTrue((mission / 'hollow-country-gameplay' / 'receipt.json').is_file())
            self.assertTrue((mission / 'hollow-country' / 'receipt.json').is_file())
            self.assertTrue(list((profiles / 'HollowCountry' / 'acceptance').glob('*.enable')))
            self.assertEqual(lts.main(['rollback', '--server-root', str(server)], out=io.StringIO()), 0)
            after = {p: p.read_bytes() for p in list(mission.rglob('*')) + list(server.rglob('*')) if p.is_file()}
            self.assertEqual(before, after)

    def test_a_changed_spawn_preset_refuses_rollback_before_anything_changes_and_the_retry_succeeds(self):
        from tests.unit import test_economy_contract, test_gameplay_delta
        with tempfile.TemporaryDirectory(prefix='hc-synthetic-real-') as t:
            base = Path(t)
            mission, server, profiles = base / 'mission', base / 'server', base / 'profiles'
            mission.mkdir()
            test_economy_contract.synthetic(mission)
            vanilla_usage_vocabulary(mission)
            test_gameplay_delta.synthetic_source(base / 'gp')
            shutil.copy(base / 'gp' / 'cfggameplay.json', mission / 'cfggameplay.json')
            server.mkdir()
            profiles.mkdir()
            (base / 'out').mkdir()
            (server / 'serverDZ.cfg').write_bytes(CFG.encode())
            built = base / 'built' / '@HollowCountry'
            (built / 'addons').mkdir(parents=True)
            (built / 'addons' / 'hollowcountry.pbo').write_bytes(pbo.pack({'config.cpp': b'synthetic'}))
            argv = ['--server-root', str(server), '--mission', str(mission), '--profiles', str(profiles),
                    '--mod', str(built), '--mod-dest', str(base / 'out' / '@HollowCountry'),
                    '--economy-profile', 'baseline']
            self.assertEqual(lts.main(['apply'] + argv, out=io.StringIO()), 0)
            preset = mission / 'hollow-country-gameplay' / 'gear' / 'hardscrabble.json'
            good = preset.read_bytes()
            preset.write_bytes(good + b' ')

            def everything():
                return {p: p.read_bytes() for root in (mission, server, profiles, base / 'out')
                        for p in root.rglob('*') if p.is_file()}
            before = everything()
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(lts.main(['rollback', '--server-root', str(server)], out=io.StringIO()), 2)
            self.assertIn('spawn preset drift', err.getvalue())
            self.assertEqual(before, everything())  # no marker, economy or config change happened
            preset.write_bytes(good)
            self.assertEqual(lts.main(['rollback', '--server-root', str(server)], out=io.StringIO()), 0)
            self.assertFalse((mission / 'hollow-country').exists())
            self.assertFalse((mission / 'hollow-country-gameplay').exists())
            self.assertEqual((server / 'serverDZ.cfg').read_bytes(), CFG.encode())


if __name__ == '__main__':
    unittest.main()
