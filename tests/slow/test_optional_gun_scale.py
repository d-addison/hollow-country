"""SYNTHETIC optional-gun scale fixtures; no Workshop input or DayZ runtime proof."""
import contextlib
import copy
from decimal import Decimal, ROUND_HALF_UP
import io
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from tools.package import economy, military_loot, snafu_optional, tactical_flava_optional
from tests.slow import test_snafu_optional as snafu_fixture
from tests.slow import test_tactical_flava_optional as tf_fixture


try:
    from tests.unit import hash_cache_isolation
except ImportError:  # run as a script from tests/unit
    import hash_cache_isolation


def setUpModule():
    # #194: the whole-PBO hashing path reads/writes the hash cache; never the user's.
    hash_cache_isolation.enter()


def tearDownModule():
    hash_cache_isolation.leave()


class OptionalGunScale(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        snafu_fixture.patch_roster(self, self.root)
        self.cases = []
        for module, fixture in ((snafu_optional, snafu_fixture),
                                (tactical_flava_optional, tf_fixture)):
            source = self.root / module.MANAGED
            source.mkdir()
            tf_fixture.mission(source)
            install = self.root / (module.MANAGED + '-mod')
            fixture.build_install(install)
            allow = copy.deepcopy(snafu_fixture.allowlist(*snafu_fixture.GOOD)
                                  if module is snafu_optional else tf_fixture.allowlist(*tf_fixture.good()))
            kwargs = {} if module is snafu_optional else {'vanilla': tf_fixture.VANILLA}
            report = module.verify_install(install, allow, **kwargs)
            self.assertEqual(report['status'], 'verified')
            self.cases.append((module, source, allow, report))

    def generate(self, case, **kwargs):
        module, source, allow, report = case
        return module.generate(source, allow, report, **kwargs)

    def types(self, files):
        return {row.get('name'): row for row in ET.fromstring(files['ce/types.xml'])}

    def test_global_scale_changes_weapons_and_existing_support_rows(self):
        for case in self.cases:
            for scale in (0.25, 0.5, 1.25, 4.0):
                with self.subTest(pack=case[0].MANAGED, scale=scale):
                    before = copy.deepcopy(case[2:])
                    files = self.generate(case, nominal_scale=scale)
                    rows = self.types(files)
                    for entry in case[2]['entries']:
                        row = rows[entry['class']]
                        budget = entry['set']
                        for field in ('nominal', 'min'):
                            expected = budget[field]
                            if entry['kind'] in {'weapon', 'magazine', 'ammo'}:
                                expected = int((Decimal(expected) * Decimal(str(scale))).quantize(
                                    Decimal('1'), rounding=ROUND_HALF_UP))
                                if budget[field]:
                                    expected = max(1, expected)
                            self.assertEqual(int(row.findtext(field)), expected, (entry['class'], field))
                        self.assertLessEqual(int(row.findtext('min')), int(row.findtext('nominal')))
                        for field in ('lifetime', 'restock'):
                            self.assertEqual(int(row.findtext(field)), budget[field])
                    self.assertEqual(case[2:], before, 'generation must not mutate verified input')

    def test_default_and_explicit_one_follow_authored_policy(self):
        for case in self.cases:
            default_scale = case[2].get('test_abundance_multiplier', 1)
            self.assertEqual(self.generate(case), self.generate(case, nominal_scale=default_scale))
            files = self.generate(case, nominal_scale=1)
            rows = self.types(files)
            self.assertEqual(set(rows), {entry['class'] for entry in case[2]['entries']})
            for entry in case[2]['entries']:
                row = rows[entry['class']]
                for field, value in entry['set'].items():
                    self.assertEqual(row.findtext(field), str(value), (entry['class'], field))
                quantities = military_loot.magazine_quantity() if entry['kind'] == 'magazine' else (-1, -1)
                self.assertEqual(tuple(int(row.findtext(field)) for field in ('quantmin', 'quantmax')),
                                 quantities)
                self.assertEqual([u.get('name') for u in row.findall('usage')], entry['usage'])
                self.assertEqual([v.get('name') for v in row.findall('value')], entry['value'])
            fragment = ET.fromstring(files['cfgeconomycore.append.xml'])
            self.assertEqual(fragment.find('ce').get('folder'), case[0].MANAGED + '/ce')
            registered = fragment.findall('ce/file')
            self.assertTrue(registered)
            for declaration in registered:
                self.assertIn('ce/' + declaration.get('name'), files)
            self.assertEqual(files['core-defaults.patch.json'], economy.encode({}))

    def test_positive_nominal_has_floor_and_halves_round_up(self):
        for case in self.cases:
            modified = copy.deepcopy(case[2])
            for row in modified['entries']:
                if row['kind'] in {'weapon', 'magazine', 'ammo'}:
                    row['set'].update(nominal=1, min=1)
            report = copy.deepcopy(case[3])
            report['allowlist_sha256'] = case[0].allowlist_sha256(modified)
            changed = (*case[:2], modified, report)
            for scale, expected_min in ((0.25, 1), (0.5, 1), (1.5, 2)):  # a positive min keeps its CE restock floor
                rows = self.types(self.generate(changed, nominal_scale=scale))
                for entry in modified['entries']:
                    if entry['kind'] not in {'weapon', 'magazine', 'ammo'}:
                        continue
                    row = rows[entry['class']]
                    self.assertEqual(int(row.findtext('nominal')), max(1, expected_min))
                    self.assertEqual(int(row.findtext('min')), expected_min)

    def test_unreasoned_zero_support_refuses_before_generation(self):
        for case in self.cases:
            modified = copy.deepcopy(case[2])
            modified['entries'].append(snafu_fixture.entry(
                'SynDisabledMagazine', kind='magazine', role='support', nominal=0, minimum=0,
                usage=['Military']))
            parent = next(e for e in modified['entries'] if e['kind'] == 'weapon' and e['magazines'])
            parent['magazines'].append('SynDisabledMagazine')
            report = copy.deepcopy(case[3])
            report['allowlist_sha256'] = case[0].allowlist_sha256(modified)
            report['classes']['SynDisabledMagazine'] = {'status': 'verified'}
            before = tf_fixture.files_of(case[1])
            for scale in (0.25, 0.5, 1.5):
                with self.subTest(pack=case[0].MANAGED, scale=scale), self.assertRaisesRegex(
                        ValueError, 'HC_MILITARY_LOOT_RETENTION:.*SynDisabledMagazine:nominal=0'):
                    self.generate((*case[:2], modified, report), nominal_scale=scale)
            self.assertEqual(tf_fixture.files_of(case[1]), before)

    def test_decimal_half_up_avoids_binary_float_rounding(self):
        for case in self.cases:
            allow = copy.deepcopy(case[2])
            allow['entries'][0]['set'].update(nominal=100, min=100)
            report = dict(case[3], allowlist_sha256=case[0].allowlist_sha256(allow))
            files = self.generate((*case[:2], allow, report), nominal_scale=1.005)
            first = self.types(files)[allow['entries'][0]['class']]
            self.assertEqual(first.findtext('nominal'), '101')
            self.assertEqual(first.findtext('min'), '101')

    def test_report_totals_and_scale_describe_generated_rows(self):
        for case in self.cases:
            for scale in (1.0, 1.5):
                files = self.generate(case, nominal_scale=scale)
                meta = json.loads(files['economy-report.json'])
                self.assertEqual(meta['nominal_scale'], scale)
                self.assertEqual(meta['runtime_acceptance'], 'pending')
                generated = self.types(files)
                for kind in ('weapon', 'magazine', 'ammo'):
                    before = sum(e['set']['nominal'] for e in case[2]['entries'] if e['kind'] == kind)
                    after = sum(int(generated[e['class']].findtext('nominal'))
                                for e in case[2]['entries'] if e['kind'] == kind)
                    self.assertEqual(meta['totals'][kind + '_nominal_before'], before)
                    self.assertEqual(meta['totals'][kind + '_nominal_after'], after)
                self.assertEqual(meta['totals']['weapon_nominal'], meta['totals']['weapon_nominal_after'])
                for row in meta['entries']:
                    self.assertEqual(row['set']['nominal'], int(generated[row['class']].findtext('nominal')))

    def test_existing_tier_field_can_select_multipliers(self):
        for case in self.cases:
            allow = copy.deepcopy(case[2])
            allow['entries'][0]['tier'] = 'common'
            report = dict(case[3], allowlist_sha256=case[0].allowlist_sha256(allow))
            files = self.generate((*case[:2], allow, report), nominal_scale=2,
                                  tier_scales={'common': 0.5, 'rare': 1.5})
            rows = self.types(files)
            self.assertEqual(int(rows[allow['entries'][0]['class']].findtext('nominal')),
                             allow['entries'][0]['set']['nominal'])
            self.assertEqual(int(rows[allow['entries'][1]['class']].findtext('nominal')),
                             3 * allow['entries'][1]['set']['nominal'])
            self.assertEqual(json.loads(files['economy-report.json'])['tier_scales'],
                             {'common': 0.5, 'rare': 1.5})

    def test_invalid_scale_refuses_before_reading_source(self):
        for module, _, allow, report in self.cases:
            for scale in (0, -1, 0.249, 4.001, 'nan', 'inf', '-inf', 'bad', True, None):
                with self.subTest(pack=module.MANAGED, scale=scale), self.assertRaisesRegex(
                        ValueError, 'nominal.scale.*0.25.*4.0'):
                    module.generate(self.root / 'missing', allow, report, nominal_scale=scale)
            for tiers in ({'unknown': 1}, {'rare': 0}, {'rare': 'nan'}, {'rare': 4}):
                with self.subTest(tiers=tiers), self.assertRaisesRegex(ValueError, 'tier|scale'):
                    module.generate(self.root / 'missing', allow, report, nominal_scale=2, tier_scales=tiers)

    def test_scale_changes_artifact_identity_even_when_rounding_leaves_xml_identical(self):
        for case in self.cases:
            first = self.generate(case, nominal_scale=1.001)
            second = self.generate(case, nominal_scale=1.002)
            self.assertEqual(first['ce/types.xml'], second['ce/types.xml'])
            self.assertNotEqual(first['economy-report.json'], second['economy-report.json'])
            self.assertNotEqual(first['delta-manifest.json'], second['delta-manifest.json'])
            for files in (first, second):
                manifest = json.loads(files['delta-manifest.json'])
                for name, digest in manifest['files'].items():
                    self.assertEqual(economy.sha(files[name]), digest)

    def test_precise_cli_scales_remain_distinct_in_audit_identity(self):
        for case in self.cases:
            first = self.generate(case, nominal_scale='1.0000000000000000000000000001')
            second = self.generate(case, nominal_scale='1.0000000000000000000000000002')
            self.assertEqual(first['ce/types.xml'], second['ce/types.xml'])
            self.assertNotEqual(first['delta-manifest.json'], second['delta-manifest.json'])
            for scale in ('4.0000000000000000000000000001', '0.2499999999999999999999999999'):
                with self.assertRaisesRegex(ValueError, 'scale.*0.25.*4.0'):
                    self.generate(case, nominal_scale=1, tier_scales={'rare': scale})
            with self.assertRaisesRegex(ValueError, 'effective.*scale.*0.25.*4.0'):
                self.generate(case, nominal_scale='2.0000000000000000000000000001',
                              tier_scales={'rare': 2})
            self.assertEqual(self.generate(case, nominal_scale=1),
                             self.generate(case, nominal_scale='1.000000'))

    def cli_args(self, case, name):
        _, source, allow, report = case
        allow_path = source.parent / (source.name + '-allow.json')
        report_path = source.parent / (source.name + '-report.json')
        allow_path.write_bytes(economy.encode(allow))
        report_path.write_bytes(economy.encode(report))
        stage = source.parent / (source.name + name)
        return ['generate', '--source', str(source), '--allowlist', str(allow_path),
                '--report', str(report_path), '--out', str(stage)], stage

    def test_cli_prints_scale_and_before_after_totals(self):
        for case in self.cases:
            for scale in (None, '1.5'):
                args, stage = self.cli_args(case, '-cli-' + str(scale))
                if scale:
                    args += ['--nominal-scale', scale]
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    case[0].main(args)
                meta = json.loads((stage / 'economy-report.json').read_bytes())
                self.assertIn('nominal_scale=' + str(meta['nominal_scale']), output.getvalue())
                for kind in ('weapon', 'magazine', 'ammo'):
                    self.assertIn(f'{kind}_nominal: {meta["totals"][kind + "_nominal_before"]}'
                                  f' -> {meta["totals"][kind + "_nominal_after"]}', output.getvalue())
                self.assertIn('runtime acceptance pending', output.getvalue())

    def test_cli_rejects_bad_scales_without_creating_stage(self):
        for case in self.cases:
            for scale in ('0.249', '4.01', 'nan', 'inf', 'bad'):
                args, stage = self.cli_args(case, '-bad-' + scale)
                error = io.StringIO()
                with contextlib.redirect_stderr(error), self.assertRaises(SystemExit) as caught:
                    case[0].main(args + ['--nominal-scale', scale])
                self.assertNotEqual(caught.exception.code, 0)
                self.assertIn('0.25', error.getvalue())
                self.assertIn('4.0', error.getvalue())
                self.assertFalse(stage.exists())

    def test_cli_accepts_tier_multipliers_and_rejects_duplicate_tiers(self):
        for case in self.cases:
            args, stage = self.cli_args(case, '-tier')
            with contextlib.redirect_stdout(io.StringIO()):
                case[0].main(args + ['--nominal-scale', '2', '--tier-scale', 'rare=0.5'])
            meta = json.loads((stage / 'economy-report.json').read_bytes())
            self.assertEqual(meta['tier_scales'], {'rare': 0.5})
            args, stage = self.cli_args(case, '-tier-duplicate')
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                case[0].main(args + ['--tier-scale', 'rare=0.5', '--tier-scale', 'rare=2'])
            self.assertFalse(stage.exists())

    def test_install_records_scale_preserves_stock_and_rolls_back_exactly(self):
        for case in self.cases:
            module, source, _, _ = case
            before = tf_fixture.files_of(source)
            files = self.generate(case, nominal_scale=2, tier_scales={'rare': 0.5})
            stage = source.parent / (source.name + '-stage')
            module.write_delta(stage, files)
            receipt = module.install(stage, source)
            self.assertEqual(receipt['nominal_scale'], 2.0)
            self.assertEqual(receipt['tier_scales'], {'rare': 0.5})
            self.assertEqual(receipt['scale_decimal'],
                             {'nominal_scale': '2', 'tier_scales': {'rare': '0.5'}})
            self.assertEqual(receipt['economy_report_sha256'], economy.sha(files['economy-report.json']))
            self.assertEqual(receipt, json.loads((source / module.MANAGED / 'receipt.json').read_bytes()))
            self.assertEqual((source / 'db/types.xml').read_bytes(), before['db/types.xml'])
            self.assertEqual(set(self.types(files)), {e['class'] for e in case[2]['entries']})
            module.rollback(source)
            self.assertEqual(tf_fixture.files_of(source), before)


if __name__ == '__main__':
    unittest.main()
