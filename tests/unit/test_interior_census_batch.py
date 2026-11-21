"""Synthetic tooling checks only. No engine processes or Enforce emulation."""
from contextlib import ExitStack, redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tests.legacy.test_ce_probe import make_source_runtime, SYNTH_BE_SHA
from tools.package import new_buildings
from tools.setup import interior_census_batch as batch, interior_census_support as support
from tools.setup import interior_sampler as sampler, probe_runtime as runtime


class BatchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        native = self.root / '.cache/hollow-country/native-scripts/scripts-1.30.164289/3_Game'
        native.mkdir(parents=True)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for target, value in (("WSL_PARENT", self.root),):
            self.stack.enter_context(patch.object(runtime, target, value))
        self.stack.enter_context(patch.object(batch.Path, 'home', return_value=self.root))
        self.stack.enter_context(patch.object(batch.os, 'statvfs', return_value=SimpleNamespace(f_flag=0)))
        self.stack.enter_context(patch.object(runtime, '_hash_file', return_value=(runtime.SERVER_EXE_SHA256, 1)))
        self.source = {'held': {'mapgroupproto.xml': b'<prototype/>', 'mapgrouppos.xml': b'<map/>'}}
        self.stack.enter_context(patch.object(runtime, 'verify_source', return_value=self.source))
        self.stdout = self.stack.enter_context(redirect_stdout(io.StringIO()))

    def fake_stage(self, *args, **kwargs):
        return {'probe': {'target_count': len(kwargs['run']['targets'])}}

    def test_default_preserves_stock_plan_and_printed_lines(self):
        names = ['Synth%d' % i for i in range(sum(batch.LEGACY_RUN_TARGET_COUNTS))]
        positions = {name: [(i, 0, i)] for i, name in enumerate(names)}
        # The legacy denominator includes classes with no stock mapgrouppos rows.
        names.append('SynthUnplaced')
        with patch.object(batch.templates, 'parse_proto', return_value=dict.fromkeys(names)), \
             patch.object(sampler.placements_tool, 'parse_placements', return_value=positions), \
             patch.object(sampler, 'stage', side_effect=self.fake_stage) as stage:
            plan = batch.prepare()
        self.assertEqual(sampler.plan_batches(sorted(names), positions), plan)
        self.assertEqual(len(plan['runs']), stage.call_count)
        for run, call, line in zip(plan['runs'], stage.call_args_list, self.stdout.getvalue().splitlines()):
            self.assertEqual(self.root / ('interior-sampler-227-' + str(run['index'])), call.args[1])
            self.assertEqual('[HC Interiors] census staged run=%d targets=%d native_run_id=%s runtime=PENDING'
                             % (run['index'], len(run['targets']), run['native_run_id']), line)

    def test_custom_classes_chunk_to_requested_budget_and_emit_launcher(self):
        names = ['Synth%d' % i for i in range(sampler.MAX_TARGETS + 3)]
        placements = {name: [(i, 0, i)] for i, name in enumerate(names)}
        with patch.object(support, 'world_placements', return_value=(names, placements, {})), \
             patch.object(support, 'stage_observation', side_effect=lambda *a, **kw: self.fake_stage(run=kw['run'])):
            plan = batch.prepare(classes=names, tag='custom', run_size=11)
        self.assertTrue(all(len(run['targets']) <= plan['run_size'] for run in plan['runs']))
        self.assertEqual(set(names), {t['class'] for run in plan['runs'] for t in run['targets']})
        runner = (self.root / 'interior-batch-custom/Run-Census.ps1').read_text()
        self.assertEqual(len(plan['runs']), runner.count("& $launcher -Kind 'interior-sampler'"))
        self.assertIn('sentinel-seen', runner)
        with self.assertRaises(ValueError):
            batch.prepare(classes=names, tag='custom')

    def test_issue_preset_stages_packaged_treatment_with_all_requested_classes(self):
        preset = support.ISSUES[317]
        names = sorted(set(preset['census'] + preset['treatment']) |
                       {name for name, role in sampler.SAMPLE_CLASSES if role == 'calibration'})
        placements = {name: [(i, 0, i)] for i, name in enumerate(names)}
        pos = ('<map>' + ''.join('<group name="%s" pos="%s 0 %s"/>' % (n, i, i)
                                 for i, n in enumerate(preset['treatment'])) + '</map>').encode()
        proto = ('<prototype>' + ''.join('<group name="%s"/>' % n for n in preset['treatment']) + '</prototype>').encode()
        replacements = {'mapgroupproto.xml': proto, 'mapgrouppos.xml': pos}
        with patch.object(support, 'world_placements', return_value=(names, placements, {})), \
             patch.object(support, 'treatment_files', return_value=(replacements, {'commit': 'synthetic'})), \
             patch.object(support, 'stage_observation', side_effect=lambda *a, **kw:
                          self.fake_stage(run=kw['run']) if 'run' in kw else {}) as stage:
            plan = batch.prepare(issue=317)
        self.assertEqual(len(plan['runs']) + 1, stage.call_count)
        treatment_call = stage.call_args_list[-1]
        self.assertEqual(set(preset['treatment']), {t['class'] for t in treatment_call.args[1]})
        self.assertEqual(replacements, treatment_call.kwargs['replacements'])
        receipt = json.loads((self.root / 'interior-batch-317/evidence.json').read_bytes())
        self.assertEqual('synthetic', receipt['treatment']['commit'])

    def test_bad_inputs_and_read_only_mount_create_nothing(self):
        before = set(self.root.iterdir())
        for kwargs in ({'classes': ['A']}, {'classes': ['A', 'A'], 'tag': 'x'},
                       {'issue': 317, 'classes': ['A']}, {'tag': '../escape'}, {'run_size': 65}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                batch.prepare(**kwargs)
        with patch.object(batch.os, 'statvfs', return_value=SimpleNamespace(f_flag=batch.os.ST_RDONLY)), \
             redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(1, batch.main(['--issue', '317']))
        self.assertIn('read-only host mount', stderr.getvalue())
        self.assertEqual(before, set(self.root.iterdir()))

    def test_pin_and_native_cache_refusals_create_no_batch(self):
        with patch.object(runtime, '_hash_file', return_value=('wrong', 1)), self.assertRaises(ValueError):
            batch.prepare(issue=317)
        names = list(support.ISSUES[317]['census'])
        positions = {name: [(i, 0, i)] for i, name in enumerate(names)}
        native = self.root / '.cache/hollow-country/native-scripts/scripts-1.30.164289/3_Game'
        native.rmdir()
        with patch.object(support, 'world_placements', return_value=(names, positions, {})), \
             self.assertRaises(ValueError):
            batch.prepare(issue=317)
        self.assertFalse((self.root / 'interior-batch-317').exists())

    def test_missing_world_class_refuses_before_any_output(self):
        with patch.object(support, 'world_placements', return_value=(['Absent'], {}, {})), \
             self.assertRaises(ValueError):
            batch.prepare(classes=['Absent'], tag='missing')
        self.assertFalse((self.root / 'interior-batch-missing').exists())


class SupportTests(unittest.TestCase):
    def test_world_selection_adds_ungrouped_wrecks_and_resolves_config_spelling(self):
        names = list(support.ISSUES[317]['census'])
        extra = 'Land_Wreck_Synthetic'
        stock = 'Land_Wreck_Stock'
        world = [(n.lower(), 'model', i, 0, i, ()) for i, n in enumerate(names + [extra, stock])]
        validation = {'rows': len(world), 'matched': len(world), 'max_pos_m': 0}
        with patch.object(new_buildings, 'STOCK_POS_SHA256', runtime.sha256(b'synthetic')), \
             patch.object(new_buildings, 'read_world', return_value=(world, 'synthetic-world')), \
             patch.object(new_buildings, 'validate_world', return_value=validation), \
             patch.object(support.interior_points_gen, 'Assets', return_value=SimpleNamespace(
                 classes=dict.fromkeys(names + [extra, stock]))):
            selected, positions, evidence = support.world_placements(b'synthetic', [stock], names, include_wrecks=True)
            self.assertEqual(set(names + [extra]), set(selected))
            self.assertEqual(set(selected), set(positions))
            self.assertEqual('synthetic-world', evidence['wrp_sha256'])
            validation['matched'] -= 1
            with self.assertRaises(ValueError):
                support.world_placements(b'synthetic', [], names)

    def test_treatment_uses_packaging_outputs_and_records_each_hash(self):
        files = [('mapgroupproto.xml', b'before', b'proto'), ('mapgrouppos.xml', b'before', b'pos'),
                 ('db/types.xml', b'before', b'types')]
        source = {'mission': Path('/synthetic-stock')}
        with patch.object(support, 'clean_commit', return_value='synthetic'), \
             patch.object(support.loot_boost, 'shipped_points', return_value=b'overlay'), \
             patch.object(support.loot_boost, 'plan', return_value={
                 'files': files, 'counts': {'new_buildings': {'applied': True}}}) as plan, \
             patch.object(runtime, 'check_unchanged'):
            replacements, evidence = support.treatment_files(source)
        plan.assert_called_once_with(source['mission'], points=b'overlay')
        self.assertEqual({n: a for n, _, a in files}, replacements)
        self.assertEqual({n: runtime.sha256(a) for n, _, a in files}, evidence['files'])

    def test_clean_commit_refuses_dirty_checkout_and_git_failure(self):
        with patch.object(support.subprocess, 'run', return_value=SimpleNamespace(stdout=' M tooling.py\n')), \
             self.assertRaises(ValueError):
            support.clean_commit()
        with patch.object(support.subprocess, 'run', side_effect=support.subprocess.CalledProcessError(1, 'git')), \
             self.assertRaises(ValueError):
            support.clean_commit()

    def test_observation_writes_real_launcher_compatible_runtime_without_stock_row(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            source = make_source_runtime(parent / 'source')
            classes = list(support.ISSUES[317]['census'])
            placements = {name: [(i, 0, i)] for i, name in enumerate(classes)}
            run = sampler.plan_batches(classes, placements)['runs'][0]
            with patch.object(runtime, 'WSL_PARENT', parent), \
                 patch.object(runtime, 'DEFAULT_SOURCE_RUNTIME', str(source)), \
                 patch.object(runtime, 'BATTLEYE_SHA256', SYNTH_BE_SHA):
                destination = parent / 'interior-sampler-synthetic'
                plan = support.stage_observation(destination, run['targets'], run=run,
                                                 wait_minutes=30, native=None, evidence={'synthetic': True})
            self.assertEqual(run['native_run_id'], plan['probe']['native_run_id'])
            self.assertEqual(run['targets'], plan['targets'])
            # Existing reader/launcher format and generated hook; no engine execution.
            saved = json.loads((destination / sampler.PLAN_NAME).read_bytes())
            self.assertEqual(plan, saved)
            stock = source / 'stock-backup/mpmissions' / runtime.MISSION_NAME / 'mapgrouppos.xml'
            self.assertEqual(stock.read_bytes(), (destination / 'mpmissions' / runtime.MISSION_NAME / 'mapgrouppos.xml').read_bytes())

    def test_treatment_stages_packaged_pos_types_and_hashes_in_real_runtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            source = make_source_runtime(parent / 'source')
            name = support.ISSUES[317]['treatment'][0]
            replacements = {
                'mapgrouppos.xml': ('<map><group name="%s" pos="1 2 3"/></map>' % name).encode(),
                'mapgroupproto.xml': ('<prototype><group name="%s"/></prototype>' % name).encode(),
                'db/types.xml': b'<types><type name="Synthetic"/></types>',
            }
            targets = sampler.placements_tool.build_targets({name: [(1, 2, 3)]}, classes=((name, 'treatment'),))
            with patch.object(runtime, 'WSL_PARENT', parent), \
                 patch.object(runtime, 'DEFAULT_SOURCE_RUNTIME', str(source)), \
                 patch.object(runtime, 'BATTLEYE_SHA256', SYNTH_BE_SHA):
                destination = parent / 'ce-probe-synthetic'
                plan = support.stage_observation(destination, targets, wait_minutes=30, native=None,
                                                 evidence={}, replacements=replacements,
                                                 treatment={'commit': 'synthetic'})
            self.assertEqual('treatment', plan['variant'])
            self.assertEqual(targets, plan['targets'])
            mission = destination / 'mpmissions' / runtime.MISSION_NAME
            staged = {row['path']: row['sha256'] for row in plan['staged_files']}
            for path, data in replacements.items():
                self.assertEqual(data, (mission / path).read_bytes())
                self.assertEqual(runtime.sha256(data), staged['mpmissions/' + runtime.MISSION_NAME + '/' + path])
                self.assertNotEqual(data, (source / 'stock-backup/mpmissions' / runtime.MISSION_NAME / path).read_bytes())

    def test_calibration_points_reach_the_unchanged_sampler_hook(self):
        calibration = [name for name, role in sampler.SAMPLE_CLASSES if role == 'calibration']
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            source = make_source_runtime(parent / 'source')
            mission = source / 'stock-backup/mpmissions' / runtime.MISSION_NAME
            proto = ('<prototype>' + ''.join(
                '<group name="%s"><container name="lootFloor"><point pos="1 2 3"/></container></group>' % name
                for name in calibration) + '</prototype>').encode()
            (mission / 'mapgroupproto.xml').write_bytes(proto)
            launch = json.loads((source / 'launch-plan.json').read_bytes())
            for file in launch['mission_files']:
                if file['path'] == 'mapgroupproto.xml':
                    file['sha256'] = runtime.sha256(proto)
            (source / 'launch-plan.json').write_text(json.dumps(launch))
            placements = {name: [(i, 0, i)] for i, name in enumerate(calibration)}
            run = sampler.plan_batches(calibration, placements)['runs'][0]
            with patch.object(runtime, 'WSL_PARENT', parent), \
                 patch.object(runtime, 'DEFAULT_SOURCE_RUNTIME', str(source)), \
                 patch.object(runtime, 'BATTLEYE_SHA256', SYNTH_BE_SHA), \
                 patch.object(sampler, 'render_hook', wraps=sampler.render_hook) as render:
                support.stage_observation(parent / 'interior-sampler-calibration', run['targets'], run=run,
                                          wait_minutes=30, native=None, evidence={})
            expected = sampler.stock_frame_points(proto, calibration)
            self.assertEqual([(name, *point) for name in calibration for point in expected[name]],
                             render.call_args.kwargs['frame_points'])
