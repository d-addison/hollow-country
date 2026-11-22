"""Synthetic staging tests; generated source is not native acceptance."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from tools.setup import stamina_transport_probe as probe


class StaminaTransportProbeTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.native=self.root/'synthetic-native'
        self.out=self.root/'probe'
        for name,tokens in probe.INTERFACES.items():
            file=self.native/name
            file.parent.mkdir(parents=True,exist_ok=True)
            file.write_text('// SYNTHETIC interface fixture\n'+'\n'.join(tokens))

    def test_hashes_without_execution_claim(self):
        result=probe.prepare(self.out,self.native)
        self.assertEqual('not-run',result['execution'])
        self.assertEqual('pending',result['runtime_acceptance'])
        self.assertEqual('disabled',result['rpc_probe'])
        self.assertEqual(result,json.loads((self.out/'manifest.json').read_text()))
        for root,key in ((self.out,'generated_sources'),(self.native,'native_sources')):
            self.assertTrue(result[key])
            for name,digest in result[key].items():
                self.assertEqual(digest,hashlib.sha256((root/name).read_bytes()).hexdigest())

    def test_missing_interface_creates_nothing(self):
        (self.native/'3_Game/gameplay.c').write_text('// APIs missing')
        with self.assertRaises(ValueError):
            probe.prepare(self.out,self.native)
        self.assertFalse(self.out.exists())

    def test_preserves_existing_output_and_rejects_symlinks(self):
        self.out.mkdir()
        (self.out/'keep').write_text('preserve')
        with self.assertRaises(ValueError):
            probe.prepare(self.out,self.native)
        self.assertEqual('preserve',(self.out/'keep').read_text())
        link=self.root/'link'
        link.symlink_to(self.native,target_is_directory=True)
        with self.assertRaises(ValueError):
            probe.prepare(link/'new',self.native)
        self.assertFalse((self.native/'new').exists())

    def test_local_probe_uses_observed_native_context(self):
        probe.prepare(self.out,self.native)
        source=(self.out/'scripts/3_Game/HCStaminaTransportProbe.c').read_text()
        for token in ('modded class ITEM_StaminaData','new ITEM_StaminaData',
                      'new CfgGameplayJson','PlayerData.StaminaData',
                      'WriteToString','ReadFromString','new ScriptReadWriteContext',
                      'GetWriteContext()','GetReadContext()',
                      'Param1<CfgGameplayJson>','HCProbeStaticWrapper'):
            self.assertIn(token,source)
        self.assertNotIn('rpc.Send(',source)

    def test_rpc_is_explicitly_opt_in_and_targeted(self):
        result=probe.prepare(self.out,self.native,matched_rpc=True)
        self.assertEqual('opt-in-matched-pair',result['rpc_probe'])
        source=(self.out/'scripts/3_Game/HCStaminaTransportProbe.c').read_text()
        mission=(self.out/'scripts/5_Mission/HCStaminaTransportMission.c').read_text()
        for token in ('rpc.Send(null, 4853791, true, identity)',
                      'sender || target','Seen.Count() >= 2'):
            self.assertIn(token,source)
        self.assertIn('OnClientReadyEvent',mission)

    def test_markers_never_promote_acceptance(self):
        result=probe.observe('[HC Stamina Transport] LOCAL json=1 context=1 static=1')
        self.assertEqual('local-marker-only',result['observation'])
        self.assertEqual('pending',result['runtime_acceptance'])
        self.assertEqual('unknown',result['network_roundtrip'])
        self.assertEqual('unknown',probe.observe('PASS')['observation'])

    def test_control_matrix(self):
        for token in ('ContextScalar(false);','ContextScalar(true);','packet.Serialize(writer)','copy.Deserializer(reader)'):
            self.assertIn(token,probe.LOCAL)
        for case in ('defaults','custom'):
            for mode in ('wrapper','param'):
                self.assertIn('ContextCfg("'+case+'-'+mode+'"',probe.LOCAL)

    def test_param_source_is_hashed(self):
        self.assertIn('1_Core/param.c',probe.INTERFACES)
        self.assertIn('return ctx.Write(param1)',probe.INTERFACES['1_Core/param.c'])

    def test_control_marker_remains_diagnostic(self):
        result=probe.observe('[HC Stamina Transport] CONTROL defaults-param writer=true reader=false fields=max=-1 schema=-1 exertion=-1 recovery=-1')
        self.assertEqual([dict(case='defaults-param',writer_ok=True,reader_ok=False,fields='max=-1 schema=-1 exertion=-1 recovery=-1')],result['local_controls'])
        self.assertEqual('unknown',result['network_roundtrip'])
        self.assertEqual('pending',result['runtime_acceptance'])
