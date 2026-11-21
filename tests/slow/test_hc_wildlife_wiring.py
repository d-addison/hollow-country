"""HC-15 lead integration (review P2s): derived config checks only; no DayZ behavior is established."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
class WildlifeWiring(unittest.TestCase):


    def test_a_full_cohort_is_resampled_within_the_fact_lifetime(self):
        config = json.loads((ROOT / 'mission/hollow-country/ecology/species.json').read_text())
        cycle_ms = -(-config['MaxAnimals'] // (config['WorkUnits'] // (1 + config['MaxPlayerChecks']))) * config['TickMs']
        self.assertLessEqual(cycle_ms, config['FactLifetimeMs'])

    def test_species_config_ships_in_the_mission_allowlist(self):
        from tools.package import pbo
        self.assertIn('ecology/species.json', pbo.MISSION_FILES)


if __name__ == '__main__':
    unittest.main()
