"""Seasonal and coastal infected placement on synthetic events (offline data checks).

Events are built from the authored rows in variants.json, so the expectations follow
the data. Nothing here establishes CE or DayZ behaviour.
"""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from tools.package import economy, infected_variety as iv

POLICY = json.loads(iv.POLICY.read_text())
BASE = POLICY['palette_rebalance']['transfers']
SEASONAL = [r for block in POLICY['seasonal_rebalance']['seasons'].values() for r in block['transfers']]
HEAVY = [e['class'] for e in POLICY['entries'] if 'Heavy_Navy' in e['class']]


def synthetic(rows):
    """Stock-like events: every donor and in-event receiver exists with ample weight."""
    events = {}
    for row in rows:
        events.setdefault(row['event'], {})
        events[row['event']].setdefault(row['from'], 0)
        events[row['event']][row['from']] += 6 * row['share'] + 6
    # A receiver already present in the stock event keeps its own weight.
    for row in rows:
        events[row['event']].setdefault(row['from'], 0)
    lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', '<events>']
    for name, children in sorted(events.items()):
        lines += ['    <event name="%s">' % name, '        <nominal>50</nominal>', '        <children>']
        lines += ['            <child lootmax="5" lootmin="0" max="0" min="%d" type="%s"/>' % (w, t)
                  for t, w in sorted(children.items())]
        lines += ['        </children>', '    </event>']
    lines.append('</events>')
    return ('\n'.join(lines) + '\n').encode()


def weights(data):
    return {n: {c.get('type'): int(c.get('min')) for c in e.findall('./children/child')}
            for n, e in iv._events(data).items()}


class SeasonalPlacementTests(unittest.TestCase):
    def setUp(self):
        data = synthetic(BASE + SEASONAL)
        self.stock = data
        self.policy = copy.deepcopy(POLICY)
        self.policy['substitutions'] = []
        self.policy['evidence']['stock_events_sha256'] = economy.sha(data)

    def build(self, season=None):
        return weights(iv.substitute(self.stock, self.stock, self.policy, season))

    def test_every_authored_season_is_a_known_season(self):
        self.assertTrue(set(POLICY['seasonal_rebalance']['seasons']) <= set(iv.SEASONS))

    def test_no_season_places_no_seasonal_outfit(self):
        placed = self.build()
        for row in SEASONAL:
            self.assertNotIn(row['to'], placed[row['event']])

    def test_season_places_exactly_its_rows(self):
        for season, block in POLICY['seasonal_rebalance']['seasons'].items():
            plain, seasonal = self.build(), self.build(season)
            for row in block['transfers']:
                self.assertEqual(seasonal[row['event']][row['to']] - plain[row['event']].get(row['to'], 0), row['share'])
                self.assertEqual(plain[row['event']][row['from']] - seasonal[row['event']][row['from']], row['share'])
            for name in plain:
                self.assertEqual(sum(plain[name].values()), sum(seasonal[name].values()))

    def test_other_seasons_place_nothing_seasonal(self):
        for season in set(iv.SEASONS) - set(POLICY['seasonal_rebalance']['seasons']):
            self.assertEqual(self.build(season), self.build())

    def test_unknown_season_is_refused(self):
        with self.assertRaises(ValueError):
            iv.season_transfers(POLICY, 'monsoon')

    def test_composition_switch_off_skips_seasonal_rows(self):
        self.policy['mix_policy']['EnableComposition'] = False
        self.assertEqual(self.build('winter'), self.build())

    def test_seasonal_donors_are_not_other_seasonal_receivers(self):
        receivers = {(r['event'], r['to']) for r in SEASONAL}
        self.assertFalse({(r['event'], r['from']) for r in SEASONAL} & receivers)


class CoastalNavyTests(unittest.TestCase):
    NAVY = 'ZmbM_eastSoldier_normal_Navy'

    def test_navy_rows_stay_in_the_coastal_tiers(self):
        rows = [r for r in BASE if r['to'] == self.NAVY]
        self.assertTrue(rows)
        # The policy names the coastal tiers in its event-scope note.
        scope = POLICY['ce_pose_policy']['scope']
        self.assertIn('Coastal tiers use CityTier1/VillageTier1', scope)
        self.assertTrue({r['event'] for r in rows} <= {'Infected' + t for t in ('CityTier1', 'VillageTier1')})

    def test_navy_weight_is_bounded_per_event(self):
        for name in {r['event'] for r in BASE if r['to'] == self.NAVY}:
            total = sum(r['share'] for r in BASE if r['event'] == name and r['to'] == self.NAVY)
            self.assertLessEqual(total * 20, 100)

    def test_heavy_navy_is_never_a_receiver(self):
        self.assertTrue(HEAVY)
        for row in BASE + SEASONAL:
            self.assertNotIn(row['to'], HEAVY)

    def test_review_notes_describe_the_placement(self):
        review = POLICY['palette_rebalance']['outside_mix_review']
        for key in ('winter_medics', 'male_navy_soldiers'):
            self.assertNotIn('deferred', review[key])


class SeasonProfileTests(unittest.TestCase):
    def profile(self, elapsed, phase=None):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__('shutil').rmtree(root, ignore_errors=True))
        (root / 'HollowCountry').mkdir()
        if elapsed is not None:
            (root / iv.SEASON_STATE).write_text(json.dumps({'Version': 1, 'ElapsedSeconds': elapsed}))
        if phase is not None:
            (root / iv.SEASON_CONFIG).write_text(json.dumps({'PhaseSeconds': phase}))
        return root

    def test_each_phase_maps_to_its_season(self):
        for index, season in enumerate(iv.SEASONS):
            self.assertEqual(iv.season_from_profile(self.profile(index * 100 + 5, 100)), season)

    def test_the_cycle_wraps(self):
        self.assertEqual(iv.season_from_profile(self.profile(4 * 100 * 3 + 350, 100)), iv.SEASONS[3])

    def test_default_phase_length_applies_without_config(self):
        self.assertEqual(iv.season_from_profile(self.profile(iv.DEFAULT_PHASE_SECONDS)), iv.SEASONS[1])

    def test_missing_or_invalid_state_selects_no_season(self):
        self.assertIsNone(iv.season_from_profile(self.profile(None)))
        self.assertIsNone(iv.season_from_profile(self.profile(-1)))
        root = self.profile(None)
        (root / iv.SEASON_STATE).write_text('not json')
        self.assertIsNone(iv.season_from_profile(root))


if __name__ == '__main__':
    unittest.main()
