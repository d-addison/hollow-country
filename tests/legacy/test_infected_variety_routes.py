"""Actual installer postconditions on hash-pinned stock XML; no native CE claim."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

from tools.package import infected_variety

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / 'mission/hollow-country/infected/variants.json'


def policy():
    return json.loads(POLICY.read_bytes())


def stock_bytes(case):
    # Optional local input; stock data is never copied into the repository.
    path = Path(os.environ.get('HC_STOCK_EVENTS',
        '/mnt/d/SteamLibrary/steamapps/common/DayZServer/mpmissions/dayzOffline.chernarusplus/db/events.xml'))
    if not path.is_file():
        case.skipTest('set HC_STOCK_EVENTS to the pinned stock events.xml')
    data = path.read_bytes()
    # External contract: the manifest pins the installed DayZ stock snapshot.
    case.assertEqual(hashlib.sha256(data).hexdigest(), policy()['evidence']['stock_events_sha256'])
    return data


class StockSubstitutionTests(unittest.TestCase):
    def setUp(self):
        self.policy = policy()
        self.stock = stock_bytes(self)
        self.output = infected_variety.substitute(self.stock, self.stock, self.policy)
        self.before = {e.get('name'): e for e in ET.fromstring(self.stock)}
        self.after = {e.get('name'): e for e in ET.fromstring(self.output)}

    def test_all_event_min_and_max_sums_are_conserved(self):
        self.assertEqual(self.before.keys(), self.after.keys())
        for name, old in self.before.items():
            for field in ('min', 'max'):
                with self.subTest(event=name, field=field):
                    def total(event):
                        return sum(int(c.get(field)) for c in event.findall('./children/child'))
                    self.assertEqual(total(old), total(self.after[name]))

    def test_donors_stay_positive_and_destination_gains_match_authored_shares(self):
        given = {}
        for row in self.policy['substitutions']:
            key = row['event'], row['from']
            given[key] = given.get(key, 0) + row['share']
            def weight(events, name):
                child = events[row['event']].find(f'./children/child[@type="{name}"]')
                return int(child.get('min')) if child is not None else 0
            self.assertEqual(weight(self.after, row['to']) - weight(self.before, row['to']), row['share'])
        for (event, donor), shares in given.items():
            with self.subTest(event=event, donor=donor):
                old = self.before[event].find(f'./children/child[@type="{donor}"]')
                new = self.after[event].find(f'./children/child[@type="{donor}"]')
                self.assertGreater(int(new.get('min')), 0)
                self.assertEqual(int(old.get('min')) - shares, int(new.get('min')))

    def test_untargeted_events_and_nonchild_metadata_are_preserved(self):
        targets = {r['event'] for r in self.policy['substitutions']}
        def structure(node):
            return node.tag, node.attrib, (node.text or '').strip(), [structure(c) for c in node]
        for name, old in self.before.items():
            new = self.after[name]
            if name not in targets:
                self.assertEqual(structure(old), structure(new))
            else:
                self.assertEqual(old.attrib, new.attrib)
                self.assertEqual([structure(c) for c in old if c.tag != 'children'],
                                 [structure(c) for c in new if c.tag != 'children'])

    def test_install_and_rollback_restore_pinned_stock_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            mission = Path(temp)
            events = mission / 'db/events.xml'
            events.parent.mkdir()
            events.write_bytes(self.stock)
            with patch.object(infected_variety, 'POLICY', POLICY):
                infected_variety.install(mission)
                self.assertEqual(self.output, events.read_bytes())
                infected_variety.rollback(mission)
            self.assertEqual(self.stock, events.read_bytes())
