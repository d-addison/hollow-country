"""Synthetic mission/source/result fixtures; no native death/render proof."""
import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest import mock

from tools.setup import infected_death_probe as probe


class InfectedDeathProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='hc-synthetic-death-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.source=self.root/'source';self.source.mkdir()
        self.initial=(b'// SYNTHETIC stock-shaped factory, not installed assets.\n'
                      b'class CustomMission : MissionServer {}\n'
                      b'Mission CreateCustomMission(string path) { return new CustomMission(); }\n')
        (self.source/'init.c').write_bytes(self.initial)
        (self.source/'synthetic.xml').write_bytes(b'<synthetic/>')
        self.scripts=self.root/'synthetic-interfaces'
        for name,tokens in probe.INTERFACES.items():
            path=self.scripts/name;path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text('\n'.join(tokens),encoding='utf-8')
        self.dest=self.root/'fresh.chernarusplus'

    def prepare(self,**kw):
        args=dict(x=6500,z=6500,run_id='a'*32)
        args.update(kw)
        return probe.prepare_probe(self.source,self.dest,self.scripts,**args)

    def result(self,manifest):
        cases=[]
        for index,name in enumerate(probe.CASES):
            sample=dict(elapsed_seconds=2.,alive=False,health=0.,body_present=False,
                        body_dynamic=False,body_active=False,velocity_sampled=False,
                        position=[6500.,10.,6500.],velocity=[0.,0.,0.],bone_available=False,
                        spine=[0.,0.,0.],animation_uuid=0,death_processed=False)
            initial=copy.deepcopy(sample);initial.update(elapsed_seconds=0.,alive=True,health=100.)
            cases.append(dict(name=name,index=index,spawned=True,command_requested=index>0,
                              impulse_requested=False,impulse_applied=False,dead_observed=True,
                              cleanup_requested=True,cleanup_confirmed=True,samples=[initial,sample]))
        return dict(schema=1,kind=probe.KIND,run_id=manifest['run_id'],world='chernarusplus',
                    engine_version='1.30.164289',server_context=True,allow_observers=False,
                    max_observed_clients=0,complete=True,failed=False,reason='',
                    frames=100,heartbeat_count=5,cases=cases,render_observed=False,
                    replication_observed=False)

    def write_result(self,data):
        path=self.root/'synthetic-result.json';path.write_text(json.dumps(data),encoding='utf-8')
        return path

    def test_prepares_bounded_five_case_native_mission_and_preserves_factory_chain(self):
        manifest=self.prepare(impulse=(5,0,0))
        text=(self.dest/'init.c').read_text()
        self.assertEqual(self.initial,(self.source/'init.c').read_bytes())
        self.assertEqual(b'<synthetic/>',(self.dest/'synthetic.xml').read_bytes())
        self.assertIn('return new HCInfectedDeathProbeMission();',text)
        self.assertIn('class HCInfectedDeathProbeMission : CustomMission',text)
        self.assertEqual(list(probe.CASES),manifest['cases'])
        self.assertEqual(1,manifest['max_owned_actors'])
        self.assertEqual('pending',manifest['runtime_acceptance'])
        self.assertTrue((self.dest/probe.MARKER).is_file())
        self.assertEqual(hashlib.sha256(self.initial).hexdigest(),manifest['files']['init.c']['source_sha256'])
        self.assertEqual(hashlib.sha256((self.dest/'init.c').read_bytes()).hexdigest(),manifest['files']['init.c']['staged_sha256'])

    def test_immediate_kickoff_diagnostic_gate_native_primitives_and_bounded_cleanup(self):
        self.prepare();text=(self.dest/'init.c').read_text()
        for token in ('#ifdef DIAG_DEVELOPER','HCDeathTick();','CALL_CATEGORY_SYSTEM',
                      'GetUpdateQueue','GetPlayerIndentities','CreateObjectEx',
                      'ECE_INITAI','ZmbF_JournalistNormal_Blue','SetHealth("", "Health", 0)',
                      'ANIM_DEATH_DEFAULT','ANIM_DEATH_IMPULSE','ANIM_DEATH_BACKSTAB',
                      'ANIM_DEATH_NECKSTAB','StartCommand_Death','dBodyIsSet',
                      'dBodyIsDynamic','dBodyApplyImpulse','GetBonePositionWS',
                      'GetCurrentAnimationInstanceUUID','ObjectDelete',
                      'cleanup_confirmed = !m_Owned','override void OnMissionFinish()',
                      'Remove(HCDeathTick)','Remove(HCDeathFrame)'):
            self.assertIn(token,text)
        for forbidden in ('PhysicsSetRagdoll','SetPosition(','CreatePlayer(','GetCurrentCommandID(',
                          'modded class ZombieBase','MakeScreenshot('):
            self.assertNotIn(forbidden,text)
        self.assertIn('render_observed = false',text)
        self.assertIn('m_Case.samples.Count() >= 32',text)
        self.assertIn('m_Receipt.frames > 20000',text)
        self.assertLess(text.index('HCDeathTick();'),text.index('CallLater(HCDeathTick'))

    def test_arguments_fail_before_output(self):
        for args in (dict(x=math.nan),dict(z=0),dict(x=True),dict(x=100001),
                     dict(seconds_per_case=0),dict(seconds_per_case=6),dict(seconds_per_case=True),
                     dict(impulse=(121,0,0)),dict(impulse=(1,2)),dict(impulse=(math.inf,0,0)),
                     dict(impulse=(.00000001,0,0)),
                     dict(allow_observers=1),dict(run_id='../bad')):
            with self.subTest(args=tuple(args)):
                with self.assertRaises(ValueError): self.prepare(**args)
                self.assertFalse(self.dest.exists())

    def test_interfaces_missing_or_changed_fail_before_output(self):
        path=self.scripts/next(iter(probe.INTERFACES))
        path.write_text('// synthetic incompatible interface')
        with self.assertRaises(ValueError): self.prepare()
        self.assertFalse(self.dest.exists())

    def test_previous_instrumentation_profiles_factory_ambiguity_and_overlap_refused(self):
        for data in (self.initial+b'\n// HCInfectedDeathProbeMission',
                     self.initial+self.initial,self.initial.replace(b'new CustomMission()',b'new OtherMission()')):
            (self.source/'init.c').write_bytes(data)
            with self.assertRaises(ValueError): self.prepare()
            self.assertFalse(self.dest.exists())
        (self.source/'init.c').write_bytes(self.initial)
        storage=self.source/'storage_1';storage.mkdir()
        with self.assertRaises(ValueError): self.prepare()
        storage.rmdir()
        with self.assertRaises(ValueError): probe.prepare_probe(self.source,self.source/'nested',self.scripts,x=1,z=1)
        self.prepare()
        with self.assertRaises(ValueError): self.prepare()

    def test_symlinks_and_reparse_inputs_are_refused(self):
        target=self.source/'synthetic.xml';link=self.source/'linked.xml'
        try: link.symlink_to(target)
        except (OSError,NotImplementedError): self.skipTest('symlink privilege unavailable; reparse guard tested separately')
        with self.assertRaises(ValueError): self.prepare()
        self.assertFalse(self.dest.exists())

    def test_native_interface_provenance_records_hashes_not_game_source(self):
        manifest=self.prepare()
        for name,record in manifest['interfaces'].items():
            self.assertEqual({'sha256','bytes'},set(record))
            self.assertEqual(hashlib.sha256((self.scripts/name).read_bytes()).hexdigest(),record['sha256'])
        self.assertEqual([0,0,0],manifest['impulse'])
        self.assertFalse(manifest['allow_observers'])
        self.assertTrue(manifest['outer_timeout_required'])

    def test_reparse_guard_does_not_require_windows_symlink_privilege(self):
        with mock.patch.object(probe.os,'lstat',return_value=NS(st_mode=0o100644,st_file_attributes=1024)):
            with self.assertRaises(ValueError): self.prepare()

    def test_malformed_marker_and_boolean_schema_are_value_errors(self):
        manifest=self.prepare();path=self.write_result(self.result(manifest))
        marker=self.dest/probe.MARKER
        for value in ({'schema':1,'kind':probe.KIND,'cases':list(probe.CASES)},
                      dict(manifest,spawn_xz=None),dict(manifest,schema=True)):
            marker.write_text(json.dumps(value))
            with self.subTest(fields=tuple(value)):
                with self.assertRaises(ValueError): probe.validate_result(path,self.dest,outer_timed_out=False)
        marker.write_text(json.dumps(manifest))
        value=self.result(manifest);value['schema']=True
        with self.assertRaises(ValueError): probe.validate_result(self.write_result(value),self.dest,outer_timed_out=False)

    def test_short_window_or_missing_live_control_cannot_complete(self):
        manifest=self.prepare()
        for field,value in (('elapsed_seconds',.5),('alive',True)):
            receipt=self.result(manifest);receipt['cases'][0]['samples'][-1][field]=value
            with self.assertRaises(ValueError): probe.validate_result(self.write_result(receipt),self.dest,outer_timed_out=False)
        receipt=self.result(manifest);receipt['cases'][0]['samples'][0]['alive']=False
        with self.assertRaises(ValueError): probe.validate_result(self.write_result(receipt),self.dest,outer_timed_out=False)

    def test_result_validation_is_not_render_or_network_acceptance(self):
        manifest=self.prepare();path=self.write_result(self.result(manifest))
        report=probe.validate_result(path,self.dest,outer_timed_out=False)
        self.assertTrue(report['authoritative_observations_complete'])
        self.assertFalse(report['visual_acceptance'])
        self.assertFalse(report['replication_acceptance'])
        self.assertFalse(report['feature_complete'])
        self.assertEqual('synthetic-result.json',path.name)

    def test_timeout_never_promotes_even_structurally_complete_receipt(self):
        manifest=self.prepare();path=self.write_result(self.result(manifest))
        for timeout in (True,None,0):
            with self.assertRaises(ValueError): probe.validate_result(path,self.dest,outer_timed_out=timeout)

    def test_stale_invalid_incomplete_cleanup_or_lifecycle_receipts_refused(self):
        manifest=self.prepare();good=self.result(manifest)
        cases=[dict(run_id='b'*32),dict(complete=False),dict(failed=True),dict(reason='deadline'),
               dict(server_context=False),dict(render_observed=True),dict(max_observed_clients=1),
               dict(cases=[]),dict(cases=good['cases'][:-1]),dict(frames=20001)]
        for field in ('spawned','dead_observed','cleanup_requested','cleanup_confirmed'):
            broken=copy.deepcopy(good['cases']);broken[0][field]=False;cases.append(dict(cases=broken))
        broken=copy.deepcopy(good['cases']);broken[0]['samples'][0]['position'][0]=math.nan
        cases.append(dict(cases=broken))
        for changes in cases:
            with self.subTest(changes=tuple(changes)):
                value=copy.deepcopy(good);value.update(changes)
                with self.assertRaises(ValueError): probe.validate_result(self.write_result(value),self.dest,outer_timed_out=False)
        for value in (None,[],{'schema':1}):
            with self.assertRaises(ValueError): probe.validate_result(self.write_result(value),self.dest,outer_timed_out=False)

    def test_tampered_staged_hook_and_duplicate_json_refused(self):
        manifest=self.prepare();path=self.write_result(self.result(manifest))
        initial=(self.dest/'init.c').read_bytes()
        (self.dest/'init.c').write_bytes(initial+b'\n// drift')
        with self.assertRaises(ValueError): probe.validate_result(path,self.dest,outer_timed_out=False)
        (self.dest/'init.c').write_bytes(initial)
        path.write_text('{"schema":1,"schema":1}')
        with self.assertRaises(ValueError): probe.validate_result(path,self.dest,outer_timed_out=False)

    def test_interrupted_copy_keeps_partial_unmarked_and_never_overwrites(self):
        actual=probe.staging._unchanged;calls=[]
        def source_changed(path,info):
            calls.append(path)
            if len(calls)==2: raise ValueError('synthetic source drift during copy')
            return actual(path,info)
        with mock.patch.object(probe.staging,'_unchanged',side_effect=source_changed):
            with self.assertRaises(ValueError): self.prepare()
        self.assertTrue(self.dest.exists())
        self.assertFalse((self.dest/probe.MARKER).exists())
        with self.assertRaises(ValueError): self.prepare()
        self.assertEqual(self.initial,(self.source/'init.c').read_bytes())

    def test_cli_prepare_and_required_outer_result_contract(self):
        def cli(*args):
            return subprocess.run([sys.executable,'-B','-m','tools.setup.infected_death_probe',*map(str,args)],
                                  cwd=Path(__file__).resolve().parents[2],capture_output=True,text=True)
        run=cli('prepare','--source',self.source,'--out',self.dest,'--scripts',self.scripts,'--x',6500,'--z',6500)
        self.assertEqual(0,run.returncode,run.stderr)
        manifest=json.loads((self.dest/probe.MARKER).read_text())
        path=self.write_result(self.result(manifest))
        args=('validate','--receipt',path,'--mission',self.dest)
        self.assertNotEqual(0,cli(*args).returncode)
        self.assertNotEqual(0,cli(*args,'--outer-outcome','timed-out').returncode)
        run=cli(*args,'--outer-outcome','finished')
        self.assertEqual(0,run.returncode,run.stderr)
        self.assertFalse(json.loads(run.stdout)['feature_complete'])


if __name__=='__main__': unittest.main()
