"""Synthetic operator XML fixtures; no engine/visual acceptance."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

from tools.package import atmosphere as a


def fixture():
    root = ET.Element('weather', reset='0', enable='0')
    for name in ('overcast', 'fog', 'rain', 'windMagnitude', 'windDirection', 'snowfall'):
        node = ET.SubElement(root, name)
        high = '20' if name == 'windMagnitude' else '1'
        low = '-3.14' if name == 'windDirection' else '0'
        if name == 'windDirection': high = '3.14'
        if name == 'snowfall': high = '0'
        ET.SubElement(node, 'current', actual='0', time='120', duration='240')
        ET.SubElement(node, 'limits', min=low, max=high)
        ET.SubElement(node, 'timelimits', min='60', max='900')
        ET.SubElement(node, 'changelimits', min='0', max=high)
        if name in ('rain', 'snowfall'):
            ET.SubElement(node, 'thresholds', min='0.6', max='1', end='60')
    ET.SubElement(root, 'storm', density='1', threshold='0.9', timeout='45')
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


class AtmosphereTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'cfgweather.xml'
        self.stock = fixture()
        self.source.write_bytes(self.stock)
        self.profile = dict(schema=1, name='operator-test', world='chernarusplus',
                            build='1.30.164289', source_sha256=hashlib.sha256(self.stock).hexdigest(),
                            enable=True, reset=False, overrides={})

    def generate(self, **kw):
        profile = copy.deepcopy(self.profile)
        profile.update(kw)
        return a.generate(self.source, profile)

    def test_explicit_delta_preserves_other_native_defaults_and_source(self):
        overrides = {'fog': {'current': {'actual': .1}, 'limits': {'max': .2}},
                     'windDirection': {'changelimits': {'min': -1, 'max': 1}}}
        files = self.generate(overrides=overrides)
        self.assertEqual(self.stock, self.source.read_bytes())
        old, new = ET.fromstring(self.stock), ET.fromstring(files['cfgweather.xml'])
        self.assertEqual('1', new.get('enable'))
        self.assertEqual('0', new.get('reset'))
        for name in ('overcast', 'rain', 'windMagnitude', 'snowfall', 'storm'):
            self.assertEqual(ET.tostring(old.find(name)), ET.tostring(new.find(name)))
        self.assertEqual(.1, float(new.find('fog/current').get('actual')))
        report = json.loads(files['atmosphere-report.json'])
        self.assertEqual(self.profile['source_sha256'], report['source_sha256'])
        self.assertEqual('pending', report['runtime_acceptance'])
        self.assertFalse(report['feature_complete'])
        self.assertEqual(overrides, report['profile']['overrides'])

    def test_noop_is_byte_exact_and_deterministic(self):
        first = self.generate(enable=False)
        self.assertEqual(self.stock, first['cfgweather.xml'])
        self.assertEqual(first, self.generate(enable=False))

    def test_profile_unknown_types_nonfinite_and_pin_fail_closed(self):
        cases = [dict(schema=True), dict(schema=2), dict(name='../bad'), dict(world='unknown'),
                 dict(build='unqualified'), dict(source_sha256='0'*64), dict(enable=1),
                 dict(reset='false'), dict(unexpected=1), dict(overrides=[]),
                 dict(overrides={'lighting': {'value': 1}}),
                 dict(overrides={'fog': {'current': {'actual': True}}}),
                 dict(overrides={'fog': {'current': {'actual': float('nan')}}}),
                 dict(overrides={'fog': {'current': {'actual': float('inf')}}}),
                 dict(overrides={'fog': {'current': {'actual': '0.2'}}}),
                 dict(overrides={'fog': {'current': {'bogus': 0}}}),
                 dict(overrides={'storm': {'density': -1}})]
        for kw in cases:
            with self.subTest(kw=tuple(kw)):
                with self.assertRaises(ValueError): self.generate(**kw)

    def test_correlated_ranges_times_windows_and_world_disabled_phenomena(self):
        cases = [
            {'fog': {'limits': {'min': .8, 'max': .2}}},
            {'fog': {'limits': {'min': .2}}},
            {'fog': {'current': {'time': -1}}},
            {'fog': {'current': {'duration': 86401}}},
            {'fog': {'timelimits': {'min': 0}}},
            {'fog': {'timelimits': {'min': 901}}},
            {'rain': {'thresholds': {'min': .9, 'max': .8}}},
            {'rain': {'thresholds': {'end': 0}}},
            {'overcast': {'limits': {'max': .5}}},
            {'windMagnitude': {'limits': {'max': 20.1}}},
            {'windDirection': {'current': {'actual': 4}}},
            {'storm': {'timeout': 0}},
            {'snowfall': {'limits': {'max': .5}}},
        ]
        for overrides in cases:
            with self.subTest(overrides=overrides):
                with self.assertRaises(ValueError): self.generate(overrides=overrides)

    def test_unknown_duplicate_missing_and_hostile_xml_rejected(self):
        cases = [self.stock.replace(b'<fog>', b'<bogus>'),
                 self.stock.replace(b'</weather>', b'<storm density="1" threshold="0.9" timeout="45"/></weather>'),
                 self.stock.replace(b'<fog>', b'<fog surprise="1">'),
                 self.stock.replace(b'</fog>', b'<limits min="0" max="1"/></fog>'),
                 self.stock.replace(b'<weather ', b'<weather bogus="1" '),
                 self.stock.replace(b'<weather ', b'<weather xmlns="urn:unexpected" '),
                 b'<!DOCTYPE weather [<!ENTITY x "x">]><weather>&x;</weather>',
                 self.stock.decode().encode('utf-16'),
                 self.stock.replace(b'<fog>', b'<fog>unexpected'),
                 b'<' * (a.MAX_XML_BYTES+1)]
        for data in cases:
            self.source.write_bytes(data)
            p=copy.deepcopy(self.profile);p['source_sha256']=hashlib.sha256(data).hexdigest()
            with self.assertRaises(ValueError): a.generate(self.source,p)

    def test_duplicate_profile_keys_and_bounded_json(self):
        path=self.root/'profile.json'
        for data in (b'{"schema":1,"schema":1}', b'{"x":NaN}',
                     b' '* (a.MAX_JSON_BYTES+1), b'['*10000):
            path.write_bytes(data)
            with self.assertRaises(ValueError): a.load_profile(path)

    def test_foreign_encoding_and_comment_tail_text_are_rejected(self):
        cases=(self.stock.replace(b"encoding='utf-8'", b"encoding='iso-8859-1'"),
               self.stock.replace(b'</weather>', b'<!-- harmless comment -->unexpected</weather>'))
        for data in cases:
            self.source.write_bytes(data)
            profile=copy.deepcopy(self.profile)
            profile['source_sha256']=hashlib.sha256(data).hexdigest()
            with self.subTest(encoding_or_tail=data[:60]):
                with self.assertRaises(ValueError): a.generate(self.source,profile)

    def test_fresh_roundtrip_provenance_and_tamper_refusal(self):
        dest=self.root/'candidate';files=self.generate()
        a.write_candidate(dest,files)
        self.assertEqual('pending', a.validate_candidate(dest,self.source)['runtime_acceptance'])
        self.assertTrue(a.validate_candidate(dest,self.source)['source_verified'])
        self.assertFalse(a.validate_candidate(dest)['source_verified'])
        with self.assertRaises(ValueError): a.write_candidate(dest,files)
        path=dest/'cfgweather.xml';path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaises(ValueError): a.validate_candidate(dest)

    def test_rehashed_unsafe_or_changed_defaults_not_accepted(self):
        for value in ('nan','0.5'):
            dest=self.root/('case-'+value);files=self.generate()
            root=ET.fromstring(files['cfgweather.xml']);root.find('fog/current').set('actual',value)
            files['cfgweather.xml']=ET.tostring(root)
            report=json.loads(files['atmosphere-report.json'])
            report['candidate_sha256']=hashlib.sha256(files['cfgweather.xml']).hexdigest()
            files['atmosphere-report.json']=a.encode(report)
            manifest=json.loads(files['atmosphere-manifest.json'])
            manifest['files']['cfgweather.xml']=hashlib.sha256(files['cfgweather.xml']).hexdigest()
            manifest['files']['atmosphere-report.json']=hashlib.sha256(files['atmosphere-report.json']).hexdigest()
            files['atmosphere-manifest.json']=a.encode(manifest)
            # Unsafe XML is rejected even with a matching digest; coherent
            # repinning still requires reconstruction from the trusted source.
            if value=='nan':
                with self.assertRaises(ValueError): a.write_candidate(dest,files)
            else:
                a.write_candidate(dest,files)
                with self.assertRaises(ValueError): a.validate_candidate(dest,self.source)

    def test_bundle_extra_files_and_invalid_metadata_refused(self):
        for bad in (None, [], {'schema':1}):
            files=self.generate();files['atmosphere-report.json']=a.encode(bad)
            with self.assertRaises(ValueError): a.write_candidate(self.root/'bad',files)
            self.assertFalse((self.root/'bad').exists())
        dest=self.root/'candidate';a.write_candidate(dest,self.generate())
        (dest/'unrelated').write_text('preserve')
        with self.assertRaises(ValueError): a.validate_candidate(dest)
        self.assertEqual('preserve',(dest/'unrelated').read_text())

    def test_write_failure_removes_only_its_own_fresh_candidate(self):
        dest=self.root/'candidate';files=self.generate()
        with mock.patch.object(a,'_write_file',side_effect=OSError('synthetic write failure')):
            with self.assertRaises(OSError): a.write_candidate(dest,files)
        self.assertFalse(dest.exists())
        a.write_candidate(dest,files)

    def test_late_failure_preserves_unrelated_data_and_incomplete_is_refused(self):
        dest=self.root/'candidate';files=self.generate();real_write=a._write_file
        def fail_late(path,data):
            if path.name=='atmosphere-report.json':
                (dest/'operator-note').write_text('preserve')
                raise OSError('synthetic second-write failure')
            return real_write(path,data)
        with mock.patch.object(a,'_write_file',side_effect=fail_late):
            with self.assertRaises(OSError): a.write_candidate(dest,files)
        self.assertEqual(['operator-note'],[p.name for p in dest.iterdir()])
        self.assertEqual('preserve',(dest/'operator-note').read_text())
        with self.assertRaises(ValueError): a.validate_candidate(dest)
        with self.assertRaises(ValueError): a.write_candidate(dest,files)

    def test_steam_and_existing_empty_destinations_are_refused(self):
        parent=self.root/'steamapps';parent.mkdir();dest=parent/'candidate'
        with self.assertRaises(ValueError): a.write_candidate(dest,self.generate())
        self.assertFalse(dest.exists())
        dest=self.root/'empty';dest.mkdir()
        with self.assertRaises(ValueError): a.write_candidate(dest,self.generate())
        self.assertEqual([],list(dest.iterdir()))

    def test_symlink_and_reparse_guards(self):
        dest=self.root/'candidate'
        link=self.root/'linked.xml'
        try: link.symlink_to(self.source)
        except (OSError,NotImplementedError): pass
        else:
            with self.assertRaises(ValueError): a.generate(link,self.profile)
        with mock.patch.object(a.os,'lstat',return_value=type('S',(),{'st_mode':0o100644,'st_file_attributes':1024})()):
            with self.assertRaises(ValueError): a.generate(self.source,self.profile)
        a.write_candidate(dest,self.generate())
        self.assertTrue((dest/'cfgweather.xml').is_file())

    def test_cli_generate_validate_and_refuse_overwrite(self):
        p=self.root/'profile.json';p.write_bytes(a.encode(self.profile));dest=self.root/'cli'
        tool=Path(a.__file__)
        def cli(*args):
            return subprocess.run([sys.executable,'-B',str(tool),*map(str,args)],capture_output=True,text=True)
        run=cli('generate','--source',self.source,'--profile',p,'--output',dest)
        self.assertEqual(0,run.returncode,run.stderr)
        run=cli('validate','--candidate',dest,'--source',self.source)
        self.assertEqual(0,run.returncode,run.stderr)
        self.assertNotEqual(0,cli('generate','--source',self.source,'--profile',p,'--output',dest).returncode)


if __name__=='__main__': unittest.main()
