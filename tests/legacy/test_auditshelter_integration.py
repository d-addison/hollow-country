"""Reviewable shared edits tested only in local, in-memory fixture copies.

The worker does not own the existing test modules or package allowlist. Exact
proposed changes are exposed by proposed_edits(); no shared file is written.
"""
import io
from pathlib import Path
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def replace_pending(source, before, after):
    """Accept the exact integrated edit; fail closed on unexpected fixture drift."""
    if after in source:
        return source
    if before not in source:
        raise AssertionError('Shared fixture changed; review the proposed edit again')
    return source.replace(before, after)


def proposed_edits():
    edits = {}
    path = 'tools/package/pbo.py'
    old = (ROOT / path).read_text()
    edits[path] = replace_pending(old, "'travel/route-surveys.json', 'travel/wreck-dispositions.json'", "'travel/route-surveys.json', 'travel/auditshelter_scenes.json', 'travel/wreck-dispositions.json'")

    path = 'tests/legacy/test_w47_shelters.py'
    old = (ROOT / path).read_text()
    new = replace_pending(old, "'excluded-missing-site-access-clearance'", "'authored-exterior-scene-native-access-pending'")
    new = replace_pending(new, "['site-terrain-clearance', 'outside-to-roof-path', 'scene-prop-slots']", "['native-site-access-and-clearance-verdict']")
    new = replace_pending(new, "self.assertEqual(0, row['authored_props'])", "self.assertEqual(3, row['authored_props'])")
    new = replace_pending(new, ".replace('HCShelterSurvey', 'HCEventSurvey')", ".replace('HCShelterSurvey', 'HCEventSurvey').replace('HCShelterRegionalConfig ', 'HCEventConfig ')")
    new = replace_pending(new, 'HCShelterCatalog=N(CandidateCount=', 'HCShelterCatalog=N(HCRegionalConfig=lambda: N(Enabled=True, Scenes=[N(Enabled=True), N(Enabled=True)]), CandidateCount=')
    new = replace_pending(new, 'candidate=synthetic-a excluded=site_access_missing', 'candidate=synthetic-a admission=authored_exterior_scene access=site_access_missing')
    new = replace_pending(new, 'candidate=synthetic-b excluded=scene_slots_missing', 'candidate=synthetic-b admission=authored_exterior_scene access=scene_slots_missing')
    edits[path] = new

    path = 'tests/legacy/test_hc_module_readiness_wave16.py'
    old = (ROOT / path).read_text()
    before = """    (S / 'Travel/HCShelterModule.c', 'HCShelterModule', 'Shelters', None, [
        ('ready', None, {'m_Started': True, 'm_Placed': 3}, False, {}),
        ('degraded', 'no_shelter_placed', {'m_Started': True, 'm_Placed': 0}, False, {}),
        ('off', OFF, {'m_Started': False, 'm_Placed': 0}, False, {})]),"""
    after = """    (S / 'Travel/HCShelterModule.c', 'HCShelterModule', 'Shelters', None, [
        ('ready', None, {'m_Started': True, 'm_Placed': 3, 'm_RegionalFailed': 0}, False,
         {'HCShelterCatalog': N(HCRegionalFault=lambda: '')}),
        ('degraded', 'no_shelter_placed', {'m_Started': True, 'm_Placed': 0, 'm_RegionalFailed': 0}, False,
         {'HCShelterCatalog': N(HCRegionalFault=lambda: '')}),
        ('degraded', 'regional_scene_placement_failed', {'m_Started': True, 'm_Placed': 3, 'm_RegionalFailed': 1}, False,
         {'HCShelterCatalog': N(HCRegionalFault=lambda: '')}),
        ('degraded', 'regional_scene_data_missing_or_invalid', {'m_Started': True, 'm_Placed': 3, 'm_RegionalFailed': 0}, False,
         {'HCShelterCatalog': N(HCRegionalFault=lambda: 'regional_scene_data_missing_or_invalid')}),
        ('off', OFF, {'m_Started': False, 'm_Placed': 0, 'm_RegionalFailed': 0}, False, {})]),"""
    edits[path] = replace_pending(old, before, after)
    return edits


class SharedIntegrationCopies(unittest.TestCase):
    def test_proposed_edits_accept_already_integrated_files(self):
        overlay = proposed_edits()
        original = Path.read_text
        def read(path, *args, **kwargs):
            relative = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else ''
            return overlay[relative] if relative in overlay else original(path, *args, **kwargs)
        with patch.object(Path, 'read_text', read):
            self.assertEqual(overlay, proposed_edits())
            self.test_updated_existing_behavioral_fixtures()
            self.test_package_allowlist_edit_in_local_fixture_copy()

    def test_updated_existing_behavioral_fixtures(self):
        for path, source in proposed_edits().items():
            if not path.startswith('tests/'):
                continue
            with self.subTest(path=path):
                fixture = types.ModuleType('auditshelter_local_' + Path(path).stem)
                fixture.__file__ = str(ROOT / path)
                exec(compile(source, str(ROOT / path) + ':local-fixture-copy', 'exec'), fixture.__dict__)
                output = io.StringIO()
                result = unittest.TextTestRunner(stream=output).run(unittest.defaultTestLoader.loadTestsFromModule(fixture))
                self.assertTrue(result.wasSuccessful(), output.getvalue())

    def test_package_allowlist_edit_in_local_fixture_copy(self):
        # Parse only the literal allowlist; importing pbo would use the unchanged
        # shared file, so this explicit local copy is the integration seam.
        import ast
        source = proposed_edits()['tools/package/pbo.py']
        tree = ast.parse(source)
        assignment = next(node for node in tree.body if isinstance(node, ast.Assign)
                          and any(isinstance(target, ast.Name) and target.id == 'MISSION_FILES' for target in node.targets))
        files = ast.literal_eval(assignment.value)
        self.assertIn('travel/auditshelter_scenes.json', files)


if __name__ == '__main__':
    unittest.main()
