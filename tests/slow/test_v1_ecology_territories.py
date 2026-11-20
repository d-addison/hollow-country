"""Explicit tiny XML fixtures, never a native territory acceptance claim."""
import importlib
import json
from pathlib import Path
import tempfile
import unittest


class TerritoryAuditBehavior(unittest.TestCase):
    def setUp(self):
        self.audit=importlib.import_module('tools.audit.ecology_territories')
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);(self.root/'db').mkdir();(self.root/'env').mkdir()
        (self.root/'db/globals.xml').write_text('<variables><var name="AnimalMaxCount" type="0" value="200"/><var name="ZombieMaxCount" type="0" value="1000"/></variables>')
        self.animal=self.root/'env/animal.xml';self.infected=self.root/'env/infected.xml'
        self.animal.write_text('<territory-type><territory><zone name="Water" smin="0" smax="0" dmin="0" dmax="0" x="10" z="20" r="30"/><zone name="Graze" smin="0" smax="0" dmin="0" dmax="0" x="50" z="60" r="40"/></territory></territory-type>')
        self.infected.write_text('<territory-type><territory><zone name="Village" smin="0" smax="0" dmin="4" dmax="6" x="100" z="200" r="50"/></territory></territory-type>')

    def run_audit(self):
        return self.audit.audit(self.root,'synthetic-world',[('animal','env/animal.xml'),('infected','env/infected.xml')])

    def test_all_zones_retained_zero_animal_density_is_unknown_not_extinction(self):
        result=self.run_audit();self.assertEqual(3,len(result['zones']))
        self.assertEqual({'animal':200,'infected':1000},result['globals'])
        self.assertIsNone(result['zones'][0]['capacity_ceiling'])
        self.assertEqual(6,result['zones'][2]['capacity_ceiling'])
        self.assertEqual('PENDING',result['runtime_acceptance'])
        self.assertFalse(result['live_occupancy_known'])
        self.assertEqual(['Water','Graze','Village'],[z['name'] for z in result['zones']])
        self.assertEqual(3,len({z['id'] for z in result['zones']}))
        self.assertEqual(result,self.run_audit())
        json.dumps(result,allow_nan=False)

    def test_missing_global_does_not_invent_capacity(self):
        (self.root/'db/globals.xml').write_text('<variables/>')
        result=self.run_audit();self.assertIsNone(result['globals']['infected'])
        self.assertIsNone(result['zones'][2]['capacity_ceiling'])

    def test_malformed_negative_nonfinite_inverted_or_oversized_data_rejected(self):
        original=self.infected.read_text()
        for before,after in [('dmax="6"','dmax="3"'),('r="50"','r="-1"'),('x="100"','x="nan"'),('dmin="4"','dmin="-1"')]:
            self.infected.write_text(original.replace(before,after))
            with self.assertRaises(ValueError):self.run_audit()
        self.infected.write_text(' '* (self.audit.MAX_BYTES+1))
        with self.assertRaises(ValueError):self.run_audit()

    def test_duplicate_input_traversal_symlink_and_doctype_rejected(self):
        for files in [[('animal','env/animal.xml')]*2,[('animal','../outside.xml')]]:
            with self.assertRaises(ValueError):self.audit.audit(self.root,'synthetic-world',files)
        self.infected.unlink();self.infected.symlink_to(self.animal)
        with self.assertRaises(ValueError):self.run_audit()
        self.infected.unlink();self.infected.write_text('<!DOCTYPE x [<!ENTITY y "z">]><territory-type/>')
        with self.assertRaises(ValueError):self.run_audit()

    def test_zone_budget_rejects_instead_of_silently_truncating(self):
        self.audit.MAX_ZONES=2
        try:
            with self.assertRaises(ValueError):self.run_audit()
        finally:self.audit.MAX_ZONES=10000
