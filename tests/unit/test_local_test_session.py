"""Behavior tests for tools/setup/local_test_session.py on synthetic temp-dir fixtures.

TDD record for #42/#11: before launcher implementation, the TemplateAndCoverage plus new bundle
behavior tests ran with PYTHONDONTWRITEBYTECODE=1 python3 -m unittest and reached the missing CLI
options. The actual exception was "SystemExit: 2" and the initial summary was:
Ran 7 tests in 0.193s
FAILED (errors=8)
One initial bundle fixture error (missing synthetic economy source pins) was corrected before source
implementation. Rerunning the two coverage refusal cases produced:
Ran 2 tests in 0.103s
FAILED (errors=2)
The focused GREEN command is:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_local_test_session tests.unit.test_friend_bundle

Every server, mission, profile, mod and installer here is synthetic and explicit. The existing
gameplay/economy/acceptance-marker tools are replaced by recording fakes in most tests (the contract
under test is how the session orchestrates them), and exercised for real in one guarded integration
test that skips when those sibling tools are absent. Offline tests never establish DayZ behavior.
"""
import contextlib
import io
import types
import json
import os
from pathlib import Path
import shutil
import subprocess
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



def vanilla_usage_vocabulary(mission, merge=False):
    """SYNTHETIC: give the fixture mission the vanilla usage names, because the default
    economy delta now carries the datamined rows (for example Hunting). merge keeps the mission's own limits."""
    from tests.unit import test_datamined_items
    names = sorted(test_datamined_items.VOCAB)
    if merge:
        import xml.etree.ElementTree as ET
        limits = ET.fromstring((mission / 'cfglimitsdefinition.xml').read_text())
        usages = limits.find('usageflags')
        have = {u.get('name') for u in usages}
        for name in names:
            if name not in have:
                ET.SubElement(usages, 'usage', {'name': name})
        (mission / 'cfglimitsdefinition.xml').write_bytes(ET.tostring(limits))
    else:
        (mission / 'cfglimitsdefinition.xml').write_text(
            '<lists><usageflags>' + ''.join('<usage name="%s"/>' % n for n in names) + '</usageflags></lists>')
    # SYNTHETIC unspawned stock entries for every datamined row the shipped list marks present.
    import xml.etree.ElementTree as ET
    types_path = mission / 'db' / 'types.xml'
    types = ET.fromstring(types_path.read_text())
    for element in test_datamined_items.stock_for(test_datamined_items.dm.load_rows()).values():
        types.append(element)
    types_path.write_bytes(ET.tostring(types))

def ai_pbo_blob(prefix='HollowCountryExpansionAI', config=None, member='config.cpp'):
    """SYNTHETIC Expansion AI addon PBO: its own prefix and a CfgPatches class of the same name."""
    import hashlib
    if config is None:
        config = b'class CfgPatches\n{\n    class HollowCountryExpansionAI\n    {\n        units[] = {};\n    };\n};\n'
    header = bytearray(b'\0' + pbo.WORDS.pack(pbo.VERS, 0, 0, 0, 0))
    header += b'prefix\0' + prefix.encode('ascii') + b'\0\0'
    header += member.encode('ascii') + b'\0' + pbo.WORDS.pack(0, 0, 0, 0, len(config))
    body = bytes(header + bytes(21) + config)
    return body + b'\0' + hashlib.sha1(body).digest()


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
    INPUTS = ('cfgeconomycore.xml',)
    rosters = []

    def __init__(self, log):
        self.log = log

    def generate(self, source, profile, roster=None):
        self.log.append(('economy.generate', profile['name']))
        self.rosters.append(roster and roster['name'])
        return {'ce/types.xml': b'<types/>'}

    def write_delta(self, stage, files):
        Path(stage).mkdir(parents=True)

    def install_delta(self, stage, target):
        # The launcher must use the manifest-driven install so datamined and firearms rows keep their permissions.
        self.log.append(('economy.install_delta', str(target)))
        (Path(target) / self.MANAGED).mkdir()
        receipt = {}
        if (Path(target) / 'mapgroupproto.xml').is_file():
            receipt['sources'] = {'mapgroupproto.xml': lts.sha((Path(target) / 'mapgroupproto.xml').read_bytes())}
        (Path(target) / self.MANAGED / 'receipt.json').write_text(json.dumps(receipt))

    def rollback(self, target):
        self.log.append(('economy.rollback', str(target)))
        receipt = json.loads((Path(target) / self.MANAGED / 'receipt.json').read_text())
        if set(receipt) - {'sources'}:
            raise ValueError('installed delta drift; inspect before rollback')
        shutil.rmtree(Path(target) / self.MANAGED)


class FakeOptional:
    """SYNTHETIC stand-in for snafu_optional / tactical_flava_optional.

    install appends a marker to cfgeconomycore.xml (as the real installers patch the core) and keeps the original
    in its receipt; rollback refuses unless its own marker is the last thing in the core (last-in-first-out)."""

    def __init__(self, log, label, managed, allowlist_path, status='verified', fail_install=False, fail_generate=False,
                 rollback_missing=False):
        self.log, self.label, self.MANAGED = log, label, managed
        self.ALLOWLIST_PATH = allowlist_path
        self.status, self.fail_install, self.fail_generate = status, fail_install, fail_generate
        self.rollback_missing = rollback_missing
        self.marker = '<!--%s-->' % label

    def load_vanilla(self, addons):
        self.log.append((self.label + '.load_vanilla', str(addons)))
        return {'CfgMagazines': {}, 'CfgAmmo': {}}

    def verify_install(self, install, allowlist, vanilla=None, **kw):
        self.log.append((self.label + '.verify_install', str(install)))
        if self.label == 'tf' and vanilla is None:
            return {'status': 'unverified', 'install': {'problems': ['vanilla-not-provided']}, 'classes': {}}
        problems = [] if self.status == 'verified' else ['publishedid-mismatch']
        return {'status': self.status, 'allowlist_sha256': 'a' * 64, 'install': {'problems': problems},
                'classes': {'Synthetic_' + self.label: {'status': 'verified' if not problems else 'missing',
                                                        'reasons': problems}}}

    def generate(self, source, allowlist, report):
        self.log.append((self.label + '.generate', str(source)))
        if self.fail_generate:
            raise ValueError('synthetic generate failure')
        if not (Path(source) / FakeEconomy.MANAGED / 'receipt.json').is_file():
            raise ValueError('economy delta is not installed in the source')
        if report['status'] != 'verified':
            raise ValueError('report is not verified')
        return {'ce/types.xml': b'<types/>'}

    def write_delta(self, stage, files):
        Path(stage).mkdir(parents=True)
        for name, data in files.items():
            (Path(stage) / name).parent.mkdir(parents=True, exist_ok=True)
            (Path(stage) / name).write_bytes(data)

    def install(self, stage, target):
        self.log.append((self.label + '.install', str(target)))
        if self.fail_install and 'hc-delta-rehearsal' not in str(target):  # only the real run fails
            raise ValueError('synthetic installer failure')
        core = Path(target) / 'cfgeconomycore.xml'
        before = core.read_text()
        (Path(target) / self.MANAGED).mkdir()
        (Path(target) / self.MANAGED / 'receipt.json').write_text(json.dumps({'before': before}))
        core.write_text(before + self.marker)

    def rollback(self, target):
        self.log.append((self.label + '.rollback', str(target)))
        if self.rollback_missing:
            raise FileNotFoundError('synthetic missing managed file')
        managed = Path(target) / self.MANAGED
        receipt = json.loads((managed / 'receipt.json').read_text())
        core = Path(target) / 'cfgeconomycore.xml'
        if not core.read_text().endswith(self.marker):
            raise ValueError('core drift (roll back later installs first); manual reconciliation required')
        core.write_text(receipt['before'])
        shutil.rmtree(managed)


class FakeMarkers:
    # SYNTHETIC opt-in (.enable) marker names. The real source has only the xai_diagnostic_spawn opt-in; the 18
    # V1/V2 features are on by default and opt out with a .disable file the launcher never writes.
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


class FakeInteriors:
    """SYNTHETIC stand-in for tools/package/interiors_profile.py: records calls, writes a managed folder."""
    MANAGED = 'hc-interiors-pack'

    def __init__(self, log, errors=()):
        self.log, self.errors = log, list(errors)

    def validate(self, pack):
        self.log.append(('interiors.validate', str(pack)))
        return {'errors': self.errors, 'pending': [{'id': 'measured-interiors', 'state': 'pending-measurement'}],
                'files': {'interiors.json': 'x'}}

    def install(self, pack, target, replace=False):
        rehearsal = 'hc-interiors-rehearsal-' in str(target)
        existing = Path(target) / 'interiors.json'
        if existing.exists() and existing.read_bytes() != b'{}':  # the real tool refuses a different file
            raise ValueError('a different interiors.json already exists; review it or pass --replace')
        self.log.append(('interiors.rehearse' if rehearsal else 'interiors.install', str(pack), str(target)))
        created = not Path(target).exists()
        Path(target).mkdir(exist_ok=True)
        (Path(target) / self.MANAGED).mkdir()
        (Path(target) / self.MANAGED / 'receipt.json').write_text(json.dumps({'created': created}))
        (Path(target) / 'interiors.json').write_text('{}')

    def rollback(self, target):
        self.log.append(('interiors.rollback', str(target)))
        managed = Path(target) / self.MANAGED
        receipt = json.loads((managed / 'receipt.json').read_text())
        extra = sorted(p.name for p in Path(target).iterdir() if p.name not in (self.MANAGED, 'interiors.json'))
        if extra:
            raise ValueError('a created directory now holds other files; rollback refuses deletion')
        shutil.rmtree(managed)
        (Path(target) / 'interiors.json').unlink()
        if receipt['created']:
            Path(target).rmdir()


MARKER_DOC = (
    '| Marker | File and class | Source |\n| :--- | :--- | :--- |\n'
    '| `$profile:HollowCountry/acceptance/fuel_siphon.enable` | `A.B` | `a.c` |\n'
    '| `$profile:HollowCountry/acceptance/atmosphere.enable` | `A.B` | `a.c` |\n'
    '| `$profile:HollowCountry/acceptance/events.enable` | `A.B` | `a.c` |\n'
    '\nOther prose mentions `$profile:HollowCountry/acceptance/prose_only.enable` outside the table.\n'
    '| #1 | row | `$profile:HollowCountry/acceptance/checklist_only.enable` | x |\n')
EXPANSION_FOLDERS = ('@CF', '@Dabs Framework', '@DayZ-Expansion-Core', '@DayZ-Expansion-AI')


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
                          (lts.ECONOMY_PROFILES + 'baseline.json', '{"name": "baseline"}'),
                          (lts.FIREARMS_ROSTER, '{"name": "roster"}')):
            (self.repo / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / rel).write_text(text)
        (self.repo / 'docs').mkdir()
        (self.repo / 'docs' / 'LOCAL_ACCEPTANCE_V1.md').write_text(MARKER_DOC)
        (self.repo / 'mission' / 'hollow-country' / 'interiors').mkdir(parents=True)
        (self.repo / 'mission' / 'hollow-country' / 'interiors' / 'pack.json').write_text('{}')
        (self.repo / 'mission' / 'hollow-country' / 'ai').mkdir(parents=True)
        (self.repo / 'mission' / 'hollow-country' / 'ai' / 'AISettings.merge.json').write_text('{"MaxDifficulty": 1}')
        (self.repo / 'mission' / 'hollow-country' / 'ai' / 'AIPatrolSettings.override.json').write_text('{"Enabled": 0}')
        self.interiors_errors = []
        self.running = []
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
        self.vanilla = self.world / 'game-addons'
        self.vanilla.mkdir()
        self.allowlist = self.world / 'allowlist.json'
        self.allowlist.write_text('{}')
        self.optional = {'snafu': {}, 'tf': {}}  # per-label FakeOptional options (status, fail_install, ...)
        self.pbo_blob = pbo.pack({'config.cpp': b'synthetic'})
        self.make_built(signed=True)
        self.dest = self.world / 'session' / '@HollowCountry'
        self.dest.parent.mkdir()
        patcher = mock.patch.object(lts, 'load_tool', self.load_tool)
        patcher.start()
        self.addCleanup(patcher.stop)
        running = mock.patch.object(lts, 'running_servers', lambda *a, **k: list(self.running), create=True)
        running.start()
        self.addCleanup(running.stop)

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
        if name == 'interiors_profile':
            return FakeInteriors(self.log, self.interiors_errors)
        if name == 'snafu_optional':
            return FakeOptional(self.log, 'snafu', 'hollow-country-snafu', self.allowlist, **self.optional['snafu'])
        if name == 'tactical_flava_optional':
            return FakeOptional(self.log, 'tf', 'hollow-country-tactical-flava', self.allowlist, **self.optional['tf'])
        return FakeMarkers(self.log)

    auto_vanilla = True  # pass --vanilla-addons with --tactical-flava (the default is <server root>/addons)

    def args(self, command='plan', *extra):
        extra = list(extra)
        if self.auto_vanilla and '--tactical-flava' in extra and '--vanilla-addons' not in extra:
            extra += ['--vanilla-addons', str(self.vanilla)]
        if command in ('plan', 'apply') and '--travel' not in extra and '--no-travel' not in extra:
            extra.append('--no-travel')  # travel CE is on by default; these fakes model the other steps
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
        code, out, err = self.run_cli(self.args('apply'))
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

    def test_the_economy_delta_includes_the_firearms_roster_by_default(self):
        FakeEconomy.rosters = []
        code, out, err = self.run_cli(self.args('apply'))
        self.assertEqual(code, 0, err)
        self.assertTrue(FakeEconomy.rosters)
        self.assertEqual(set(FakeEconomy.rosters), {'roster'})  # plan, rehearsal and apply all use the roster
        self.assertIn('firearms roster', out)
        self.assertEqual(self.run_cli(['rollback', '--server-root', str(self.server)])[0], 0)

    def test_the_default_economy_profile_never_enables_ce_diagnostic_logging(self):
        self.assertNotEqual(lts.DEFAULT_ECONOMY_PROFILE, 'diagnostic')
        root = Path(__file__).resolve().parents[2] / lts.ECONOMY_PROFILES
        default = json.loads((root / (lts.DEFAULT_ECONOMY_PROFILE + '.json')).read_text())
        self.assertFalse(default.get('diagnostics'))
        self.assertTrue(json.loads((root / 'diagnostic.json').read_text()).get('diagnostics'))

    def test_no_roster_drops_the_firearms_roster(self):
        FakeEconomy.rosters = []
        code, out, err = self.run_cli(self.args('apply', '--no-roster'))
        self.assertEqual(code, 0, err)
        self.assertTrue(FakeEconomy.rosters)
        self.assertEqual(set(FakeEconomy.rosters), {None})

    def test_no_roster_with_economy_profile_none_is_harmless(self):
        code, _, err = self.run_cli(self.args('plan', '--economy-profile', 'none', '--no-roster'))
        self.assertEqual(code, 0, err)

    def test_travel_is_on_by_default_and_skips_with_an_advisory_unless_explicit(self):
        # Owner decision 2026-11-17: all features on by default. Synthetic travel port only.
        base = lts.load_tool
        travel = types.SimpleNamespace(preference=lambda profiles: True, validate=lambda mission: None,
                                       MANAGED='hollow-country-travel-synthetic')
        with mock.patch.object(lts, 'load_tool', lambda name: travel if name == 'travel' else base(name)):
            default = [a for a in self.args('plan', '--economy-profile', 'none') if a != '--no-travel']
            code, out, err = self.run_cli(default)
            self.assertEqual(code, 0, err)
            self.assertIn('travel CE skipped: it needs the economy delta', out)
            code, _, err = self.run_cli(self.args('plan', '--economy-profile', 'none', '--travel'))
            self.assertNotEqual(code, 0)
            self.assertIn('--travel requires the economy delta', err)

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


class OptionalSteps(SessionCase):
    """--interiors, --expansion-ai and --markers (doc-listed names, all-local) as opt-in session steps."""

    def setUp(self):
        super().setUp()
        self.workshop = self.world / 'workshop'
        for name in EXPANSION_FOLDERS:
            (self.workshop / name / 'addons').mkdir(parents=True)
            (self.workshop / name / 'addons' / 'synthetic.pbo').write_bytes(b'synthetic third-party bytes ' + name.encode())
        self.ai_built = self.world / 'built' / '@HollowCountryExpansionAI'
        (self.ai_built / 'addons').mkdir(parents=True)
        self.ai_blob = ai_pbo_blob()
        (self.ai_built / 'addons' / 'hollowcountryexpansionai.pbo').write_bytes(self.ai_blob)
        self.ai_dest = self.world / 'session' / '@HollowCountryExpansionAI'
        # SYNTHETIC shipped AI content and an Expansion-written AISettings.json (Expansion writes it on first start).
        ai = self.repo / 'mission' / 'hollow-country' / 'ai'
        (ai / 'sites.json').write_text('{"Sites": ["synthetic"]}')
        (ai / 'loadouts').mkdir()
        (ai / 'loadouts' / 'HollowCountry_Patrol.json').write_text('{"Synthetic": "patrol"}')
        (ai / 'loadouts' / 'HollowCountry_Holdout.json').write_text('{"Synthetic": "holdout"}')
        self.ai_settings = self.profiles / 'ExpansionMod' / 'Settings' / 'AISettings.json'
        self.ai_settings.parent.mkdir(parents=True)
        self.ai_settings.write_text('{\n    "m_Version": 20,\n    "MaxDifficulty": 3,\n    "Other": "kept"\n}\n')

    def ai_args(self, command='plan', *extra):
        return self.args(command, '--expansion-ai', '--workshop-dir', str(self.workshop),
                         '--expansion-ai-mod', str(self.ai_built), '--expansion-ai-dest', str(self.ai_dest), *extra)

    def receipt(self):
        return json.loads((self.state / lts.RECEIPT_NAME).read_text())

    def steps(self):
        code, out, err = self.run_cli(['rollback', '--server-root', str(self.server), '--dry-run'])
        self.assertEqual((code, err), (0, ''), out)
        names = {'serverDZ.cfg': 'cfg', 'server keys': 'server_keys', 'mod folder': 'mod',
                 'Expansion AI addon folder': 'expansion_ai', 'Expansion AI settings': 'expansion_ai_config'}
        found = [line[len('would '):].split(':')[0] for line in out.splitlines() if line.startswith('would ')]
        return [names.get(name, name) for name in found]

    def test_no_new_step_appears_unless_asked_for(self):
        code, out, err = self.run_cli(self.args('plan'))
        self.assertEqual(code, 0, err)
        for word in ('Interiors', 'Expansion', 'AISettings'):
            self.assertNotIn(word, out)
        self.assertEqual([n for n, *_ in self.log if n.startswith('interiors')], [])

    # ---- interiors
    def test_plan_lists_the_interiors_install_and_writes_nothing(self):
        before = self.tree(self.world)
        code, out, err = self.run_cli(self.args('plan', '--interiors', 'legacy'))
        self.assertEqual(code, 0, err)
        self.assertIn('Interiors data pack', out)
        self.assertIn(str(self.profiles / 'HollowCountry'), out)
        self.assertIn('measured-interiors', out)  # the pending component is surfaced, not hidden
        self.assertEqual(before, self.tree(self.world))
        self.assertNotIn('interiors.install', [n for n, *_ in self.log])

    def test_apply_installs_after_the_economy_before_the_markers_and_records_it_in_the_receipt(self):
        code, out, err = self.run_cli(self.args('apply', '--interiors', 'legacy'))
        self.assertEqual(code, 0, err)
        order = [n for n, *_ in self.log if n in ('economy.install_delta', 'interiors.install')]
        self.assertEqual(order, ['economy.install_delta', 'interiors.install'])
        install = [row for row in self.log if row[0] == 'interiors.install'][0]
        self.assertEqual(install[1:], (str(self.repo / 'mission/hollow-country/interiors'), str(self.profiles / 'HollowCountry')))
        receipt = self.receipt()
        self.assertEqual(receipt['steps']['interiors'], 'done')
        self.assertEqual(receipt['interiors']['target'], str(self.profiles / 'HollowCountry'))
        self.assertTrue((self.profiles / 'HollowCountry' / 'hc-interiors-pack' / 'receipt.json').is_file())
        self.assertTrue((self.profiles / 'HollowCountry' / 'acceptance').is_dir())  # markers coexist

    def test_rollback_runs_in_reverse_order_and_leaves_the_world_byte_identical(self):
        before = self.tree(self.world)
        self.assertEqual(self.run_cli(self.args('apply', '--interiors', 'legacy'))[0], 0)
        self.assertEqual(self.steps(), ['markers', 'interiors', 'economy', 'gameplay', 'cfg', 'server_keys', 'mod'])
        code, out, err = self.run_cli(['rollback', '--server-root', str(self.server)])
        self.assertEqual((code, err), (0, ''), out)
        self.assertEqual(before, self.tree(self.world))
        self.assertIn('interiors.rollback', [n for n, *_ in self.log])

    def test_interiors_pack_that_fails_validation_is_refused_before_anything_is_written(self):
        self.interiors_errors = ['interiors.json: synthetic validation failure']
        before = self.tree(self.world)
        for command in ('plan', 'apply'):
            code, out, err = self.run_cli(self.args(command, '--interiors', 'legacy'))
            self.assertEqual(code, 2, out)
            self.assertIn('synthetic validation failure', err)
        self.assertEqual(before, self.tree(self.world))

    def test_an_already_installed_interiors_pack_is_refused_and_not_touched(self):
        managed = self.profiles / 'HollowCountry' / 'hc-interiors-pack'
        managed.mkdir(parents=True)
        before = self.tree(self.world)
        code, out, err = self.run_cli(self.args('apply', '--interiors', 'legacy'))
        self.assertEqual(code, 2, out)
        self.assertIn('interiors', err)
        self.assertEqual(before, self.tree(self.world))

    def test_a_drifted_interiors_install_refuses_rollback_before_any_change(self):
        self.assertEqual(self.run_cli(self.args('apply', '--interiors', 'legacy'))[0], 0)
        (self.profiles / 'HollowCountry' / 'stray.json').write_text('operator file')
        before = self.tree(self.world)
        code, out, err = self.run_cli(['rollback', '--server-root', str(self.server)])
        self.assertEqual(code, 2, out)
        self.assertIn('interiors', err)
        self.assertEqual(before, self.tree(self.world))  # markers, economy and cfg untouched by the refused attempt
        (self.profiles / 'HollowCountry' / 'stray.json').unlink()
        self.assertEqual(self.run_cli(['rollback', '--server-root', str(self.server)])[0], 0)

    # ---- Expansion AI
    def test_expansion_ai_needs_its_inputs_and_the_flags_need_the_step(self):
        for argv in (self.args('plan', '--expansion-ai'),
                     self.args('plan', '--expansion-ai', '--workshop-dir', str(self.workshop)),
                     self.args('plan', '--workshop-dir', str(self.workshop))):
            code, out, err = self.run_cli(argv)
            self.assertEqual(code, 2, out)
            self.assertIn('expansion', err.lower())

    def test_missing_expansion_dependencies_are_refused_by_name_and_nothing_is_copied(self):
        shutil.rmtree(self.workshop / '@CF')
        shutil.rmtree(self.workshop / '@DayZ-Expansion-AI')
        before = self.tree(self.world)
        for command in ('plan', 'apply'):
            code, out, err = self.run_cli(self.ai_args(command))
            self.assertEqual(code, 2, out)
            self.assertIn('CF', err)
            self.assertIn('Expansion-AI', err)
            self.assertIn('2792982069', err)
            self.assertNotIn('Dabs', err)
        self.assertEqual(before, self.tree(self.world))

    def test_a_workshop_id_folder_satisfies_a_dependency(self):
        (self.workshop / '@CF').rename(self.workshop / '1559212036')
        code, out, err = self.run_cli(self.ai_args('plan'))
        self.assertEqual(code, 0, err)
        self.assertIn(str(self.workshop / '1559212036'), out)

    def test_steam_workshop_id_folders_satisfy_every_expansion_dependency(self):
        # Steam names each subscribed folder by its Workshop id.
        for name, item_id in (('@CF', '1559212036'), ('@Dabs Framework', '2545327648'),
                              ('@DayZ-Expansion-Core', '2291785308'),
                              ('@DayZ-Expansion-AI', '2792982069')):
            (self.workshop / name).rename(self.workshop / item_id)
        code, out, err = self.run_cli(self.ai_args('plan'))
        self.assertEqual(code, 0, err)
        self.assertIn(str(self.workshop / '2792982069'), out)

    def test_plan_prints_subscriptions_the_merge_instruction_and_the_mod_order_without_writing(self):
        before = self.tree(self.world)
        code, out, err = self.run_cli(self.ai_args('plan', '--snafu', str(self.snafu), '--tactical-flava', str(self.tf)))
        self.assertEqual(code, 0, err)
        for text in ('CF', 'Dabs Framework', 'Expansion-Core', '2291785308', 'Expansion-AI',
                     '2792982069', 'never copied'):
            self.assertIn(text, out)
        self.assertIn('AISettings.merge.json', out)
        self.assertIn('ExpansionMod', out)
        self.assertIn('manual', out.lower())
        deps = [self.workshop / n for n in ('@CF', '@Dabs Framework',
                                             '@DayZ-Expansion-Core', '@DayZ-Expansion-AI')]
        mods = ';'.join([str(d) for d in deps] + [str(self.snafu), str(self.tf), str(self.dest)])
        # Server and client both load the AI addon last, right after HollowCountry (V2 factions/talk binding).
        self.assertEqual(out.count('-mod=' + mods + ';' + str(self.ai_dest)), 2)
        self.assertNotIn('-serverMod=', out)
        self.assertEqual(before, self.tree(self.world))

    def test_apply_installs_the_shipped_sites_loadouts_patrol_override_and_merged_settings(self):
        ai = self.repo / 'mission' / 'hollow-country' / 'ai'
        sites = self.profiles / 'HollowCountry' / 'expansion-ai-sites.json'
        loadouts = self.profiles / 'ExpansionMod' / 'Loadouts'
        patrols = self.mission / 'expansion' / 'settings' / 'AIPatrolSettings.json'
        before = self.tree(self.world)
        code, out, err = self.run_cli(self.ai_args('plan'))
        self.assertEqual(code, 0, err)
        for path in (sites, loadouts / 'HollowCountry_Patrol.json', loadouts / 'HollowCountry_Holdout.json', patrols,
                     self.ai_settings):
            self.assertIn(str(path), out)
        self.assertEqual(before, self.tree(self.world))  # a plan writes nothing
        # The addon retired the expansion-ai.json lease policy: AI_ENCOUNTER binds the site patrols.
        self.assertIn('expansion-ai.json is retired and not read', out)
        self.assertNotIn('written as a template on first start', out)
        code, out, err = self.run_cli(self.ai_args('apply'))
        self.assertEqual(code, 0, err)
        self.assertEqual(sites.read_bytes(), (ai / 'sites.json').read_bytes())
        for name in ('HollowCountry_Patrol.json', 'HollowCountry_Holdout.json'):
            self.assertEqual((loadouts / name).read_bytes(), (ai / 'loadouts' / name).read_bytes())
        self.assertEqual(patrols.read_bytes(), (ai / 'AIPatrolSettings.override.json').read_bytes())
        merged = json.loads(self.ai_settings.read_text())
        self.assertEqual(merged, {'m_Version': 20, 'MaxDifficulty': 1, 'Other': 'kept'})  # a field merge, not a copy
        self.assertFalse((self.profiles / 'HollowCountry' / 'expansion-ai.json').exists())  # lease policy untouched
        receipt = self.receipt()
        self.assertEqual(receipt['steps']['expansion_ai_config'], 'done')
        created = sorted(row['path'] for row in receipt['expansion_ai_config']['created'])
        self.assertEqual(created, sorted(str(p) for p in (sites, loadouts / 'HollowCountry_Patrol.json',
                                                          loadouts / 'HollowCountry_Holdout.json', patrols)))
        replaced = receipt['expansion_ai_config']['replaced']
        self.assertEqual([row['path'] for row in replaced], [str(self.ai_settings)])

    def test_an_absent_expansion_ai_settings_file_refuses_plan_and_apply(self):
        self.ai_settings.unlink()
        before = self.tree(self.world)
        for command in ('plan', 'apply'):
            code, out, err = self.run_cli(self.ai_args(command))
            self.assertEqual(code, 2, out)
            self.assertIn('AISettings.json', err)
            self.assertIn('start the server once', err)
            self.assertEqual(before, self.tree(self.world))

    def test_an_existing_patrol_settings_file_is_backed_up_replaced_and_restored_by_rollback(self):
        patrols = self.mission / 'expansion' / 'settings' / 'AIPatrolSettings.json'
        patrols.parent.mkdir(parents=True)
        patrols.write_text('{"Enabled": 1, "Patrols": ["expansion default"]}')
        before = self.tree(self.world)
        self.assertEqual(self.run_cli(self.ai_args('apply'))[0], 0)
        self.assertEqual(patrols.read_text(), '{"Enabled": 0}')
        self.assertEqual(self.steps()[:3], ['markers', 'expansion_ai_config', 'expansion_ai'])
        code, out, err = self.run_cli(['rollback', '--server-root', str(self.server)])
        self.assertEqual((code, err), (0, ''), out)
        self.assertEqual(before, self.tree(self.world))

    def test_stale_sites_refresh_keeps_timestamped_backup_and_identical_sites_are_kept(self):
        sites = self.profiles / 'HollowCountry' / 'expansion-ai-sites.json'
        sites.parent.mkdir()
        stale = b'{"Sites": ["synthetic stale deployment"]}'
        sites.write_bytes(stale)
        before = self.tree(self.world)
        code, out, err = self.run_cli(self.ai_args('plan'))
        self.assertEqual(code, 0, err)
        self.assertEqual(before, self.tree(self.world))
        code, out, err = self.run_cli(self.ai_args('apply'))
        self.assertEqual(code, 0, err)
        self.assertEqual(sites.read_bytes(), (self.repo / 'mission/hollow-country/ai/sites.json').read_bytes())
        backups = list(sites.parent.glob('expansion-ai-sites.json.*.bak'))
        self.assertEqual(len(backups), 1)
        self.assertRegex(backups[0].name, r'\.\d{8}T\d{6}\d{6}Z\.bak$')
        self.assertEqual(backups[0].read_bytes(), stale)
        self.assertIn('sites refresh', out)
        self.assertIn(lts.sha(stale), out)
        self.assertEqual(self.run_cli(['rollback', '--server-root', str(self.server)])[0], 0)
        self.assertEqual(sites.read_bytes(), stale)
        self.assertEqual(backups[0].read_bytes(), stale)  # operator recovery copy survives rollback
        sites.write_bytes((self.repo / 'mission/hollow-country/ai/sites.json').read_bytes())
        before = self.tree(self.world)
        self.assertEqual(self.run_cli(self.ai_args('apply'))[0], 0)
        self.assertNotIn(str(sites), [row['path'] for row in self.receipt()['expansion_ai_config']['created']])
        self.assertEqual(self.run_cli(['rollback', '--server-root', str(self.server)])[0], 0)
        self.assertEqual(before, self.tree(self.world))  # the identical file was never ours and stays

    def test_drift_in_the_merged_ai_settings_refuses_rollback_before_any_change(self):
        self.assertEqual(self.run_cli(self.ai_args('apply'))[0], 0)
        merged = self.ai_settings.read_bytes()
        self.ai_settings.write_bytes(merged + b' ')
        before = self.tree(self.world)
        for argv in (['rollback', '--server-root', str(self.server), '--dry-run'], ['rollback', '--server-root', str(self.server)]):
            code, out, err = self.run_cli(argv)
            self.assertEqual(code, 2, argv)
            self.assertIn('AISettings.json', err)
            self.assertIn('drift', err)
            self.assertEqual(before, self.tree(self.world))
        self.ai_settings.write_bytes(merged)
        self.assertEqual(self.run_cli(['rollback', '--server-root', str(self.server)])[0], 0)
        self.assertEqual(json.loads(self.ai_settings.read_text())['MaxDifficulty'], 3)

    def test_a_replacement_refused_by_an_intervening_edit_is_never_restored_by_rollback(self):
        # The operator writes the very bytes apply would merge, after the plan and before the switch: apply
        # refuses that replacement, so rollback must not "restore" the old backup over the operator's file.
        self.assertEqual(self.run_cli(self.ai_args('plan'))[0], 0)
        original = self.ai_settings.read_bytes()
        merged = dict(json.loads(original), **json.loads(
            (self.repo / 'mission' / 'hollow-country' / 'ai' / 'AISettings.merge.json').read_text()))
        operator = (json.dumps(merged, indent=4) + '\n').encode()
        native = lts.write_new

        def edit_after_backup(path, data, *args, **kwargs):
            result = native(path, data, *args, **kwargs)
            if Path(path).name == 'expansion-ai-backup-0':
                self.ai_settings.write_bytes(operator)
            return result

        with mock.patch.object(lts, 'write_new', side_effect=edit_after_backup):
            code, out, err = self.run_cli(self.ai_args('apply'))
        self.assertEqual(code, 2, out)
        self.assertIn('changed since the plan', err)
        self.assertEqual(self.ai_settings.read_bytes(), operator)
        states = [row.get('state') for row in self.receipt()['expansion_ai_config']['replaced']]
        code, out, err = self.run_cli(['rollback', '--server-root', str(self.server)])
        self.assertEqual((code, err), (0, ''), out)
        self.assertEqual(self.ai_settings.read_bytes(), operator)  # the operator's file, not the old backup
        self.assertEqual(states, ['skipped'])

    def test_the_session_reports_pve_patrols_on_by_default_and_never_writes_a_marker_for_it(self):
        code, out, err = self.run_cli(self.ai_args('plan', '--markers', 'none'))
        self.assertEqual(code, 0, err)
        self.assertIn('pve_patrols is on by default', out)
        self.assertIn('pve_patrols.disable', out)
        self.assertNotIn('opt-in marker', out)
        code, out, err = self.run_cli(self.ai_args('apply'))
        self.assertEqual(code, 0, err)
        self.assertIn('pve_patrols is on by default', out)
        acceptance = self.profiles / 'HollowCountry' / 'acceptance'
        self.assertFalse((acceptance / 'pve_patrols.enable').exists())
        self.assertEqual([], list(acceptance.glob('*.disable')), 'the launcher never writes an opt-out marker')

    def test_unreadable_patrol_override_refuses_the_ai_plan(self):
        (self.repo / 'mission' / 'hollow-country' / 'ai' / 'AIPatrolSettings.override.json').write_text('{')
        code, out, err = self.run_cli(self.ai_args('plan'))
        self.assertEqual(code, 2, out)
        self.assertIn('AIPatrolSettings.override.json', err)

    def test_apply_stages_only_the_hollow_country_addon_never_touches_expansion_or_the_settings(self):
        workshop_before = self.tree(self.workshop)
        code, out, err = self.run_cli(self.ai_args('apply'))
        self.assertEqual(code, 0, err)
        self.assertEqual(sorted(p.name for p in (self.ai_dest / 'addons').iterdir()), ['hollowcountryexpansionai.pbo'])
        self.assertEqual(self.tree(self.workshop), workshop_before)
        self.assertEqual(json.loads(self.ai_settings.read_text())['MaxDifficulty'], 1)  # merged, with a backup
        receipt = self.receipt()
        self.assertEqual(receipt['steps']['expansion_ai'], 'done')
        self.assertEqual(receipt['expansion_ai']['dest'], str(self.ai_dest))
        self.assertIn('addons/hollowcountryexpansionai.pbo', receipt['expansion_ai']['files'])
        self.assertIn('AISettings.merge.json', out)

    def test_rollback_removes_the_ai_addon_before_anything_older_and_keeps_expansion(self):
        before = self.tree(self.world)
        self.assertEqual(self.run_cli(self.ai_args('apply', '--interiors', 'legacy'))[0], 0)
        self.assertEqual(self.steps(), ['markers', 'expansion_ai_config', 'expansion_ai', 'interiors', 'economy',
                                        'gameplay', 'cfg', 'server_keys', 'mod'])
        self.assertEqual(self.run_cli(['rollback', '--server-root', str(self.server)])[0], 0)
        self.assertEqual(before, self.tree(self.world))

    def test_an_ai_destination_equal_to_the_main_one_or_existing_is_refused(self):
        for destination in (self.dest, self.world / 'session'):
            code, out, err = self.run_cli(self.args(
                'plan', '--expansion-ai', '--workshop-dir', str(self.workshop), '--expansion-ai-mod', str(self.ai_built),
                '--expansion-ai-dest', str(destination)))
            self.assertEqual(code, 2, out)

    # ---- markers
    def test_marker_names_come_from_the_acceptance_table_parsed_at_run_time(self):
        for bad in ('prose_only', 'checklist_only', 'events,prose_only'):
            code, out, err = self.run_cli(self.args('plan', '--markers', bad))
            self.assertEqual(code, 2, bad)
            self.assertIn('LOCAL_ACCEPTANCE_V1', err)
        doc = self.repo / 'docs' / 'LOCAL_ACCEPTANCE_V1.md'
        doc.write_text(MARKER_DOC + '| `$profile:HollowCountry/acceptance/atmosphere_two.enable` | `A.B` | `a.c` |\n')
        code, out, err = self.run_cli(self.args('plan', '--markers', 'atmosphere_two'))
        self.assertEqual(code, 2)  # in the table now, but the scan still has no such marker
        self.assertIn('unknown marker', err)

    def test_all_local_creates_every_listed_marker_and_rollback_removes_only_its_own(self):
        base = self.profiles / 'HollowCountry' / 'acceptance'
        base.mkdir(parents=True)
        (base / 'events.enable').write_text('')  # pre-existing: the operator's, not ours
        code, out, err = self.run_cli(self.args('apply', '--markers', 'all-local', '--no-gameplay',
                                                '--economy-profile', 'none'))
        self.assertEqual(code, 0, err)
        self.assertEqual(sorted(p.name for p in base.iterdir()), ['atmosphere.enable', 'events.enable', 'fuel_siphon.enable'])
        self.assertEqual(sorted(Path(p).name for p in self.receipt()['markers']['created']),
                         ['atmosphere.enable', 'fuel_siphon.enable'])
        self.assertEqual(self.run_cli(['rollback', '--server-root', str(self.server)])[0], 0)
        self.assertEqual([p.name for p in base.iterdir()], ['events.enable'])

    def test_all_local_without_the_table_is_refused(self):
        (self.repo / 'docs' / 'LOCAL_ACCEPTANCE_V1.md').write_text('no table here\n')
        code, out, err = self.run_cli(self.args('plan', '--markers', 'all-local'))
        self.assertEqual(code, 2)
        self.assertIn('LOCAL_ACCEPTANCE_V1', err)

    def test_the_default_all_and_none_do_not_need_the_table(self):
        (self.repo / 'docs' / 'LOCAL_ACCEPTANCE_V1.md').unlink()
        self.assertEqual(self.run_cli(self.args('plan', '--markers', 'all'))[0], 0)
        self.assertEqual(self.run_cli(self.args('plan', '--markers', 'none'))[0], 0)

    def test_real_acceptance_table_in_this_checkout_lists_only_names_the_code_scan_knows(self):
        from tools.audit import acceptance_markers
        # The 18 V1/V2 features are on by default and listed in the doc as `.disable` opt-outs, which the launcher
        # never reads as something to create. The only `.enable` row is the opt-in xai_diagnostic_spawn diagnostic.
        names = lts.local_marker_names(ROOT)
        self.assertEqual(['xai_diagnostic_spawn'], names)
        self.assertFalse(set(names) - set(acceptance_markers.creatable_names(acceptance_markers.scan_tree(ROOT))))
        self.assertFalse(set(names) & set(acceptance_markers.opt_out_names(acceptance_markers.scan_tree(ROOT))))

    # ---- running server
    def test_apply_and_rollback_refuse_while_the_server_runs_and_plan_only_warns(self):
        self.assertEqual(self.run_cli(self.args('apply', '--interiors', 'legacy'))[0], 0)
        self.running = [4242]
        before = self.tree(self.world)
        code, out, err = self.run_cli(['rollback', '--server-root', str(self.server)])
        self.assertEqual(code, 2)
        self.assertIn('server is running', err)
        self.assertEqual(before, self.tree(self.world))
        self.running = []
        self.assertEqual(self.run_cli(['rollback', '--server-root', str(self.server)])[0], 0)
        self.running = [4242]
        code, out, err = self.run_cli(self.args('apply', '--interiors', 'legacy'))
        self.assertEqual(code, 2)
        self.assertIn('server is running', err)
        self.assertFalse(self.state.exists())
        code, out, err = self.run_cli(self.args('plan', '--interiors', 'legacy'))
        self.assertEqual(code, 0, err)
        self.assertIn('server is running', out)

    def test_a_running_dayzdiag_server_is_detected_but_a_diag_client_is_not(self):
        proc = self.base / 'proc'
        for pid, cmd in (('20', b'DayZDiag_x64.exe\0-server\0-config=serverDZ.cfg\0'),
                         ('21', b'Z:\\srv\\DayZDiag_x64.exe\0-client\0-connect=127.0.0.1\0'),
                         ('22', b'DayZDiag_x64.exe\0-mod=@x\0')):
            (proc / pid).mkdir(parents=True)
            (proc / pid / 'cmdline').write_bytes(cmd)
        self.assertEqual(lts.find_server_processes(proc, query=lambda: []), [20])

    def test_the_windows_query_finds_dayzdiag_servers_through_their_command_line(self):
        def run(argv, **kwargs):
            text = ' '.join(argv).lower()
            out = ''
            if 'dayzserver' in text:
                out = '"DayZServer_x64.exe","300","Console","1","1,000 K"\n'
            elif argv[0].endswith('powershell.exe'):
                out = '400\tDayZDiag_x64.exe -server -config=serverDZ.cfg\n401\tDayZDiag_x64.exe -connect=1.2.3.4\n'
            return subprocess.CompletedProcess(argv, 0, out, '')
        which = {'tasklist.exe': '/x/tasklist.exe', 'powershell.exe': '/x/powershell.exe'}
        with mock.patch.object(lts.shutil, 'which', lambda name: which.get(name)), \
                mock.patch.object(lts.subprocess, 'run', run):
            self.assertEqual(sorted(lts.windows_task_list()), [300, 400])
        which.pop('powershell.exe')  # cannot read command lines: every DayZDiag counts (fail closed)

        def run_no_shell(argv, **kwargs):
            out = '"DayZDiag_x64.exe","500","Console","1","1 K"\n' if 'dayzdiag' in ' '.join(argv).lower() else ''
            return subprocess.CompletedProcess(argv, 0, out, '')
        with mock.patch.object(lts.shutil, 'which', lambda name: which.get(name)), \
                mock.patch.object(lts.subprocess, 'run', run_no_shell):
            self.assertEqual(lts.windows_task_list(), [500])

    def test_running_servers_reads_process_command_lines_and_the_windows_task_list(self):
        proc = self.base / 'proc'
        for pid, cmd in (('10', b'/usr/bin/python3\0x'), ('11', b'Z:\\srv\\DayZServer_x64.exe\0-config=x'), ('abc', b'DayZServer_x64')):
            (proc / pid).mkdir(parents=True)
            (proc / pid / 'cmdline').write_bytes(cmd)
        self.assertEqual(lts.find_server_processes(proc, query=lambda: []), [11])
        self.assertEqual(lts.find_server_processes(proc, query=lambda: [77]), [11, 77])
        self.assertEqual(lts.find_server_processes(self.base / 'missing', query=lambda: []), [])

    # ---- everything together, and the Tactical Flava path
    # ---- review round: P1 interiors preflight, P1 AI drift, P1 AI source, P2 casing, serverMod

    def test_a_hard_linked_interiors_file_refuses_the_dry_run_and_the_real_rollback_before_any_change(self):
        self.assertEqual(self.run_cli(self.args('apply', '--interiors', 'legacy', '--markers', 'all-local'))[0], 0)
        os.link(self.profiles / 'HollowCountry' / 'interiors.json', self.world / 'elsewhere.json')
        before = self.tree(self.world)
        for argv in (['rollback', '--server-root', str(self.server), '--dry-run'], ['rollback', '--server-root', str(self.server)]):
            code, out, err = self.run_cli(argv)
            self.assertEqual(code, 2, argv)
            self.assertIn('interiors', err)
            self.assertEqual(before, self.tree(self.world))  # all markers still present, receipt kept
        (self.world / 'elsewhere.json').unlink()
        self.assertEqual(self.run_cli(['rollback', '--server-root', str(self.server)])[0], 0)

    def test_drift_in_a_completed_ai_addon_refuses_the_whole_rollback_before_any_change(self):
        self.assertEqual(self.run_cli(self.ai_args('apply', '--interiors', 'legacy', '--markers', 'all-local'))[0], 0)
        staged = self.ai_dest / 'addons' / 'hollowcountryexpansionai.pbo'
        original = staged.read_bytes()
        staged.write_bytes(original + b'drift')
        before = self.tree(self.world)
        for argv in (['rollback', '--server-root', str(self.server), '--dry-run'], ['rollback', '--server-root', str(self.server)]):
            code, out, err = self.run_cli(argv)
            self.assertEqual(code, 2, argv)
            self.assertIn('Expansion AI', err)
            self.assertIn('drift', err)
            self.assertEqual(before, self.tree(self.world))
        staged.write_bytes(original)
        self.assertEqual(self.run_cli(['rollback', '--server-root', str(self.server)])[0], 0)
        self.assertFalse(self.ai_dest.exists())

    def test_an_ai_source_inside_the_workshop_dir_is_refused_even_through_a_symlink(self):
        stolen = self.workshop / '@CF' / 'addons' / 'x.pbo'
        stolen.write_bytes(self.ai_blob)
        link = self.world / 'built' / 'link.pbo'
        link.symlink_to(stolen)
        for source in (stolen, self.workshop / '@CF' / 'addons', link, self.workshop / '@CF' / 'addons' / '..' / 'addons' / 'x.pbo'):
            before = self.tree(self.world)
            code, out, err = self.run_cli(self.args(
                'apply', '--expansion-ai', '--workshop-dir', str(self.workshop), '--expansion-ai-mod', str(source),
                '--expansion-ai-dest', str(self.ai_dest)))
            self.assertEqual(code, 2, source)
            self.assertIn('Workshop', err)
            self.assertEqual(before, self.tree(self.world))

    def test_every_write_destination_is_kept_out_of_the_workshop_dir(self):
        base = ['--expansion-ai', '--workshop-dir', str(self.workshop), '--expansion-ai-mod', str(self.ai_built),
                '--expansion-ai-dest', str(self.ai_dest)]
        inner = self.workshop / '@DayZ-Expansion-AI' / 'sub'
        (inner / 'profiles').mkdir(parents=True)
        (inner / 'mission').mkdir()
        link = self.world / 'link-to-workshop'
        link.symlink_to(self.workshop / '@DayZ-Expansion-AI')
        for flag, value in (('--mod-dest', inner / '@HollowCountry'), ('--mod-dest', link / 'sub' / '@HollowCountry'),
                            ('--profiles', inner / 'profiles'), ('--mission', inner / 'mission')):
            argv = self.args('apply', *base)
            argv[argv.index(flag) + 1] = str(value)
            before = self.tree(self.world)
            with self.subTest(flag=flag, value=str(value)):
                code, out, err = self.run_cli(argv)
                self.assertEqual(code, 2, out)
                self.assertIn('Workshop' if 'link-to' not in str(value) else 'symlink', err)
                self.assertEqual(self.tree(self.world), before)
                self.assertFalse(self.state.exists())
                plan_code, _, plan_err = self.run_cli(['plan', *argv[1:]])
                self.assertEqual(plan_code, 2)

    def test_an_operator_interiors_file_refuses_at_plan_time_and_apply_changes_nothing(self):
        (self.profiles / 'HollowCountry').mkdir()
        (self.profiles / 'HollowCountry' / 'interiors.json').write_text('{"operator":true}')
        before = self.tree(self.world)
        for command in ('plan', 'apply'):
            code, out, err = self.run_cli(self.args(command, '--interiors', 'legacy'))
            self.assertEqual(code, 2, command)
            self.assertIn('interiors', err)
            self.assertEqual(self.tree(self.world), before, command)

    def test_existing_optional_managed_paths_refuse_at_plan_time_and_apply_changes_nothing(self):
        for flag, folder in (('--snafu', 'hollow-country-snafu'), ('--tactical-flava', 'hollow-country-tactical-flava')):
            (self.mission / folder).mkdir()
            (self.mission / folder / 'operator.txt').write_text('mine')
            value = str(self.snafu if flag == '--snafu' else self.tf)
            before = self.tree(self.world)
            for command in ('plan', 'apply'):
                with self.subTest(flag=flag, command=command):
                    code, out, err = self.run_cli(self.args(command, flag, value))
                    self.assertEqual(code, 2, out)
                    self.assertIn(folder, err)
                    self.assertEqual(self.tree(self.world), before)
            shutil.rmtree(self.mission / folder)

    def test_for_every_refusal_class_plan_already_refuses_and_apply_leaves_the_tree_byte_identical(self):
        def operator_interiors():
            (self.profiles / 'HollowCountry').mkdir(exist_ok=True)
            (self.profiles / 'HollowCountry' / 'interiors.json').write_text('{"operator":true}')
            return ['--interiors', 'legacy']

        def optional_path():
            (self.mission / 'hollow-country-snafu').mkdir()
            (self.mission / 'hollow-country-snafu' / 'operator.txt').write_text('mine')
            return ['--snafu', str(self.snafu)]

        def workshop_dest():
            argv = list(self.ai_args('apply')[1:])
            inner = self.workshop / '@DayZ-Expansion-AI'
            argv[argv.index('--mod-dest') + 1] = str(inner / '@HollowCountry')
            return argv

        def running_diag():
            self.running = [4242]
            return []

        cases = (('operator interiors file', operator_interiors), ('optional managed path', optional_path),
                 ('mod-dest in the Workshop', workshop_dest), ('server running', running_diag))
        for label, setup in cases:
            with self.subTest(label):
                self.tearDown_world()
                extra = setup()
                argv_tail = extra
                before = self.tree(self.world)
                if label == 'mod-dest in the Workshop':
                    plan_argv, apply_argv = ['plan', *argv_tail], ['apply', *argv_tail]
                else:
                    plan_argv, apply_argv = self.args('plan', *argv_tail), self.args('apply', *argv_tail)
                if label == 'server running':
                    self.assertEqual(self.run_cli(plan_argv)[0], 0)  # a plan only warns; apply is what refuses
                else:
                    self.assertEqual(self.run_cli(plan_argv)[0], 2, label)
                self.assertEqual(self.run_cli(apply_argv)[0], 2, label)
                self.assertEqual(self.tree(self.world), before, label)
                self.running = []

    def tearDown_world(self):
        """Reset the synthetic mission, profiles and server to their starting content between sub-cases."""
        for directory in (self.mission, self.profiles):
            for child in list(directory.iterdir()):
                shutil.rmtree(child) if child.is_dir() else child.unlink()
        (self.mission / 'cfggameplay.json').write_text('{"version": 1}')
        (self.mission / 'cfgeconomycore.xml').write_text('<economycore/>')
        self.running = []

    def test_an_ai_destination_inside_the_workshop_dir_is_refused(self):
        code, out, err = self.run_cli(self.args(
            'plan', '--expansion-ai', '--workshop-dir', str(self.workshop), '--expansion-ai-mod', str(self.ai_built),
            '--expansion-ai-dest', str(self.workshop / '@HollowCountryExpansionAI')))
        self.assertEqual(code, 2)
        self.assertIn('Workshop', err)

    def test_the_ai_pbo_must_carry_the_ai_prefix_and_cfgpatches_name(self):
        pbo_path = self.ai_built / 'addons' / 'hollowcountryexpansionai.pbo'
        for label, blob in (('the HollowCountry PBO', self.pbo_blob),
                            ('another prefix', ai_pbo_blob(prefix='SomethingElse')),
                            ('another CfgPatches name', ai_pbo_blob(config=b'class CfgPatches { class Other {}; };')),
                            ('no config member', ai_pbo_blob(member='readme.txt')),
                            ('a bad checksum', self.ai_blob[:-1] + bytes([self.ai_blob[-1] ^ 1]))):
            pbo_path.write_bytes(blob)
            code, out, err = self.run_cli(self.ai_args('plan'))
            self.assertEqual(code, 2, label)
            self.assertIn('Expansion AI', err, label)
        pbo_path.write_bytes(ai_pbo_blob(member='config.bin', config=b'\0raP\0CfgPatches\0HollowCountryExpansionAI\0'))
        self.assertEqual(self.run_cli(self.ai_args('plan'))[0], 0)  # a rapified config carries the same names
        pbo_path.write_bytes(self.ai_blob)
        self.assertEqual(self.run_cli(self.ai_args('plan'))[0], 0)

    def test_expansion_folders_are_found_whatever_the_case_of_addons(self):
        (self.workshop / '@CF' / 'addons').rename(self.workshop / '@CF' / 'Addons')
        code, out, err = self.run_cli(self.ai_args('plan'))
        self.assertEqual((code, err), (0, ''))

    def test_the_ai_addon_loads_in_the_mod_list_after_hollow_country_on_server_and_client(self):
        code, out, err = self.run_cli(self.ai_args('plan'))
        self.assertEqual((code, err), (0, ''))
        server = [row for row in out.splitlines() if 'DayZServer_x64.exe' in row][0]
        client = [row for row in out.splitlines() if 'DayZ_BE.exe' in row][0]
        for line in (server, client):
            mods = line.index('-mod=')
            listed = line[mods:line.index("'", mods)]
            self.assertIn(str(self.ai_dest), listed)
            self.assertLess(listed.index(str(self.dest)), listed.index(str(self.ai_dest)))
        self.assertNotIn('serverMod', server)
        self.assertNotIn('serverMod', client)
        self.assertIn('-mod=', out.split('6. Expansion AI')[1].split('Server (PowerShell)')[0])


    def test_a_full_session_round_trips_and_orders_every_step(self):
        before = self.tree(self.world)
        code, out, err = self.run_cli(self.ai_args('apply', '--interiors', 'legacy', '--markers', 'all-local',
                                                   '--tactical-flava', str(self.tf), '--install-key'))
        self.assertEqual(code, 0, err)
        receipt = self.receipt()
        self.assertEqual([k for k in ('mod', 'server_keys', 'cfg', 'gameplay', 'economy', 'tactical_flava', 'interiors',
                                      'expansion_ai', 'expansion_ai_config', 'markers') if receipt['steps'].get(k) == 'done'],
                         ['mod', 'server_keys', 'cfg', 'gameplay', 'economy', 'tactical_flava', 'interiors',
                          'expansion_ai', 'expansion_ai_config', 'markers'])
        self.assertEqual(self.steps(), ['markers', 'expansion_ai_config', 'expansion_ai', 'interiors', 'tactical_flava', 'economy',
                                        'gameplay', 'cfg', 'server_keys', 'mod'])
        self.assertEqual(self.run_cli(['rollback', '--server-root', str(self.server)])[0], 0)
        self.assertEqual(before, self.tree(self.world))


class OptionalDeltas(SessionCase):
    """--snafu and --tactical-flava install the optional-subset CE deltas through snafu_optional and
    tactical_flava_optional (their own verify/generate/install/rollback), after economy and before interiors."""
    auto_vanilla = False

    def setUp(self):
        super().setUp()
        (self.server / 'addons').mkdir()  # the game's own Addons folder, the --vanilla-addons default

    def both(self, *extra):
        return ['--snafu', str(self.snafu), '--tactical-flava', str(self.tf), *extra]

    def real(self, *names):
        """Log entries of the named calls that ran on the real mission (not a scratch rehearsal or trial)."""
        return [name for name, *rest in self.log if name in names and str(self.mission) in rest]

    def test_both_flags_install_snafu_then_tactical_flava_after_economy_before_interiors(self):
        code, out, err = self.run_cli(self.args('apply', *self.both('--interiors', 'legacy')))
        self.assertEqual(code, 0, err)
        self.assertEqual(self.real('economy.install_delta', 'snafu.install', 'tf.install'),
                         ['economy.install_delta', 'snafu.install', 'tf.install'])
        calls = [row[0] for row in self.log if row[0] in ('economy.install_delta', 'snafu.install', 'tf.install',
                                                           'interiors.install')
                 and (row[0] == 'interiors.install' or str(self.mission) in row[1:])]
        self.assertEqual(calls, ['economy.install_delta', 'snafu.install', 'tf.install', 'interiors.install'])
        receipt = json.loads((self.state / lts.RECEIPT_NAME).read_text())
        for step in ('economy', 'snafu', 'tactical_flava', 'interiors'):
            self.assertEqual(receipt['steps'][step], 'done')
        self.assertEqual(receipt['snafu_delta']['install'], str(self.snafu))
        self.assertEqual(receipt['tactical_flava_delta']['install'], str(self.tf))
        self.assertEqual(receipt['tactical_flava_delta']['vanilla_addons'], str(self.server / 'addons'))
        self.assertEqual(receipt['snafu_delta']['verification'], 'verified')
        self.assertTrue((self.mission / 'hollow-country-snafu' / 'receipt.json').is_file())
        self.assertTrue((self.mission / 'hollow-country-tactical-flava' / 'receipt.json').is_file())
        self.assertTrue((self.state / 'deltas' / 'snafu').is_dir())
        self.assertTrue((self.state / 'deltas' / 'tactical_flava').is_dir())

    def test_the_default_roster_rides_with_both_optional_deltas_and_rolls_back(self):
        FakeEconomy.rosters = []
        code, out, err = self.run_cli(self.args('apply', *self.both()))
        self.assertEqual(code, 0, err)
        self.assertEqual(set(FakeEconomy.rosters), {'roster'})  # the launcher default, not --no-roster
        self.assertIn('firearms roster', out)
        self.assertEqual(self.real('economy.install_delta', 'snafu.install', 'tf.install'),
                         ['economy.install_delta', 'snafu.install', 'tf.install'])
        self.assertEqual(self.run_cli(['rollback', '--server-root', str(self.server)])[0], 0)

    def test_an_installer_rollback_that_raises_file_not_found_refuses_the_session_rollback_with_nothing_changed(self):
        self.assertEqual(self.run_cli(self.args('apply', '--snafu', str(self.snafu)))[0], 0)
        self.optional['snafu']['rollback_missing'] = True
        for stamp in (False, True):  # a finished step, then one an interrupted run left 'started'
            if stamp:
                path = self.state / lts.RECEIPT_NAME
                data = json.loads(path.read_text())
                data['steps']['snafu'] = 'started'
                path.write_text(json.dumps(data))
            self.assert_file_not_found_refuses()

    def assert_file_not_found_refuses(self):
        before = self.tree(self.world)
        for extra in ([], ['--dry-run']):
            code, out, err = self.run_cli(['rollback', '--server-root', str(self.server), *extra])
            self.assertEqual(code, 2, (extra, out))
            self.assertIn('synthetic missing managed file', err)
            self.assertEqual(self.tree(self.world), before)
        self.assertTrue((self.state / lts.RECEIPT_NAME).is_file())

    def test_verification_precedes_every_write_and_tf_gets_the_vanilla_addons(self):
        self.assertEqual(self.run_cli(self.args('apply', *self.both()))[0], 0)
        names = [row[0] for row in self.log]
        self.assertLess(names.index('snafu.verify_install'), names.index('snafu.install'))
        self.assertLess(names.index('tf.verify_install'), names.index('economy.install_delta'))
        self.assertIn(('tf.load_vanilla', str(self.server / 'addons')), self.log)
        self.assertNotIn('snafu.load_vanilla', names)

    def test_vanilla_addons_flag_overrides_the_default(self):
        other = self.world / 'other-game-addons'
        other.mkdir()
        self.assertEqual(self.run_cli(self.args('apply', *self.both('--vanilla-addons', str(other))))[0], 0)
        self.assertIn(('tf.load_vanilla', str(other)), self.log)
        receipt = json.loads((self.state / lts.RECEIPT_NAME).read_text())
        self.assertEqual(receipt['tactical_flava_delta']['vanilla_addons'], str(other))

    def test_plan_rehearses_on_a_scratch_copy_and_writes_nothing(self):
        before = self.tree(self.world, self.repo)
        code, out, err = self.run_cli(self.args('plan', *self.both()))
        self.assertEqual((code, err), (0, ''))
        self.assertEqual(before, self.tree(self.world, self.repo))
        self.assertEqual(self.real('snafu.install', 'tf.install', 'economy.install_delta'), [])
        scratch = [row for row in self.log if row[0] in ('snafu.install', 'tf.install')]
        self.assertEqual([row[0] for row in scratch], ['snafu.install', 'tf.install'])
        self.assertTrue(all('hc-delta-rehearsal' in row[1] for row in scratch))
        self.assertIn('SNAFU subset CE delta', out)
        self.assertIn('Tactical Flava subset CE delta', out)
        self.assertIn('snafu_optional', out)
        self.assertIn('read-only', out)

    def test_without_the_flags_nothing_optional_is_verified_or_installed(self):
        self.assertEqual(self.run_cli(self.args('apply'))[0], 0)
        self.assertFalse([row for row in self.log if row[0].startswith(('snafu.', 'tf.'))])

    def test_snafu_alone_installs_only_the_snafu_delta(self):
        self.assertEqual(self.run_cli(self.args('apply', '--snafu', str(self.snafu)))[0], 0)
        self.assertEqual(self.real('snafu.install', 'tf.install'), ['snafu.install'])
        self.assertTrue((self.mission / 'hollow-country-snafu').is_dir())
        self.assertFalse((self.mission / 'hollow-country-tactical-flava').exists())
        receipt = json.loads((self.state / lts.RECEIPT_NAME).read_text())
        self.assertIsNone(receipt['tactical_flava_delta'])
        self.assertNotIn('tactical_flava', receipt['steps'])

    def test_tactical_flava_alone_installs_only_its_delta(self):
        self.assertEqual(self.run_cli(self.args('apply', '--tactical-flava', str(self.tf)))[0], 0)
        self.assertEqual(self.real('snafu.install', 'tf.install'), ['tf.install'])
        self.assertIsNone(json.loads((self.state / lts.RECEIPT_NAME).read_text())['snafu_delta'])

    def test_rollback_runs_in_reverse_and_the_whole_tree_is_byte_identical(self):
        before = self.tree(self.server, self.mission, self.profiles, self.snafu, self.tf, self.world / 'session')
        args = self.both('--interiors', 'legacy', '--markers', 'all-local')
        self.assertEqual(self.run_cli(self.args('apply', *args))[0], 0)
        self.assertIn('<!--tf-->', (self.mission / 'cfgeconomycore.xml').read_text())
        del self.log[:]
        code, out, err = self.run_cli(['rollback', '--server-root', str(self.server)])
        self.assertEqual((code, err), (0, ''))
        self.assertEqual(self.real('tf.rollback', 'snafu.rollback', 'economy.rollback', 'gameplay.rollback'),
                         ['tf.rollback', 'snafu.rollback', 'economy.rollback', 'gameplay.rollback'])
        order = [row[0] for row in self.log if row[0] in ('interiors.rollback', 'tf.rollback', 'snafu.rollback',
                                                           'economy.rollback') and 'hc-rollback-trial' not in ''.join(row[1:])]
        self.assertEqual(order, ['interiors.rollback', 'tf.rollback', 'snafu.rollback', 'economy.rollback'])
        self.assertEqual(before, self.tree(self.server, self.mission, self.profiles, self.snafu, self.tf,
                                           self.world / 'session'))
        self.assertEqual((self.mission / 'cfgeconomycore.xml').read_text(), '<economycore/>')

    def test_rollback_dry_run_changes_nothing_and_lists_the_optional_steps(self):
        self.assertEqual(self.run_cli(self.args('apply', *self.both()))[0], 0)
        before = self.tree(self.server, self.mission, self.profiles)
        code, out, err = self.run_cli(['rollback', '--server-root', str(self.server), '--dry-run'])
        self.assertEqual((code, err), (0, ''))
        self.assertEqual(before, self.tree(self.server, self.mission, self.profiles))
        self.assertLess(out.index('tactical_flava'), out.index('snafu'))
        self.assertLess(out.index('snafu'), out.index('economy'))

    def test_a_drifted_snafu_delta_refuses_the_whole_rollback_before_any_change(self):
        self.assertEqual(self.run_cli(self.args('apply', *self.both('--markers', 'none')))[0], 0)
        core = (self.mission / 'cfgeconomycore.xml').read_text()
        (self.mission / 'cfgeconomycore.xml').write_text(core + 'hand edit')  # tf is no longer the last writer
        before = self.tree(self.server, self.mission, self.profiles)
        code, out, err = self.run_cli(['rollback', '--server-root', str(self.server)])
        self.assertEqual(code, 2)
        self.assertIn('tactical_flava', err)
        self.assertIn('would be refused', err)
        self.assertEqual(before, self.tree(self.server, self.mission, self.profiles))

    def test_a_failed_tf_install_leaves_a_receipt_and_rollback_restores_everything(self):
        before = self.tree(self.server, self.mission, self.profiles, self.world / 'session')
        self.optional['tf']['fail_install'] = True
        code, out, err = self.run_cli(self.args('apply', *self.both()))
        self.assertEqual(code, 2)
        self.assertIn('synthetic installer failure', err)
        receipt = json.loads((self.state / lts.RECEIPT_NAME).read_text())
        self.assertEqual((receipt['steps']['snafu'], receipt['steps']['tactical_flava']), ('done', 'started'))
        self.assertEqual(self.run_cli(['rollback', '--server-root', str(self.server)])[0], 0)
        self.assertEqual(before, self.tree(self.server, self.mission, self.profiles, self.world / 'session'))

    def test_an_unverified_snafu_install_is_refused_before_anything_is_written(self):
        self.optional['snafu']['status'] = 'unverified'
        before = self.tree(self.world)
        code, out, err = self.run_cli(self.args('apply', *self.both()))
        self.assertEqual(code, 2)
        self.assertIn('SNAFU', err)
        self.assertIn('publishedid-mismatch', err)
        self.assertEqual(before, self.tree(self.world))
        self.assertFalse(self.state.exists())

    def test_an_unverified_tactical_flava_install_is_refused_before_anything_is_written(self):
        self.optional['tf']['status'] = 'unverified'
        before = self.tree(self.world)
        code, out, err = self.run_cli(self.args('apply', '--tactical-flava', str(self.tf)))
        self.assertEqual(code, 2)
        self.assertIn('Tactical Flava', err)
        self.assertIn('publishedid-mismatch', err)
        self.assertEqual(before, self.tree(self.world))

    def test_the_plan_refuses_an_unverified_install_too(self):
        self.optional['tf']['status'] = 'unverified'
        code, out, err = self.run_cli(self.args('plan', '--tactical-flava', str(self.tf)))
        self.assertEqual(code, 2)
        self.assertEqual(out, '')

    def test_a_delta_that_cannot_be_generated_is_refused_at_plan_time(self):
        self.optional['tf']['fail_generate'] = True
        before = self.tree(self.world)
        code, out, err = self.run_cli(self.args('apply', *self.both()))
        self.assertEqual(code, 2)
        self.assertIn('Tactical Flava delta cannot be generated', err)
        self.assertEqual(before, self.tree(self.world))

    def test_the_deltas_need_the_economy_install(self):
        for flag, path in (('--snafu', self.snafu), ('--tactical-flava', self.tf)):
            code, out, err = self.run_cli(self.args('plan', flag, str(path), '--economy-profile', 'none'))
            self.assertEqual(code, 2)
            self.assertIn('economy', err)

    def test_tactical_flava_needs_a_vanilla_addons_folder(self):
        shutil.rmtree(self.server / 'addons')
        code, out, err = self.run_cli(self.args('plan', '--tactical-flava', str(self.tf)))
        self.assertEqual(code, 2)
        self.assertIn('--vanilla-addons', err)
        # SNAFU does not read the game files
        self.assertEqual(self.run_cli(self.args('plan', '--snafu', str(self.snafu)))[0], 0)

    def test_vanilla_addons_only_applies_with_tactical_flava(self):
        code, out, err = self.run_cli(self.args('plan', '--vanilla-addons', str(self.server / 'addons')))
        self.assertEqual(code, 2)
        self.assertIn('--tactical-flava', err)

    def test_optional_installs_stay_read_only_and_never_copy_their_content(self):
        before = self.tree(self.snafu, self.tf)
        self.assertEqual(self.run_cli(self.args('apply', *self.both('--install-key')))[0], 0)
        self.assertEqual(before, self.tree(self.snafu, self.tf))
        owned = {str(p) for p in self.state.rglob('*')} | {str(p) for p in self.mission.rglob('*')}
        self.assertFalse([p for p in owned if p.endswith(('.pbo', '.bikey')) and '/deltas/' in p])


class PlannedDestinations(SessionCase):
    """Review P1s: planned write destinations may not collide; a server seen while planning refuses apply;
    a DayZDiag process with no readable command line counts as a possible server."""

    def test_a_mod_destination_on_an_optional_installer_directory_is_refused_before_any_write(self):
        for label, dest, extra in (('snafu', self.mission / 'hollow-country-snafu', ['--snafu', str(self.snafu)]),
                                   ('economy', self.mission / 'hollow-country', []),
                                   ('state', self.server / lts.STATE_NAME, [])):
            with self.subTest(label):
                argv = self.args('plan', *extra)
                argv[argv.index('--mod-dest') + 1] = str(dest)
                before = self.tree(self.world)
                code, out, err = self.run_cli(argv)
                self.assertEqual(code, 2, (out, err))
                self.assertIn('destination', err)
                argv[0] = 'apply'
                code, out, err = self.run_cli(argv)
                self.assertEqual(code, 2, (out, err))
                self.assertEqual(self.tree(self.world), before)  # nothing was written, cfg and mission untouched
                self.assertFalse([row for row in self.log if 'install' in row[0]], self.log)

    def test_a_server_seen_during_planning_refuses_apply_before_any_write(self):
        before = self.tree(self.world)
        with mock.patch.object(lts, 'running_servers', side_effect=[[], [4242]]):
            code, out, err = self.run_cli(self.args('apply'))
        self.assertEqual(code, 2, (out, err))
        self.assertIn('4242', err)
        self.assertEqual(self.tree(self.world), before)
        self.assertFalse(self.state.exists())

    def test_a_dayzdiag_with_a_blank_command_line_counts_as_a_possible_server(self):
        def run(argv, **kwargs):
            out = ''
            if argv[0].endswith('powershell.exe'):
                out = '4242\t\n'
            elif 'dayzdiag' in ' '.join(argv).lower():
                out = '"DayZDiag_x64.exe","4242","Console","1","1 K"\n'
            return subprocess.CompletedProcess(argv, 0, out, '')
        which = {'tasklist.exe': '/x/tasklist.exe', 'powershell.exe': '/x/powershell.exe'}
        with mock.patch.object(lts.shutil, 'which', lambda name: which.get(name)), \
                mock.patch.object(lts.subprocess, 'run', run):
            self.assertEqual(lts.windows_task_list(), [4242])


@unittest.skipUnless(all((ROOT / p).is_file() for p in (
    'tools/package/gameplay.py', 'tools/audit/acceptance_markers.py', lts.GAMEPLAY_PROFILE, lts.GAMEPLAY_PRESET,
    lts.ECONOMY_PROFILES + 'baseline.json')), 'sibling gameplay/acceptance tools or committed profiles absent')
class RealInstallers(unittest.TestCase):
    """The actual gameplay.py, economy.py and acceptance_markers.py on a synthetic mission copy."""

    def setUp(self):
        # The host may run an unrelated DayZ server (a probe); the running-server refusal has its own tests.
        patcher = mock.patch.object(lts, 'running_servers', lambda: [])
        patcher.start()
        self.addCleanup(patcher.stop)

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
                    '--economy-profile', 'baseline', '--no-roster']
            (base / 'out').mkdir()
            out = io.StringIO()
            self.assertEqual(lts.main(['apply'] + argv, out=out), 0, out.getvalue())
            self.assertTrue((mission / 'hollow-country-gameplay' / 'receipt.json').is_file())
            self.assertTrue((mission / 'hollow-country' / 'receipt.json').is_file())
            self.assertTrue(list((profiles / 'HollowCountry' / 'acceptance').glob('*.enable')))
            self.assertEqual(lts.main(['rollback', '--server-root', str(server)], out=io.StringIO()), 0)
            after = {p: p.read_bytes() for p in list(mission.rglob('*')) + list(server.rglob('*')) if p.is_file()}
            self.assertEqual(before, after)

    def test_the_real_interiors_pack_and_all_local_markers_install_and_roll_back_byte_identically(self):
        from tests.unit import test_economy_contract, test_gameplay_delta
        with tempfile.TemporaryDirectory(prefix='hc-synthetic-real-') as t:
            base = Path(t)
            mission, server, profiles = base / 'mission', base / 'server', base / 'profiles'
            mission.mkdir()
            test_economy_contract.synthetic(mission)
            vanilla_usage_vocabulary(mission)
            test_gameplay_delta.synthetic_source(base / 'gp')
            shutil.copy(base / 'gp' / 'cfggameplay.json', mission / 'cfggameplay.json')
            for directory in (server, profiles, base / 'out'):
                directory.mkdir()
            (server / 'serverDZ.cfg').write_bytes(CFG.encode())
            built = base / 'built' / '@HollowCountry'
            (built / 'addons').mkdir(parents=True)
            (built / 'addons' / 'hollowcountry.pbo').write_bytes(pbo.pack({'config.cpp': b'synthetic'}))
            argv = ['--server-root', str(server), '--mission', str(mission), '--profiles', str(profiles),
                    '--mod', str(built), '--mod-dest', str(base / 'out' / '@HollowCountry'),
                    '--economy-profile', 'baseline', '--no-roster', '--interiors', 'legacy', '--markers', 'all-local']

            def everything():
                return {p: p.read_bytes() for root in (mission, server, profiles, base / 'out')
                        for p in root.rglob('*') if p.is_file()}
            before = everything()
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(lts.main(['apply'] + argv, out=out), 0, err.getvalue())
                self.assertTrue((profiles / 'HollowCountry' / 'hc-interiors-pack' / 'receipt.json').is_file())
                self.assertTrue((profiles / 'HollowCountry' / 'interiors.json').is_file())
                self.assertTrue(list((profiles / 'HollowCountry' / 'acceptance').glob('*.enable')))
                self.assertEqual(lts.main(['rollback', '--server-root', str(server)], out=io.StringIO()), 0, err.getvalue())
            self.assertEqual(before, everything())
            self.assertFalse((profiles / 'HollowCountry').exists())

    def test_the_real_interiors_installer_agrees_with_the_dry_run_when_a_profile_file_is_hard_linked(self):
        from tests.unit import test_economy_contract, test_gameplay_delta
        with tempfile.TemporaryDirectory(prefix='hc-synthetic-real-') as t:
            base = Path(t)
            mission, server, profiles = base / 'mission', base / 'server', base / 'profiles'
            mission.mkdir()
            test_economy_contract.synthetic(mission)
            vanilla_usage_vocabulary(mission)
            test_gameplay_delta.synthetic_source(base / 'gp')
            shutil.copy(base / 'gp' / 'cfggameplay.json', mission / 'cfggameplay.json')
            for directory in (server, profiles, base / 'out'):
                directory.mkdir()
            (server / 'serverDZ.cfg').write_bytes(CFG.encode())
            built = base / 'built' / '@HollowCountry'
            (built / 'addons').mkdir(parents=True)
            (built / 'addons' / 'hollowcountry.pbo').write_bytes(pbo.pack({'config.cpp': b'synthetic'}))
            argv = ['--server-root', str(server), '--mission', str(mission), '--profiles', str(profiles),
                    '--mod', str(built), '--mod-dest', str(base / 'out' / '@HollowCountry'),
                    '--economy-profile', 'baseline', '--no-roster', '--interiors', 'legacy', '--markers', 'all-local']
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(lts.main(['apply'] + argv, out=io.StringIO()), 0, err.getvalue())
                os.link(profiles / 'HollowCountry' / 'interiors.json', base / 'elsewhere.json')

                def everything():
                    return {p: p.read_bytes() for root in (mission, server, profiles, base / 'out')
                            for p in root.rglob('*') if p.is_file()}
                before = everything()
                for command in (['rollback', '--server-root', str(server), '--dry-run'], ['rollback', '--server-root', str(server)]):
                    self.assertEqual(lts.main(command, out=io.StringIO()), 2, command)
                    self.assertEqual(before, everything())  # every marker is still there
                (base / 'elsewhere.json').unlink()
                self.assertEqual(lts.main(['rollback', '--server-root', str(server)], out=io.StringIO()), 0, err.getvalue())

    def test_the_real_snafu_and_tactical_flava_deltas_install_and_roll_back_byte_identically(self):
        """SYNTHETIC mod installs and allowlists (the fixtures of the two optional tools' own tests); the real
        snafu_optional and tactical_flava_optional verify, generate, install and roll back."""
        from tests.unit import test_firearms_roster, test_snafu_optional as snafu_fixture
        from tests.unit import test_tactical_flava_optional as tf_fixture
        from tools.package import snafu_optional, tactical_flava_optional
        with tempfile.TemporaryDirectory(prefix='hc-synthetic-real-') as t:
            base = Path(t)
            patchers = [mock.patch.object(tactical_flava_optional, 'ALLOWLIST_PATH', base / 'tf-allowlist.json'),
                        mock.patch.object(snafu_optional, 'ALLOWLIST_PATH', base / 'snafu-allowlist.json'),
                        mock.patch.object(tactical_flava_optional, 'load_vanilla', lambda addons: tf_fixture.VANILLA)]
            for patcher in patchers:
                patcher.start()
                self.addCleanup(patcher.stop)
            test_firearms_roster.patch_roster(self, t)
            (base / 'tf-allowlist.json').write_text(json.dumps(tf_fixture.allowlist(*tf_fixture.good())))
            (base / 'snafu-allowlist.json').write_text(json.dumps(snafu_fixture.allowlist(*snafu_fixture.GOOD)))
            tf_install, snafu_install = base / 'workshop' / '@TF', base / 'workshop' / '@SNAFU'
            tf_fixture.build_install(tf_install)
            snafu_fixture.build_install(snafu_install)
            mission, server, profiles = base / 'mission', base / 'server', base / 'profiles'
            for directory in (mission, server, profiles, server / 'addons', base / 'out'):
                directory.mkdir()
            tf_fixture.mission(mission)
            vanilla_usage_vocabulary(mission, merge=True)
            (mission / 'cfggameplay.json').write_text('{"version": 1}')
            (server / 'serverDZ.cfg').write_bytes(CFG.encode())
            built = base / 'built' / '@HollowCountry'
            (built / 'addons').mkdir(parents=True)
            (built / 'addons' / 'hollowcountry.pbo').write_bytes(pbo.pack({'config.cpp': b'synthetic'}))
            argv = ['--server-root', str(server), '--mission', str(mission), '--profiles', str(profiles),
                    '--mod', str(built), '--mod-dest', str(base / 'out' / '@HollowCountry'),
                    '--economy-profile', 'baseline', '--no-roster', '--no-gameplay', '--snafu', str(snafu_install),
                    '--tactical-flava', str(tf_install), '--interiors', 'legacy', '--markers', 'all-local']

            def everything():
                return {p: p.read_bytes() for root in (mission, server, profiles, base / 'out', base / 'workshop')
                        for p in root.rglob('*') if p.is_file()}
            before = everything()
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(lts.main(['plan'] + argv, out=out), 0, err.getvalue())
                self.assertEqual(before, everything())
                self.assertEqual(lts.main(['apply'] + argv, out=out), 0, err.getvalue())
                core = (mission / 'cfgeconomycore.xml').read_bytes()
                for folder in (b'hollow-country/ce', b'hollow-country-snafu/ce', b'hollow-country-tactical-flava/ce'):
                    self.assertIn(folder, core)
                for managed in ('hollow-country', 'hollow-country-snafu', 'hollow-country-tactical-flava'):
                    self.assertTrue((mission / managed / 'receipt.json').is_file(), managed)
                self.assertEqual(lts.main(['rollback', '--server-root', str(server), '--dry-run'], out=io.StringIO()), 0)
                self.assertEqual(lts.main(['rollback', '--server-root', str(server)], out=io.StringIO()), 0, err.getvalue())
            self.assertEqual(before, everything())
            self.assertFalse((profiles / 'HollowCountry').exists())
            for managed in ('hollow-country', 'hollow-country-snafu', 'hollow-country-tactical-flava'):
                self.assertFalse((mission / managed).exists(), managed)

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
                    '--economy-profile', 'baseline', '--no-roster']
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



def synthetic_template_pack(base):
    """SYNTHETIC geometry, run IDs, stock and search groups; no native observations."""
    from tests.unit import test_interior_templates as fixtures
    from tools.package import interior_templates, interiors_profile, search_context
    stock = base / 'template-stock'
    (stock / 'db').mkdir(parents=True)
    (stock / 'mapgroupproto.xml').write_bytes(fixtures.PROTO)
    (stock / 'mapgrouppos.xml').write_bytes(fixtures.POS)
    (stock / 'db/types.xml').write_bytes(fixtures.TYPES)
    for relative in ('cfgspawnabletypes.xml', 'cfglimitsdefinition.xml'):
        (stock / relative).write_bytes(b'<synthetic/>')
    census = base / 'synthetic-census.json'
    census.write_bytes(fixtures.encode(fixtures.census(
        fixtures.house_rows() + fixtures.calibration_rows(), fixtures.CLASSES)))
    build, pack, search = base / 'template-build', base / 'template-pack', base / 'search-build'
    with contextlib.redirect_stdout(io.StringIO()):
        assert interior_templates.main(['build', '--census', str(census),
            '--proto', str(stock / 'mapgroupproto.xml'), '--pos', str(stock / 'mapgrouppos.xml'),
            '--out', str(build)]) == 0
        assert search_context.main(['--mapgroupproto', str(stock / 'mapgroupproto.xml'),
            '--types', str(stock / 'db/types.xml'), '--output-dir', str(search)]) == 0
    interiors_profile.templates_assemble(build, pack, search, stock)
    return pack


class TemplateAndCoverage(SessionCase):
    """Real package entry points on explicit synthetic inputs; remaining session tools are fakes."""

    def load_tool(self, name):
        if name == 'interiors_profile':
            from tools.package import interiors_profile
            return interiors_profile
        if name == 'ce_coverage':
            from tools.package import ce_coverage
            return ce_coverage
        return super().load_tool(name)

    def template_args(self, command):
        return self.args(command, '--interiors', '--interiors-pack', str(self.pack))

    def coverage_result(self):
        from tests.unit import test_ce_coverage as fixtures
        stock = fixtures.stock_proto(eol='\r\n')
        (self.mission / 'mapgroupproto.xml').write_bytes(stock)
        result = self.base / 'synthetic-coverage-result.json'
        result.write_bytes(fixtures.blob(fixtures.result_doc(stock)))
        return result

    def test_default_interiors_plan_uses_templates_and_apply_rolls_back_profile_byte_exactly(self):
        self.pack = synthetic_template_pack(self.base)
        target = self.profiles / 'HollowCountry'
        target.mkdir()
        (target / 'settings.json').write_bytes(b'{ "operator": true }\r\n')
        # An identical existing chunk belongs to the operator and must survive rollback.
        (target / 'templates').mkdir()
        chunk = next((self.pack / 'templates').glob('search-groups-*.json'))
        (target / 'templates' / chunk.name).write_bytes(chunk.read_bytes())
        before = self.tree(self.world)
        code, out, err = self.run_cli(self.template_args('plan'))
        self.assertEqual(code, 0, err)
        self.assertIn('Interior template pack', out)
        self.assertIn(str(target / 'templates'), out)
        self.assertEqual(before, self.tree(self.world))
        code, out, err = self.run_cli(self.template_args('apply'))
        self.assertEqual(code, 0, err)
        self.assertTrue((target / 'templates/index.json').is_file())
        self.assertTrue((target / 'templates/hc-interiors-pack/receipt.json').is_file())
        self.assertFalse((target / 'interiors.json').exists())
        receipt = json.loads((self.state / lts.RECEIPT_NAME).read_text())
        self.assertEqual(receipt['interiors']['mode'], 'templates')
        self.assertEqual(receipt['steps']['interiors'], 'done')
        code, out, err = self.run_cli(['rollback', '--server-root', str(self.server)])
        self.assertEqual(code, 0, err)
        self.assertEqual(before, self.tree(self.world))

    def test_template_plan_refuses_each_legacy_room_owner_without_writing(self):
        self.pack = synthetic_template_pack(self.base)
        for relative in ('interiors.json', 'Infected/production-rooms.json'):
            with self.subTest(owner=relative):
                owner = self.profiles / 'HollowCountry' / relative
                owner.parent.mkdir(parents=True, exist_ok=True)
                owner.write_bytes(b'{}')
                before = self.tree(self.world)
                for command in ('plan', 'apply'):
                    code, out, err = self.run_cli(self.template_args(command))
                    self.assertEqual(code, 2, out)
                    self.assertIn('rooms_conflict', err)
                    self.assertIn(relative, err)
                    self.assertEqual(before, self.tree(self.world))
                owner.unlink()

    def test_ce_coverage_pending_refuses_plan_and_apply_without_writing(self):
        missing = self.base / 'absent-synthetic-result.json'
        before = self.tree(self.world)
        for command in ('plan', 'apply'):
            code, out, err = self.run_cli(self.args(command, '--ce-coverage',
                '--ce-coverage-result', str(missing)))
            self.assertEqual(code, 2, out)
            self.assertIn('PENDING', err)
            self.assertEqual(before, self.tree(self.world))

    def test_validated_coverage_installs_after_economy_and_rolls_back_byte_exactly(self):
        result = self.coverage_result()
        before = self.tree(self.world)
        argv = ['--ce-coverage', '--ce-coverage-result', str(result)]
        code, out, err = self.run_cli(self.args('plan', *argv))
        self.assertEqual(code, 0, err)
        self.assertIn('CE building coverage', out)
        self.assertEqual(before, self.tree(self.world))
        code, out, err = self.run_cli(self.args('apply', *argv))
        self.assertEqual(code, 0, err)
        self.assertIn(b'<point', (self.mission / 'mapgroupproto.xml').read_bytes())
        self.assertTrue((self.mission / 'hollow-country-ce-coverage/receipt.json').is_file())
        receipt = json.loads((self.state / lts.RECEIPT_NAME).read_text())
        self.assertEqual(receipt['steps']['ce_coverage'], 'done')
        _, _, todo = lts.plan_rollback(self.server, self.repo)
        names = [name for name, _, _ in todo]
        self.assertLess(names.index('ce_coverage'), names.index('economy'))
        code, out, err = self.run_cli(['rollback', '--server-root', str(self.server)])
        self.assertEqual(code, 0, err)
        self.assertEqual(before, self.tree(self.world))

    def test_drifted_coverage_refuses_all_rollback_writes(self):
        result = self.coverage_result()
        code, out, err = self.run_cli(self.args('apply', '--ce-coverage', '--ce-coverage-result', str(result)))
        self.assertEqual(code, 0, err)
        proto = self.mission / 'mapgroupproto.xml'
        proto.write_bytes(proto.read_bytes() + b'<!-- operator drift -->')
        before = self.tree(self.world)
        for dry in (['--dry-run'], []):
            code, out, err = self.run_cli(['rollback', '--server-root', str(self.server)] + dry)
            self.assertEqual(code, 2, out)
            self.assertIn('ce_coverage', err)
            self.assertEqual(before, self.tree(self.world))


    def test_templates_and_coverage_use_real_economy_receipts_and_restore_every_byte(self):
        from tests.unit import test_economy_contract, test_ce_coverage as fixtures
        from tools.package import economy
        self.pack = synthetic_template_pack(self.base)
        test_economy_contract.synthetic(self.mission)
        vanilla_usage_vocabulary(self.mission)
        result = self.coverage_result()
        real_economy = economy.generate
        # Exercise the authored baseline profile against the explicit synthetic mission.
        profile = json.loads((ROOT / lts.ECONOMY_PROFILES / 'baseline.json').read_bytes())
        def real_tools(name):
            if name == 'economy':
                return economy
            return self.load_tool(name)

        # Template/coverage/economy operations are real; gameplay and marker tools remain recording fakes.
        with mock.patch.object(lts, 'economy_delta', lambda tool, mission, repo, spec: real_economy(mission, profile)), \
                mock.patch.object(lts, 'load_tool', real_tools):
            before = self.tree(self.world)
            argv = self.template_args('apply') + ['--ce-coverage', '--ce-coverage-result', str(result)]
            code, out, err = self.run_cli(argv)
            self.assertEqual(code, 0, err)
            self.assertEqual((self.mission / 'hollow-country-ce-coverage/mapgroupproto.backup').read_bytes(),
                             fixtures.stock_proto(eol='\r\n'))
            for dry in (['--dry-run'], []):
                code, out, err = self.run_cli(['rollback', '--server-root', str(self.server)] + dry)
                self.assertEqual(code, 0, err)
            self.assertEqual(before, self.tree(self.world))

    def test_templates_require_an_external_assembled_pack(self):
        before = self.tree(self.world)
        code, out, err = self.run_cli(self.args('plan', '--interiors'))
        self.assertEqual(code, 2, out)
        self.assertIn('--interiors-pack', err)
        self.assertEqual(before, self.tree(self.world))

    def test_default_coverage_result_is_pending_and_flags_require_their_steps(self):
        from tools.package import ce_coverage
        before = self.tree(self.world)
        with mock.patch.object(ce_coverage, 'REPO_ROOT', self.repo):
            code, out, err = self.run_cli(self.args('plan', '--ce-coverage'))
        self.assertEqual(code, 2, out)
        self.assertIn('PENDING', err)
        for extra in (['--interiors-pack', str(self.base / 'pack')],
                      ['--ce-coverage-result', str(self.base / 'result')]):
            code, out, err = self.run_cli(self.args('plan', *extra))
            self.assertEqual(code, 2, out)
            self.assertIn('requires', err)
        self.assertEqual(before, self.tree(self.world))


    def test_coverage_result_symlink_refuses_before_any_write(self):
        result = self.coverage_result()
        link = self.base / 'linked-result.json'
        link.symlink_to(result)
        before = self.tree(self.world)
        code, out, err = self.run_cli(self.args('plan', '--ce-coverage', '--ce-coverage-result', str(link)))
        self.assertEqual(code, 2, out)
        self.assertIn('symlink', err)
        self.assertEqual(before, self.tree(self.world))


if __name__ == '__main__':
    unittest.main()
