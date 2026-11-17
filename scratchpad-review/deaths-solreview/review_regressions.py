"""Expected-red review regressions; all writes are scratch-only, all inputs synthetic.
The path-reader stub is limited to synthetic scratch inputs and does not replace
the real reader for the production policy source being checked.
"""
import contextlib
import importlib
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT/'tests/unit')]
sys.dont_write_bytecode = True
p = importlib.import_module('tools.setup.death_selection_probe')
t = importlib.import_module('test_death_selection_probe')
POLICY = ROOT/'mods/HollowCountry/scripts/4_World/Infected/HCInfectedDeathPolicy.c'
INTERFACES = {n:'\n'.join(v).encode() for n,v in p.INTERFACES.items()}

class ReviewRegressions(unittest.TestCase):
    def cli_args(self, suffix, with_selection):
        fixture = OUT/'regression_fixtures'/suffix
        fixture.mkdir(parents=True,exist_ok=True)
        if (fixture/'stage').exists():
            import shutil
            shutil.rmtree(fixture/'stage')
        args = ['--stock-init',str(fixture/'init.c'),'--interfaces',str(fixture/'native'),
                '--destination',str(fixture/'stage'),'--victim','100','100','--source','102','100',
                '--policy-source',str(POLICY),'--run-id','a'*32]
        if with_selection: args += ['--selection','policy']
        original = p._read
        def synthetic_reader(path,limit):
            path = Path(path)
            if path == fixture/'init.c': return t.STOCK
            for name,blob in INTERFACES.items():
                if path == fixture/'native'/name: return blob
            return original(path,limit)
        return args,synthetic_reader

    def test_documented_cli_can_read_the_production_policy(self):
        args,reader = self.cli_args('documented',True)
        with patch.object(p,'_read',reader),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0,p.main(args))

    def test_cli_refuses_policy_source_without_selection(self):
        args,reader = self.cli_args('stray_policy',False)
        with patch.object(p,'_read',reader),contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises((ValueError,SystemExit)):
                p.main(args)

    def test_policy_receipt_requires_two_seconds_after_the_command(self):
        files = p.generate_probe(t.STOCK,dict(t.request(),selection='policy'),INTERFACES,
                                 run_id='a'*32,policy_source=POLICY.read_bytes())
        row = t.policy_receipt(p,files)
        for case in row['cases']:
            case['command_elapsed'] = case['delete_elapsed']-.01
        with self.assertRaises(ValueError):
            p.validate_receipt(json.dumps(row).encode(),files,outer_timed_out=False,outer_elapsed_seconds=80)

if __name__=='__main__': unittest.main(verbosity=2)
