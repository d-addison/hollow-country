"""Synthetic offline generator tests; no engine or translated Enforce execution."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.package import ai_route_precompute as routes
from tools.package import generated_digests, pbo, regenerate_all


class RoutePrecomputeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.mission = self.root / 'mission/hollow-country'
        self.nodes = [((1.25, 0, 2), 7, [1, 1]), ((3, 4, 5), 0, []),
                      ((6, 7, 8), -1, [0])]
        self.limits = dict(RoadMapWidth=100, RoadMapHeight=200,
                           MaxRoadNodes=len(self.nodes), MaxRoadDegree=3)
        self.roads = self.root / 'input.roads'
        self.roads.write_bytes(self.road_data())
        self.save('mission/hollow-country/ai/caravans.json', self.limits)
        self.local = self.mission / 'ai/sites.json'
        self.local.write_bytes(b'{"sites":[]}\n')
        chunk = 32
        self.pins = {'SchemaVersion': 1, 'ChunkBytes': chunk,
                     'MaxSourceBytes': routes.MAX_SOURCE_BYTES, 'Files': []}
        for name, data in ((routes.ROAD_PATH, self.roads.read_bytes()),
                           ('$mission:hollow-country/ai/sites.json', self.local.read_bytes())):
            self.pins['Files'].append(dict(Path=name, Bytes=len(data), Sha256=routes.sha(data),
                Pages=[routes.sha(data[i:i + chunk]) for i in range(0, len(data), chunk)]))
        self.save(routes.PINS, self.pins)

    def save(self, path, doc):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(doc))

    def road_data(self):
        lines = [4, self.limits['RoadMapWidth'], self.limits['RoadMapHeight'], len(self.nodes)]
        for index, (xyz, flags, links) in enumerate(self.nodes):
            lines.extend([index, ' '.join(map(str, xyz)), flags, len(links), *links])
        return ('\n'.join(map(str, lines)) + '\n').encode()

    def plan(self):
        return routes.plan(self.root, roads=self.roads)

    def test_flat_arrays_preserve_ids_flags_directed_links_duplicates_and_isolated_nodes(self):
        graph = json.loads(self.plan()[routes.OUTPUTS[1]])
        self.assertEqual(len(self.nodes), graph['NodeCount'])
        self.assertEqual(sum(len(row[2]) for row in self.nodes), graph['EdgeCount'])
        self.assertEqual(len(self.nodes) + 1, len(graph['Offsets']))
        for node, (xyz, flags, links) in enumerate(self.nodes):
            self.assertEqual(list(xyz), graph['Positions'][3 * node:3 * node + 3])
            self.assertEqual(flags, graph['Flags'][node])
            start, end = graph['Offsets'][node:node + 2]
            self.assertEqual(links, graph['Edges'][start:end])

    def test_manifest_pages_cover_current_sources_and_bind_graph(self):
        # Authored mission changes produce new pins; dependency changes must refuse.
        self.local.write_bytes(b'{"sites":["new"]}\n')
        outputs = self.plan()
        manifest = json.loads(outputs[routes.OUTPUTS[0]])
        hash_pages = []
        for identity in manifest['HashPages']:
            data = outputs[identity['Path'].replace('$mission:', 'mission/', 1)]
            self.assertEqual(len(data), identity['Bytes'])
            self.assertEqual(routes.sha(data), identity['Sha256'])
            self.assertLessEqual(len(data), routes.MANIFEST_PAGE_BYTES)
            page = json.loads(data)
            self.assertEqual(len(hash_pages), page['PageStart'])
            hash_pages.extend(page['Hashes'])
        self.assertLessEqual(len(outputs[routes.OUTPUTS[0]]), routes.MANIFEST_ROOT_BYTES)
        cursor = 0
        for row, data in zip(manifest['Files'], (self.roads.read_bytes(), self.local.read_bytes())):
            self.assertEqual(cursor, row['PageStart'])
            self.assertEqual(len(data), row['Bytes'])
            self.assertEqual(routes.sha(data), row['Sha256'])
            pages = [routes.sha(data[i:i + manifest['ChunkBytes']])
                     for i in range(0, len(data), manifest['ChunkBytes'])]
            self.assertEqual(pages, hash_pages[cursor:cursor + row['PageCount']])
            self.assertEqual(len(pages), row['PageCount'])
            cursor += len(pages)
        self.assertEqual(cursor, manifest['PageCount'])
        self.assertEqual(routes.sha(outputs[routes.OUTPUTS[1]]), manifest['RoadGraphSha256'])
        self.assertEqual(routes.sha((self.root / routes.PINS).read_bytes()), manifest['SourcePagesSha256'])

    def test_catalog_row_packing_preserves_rows_identities_and_byte_bound(self):
        catalog = routes.gapcov_routes
        count = catalog.CATALOG_PAGE_ROWS * 3 + 1
        self.save('mission/hollow-country/ai/localities.json',
                  {'Localities': [{'Id': str(i)} for i in range(count)]})
        self.save('mission/hollow-country/travel/route-surveys.json', {})
        self.save('mission/hollow-country/ai/picker-routes.json', {})
        self.save('mission/hollow-country/infected/route-surveys.json', {})
        # Exercise the full serialized row budget, including punctuation.
        rows = [{'id': str(i), 'padding': ''} for i in range(count)]
        for row in rows:
            row['padding'] = 'x' * (catalog.CATALOG_ROW_BYTES - len(routes.encode(row)) + 1)
        outputs = catalog.catalog_outputs(self.root, {'routes': rows})
        header = json.loads(outputs[str(catalog.MISSION / catalog.CATALOG_INDEX)])
        emitted = []
        for pin in header['pages']:
            data = outputs[pin['Path'].replace('$mission:', 'mission/', 1)]
            page = json.loads(data)
            self.assertLessEqual(len(data), catalog.CATALOG_PAGE_BYTES)
            self.assertEqual(len(data), pin['Bytes'])
            self.assertEqual(routes.sha(data), pin['Sha256'])
            self.assertEqual(len(page['routes']), pin['Rows'])
            identity = page.pop('identity_sha256')
            self.assertEqual(catalog.digest(page), identity)
            self.assertEqual(identity, pin['IdentitySha256'])
            emitted.extend(page['routes'])
        self.assertEqual(rows, emitted)
        self.assertEqual(len(rows), header['row_count'])
        self.assertEqual(set(catalog.page_paths(self.root)),
                         {p['Path'].removeprefix('$mission:hollow-country/') for p in header['pages']})
        rows[0]['padding'] += 'x'
        with self.assertRaises(ValueError):
            catalog.catalog_outputs(self.root, {'routes': rows})

    def test_manifest_catalog_pins_span_bounded_ordered_pages(self):
        count = routes.MANIFEST_CATALOG_PINS_PER_PAGE * 3 + 1
        pins = [{'Path': '$mission:hollow-country/travel/gapcov-roads/page-%03d.json' % i,
                 'Bytes': routes.gapcov_routes.CATALOG_PAGE_BYTES,
                 'Sha256': routes.sha(str(i).encode()),
                 'IdentitySha256': routes.sha(('identity-%d' % i).encode()),
                 'Rows': routes.gapcov_routes.CATALOG_PAGE_ROWS} for i in range(count)]
        header = {'pages': pins, 'identity_sha256': routes.sha(b'catalog')}
        derived = {str(routes.gapcov_routes.MISSION / routes.gapcov_routes.CATALOG_INDEX):
                   routes.encode(header)}
        # Enable the full-catalog branch without needing a dependency-sized graph.
        self.save(routes.gapcov_routes.OUTPUTS[0], {})
        with patch.object(routes.gapcov_routes, 'build', return_value={}), \
                patch.object(routes.gapcov_routes, 'catalog_outputs', return_value=derived):
            outputs = self.plan()
        manifest = json.loads(outputs[routes.OUTPUTS[0]])
        self.assertLessEqual(len(outputs[routes.OUTPUTS[0]]), routes.MANIFEST_ROOT_BYTES)
        collected, hashes = [], []
        for identity in manifest['HashPages']:
            data = outputs[identity['Path'].replace('$mission:', 'mission/', 1)]
            self.assertLessEqual(len(data), routes.MANIFEST_PAGE_BYTES)
            self.assertEqual(routes.sha(data), identity['Sha256'])
            page = json.loads(data)
            self.assertEqual(len(collected), page['CatalogPageStart'])
            self.assertEqual(len(hashes), page['PageStart'])
            collected.extend(page['CatalogPages'])
            hashes.extend(page['Hashes'])
        self.assertEqual(pins, collected)
        self.assertEqual(manifest['PageCount'], len(hashes))

    def test_deterministic_sha_write_and_read_only_drift_check(self):
        first = routes.write(self.root, roads=self.roads)
        second = self.plan()
        self.assertEqual({k: hashlib.sha256(v).hexdigest() for k, v in first.items()},
                         {k: hashlib.sha256(v).hexdigest() for k, v in second.items()})
        self.assertTrue(routes.check(self.root, roads=self.roads))
        output = self.root / routes.OUTPUTS[0]
        output.write_bytes(b'drift')
        self.assertFalse(routes.check(self.root, roads=self.roads))
        self.assertEqual(b'drift', output.read_bytes())

    def test_dependency_whole_file_and_individual_page_mismatch_refuse_before_writing(self):
        for key, value in (('Sha256', '0' * 64), ('Pages', ['0' * 64]), ('Bytes', 1)):
            with self.subTest(key=key):
                pins = copy.deepcopy(self.pins)
                pins['Files'][0][key] = value
                self.save(routes.PINS, pins)
                with self.assertRaises(ValueError):
                    routes.write(self.root, roads=self.roads)
                self.assertFalse((self.root / routes.OUTPUTS[0]).exists())

    def test_invalid_source_inventory_and_paths_refuse(self):
        variants = [dict(self.pins, SchemaVersion=2), dict(self.pins, ChunkBytes=0),
                    dict(self.pins, Files=self.pins['Files'] * 2),
                    dict(self.pins, Files=self.pins['Files'][1:])]
        for path in ('$mission:hollow-country/../escape', '/absolute', '$mission:hollow-country/ai\\escape'):
            pins = copy.deepcopy(self.pins)
            pins['Files'][1]['Path'] = path
            variants.append(pins)
        for pins in variants:
            with self.subTest(pins=pins):
                self.save(routes.PINS, pins)
                with self.assertRaises(ValueError):
                    self.plan()

    def test_malformed_graphs_refuse(self):
        good = self.road_data()
        bad = [good.replace(b'4\n', b'5\n', 1), good[:-1], good + b'junk\n',
               good.replace(b'1.25 0 2', b'nan 0 2'),
               good.replace(b'1.25 0 2', b'1 2'), good.replace(b'0\n1.25', b'9\n1.25')]
        for data in bad:
            with self.subTest(data=data), self.assertRaises(ValueError):
                routes.compact_graph(data, self.limits)
        for key in ('MaxRoadNodes', 'MaxRoadDegree'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                routes.compact_graph(good, dict(self.limits, **{key: 0}))
        self.nodes[0][2].append(len(self.nodes))
        with self.assertRaises(ValueError):
            routes.compact_graph(self.road_data(), self.limits)

    def test_receipt_adapter_and_packaging_inventory(self):
        contract = next(c for c in generated_digests.contracts() if c.name == 'ai_route_precompute')
        self.assertEqual(set(routes.OUTPUTS), set(contract.outputs))
        self.assertTrue(any(g.name == contract.name for g in regenerate_all.GENERATORS))
        self.assertIn('HollowCountryExpansionAI\\compat', pbo.PREFIXES)
        for name in routes.OUTPUTS:
            self.assertIn(str(Path(name).relative_to('mission/hollow-country')), pbo.MISSION_FILES)
        with patch.object(generated_digests, 'ROOT', self.root), \
                patch.object(routes, 'road_bytes', return_value=self.roads.read_bytes()):
            self.assertEqual(self.plan(), generated_digests.regenerate(contract, {'workshop': self.root}, self.root))


if __name__ == '__main__':
    unittest.main()
