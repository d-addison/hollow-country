"""Offline evidence contracts: no native process or gate invocation."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools.release import activity_check as activity, release_gate as gate, rpt_summary
from tools.audit import rpt_config_audit as census


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rpt = self.root / 'server.RPT'

    def test_post_stop_crash_and_midnight_span(self):
        self.rpt.write_text('23:59:00 [CE][Hive] :: Init sequence finished\n'
                            '00:30:00 Server modules stopped\n')
        self.assertEqual(rpt_summary.soak_span(self.rpt), 1860)
        with contextlib.redirect_stdout(io.StringIO()):
            gate.post_stop_check(self.rpt, soak_minutes=30)
            with self.assertRaisesRegex(gate.Refused, 'measured_seconds=1860.000'):
                gate.post_stop_check(self.rpt, soak_minutes=32)
        with self.rpt.open('a') as stream:
            stream.write('00:30:01 Unhandled exception 0xc0000374\n00:30:01 minidump written\n')
        with self.assertRaisesRegex(gate.Refused, 'post-stop crash'):
            gate.post_stop_check(self.rpt, soak_minutes=30)

    def test_duration_requires_both_markers_and_unique_hive(self):
        for content in ('12:00:00 Server modules stopped\n',
                        '12:00:00 [CE][Hive] :: Init sequence finished\n',
                        '12:00:00 [CE][Hive] :: Init sequence finished\n'
                        '12:01:00 [CE][Hive] :: Init sequence finished\n12:40:00 Server modules stopped\n'):
            self.rpt.write_text(content)
            self.assertIsNone(rpt_summary.soak_span(self.rpt))

    def test_quarantine_markers_and_negative_controls(self):
        import re
        controls = ('[HC Infected] native release status: pending=0 quarantined=2',
                    '[HC Use] module=Infected feature=group_quarantine count=3',
                    '[HC Plan] HC-28 recovery=validate_each_store quarantine=0 runtime=PENDING')
        for raw in controls:
            self.assertFalse(any(re.search(p, raw) for p in gate.STORE_QUARANTINE_MARKERS.values()))
        actual = {'hc28-store-recovery': '[HC Plan] HC-28 store=test recovery=quarantined',
                  'ecology-recovery': '[HC Ecology] recovery=quarantined reason=test',
                  'ecology-migration': '[HC Ecology] migration quarantine in place',
                  'event-cleanup': '[HC Events] cleanup quarantined:',
                  'interior-slot': '[HC Interiors] slot 4 quarantined:',
                  'infected-cohort': '[HollowCountry] infected cohort quarantined',
                  'betrayal-store': '[HC Plan] HC-5 signals=off betrayal_store=quarantined',
                  'staged-store': '[HC Store] recover path=sample action=quarantine',
                  'sites-state': '[HC Sites] state recovered=0 quarantined=1 persist=1'}
        self.assertEqual(actual.keys(), gate.STORE_QUARANTINE_MARKERS.keys())
        for marker, raw in actual.items():
            self.assertRegex(raw, gate.STORE_QUARANTINE_MARKERS[marker])

    def test_texture_path_boundaries_and_noise(self):
        self.rpt.write_text("Cannot load texture 'own/ok.paa'\nCannot load texture 'dep\\bad.paa'\n"
                            "Cannot load texture 'ownish/bad.paa'\nCannot load texture 'dz/foo.paa'\n"
                            "Cannot load texture 'a3/foo.paa'\nCannot load texture 'd:\\p4\\foo.paa'\n"
                            "Cannot load texture 'default'\nANIMATION: Can't load skeletons.anim.xml\n"
                            "MATERIAL: Can't load particle\n")
        self.assertEqual(gate.texture_counts(self.rpt, ({'own'}, {'dep'})),
                         dict(missing_textures=2, vanilla_texture_noise=4, other_texture_noise=1))

    def test_prefixes_come_from_repo_and_declared_dependency_headers(self):
        own = self.root / 'mods/Example'
        own.mkdir(parents=True)
        (own / 'config.cpp').write_text('class CfgPatches {};')
        (own / '$PBOPREFIX$').write_text('author/root')
        setup = self.root / 'tools/setup'
        setup.mkdir(parents=True)
        (setup / 'workshop_mods.json').touch()
        workshop = self.root / 'workshop'
        folder = workshop / '123456/addons'
        folder.mkdir(parents=True)
        (folder / 'dep.pbo').touch()
        manifest = dict(mods=[dict(id='123456', publish=False)])
        with patch('tools.setup.workshop_sync.load_manifest', return_value=manifest), patch(
                'tools.audit.pbo_config.read_pbo_index', return_value=dict(prefix='upstream/assets')):
            self.assertEqual(gate.texture_prefixes(self.root, workshop),
                             ({'author\\root'}, {'upstream\\assets'}))

    def campaign(self):
        for directory in ('server', 'client'):
            (self.root / directory).mkdir(exist_ok=True)
        server = self.root / 'server/run.RPT'
        server.write_text('[HC Ready] module=Core enabled=true ready=true\n'
                          '[HC Use] module=Core feature=foo count=1\n')
        (self.root / 'selection.json').write_text(json.dumps(
            dict(commit='a' * 40, targeted=False, release_class=True)))
        return server

    def test_campaign_admission(self):
        server = self.campaign()
        self.assertEqual(gate.campaign_evidence(self.root, 'a' * 40), (server, None))
        for change, reason in ((dict(targeted=True), 'targeted'), (dict(commit='b' * 40), 'commit'),
                               (dict(release_class=False), 'release-class')):
            receipt = dict(commit='a' * 40, targeted=False, release_class=True, **{})
            receipt.update(change)
            (self.root / 'selection.json').write_text(json.dumps(receipt))
            with self.assertRaisesRegex(gate.Refused, reason):
                gate.campaign_evidence(self.root, 'a' * 40)
        self.campaign()
        for error in ('Unhandled exception', 'SCRIPT (E): error', 'VME', 'Virtual Machine Exception'):
            server.write_text(error)
            with self.assertRaisesRegex(gate.Refused, 'crash/script/VME'):
                gate.campaign_evidence(self.root, 'a' * 40)

    def test_activity_union_has_run_provenance(self):
        self.rpt.write_text('[HC Ready] module=Core enabled=true ready=true\n'
                            '[HC Use] module=Core feature=foo count=0\n'
                            '[HC Use] module=Core feature=bar count=1\n')
        server = self.campaign()
        result = activity.scan_release(self.rpt, entries=[], evidence=(server, None))
        rows = {row['feature']: row for row in result['features']}
        self.assertEqual(rows['foo']['active_runs'], ['campaign'])
        self.assertEqual(rows['bar']['active_runs'], ['gate'])
        self.assertEqual(result['count'], 0)

    def test_r2b_warn_only_and_owner_r2_remains_separate(self):
        self.rpt.write_text('[HC Perf] window=4 work_max=23.09\n[HC Perf] window=5 work_max=21.61\n')
        self.assertEqual(rpt_summary.r2b_warnings(self.rpt, 20),
                         ['WARN perf_rule=R2b combined_work_max_ms=23.09 limit_ms=20'])
        self.assertEqual(rpt_summary.r2b_warnings(self.rpt, 24), [])

    def test_smoke_plan_detects_new_registration(self):
        mod = self.root / 'mods/Example'
        mod.mkdir(parents=True)
        (mod / 'test.c').write_text('// HCRegisterUse("Ignored", "comment");\n'
                                   'HCModuleReadiness.HCRegisterUse("New", "feature");')
        release = self.root / 'tools/release'
        release.mkdir(parents=True)
        (release / 'r3_smoke_plan.json').write_text('{"entries": []}')
        with self.assertRaisesRegex(ValueError, 'New/feature'):
            activity.check_smoke_plan(self.root)
        self.assertEqual(activity.check_smoke_plan(), 130)

    def test_engine_noise_keeps_hc_separate(self):
        rules = census.category_rules()
        for raw in ('Warning: No components in dz/water/pond.p3d:geometry', 'Sliding pose',
                    'Initializing ragdoll NONE', 'Player Simulation entity eAI_Survivor', 'Loaded'):
            self.assertEqual(census.classify(raw, rules), census.ENGINE_NOISE)
        self.assertNotEqual(census.classify('[HC Example] missing component', rules), census.ENGINE_NOISE)
        self.assertEqual(census.classify('Unknown synthetic warning', rules), 0)

    def test_ceiling_proposal_never_writes_policy(self):
        stock = self.root / 'stock.RPT'
        stock.write_text("No entry 'Cfg/Stock'\n")
        self.rpt.write_text("No entry 'Cfg/Stock'\nNo entry 'Cfg/Candidate'\n")
        targets = self.root / 'targets.json'
        original = json.dumps(dict(rpt_category_ceilings={str(k): 0 for k in census.RULES}), indent=2) + '\n'
        targets.write_text(original)
        result, diff = census.ceiling_proposal(stock, self.rpt, targets)
        self.assertEqual(targets.read_text(), original)
        self.assertEqual(result['categories'][0]['vanilla_count'], 1)
        self.assertIn('+    "1": 2,', diff)

    def test_previous_release_download_verifies_manifest_and_reuses_cache(self):
        def run(argv, **kwargs):
            if 'view' in argv:
                return subprocess.CompletedProcess(argv, 0, json.dumps(dict(assets=[dict(name='friend-bundle.zip')])))
            destination = Path(argv[argv.index('--dir') + 1])
            with zipfile.ZipFile(destination / 'friend-bundle.zip', 'w') as archive:
                archive.writestr('bundle/bundle-manifest.json', '{}')
            return subprocess.CompletedProcess(argv, 0)
        with patch.object(gate.subprocess, 'run', side_effect=run) as child, patch(
                'tools.setup.friend_install.load_bundle', return_value=dict(files=[dict(path='file')])) as verify:
            result = gate.previous_release('test-tag', self.root)
            self.assertTrue(result.is_dir())
            gate.previous_release('test-tag', self.root)
            self.assertEqual(child.call_count, 2)
            self.assertGreaterEqual(verify.call_count, 2)

    def test_previous_release_rejects_archive_traversal(self):
        def run(argv, **kwargs):
            if 'view' in argv:
                return subprocess.CompletedProcess(argv, 0, '{"assets":[{"name":"bundle.zip"}]}')
            with zipfile.ZipFile(Path(argv[argv.index('--dir') + 1]) / 'bundle.zip', 'w') as archive:
                archive.writestr('../escape', 'bad')
            return subprocess.CompletedProcess(argv, 0)
        with patch.object(gate.subprocess, 'run', side_effect=run):
            with self.assertRaisesRegex(gate.Refused, 'archive unsafe'):
                gate.previous_release('test-tag', self.root)

    def test_campaign_full_format_requires_commit_manifest(self):
        server = self.campaign()
        (self.root / 'selection.json').unlink()
        (self.root / 'report.md').write_text('# Soak campaign report\n\nworks=1\n')
        with self.assertRaisesRegex(gate.Refused, 'commit'):
            gate.campaign_evidence(self.root, 'a' * 40)
        (self.root / 'BUILD_MANIFEST.json').write_text(json.dumps(dict(commit='a' * 40)))
        self.assertEqual(gate.campaign_evidence(self.root, 'a' * 40), (server, None))
        (self.root / 'report.md').write_text('# Soak campaign report\n\n**Targeted run:**\n')
        with self.assertRaisesRegex(gate.Refused, 'release-class'):
            gate.campaign_evidence(self.root, 'a' * 40)

    def test_previous_install_refused_is_named_before_candidate_install(self):
        from types import SimpleNamespace
        args = SimpleNamespace(previous_bundle=Path('previous'), bundle=Path('candidate'))
        steps = gate.NativeSteps(args)
        with patch.object(steps, 'install', side_effect=gate.Refused('install failed code=overlays-map')) as install:
            with self.assertRaisesRegex(gate.Refused, 'upgrade previous-install-refused reason=install failed code=overlays-map'):
                steps.upgrade()
            install.assert_called_once_with(Path('previous'))

    def test_stop_checks_final_rpt_after_server_exits(self):
        from types import SimpleNamespace
        steps = gate.NativeSteps(SimpleNamespace())
        steps.boot_rpt, steps.boot_soak = self.rpt, 30
        self.rpt.write_text('12:00:00 [CE][Hive] :: Init sequence finished\n')
        def stopped():
            with self.rpt.open('a') as stream:
                stream.write('12:31:00 Server modules stopped\n12:31:01 minidump written\n')
        with patch.object(steps, 'stop_server', side_effect=stopped):
            with self.assertRaisesRegex(gate.Refused, 'post-stop crash'):
                steps.stop()

    def test_loot_breakdown_compares_every_type_with_quantity_and_policy(self):
        self.rpt.write_text('[CE][LootRespawner] Item is hard to place: "CableReel"\n' * 2)
        shipped, stock = self.root / 'types.xml', self.root / 'stock-types.xml'
        template = '<types><type name="CableReel"><nominal>{}</nominal><min>{}</min><usage name="Industrial"/><category name="tools"/></type></types>'
        shipped.write_text(template.format(280, 175))
        stock.write_text(template.format(80, 50))
        settings = self.root / 'settings.json'
        settings.write_text('{"UsageMultiplier":{"Industrial":3.5},"CapacityMultiplier":{"Industrial":1.0}}')
        row, = census.loot_breakdown(self.rpt, [shipped], [stock], settings)
        self.assertEqual(row['count'], 2)
        self.assertTrue(row['nominal_or_min_boosted'])
        self.assertEqual(row['shipped']['minimum'], 175)
        self.assertEqual(row['usage_multiplier'], 3.5)
        self.assertEqual(row['capacity_multiplier'], 1.0)

    def test_r2b_does_not_refuse_gate_audit(self):
        self.rpt.write_text('12:00:00 Player connect enabled\n'
                            '12:00:00 [CE][Hive] :: Init sequence finished\n'
                            '12:00:01 [HC Ready] module=Core enabled=true ready=true\n'
                            '12:01:00 [HC Perf] window=1 work_max=23.09\n')
        targets = gate.load_targets()
        targets['rpt_category_ceilings'] = {str(k): 0 for k in census.RULES}
        output = io.StringIO()
        with contextlib.redirect_stdout(output), patch.object(gate, 'perf_rules', return_value=[]):
            evidence = gate.audit(self.rpt, targets=targets)
        self.assertIn('WARN perf_rule=R2b', output.getvalue())
        self.assertEqual(len(evidence['warnings']), 1)

    def test_oversized_final_crash_or_campaign_line_is_incomplete(self):
        self.rpt.write_text('12:00:00 [CE][Hive] :: Init sequence finished\n'
                            '12:31:00 Server modules stopped\n' + 'x' * 17000 + 'Unhandled exception\n')
        with self.assertRaisesRegex(gate.Refused, 'oversized'):
            gate.post_stop_check(self.rpt, soak_minutes=30)
        server = self.campaign()
        server.write_text(self.rpt.read_text())
        with self.assertRaisesRegex(gate.Refused, 'oversized'):
            gate.campaign_evidence(self.root, 'a' * 40)
