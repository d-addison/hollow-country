"""Synthetic adversarial behavioral regressions. Expected RED on the unmodified r6 source."""
import contextlib
import io
import json
from pathlib import Path
import sys
import unittest
from unittest import mock
HERE=Path(__file__).resolve().parent
SOURCE=HERE/'source'
sys.path.insert(0,str(SOURCE))
from tools.audit import interior_points as pts
from tests.unit import test_interior_points as tp

class ReviewRegressions(unittest.TestCase):
    def test_valid_baseline_builds(self):
        self.assertEqual('ok',pts.build_treatment(tp.encode(tp.full_census()),tp.STOCK,0.4)[1]['status'])

    def test_player_contributor_without_closed_codes_still_requires_door_evidence(self):
        for label in ('missing','not-restored','open-stalled'):
            with self.subTest(label=label):
                document=(HERE/('player-skip-'+label+'-census.json')).read_bytes()
                with self.assertRaises(ValueError):
                    pts.build_treatment(document,tp.STOCK,0.4,reach_source='player')

    def test_legacy_requested_state_observations_cannot_qualify_actual_phase_evidence(self):
        with self.assertRaises(ValueError):
            pts.build_treatment((HERE/'legacy-stalled-close-accepted-census.json').read_bytes(),tp.STOCK,0.4)

    def test_per_door_flags_and_phases_must_agree_with_the_counts(self):
        for label in ('already-open','locked-closed','invalid-phase','nonbinary-flags'):
            with self.subTest(label=label),self.assertRaises(ValueError):
                pts.build_treatment((HERE/('forged-'+label+'-census.json')).read_bytes(),tp.STOCK,0.4)

    def test_cli_refusal_cannot_follow_a_swapped_parent_into_the_checkout(self):
        parent=HERE/'regression-parent'
        saved=HERE/'regression-parent-saved'
        inside=SOURCE/'regression-inside'
        parent.mkdir()
        inside.mkdir()
        report=parent/'refusal.json'
        original=pts._write_refusal
        def replace_parent(path,error):
            parent.rename(saved)
            parent.symlink_to(inside,target_is_directory=True)
            original(path,error)
        with mock.patch.object(pts,'_write_refusal',replace_parent),contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(1,pts.main(['--radius','bad','--report',str(report)]))
        self.assertFalse((inside/'refusal.json').exists(),'report was written inside the source checkout')

    def test_finite_numeric_overflow_is_refused_with_a_report(self):
        for label in ('finite-overflow','tiny-grid'):
            with self.subTest(label=label):
                root=HERE/label
                report=root/'regression-report.json'
                with contextlib.redirect_stderr(io.StringIO()):
                    code=pts.main(['--census',str(root/'census.json'),'--stock-proto',str(root/'stock.xml'),
                                   '--output',str(root/'regression-treatment.xml'),'--report',str(report),'--min-calibration','0.4'])
                self.assertEqual(1,code)
                self.assertEqual('refused',json.loads(report.read_text())['status'])

if __name__=='__main__': unittest.main(verbosity=2)
