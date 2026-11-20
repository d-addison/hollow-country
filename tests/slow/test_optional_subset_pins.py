"""HC-61 / #183: subset pins instead of whole-PBO pins; synthetic Workshop-shaped fixtures only.

A Workshop update that leaves the used subset's classes unchanged must still verify, a change in a pinned
class must report drift naming the class, and verify must not hash whole PBO files once the subset is pinned.
Nothing here reads a real Workshop item or establishes DayZ behaviour; runtime acceptance stays pending.

RED (before implementation), command:
  PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.slow.test_optional_subset_pins -v
GREEN command and result are recorded in the commit message.
"""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools.package import hash_cache, snafu_optional as sf, tactical_flava_optional as tf
from tests.slow import test_snafu_optional as sf_fixture
from tests.slow import test_tactical_flava_optional as tf_fixture
from tests.unit.test_pbo_config import klass, pbo, rap


def pinned(allow, report):
    """Pin the used subset the way an operator would after a first verify (synthetic policy)."""
    policy = {'schema': 1, 'members': [], 'family_budgets': [],
              'dependency_pins': [], 'class_pins': dict(report['subset_pins']),
              'aggregate_weapon_budget': {'nominal': 62, 'min': 31},
              'refusals': ['HC61_SUBSET_RUNTIME_PENDING']}
    for entry in allow['entries']:
        weight = 20 if entry['kind'] == 'ammo' else 1
        policy['members'].append({
            'class': entry['class'], 'family': entry['class'], 'unit_rounds': weight,
            'parts': [{'class': name, 'route': 'native-carrier'} for name in entry.get('optic_requires', [])]})
        policy['family_budgets'].append({
            'family': entry['class'], 'kind': entry['kind'] if entry['kind'] in sf.KINDS else 'magazine',
            **{field: entry['set'][field] * weight for field in ('nominal', 'min')}})
    out = copy.deepcopy(allow)
    out['hc61'] = policy
    return out


def sf_configs(extra=None, wood_ammo='SynAmmoA'):
    tree = sf_fixture.configs()
    weapons = {k: v for k, v in tree['CfgWeapons'].items() if k != '__parent__'}
    weapons['SynWood'] = klass('Rifle_Base', scope=2, model=sf_fixture.MODEL.format('wood'),
                               chamberableFrom=[wood_ammo])
    weapons.update(extra or {})
    tree['CfgWeapons'] = klass('', **weapons)
    return tree


def sf_rewrite(root, tree):
    members = {'Data/wood.p3d': b'x', 'Data/pistol.p3d': b'x', 'config.bin': rap(tree)}
    (root / 'Addons/Synth_Guns.pbo').write_bytes(pbo(members, prefix='Synth\\Guns'))


try:
    from tests.unit import hash_cache_isolation
except ImportError:  # run as a script from tests/unit
    import hash_cache_isolation


def setUpModule():
    # #194: the whole-PBO hashing path reads/writes the hash cache; never the user's.
    hash_cache_isolation.enter()


def tearDownModule():
    hash_cache_isolation.leave()


class SubsetPins(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def test_snafu_unrelated_update_passes_and_changed_class_names_the_drift(self):
        install = self.root / 'sf'
        sf_fixture.build_install(install)
        allow = sf_fixture.allowlist(*sf_fixture.GOOD)
        first = sf.verify_install(install, allow)
        self.assertEqual(first['status'], 'verified')
        self.assertEqual(set(first['subset_pins']), {e['class'] for e in allow['entries']})
        allow = pinned(allow, first)
        sf.validate_allowlist(allow)
        # Workshop update: a new unrelated class and different bytes, subset classes unchanged.
        sf_rewrite(install, sf_configs(extra={'SynUnrelated': klass('Rifle_Base', scope=2)}))
        update = sf.verify_install(install, allow)
        self.assertEqual(update['install']['problems'], [])
        self.assertEqual(update['status'], 'verified')
        # A pinned class changes: drift names exactly that class and verification is not trusted.
        sf_rewrite(install, sf_configs(wood_ammo='SynAmmoB'))
        drift = sf.verify_install(install, allow)
        self.assertEqual(drift['status'], 'unverified')
        self.assertIn('HC61_SUBSET_PIN_DRIFT:SynWood', drift['install']['problems'])
        self.assertEqual([p for p in drift['install']['problems'] if p.startswith('HC61_SUBSET_PIN_DRIFT')],
                         ['HC61_SUBSET_PIN_DRIFT:SynWood'])

    def test_snafu_subset_pins_skip_whole_pbo_hashing_and_generate_rechecks_pins(self):
        install = self.root / 'sf'
        sf_fixture.build_install(install)
        allow = sf_fixture.allowlist(*sf_fixture.GOOD)
        allow = pinned(allow, sf.verify_install(install, allow))
        with mock.patch.object(sf, '_pbo_sha256', side_effect=AssertionError('whole-PBO hash')):
            report = sf.verify_install(install, allow)
        self.assertEqual(report['status'], 'verified')
        self.assertTrue(all('sha256' not in row for row in report['install']['pbos']))
        stale = copy.deepcopy(report)
        stale['subset_pins']['SynWood'] = '0' * 64
        mission = self.root / 'mission'
        mission.mkdir()
        sf_fixture.patch_roster(self, self.root)
        tf_fixture.mission(mission)
        with self.assertRaisesRegex(ValueError, 'HC61_SUBSET_PIN_DRIFT:SynWood'):
            sf.generate(mission, allow, stale)

    def test_legacy_pbo_pins_still_pin_the_whole_file(self):
        install = self.root / 'sf'
        sf_fixture.build_install(install)
        allow = sf_fixture.allowlist(*sf_fixture.GOOD)
        report = sf.verify_install(install, allow)
        allow = pinned(allow, report)
        del allow['hc61']['class_pins']
        allow['hc61']['dependency_pins'] = [{k: row[k] for k in ('name', 'size', 'sha256')}
                                            for row in report['install']['pbos']]
        sf_rewrite(install, sf_configs(extra={'SynUnrelated': klass('Rifle_Base', scope=2)}))
        self.assertIn('HC61_DEPENDENCY_PIN_MISMATCH', sf.verify_install(install, allow)['install']['problems'])

    def test_tactical_flava_subset_pins_pass_unrelated_text_update_and_name_changes(self):
        install = self.root / 'tf'
        tf_fixture.build_install(install)
        allow = tf_fixture.allowlist(*tf_fixture.good())
        first = tf.verify_install(install, allow, vanilla=tf_fixture.VANILLA)
        self.assertEqual(first['status'], 'verified', first['install']['problems'])
        allow = pinned(allow, first)
        tf.validate_allowlist(allow)
        update = tf_fixture.TEXT_A.replace('class SynHidden: Rifle_Base { scope = 0;',
                                           'class SynHidden: Rifle_Base { scope = 0; ignored = 1;')
        self.assertNotEqual(update, tf_fixture.TEXT_A)
        (install / 'addons/syn_a.pbo').unlink()
        tf_fixture.build_install(self.root / 'tf2', text=update)
        os.replace(self.root / 'tf2/addons/syn_a.pbo', install / 'addons/syn_a.pbo')
        with mock.patch.object(sf, '_pbo_sha256', side_effect=AssertionError('whole-PBO hash')):
            ok = tf.verify_install(install, allow, vanilla=tf_fixture.VANILLA)
        self.assertEqual(ok['status'], 'verified', ok['install']['problems'])
        changed = tf_fixture.TEXT_A.replace('chamberableFrom[] = {"Ammo_545x39","Ammo_545x39Tracer"};',
                                            'chamberableFrom[] = {"Ammo_545x39"};')
        self.assertNotEqual(changed, tf_fixture.TEXT_A)
        tf_fixture.build_install(self.root / 'tf3', text=changed)
        os.replace(self.root / 'tf3/addons/syn_a.pbo', install / 'addons/syn_a.pbo')
        drift = tf.verify_install(install, allow, vanilla=tf_fixture.VANILLA)
        self.assertEqual(drift['status'], 'unverified')
        names = [p for p in drift['install']['problems'] if p.startswith('HC61_SUBSET_PIN_DRIFT')]
        self.assertIn('HC61_SUBSET_PIN_DRIFT:SynRifle', names)


def with_dependency_pins(allow, report):
    """Keep subset pins and ALSO record the whole-PBO pins (what the real allowlists carry)."""
    out = copy.deepcopy(allow)
    out['hc61']['dependency_pins'] = [{k: row[k] for k in ('name', 'size', 'sha256')}
                                      for row in report['install']['pbos']]
    return out


class DependencyUpdateWarning(unittest.TestCase):
    """#183 P2 a: a whole-PBO change with unchanged pinned classes is a named warning, not a failure."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.dict(os.environ, {'HC_HASH_CACHE_DIR': str(self.root / 'cache')})
        patcher.start()
        self.addCleanup(patcher.stop)

    def _sf_pinned(self):
        install = self.root / 'sf'
        sf_fixture.build_install(install)
        allow = sf_fixture.allowlist(*sf_fixture.GOOD)
        first = sf.verify_install(install, allow)  # no hc61 block: whole-PBO rows carry sha256
        return install, with_dependency_pins(pinned(allow, first), first)

    def test_snafu_unchanged_dependency_has_no_warning(self):
        install, allow = self._sf_pinned()
        report = sf.verify_install(install, allow)
        self.assertEqual(report['status'], 'verified', report['install']['problems'])
        self.assertEqual(report['install']['warnings'], [])
        self.assertFalse(report['dependency_changed'])

    def test_snafu_whole_pbo_change_with_same_pinned_classes_warns_and_names_the_pbo(self):
        install, allow = self._sf_pinned()
        sf_rewrite(install, sf_configs(extra={'SynUnrelated': klass('Rifle_Base', scope=2)}))
        report = sf.verify_install(install, allow)
        self.assertEqual(report['install']['problems'], [])
        self.assertEqual(report['status'], 'verified')
        self.assertEqual(report['install']['warnings'], ['HC61_DEPENDENCY_UPDATED:Synth_Guns.pbo'])
        self.assertTrue(report['dependency_changed'])
        # The warning does not block generation from a verified report.
        sf_fixture.patch_roster(self, self.root)
        mission = self.root / 'mission'
        mission.mkdir()
        tf_fixture.mission(mission)
        sf.generate(mission, allow, report)

    def test_snafu_pinned_class_change_still_fails_and_names_class_and_pbo(self):
        install, allow = self._sf_pinned()
        sf_rewrite(install, sf_configs(wood_ammo='SynAmmoB'))
        report = sf.verify_install(install, allow)
        self.assertEqual(report['status'], 'unverified')
        self.assertIn('HC61_SUBSET_PIN_DRIFT:SynWood', report['install']['problems'])
        self.assertEqual(report['install']['warnings'], ['HC61_DEPENDENCY_UPDATED:Synth_Guns.pbo'])

    def test_tactical_flava_whole_pbo_change_warns_without_failing(self):
        install = self.root / 'tf'
        tf_fixture.build_install(install)
        allow = tf_fixture.allowlist(*tf_fixture.good())
        first = tf.verify_install(install, allow, vanilla=tf_fixture.VANILLA)
        allow = with_dependency_pins(pinned(allow, first), first)
        same = tf.verify_install(install, allow, vanilla=tf_fixture.VANILLA)
        self.assertEqual(same['install']['warnings'], [])
        update = tf_fixture.TEXT_A.replace('class SynHidden: Rifle_Base { scope = 0;',
                                           'class SynHidden: Rifle_Base { scope = 0; ignored = 1;')
        tf_fixture.build_install(self.root / 'tf2', text=update)
        os.replace(self.root / 'tf2/addons/syn_a.pbo', install / 'addons/syn_a.pbo')
        report = tf.verify_install(install, allow, vanilla=tf_fixture.VANILLA)
        self.assertEqual(report['status'], 'verified', report['install']['problems'])
        self.assertEqual(report['install']['warnings'], ['HC61_DEPENDENCY_UPDATED:syn_a.pbo'])
        self.assertTrue(report['dependency_changed'])
        changed = tf_fixture.TEXT_A.replace('chamberableFrom[] = {"Ammo_545x39","Ammo_545x39Tracer"};',
                                            'chamberableFrom[] = {"Ammo_545x39"};')
        tf_fixture.build_install(self.root / 'tf3', text=changed)
        os.replace(self.root / 'tf3/addons/syn_a.pbo', install / 'addons/syn_a.pbo')
        drift = tf.verify_install(install, allow, vanilla=tf_fixture.VANILLA)
        self.assertEqual(drift['status'], 'unverified')
        self.assertIn('HC61_SUBSET_PIN_DRIFT:SynRifle', drift['install']['problems'])

    def test_a_removed_or_added_pbo_is_named_in_the_warning(self):
        install, allow = self._sf_pinned()
        allow['hc61']['dependency_pins'].append({'name': 'Gone.pbo', 'size': 5, 'sha256': 'a' * 64})
        report = sf.verify_install(install, allow)
        self.assertEqual(report['install']['warnings'], ['HC61_DEPENDENCY_UPDATED:Gone.pbo'])
        self.assertEqual(report['status'], 'verified')

    def test_cli_prints_the_warning(self):
        install, allow = self._sf_pinned()
        sf_rewrite(install, sf_configs(extra={'SynUnrelated': klass('Rifle_Base', scope=2)}))
        allow_path = self.root / 'allow.json'
        allow_path.write_bytes(json.dumps(allow).encode())
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            sf.main(['verify', '--install', str(install), '--allowlist', str(allow_path),
                     '--out', str(self.root / 'report.json')])
        self.assertIn('install warning: HC61_DEPENDENCY_UPDATED:Synth_Guns.pbo', printed.getvalue())


class HashCache(unittest.TestCase):
    """#183 P2 b: PBO hashes are cached by (absolute path, size, mtime_ns) under ~/.cache, never in the repo."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.cache = self.root / 'cache'
        self.file = self.root / 'a.pbo'
        self.file.write_bytes(b'one')
        os.utime(self.file, ns=(10 ** 9, 10 ** 9))  # old mtime: outside the racy-write guard

    def _count(self):
        real = hash_cache._hash_file
        calls = []

        def counting(path):
            calls.append(path)
            return real(path)
        return calls, mock.patch.object(hash_cache, '_hash_file', counting)

    def test_second_call_hits_the_cache(self):
        calls, patch = self._count()
        with patch:
            first = hash_cache.cached_sha256(self.file, self.cache)
            second = hash_cache.cached_sha256(self.file, self.cache)
        self.assertEqual(first, second)
        self.assertEqual(len(calls), 1)

    def test_size_or_mtime_change_rehashes(self):
        calls, patch = self._count()
        with patch:
            before = hash_cache.cached_sha256(self.file, self.cache)
            self.file.write_bytes(b'one!')
            os.utime(self.file, ns=(10 ** 9, 10 ** 9))
            after_size = hash_cache.cached_sha256(self.file, self.cache)
            self.file.write_bytes(b'two!')  # same size as before, different mtime_ns
            os.utime(self.file, ns=(2 * 10 ** 9, 2 * 10 ** 9))
            after_mtime = hash_cache.cached_sha256(self.file, self.cache)
        self.assertEqual(len(calls), 3)
        self.assertEqual(len({before, after_size, after_mtime}), 3)

    def test_corrupt_or_wrong_shape_cache_is_ignored_not_fatal(self):
        self.cache.mkdir()
        want = hash_cache._hash_file(self.file)
        for junk in (b'{not json', b'[]', b'{"schema": 1, "entries": {"x": 5}}', b'\xff\xfe'):
            (self.cache / hash_cache.CACHE_FILE).write_bytes(junk)
            self.assertEqual(hash_cache.cached_sha256(self.file, self.cache), want)
        # A poisoned entry for this file with a wrong digest shape is not trusted either.
        st = self.file.stat()
        entry = {str(self.file.absolute()): {'size': st.st_size, 'mtime_ns': st.st_mtime_ns, 'sha256': 'zz'}}
        (self.cache / hash_cache.CACHE_FILE).write_text(json.dumps({'schema': 1, 'entries': entry}))
        self.assertEqual(hash_cache.cached_sha256(self.file, self.cache), want)

    def test_unwritable_cache_directory_is_not_fatal(self):
        blocker = self.root / 'blocker'
        blocker.write_bytes(b'file, not a directory')
        self.assertEqual(hash_cache.cached_sha256(self.file, blocker / 'sub'), hash_cache._hash_file(self.file))

    def test_a_file_modified_just_now_is_not_cached(self):
        fresh = self.root / 'fresh.pbo'
        fresh.write_bytes(b'fresh')
        calls, patch = self._count()
        with patch:
            hash_cache.cached_sha256(fresh, self.cache)
            hash_cache.cached_sha256(fresh, self.cache)
        self.assertEqual(len(calls), 2)

    def test_default_cache_lives_under_home_cache_not_the_repo(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop('HC_HASH_CACHE_DIR', None)
            directory = hash_cache.cache_dir()
        self.assertEqual(directory, Path.home() / '.cache' / 'hollow-country' / 'pbo-hash')

    def test_verify_uses_the_cache_for_whole_pbo_hashes(self):
        install = self.root / 'sf'
        sf_fixture.build_install(install)
        for pbo_path in (install / 'Addons').glob('*.pbo'):
            os.utime(pbo_path, ns=(10 ** 9, 10 ** 9))
        allow = sf_fixture.allowlist(*sf_fixture.GOOD)
        calls, patch = self._count()
        with patch, mock.patch.dict(os.environ, {'HC_HASH_CACHE_DIR': str(self.cache)}):
            sf.verify_install(install, allow)
            sf.verify_install(install, allow)
        self.assertEqual(len(calls), len(list((install / 'Addons').glob('*.pbo'))))


PIN_SCOPE_SENTENCE = ('Subset pins hash only the parsed fields (scope, model, ammo, count, magazines, '
                      'chamberableFrom, handAnim, attachments, inventorySlot) plus the parent chain; '
                      'an update that only changes damage/hit values passes.')


class SubsetPinScopeStatement(unittest.TestCase):
    """#191: the deliberate trade (fast subset pins that ignore damage/hit values) is stated, not implied."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def test_the_scope_sentence_is_in_the_docstring_the_hint_and_both_reports(self):
        self.assertEqual(sf.SUBSET_PIN_SCOPE, PIN_SCOPE_SENTENCE)
        self.assertIn(PIN_SCOPE_SENTENCE, ' '.join(sf.subset_pins.__doc__.split()))
        install = self.root / 'sf'
        sf_fixture.build_install(install)
        self.assertEqual(sf.verify_install(install, sf_fixture.allowlist(*sf_fixture.GOOD))['subset_pins_scope'],
                         PIN_SCOPE_SENTENCE)
        tf_install = self.root / 'tf'
        tf_fixture.build_install(tf_install)
        tf_report = tf.verify_install(tf_install, tf_fixture.allowlist(*tf_fixture.good()),
                                      vanilla=tf_fixture.VANILLA)
        self.assertEqual(tf_report['subset_pins_scope'], PIN_SCOPE_SENTENCE)
        out = self.root / 'report.json'
        allow_path = self.root / 'allow.json'
        allow_path.write_bytes(json.dumps(sf_fixture.allowlist(*sf_fixture.GOOD)).encode())
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            sf.main(['verify', '--install', str(install), '--allowlist', str(allow_path), '--out', str(out)])
        self.assertIn(PIN_SCOPE_SENTENCE, printed.getvalue())

    def test_verify_parses_the_allowlist_once(self):
        install = self.root / 'sf'
        sf_fixture.build_install(install)
        allow_path = self.root / 'allow.json'
        allow_path.write_bytes(json.dumps(sf_fixture.allowlist(*sf_fixture.GOOD)).encode())
        reads = []
        real = Path.read_bytes

        def counting(path):
            if path == allow_path:
                reads.append(path)
            return real(path)
        with mock.patch.object(Path, 'read_bytes', counting), contextlib.redirect_stdout(io.StringIO()):
            sf.main(['verify', '--install', str(install), '--allowlist', str(allow_path),
                     '--out', str(self.root / 'report.json')])
        self.assertEqual(len(reads), 1)

    def test_a_parent_class_field_change_drifts_every_pinned_child(self):
        install = self.root / 'sf'
        sf_fixture.build_install(install)
        allow = sf_fixture.allowlist(*sf_fixture.GOOD)
        allow = pinned(allow, sf.verify_install(install, allow))
        # Synthetic update: only the parent class Rifle_Base changes (a parsed field: handAnim).
        tree = sf_configs()
        tree['CfgWeapons']['Rifle_Base'] = klass('', scope=0, handAnim=['a', 'b'])
        sf_rewrite(install, tree)
        drift = sf.verify_install(install, allow)
        self.assertEqual(drift['status'], 'unverified')
        self.assertIn('HC61_SUBSET_PIN_DRIFT:SynWood', drift['install']['problems'])


if __name__ == '__main__':
    unittest.main()
