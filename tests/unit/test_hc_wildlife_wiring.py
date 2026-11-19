"""HC-15 lead integration (review P2s): source-shape checks only; no DayZ behavior is established."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ECO = ROOT / 'mods/HollowCountry/scripts/4_World/Ecology'


def method(text, cls, name):
    start = text.index('class ' + cls)
    body = text[start:]
    at = body.index(name + '(')
    depth, i = 0, body.index('{', at)
    for j in range(i, len(body)):
        depth += {'{': 1, '}': -1}.get(body[j], 0)
        if depth == 0:
            return body[i:j + 1]
    raise AssertionError(name)


class WildlifeWiring(unittest.TestCase):
    def test_animal_delete_releases_wildlife_row_even_after_kill_cleared_ecology_flag(self):
        hooks = (ECO / 'HCEcologyHooks.c').read_text()
        delete = method(hooks, 'AnimalBase', 'EEDelete')
        guarded = re.search(r'if \(m_HCEcoRegistered\)\s*\{[^}]*\}', delete).group(0)
        self.assertIn('HCWildlifeObservation.HCUnregister(this);', delete)
        self.assertNotIn('HCWildlifeObservation', guarded)
        self.assertIn('HCWildlifeObservation.HCRegister(this)', method(hooks, 'AnimalBase', 'EEInit'))

    def test_every_disabled_or_rejected_path_closes_wildlife_collection(self):
        module = (ECO / 'HCEcologyRuntimeModule.c').read_text()
        self.assertEqual(module.count('HCEcologyRuntime.CloseCollection();'), module.count('HCWildlifeObservation.HCStart(false);'))
        self.assertIn('HCWildlifeObservation.HCStart(true);', module)
        self.assertIn('HCWildlifeObservation.HCTick(', method(module, 'HCEcologyRuntimeModule', 'OnTick'))
        self.assertIn('HCWildlifeObservation.HCStop();', method(module, 'HCEcologyRuntimeModule', 'OnStop'))

    def test_a_full_cohort_is_resampled_within_the_fact_lifetime(self):
        config = json.loads((ROOT / 'mission/hollow-country/ecology/species.json').read_text())
        cycle_ms = -(-config['MaxAnimals'] // (config['WorkUnits'] // (1 + config['MaxPlayerChecks']))) * config['TickMs']
        self.assertLessEqual(cycle_ms, config['FactLifetimeMs'])

    def test_species_config_ships_in_the_mission_allowlist(self):
        from tools.package import pbo
        self.assertIn('ecology/species.json', pbo.MISSION_FILES)


if __name__ == '__main__':
    unittest.main()
