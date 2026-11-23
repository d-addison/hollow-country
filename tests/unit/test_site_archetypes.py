"""Offline checks for the composed-site archetype templates (config/sites/archetypes).

These checks establish template well-formedness only; they never establish DayZ behaviour.

Format (the contract the site composer consumes; operator reference in docs/SITES.md)
------------------------------------------------------------------------------------
config/sites/archetypes/<id>.json, one authored story per file, validated against schema.json:

  kind/id/version/title/story   identity and the one-line story the owner sees in docs/SITES.md
  frame {kind, forward}         road | approach | view | fall_line | building, plus a named forward axis.
                                s = metres along forward, side/offset_m = lateral distance from the axis
                                (in a road frame the axis is the carriageway centreline).
  location {...}                predicates the composer must satisfy when it picks the spot (units in metres,
                                degrees, percent); every key is optional but at least two are required.
  lane                          passable (every barrier set leaves a gap >= 3.5 m), blocking, or none
                                (off-road archetypes). Vehicle wrecks never close a lane.
  allowed_roles                 the closed set of classes.json roles the archetype may use (story matching).
  loot_theme                    civilian | military | medical | scavenged: which class families may carry
                                loot rows. Parts with "loot": "proto" emit mapgrouppos rows (classes whose
                                classes.json loot_group is true only); 1-4 rows per site, or none with a
                                loot_none_reason. A multi-instance part (count n) emits n rows.
  parts[]                       {id, class (one or a variant list), op, ...}; exactly one "anchor": true
                                part, placed first; every other part is placed relative to a named part
                                (of) or the frame (s/side/offset_m) with one of the 11 closed operators.
                                "origin" names the frame origin. Yaw intent is in align/faces; the composer
                                subtracts the class front_yaw_deg (W1 geometry) to get the object yaw.
  external_anchors[]            vanilla buildings (match_prefix) the site hangs off (farm holdout); such a
                                template has no anchor part and parts refer to the external id in "of".
  zones[]                       scatter zones: disc | cone | strip anchored on a part, seeded by site id.
  variants / part.variant       optional part groups the composer enables per site (field-hospital medevac).
  story_items                   note {key, on}: a lead-note key put on a table part; ai {role, guard_posts}:
                                parts flagged guard_post become guard slots in the zone contract.
  density {max_per_map, min_same_m, min_any_m, count_basis}
                                count_basis "holdout" means the site is dressing for a live holdout and does
                                not count against the composed-site budget.

Budget proxies checked here: composed sites <= 75, objects <= 1,800, loot rows <= 300 (one row per proto
object; the composer measures real mapgrouppos rows).
"""
import json
from pathlib import Path
import re
import unittest

from tools.package.inventory_sources import safe_text

ROOT = Path(__file__).resolve().parents[2]
ARCHETYPES = ROOT / 'config' / 'sites' / 'archetypes'
CLASSES = ROOT / 'config' / 'map-overlays' / 'classes.json'
DOC = ROOT / 'docs' / 'SITES.md'

IDS = {
    'military-checkpoint', 'police-roadblock', 'quarantine-post', 'bandit-roadblock', 'crashed-convoy',
    'fuel-stop', 'military-camp', 'supply-dump', 'field-hospital', 'overwatch-post', 'helicopter-crash',
    'refugee-camp', 'hunter-camp', 'mass-grave', 'farm-holdout',
}
OPERATORS = {'in_lane', 'across_lane', 'shoulder', 'offroad', 'row', 'ring', 'facing', 'beside', 'behind',
             'scatter', 'on_slope'}
ROAD_OPS = {'in_lane', 'across_lane', 'shoulder'}
FRAME_FACES = {'forward', '-forward', 'outward', 'view', 'axis', 'of', 'road'}
THEME_FAMILIES = {
    'civilian': {'civilian', 'neutral', 'medical'},
    'military': {'military', 'neutral'},
    'medical': {'medical', 'neutral'},
    'scavenged': {'civilian', 'military', 'neutral'},
}
MAX_SITES, MAX_OBJECTS, MAX_ROWS, MAX_TEMPLATE_OBJECTS = 75, 1800, 300, 40
MILITARY_WRECKS = {'StaticObj_Wreck_MTVR_Cargo', 'StaticObj_Wreck_Stryker'}


def validate(value, schema, root, path='$'):
    """Small draft-07 subset validator (the repo carries no jsonschema dependency)."""
    errors = []
    if '$ref' in schema:
        node = root
        for key in schema['$ref'].lstrip('#/').split('/'):
            node = node[key]
        return validate(value, node, root, path)

    def kind_ok(expected):
        return {'object': isinstance(value, dict), 'array': isinstance(value, list),
                'string': isinstance(value, str), 'boolean': isinstance(value, bool),
                'integer': isinstance(value, int) and not isinstance(value, bool),
                'number': isinstance(value, (int, float)) and not isinstance(value, bool)}[expected]

    if 'type' in schema and not kind_ok(schema['type']):
        return [path + ': expected ' + schema['type']]
    if 'const' in schema and value != schema['const']:
        errors.append('%s: expected %r' % (path, schema['const']))
    if 'enum' in schema and value not in schema['enum']:
        errors.append('%s: %r not in enum' % (path, value))
    if isinstance(value, str):
        if len(value) < schema.get('minLength', 0) or len(value) > schema.get('maxLength', 1 << 30):
            errors.append(path + ': length out of range')
        if 'pattern' in schema and not re.search(schema['pattern'], value):
            errors.append('%s: %r does not match %s' % (path, value, schema['pattern']))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if 'minimum' in schema and value < schema['minimum']:
            errors.append('%s: below minimum' % path)
        if 'maximum' in schema and value > schema['maximum']:
            errors.append('%s: above maximum' % path)
    if isinstance(value, list):
        if len(value) < schema.get('minItems', 0) or len(value) > schema.get('maxItems', 1 << 30):
            errors.append(path + ': item count out of range')
        if schema.get('uniqueItems') and len({json.dumps(v, sort_keys=True) for v in value}) != len(value):
            errors.append(path + ': duplicate items')
        if 'items' in schema:
            for i, item in enumerate(value):
                errors.extend(validate(item, schema['items'], root, '%s[%d]' % (path, i)))
    if isinstance(value, dict):
        props = schema.get('properties', {})
        for key in schema.get('required', []):
            if key not in value:
                errors.append('%s: missing %s' % (path, key))
        if len(value) < schema.get('minProperties', 0):
            errors.append(path + ': too few properties')
        for key, item in value.items():
            if key in props:
                errors.extend(validate(item, props[key], root, path + '.' + key))
            elif schema.get('additionalProperties') is False:
                errors.append('%s: unknown key %s' % (path, key))
    if 'oneOf' in schema:
        hits = sum(1 for sub in schema['oneOf'] if not validate(value, sub, root, path))
        if hits != 1:
            errors.append('%s: matches %d of oneOf' % (path, hits))
    if 'anyOf' in schema and not any(not validate(value, sub, root, path) for sub in schema['anyOf']):
        errors.append(path + ': matches none of anyOf')
    for sub in schema.get('allOf', []):
        if 'if' in sub:
            if not validate(value, sub['if'], root, path):
                errors.extend(validate(value, sub['then'], root, path))
        else:
            errors.extend(validate(value, sub, root, path))
    return errors


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def classes_of(part):
    return [part['class']] if isinstance(part['class'], str) else list(part['class'])


def hi(value):
    return value[-1] if isinstance(value, list) else value


def family(name):
    if name.startswith('Land_Mil_') or name in MILITARY_WRECKS:
        return 'military'
    if name.startswith('Land_Medical_'):
        return 'medical'
    if name.startswith('Land_Wreck_'):
        return 'civilian'
    return 'neutral'


def instances(template):
    """Max object instances per part id (multi-instance `of` repeats beside/behind per instance)."""
    result = {}
    for part in template['parts']:
        n = hi(part.get('count', 1))
        if part['op'] in ('beside', 'behind') and part.get('instance', 'all') == 'all':
            n *= result.get(part['of'], 1)
        result[part['id']] = n
    return result


class SiteArchetypeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = load(ARCHETYPES / 'schema.json')
        cls.classes = load(CLASSES)['classes']
        cls.templates = {p.stem: load(p) for p in sorted(ARCHETYPES.glob('*.json')) if p.name != 'schema.json'}

    def test_fifteen_templates_named_by_id(self):
        self.assertEqual(set(self.templates), IDS)
        for name, template in self.templates.items():
            self.assertEqual(template['id'], name)

    def test_every_template_validates_against_schema(self):
        for name, template in self.templates.items():
            with self.subTest(template=name):
                self.assertEqual(validate(template, self.schema, self.schema), [])

    def test_validator_rejects_bad_templates(self):
        template = json.loads(json.dumps(self.templates['bandit-roadblock']))
        template['parts'][1]['op'] = 'teleport'
        self.assertTrue(validate(template, self.schema, self.schema))
        template = json.loads(json.dumps(self.templates['bandit-roadblock']))
        del template['parts'][1]['count']
        self.assertTrue(validate(template, self.schema, self.schema))
        template = json.loads(json.dumps(self.templates['bandit-roadblock']))
        template['parts'][1]['gap_m'] = 2
        self.assertTrue(validate(template, self.schema, self.schema))

    def test_operator_set_is_the_closed_design_set(self):
        part = self.schema['$defs']['part']['properties']['op']['enum']
        self.assertEqual(set(part), OPERATORS)
        conditions = {c['if']['properties']['op']['const'] for c in self.schema['$defs']['part']['allOf']}
        self.assertEqual(conditions, OPERATORS)
        used = {p['op'] for t in self.templates.values() for p in t['parts']}
        self.assertEqual(used, OPERATORS)

    def test_classes_exist_and_roles_are_allowed(self):
        for name, template in self.templates.items():
            roles = set()
            for part in template['parts']:
                role_set = set()
                for cls in classes_of(part):
                    with self.subTest(template=name, part=part['id'], cls=cls):
                        self.assertIn(cls, self.classes)
                    role_set.add(self.classes[cls]['role'])
                roles |= role_set
            with self.subTest(template=name):
                self.assertEqual(roles, set(template['allowed_roles']))

    def test_no_pack_class_or_banned_text(self):
        for path in list(ARCHETYPES.glob('*.json')) + [DOC]:
            text = path.read_text(encoding='utf-8')
            with self.subTest(path=path.name):
                for line in text.splitlines():
                    self.assertTrue(safe_text(line), line)
                for token in re.findall(r'\b(?:Land|StaticObj)_[A-Za-z0-9_]+', text):
                    if token.endswith('_'):
                        continue
                    self.assertIn(token, self.classes)
                self.assertNotRegex(text, r'/home/|[A-Za-z]:\\|7656119')

    def test_references_and_anchor(self):
        for name, template in self.templates.items():
            parts = template['parts']
            ids = [p['id'] for p in parts]
            external = {e['id'] for e in template.get('external_anchors', [])}
            zones = {z['id'] for z in template.get('zones', [])}
            with self.subTest(template=name):
                self.assertEqual(len(ids), len(set(ids)))
                self.assertFalse(set(ids) & external)
                anchors = [p for p in parts if p.get('anchor')]
                self.assertEqual(len(anchors), 0 if external else 1)
                if anchors:
                    self.assertEqual(anchors[0]['op'] in {'facing', 'beside', 'behind', 'ring', 'scatter'}, False)
                    self.assertNotIn('of', anchors[0])
                self.assertEqual(len(zones), len(template.get('zones', [])))
            for index, part in enumerate(parts):
                known = set(ids[:index]) | external | {'origin'}
                with self.subTest(template=name, part=part['id']):
                    if 'of' in part:
                        self.assertIn(part['of'], known)
                    if 'stack_on' in part:
                        self.assertIn(part['stack_on'], known)
                    if 'faces' in part:
                        self.assertTrue(part['faces'] in FRAME_FACES or part['faces'] in known, part['faces'])
                    if part['op'] == 'scatter':
                        self.assertIn(part['zone'], zones)
                    if 'variant' in part:
                        self.assertIn(part['variant'], template.get('variants', []))
            for zone in template.get('zones', []):
                owner = zone['of']
                with self.subTest(template=name, zone=zone['id']):
                    self.assertTrue(owner in ids or owner in external or owner == 'origin')
                    users = [i for i, p in enumerate(parts) if p.get('zone') == zone['id']]
                    self.assertTrue(users, 'zone without a scatter part')
                    if owner in ids:
                        self.assertTrue(all(i > ids.index(owner) for i in users))
            for zone_id in zones:
                self.assertTrue(any(p.get('zone') == zone_id for p in parts))

    def test_operator_placement_rules(self):
        for name, template in self.templates.items():
            road = template['frame']['kind'] == 'road'
            with self.subTest(template=name):
                self.assertEqual(template['lane'] != 'none', road)
                if road:
                    self.assertIn('road', template['location'])
            for part in template['parts']:
                op = part['op']
                with self.subTest(template=name, part=part['id']):
                    if op in ROAD_OPS:
                        self.assertTrue(road, 'road operator in a non-road frame')
                    if op == 'shoulder':
                        offset = part['offset_m']
                        self.assertTrue(0.5 <= min(offset if isinstance(offset, list) else [offset]) and
                                        hi(offset) <= 6)
                    if op == 'offroad' and road:
                        offset = part['offset_m']
                        self.assertTrue(min(offset if isinstance(offset, list) else [offset]) >= 8)
                    if op == 'row':
                        frame_coords = all(k in part for k in ('s', 'side', 'offset_m'))
                        self.assertTrue(frame_coords or ('of' in part and 'dist_m' in part))
                    if op == 'ring' and part['of'] == 'origin' and 'centre' in part:
                        self.assertIn(part['centre']['side'], ('left', 'right', 'center'))
                    if op == 'ring':
                        self.assertLessEqual(part['r_m'] * 6.2832 * part['arc_deg'] / 360 / part['count'], 60)
                    if op == 'scatter':
                        for cls in classes_of(part):
                            info = self.classes[cls]
                            self.assertEqual(info['kind'], 'prop')
                            self.assertFalse(info['loot_group'])
                            self.assertLessEqual(max(info['footprint_reserve_m']), 3, 'scatter is small litter')
                        self.assertNotIn('loot', part)
                    if 'stack_on' in part:
                        self.assertEqual(part['dist_m'], 0)
                    if 'reverse_slope' in part:
                        self.assertIn(template['frame']['kind'], ('view', 'approach'))

    def test_loot_rules(self):
        for name, template in self.templates.items():
            rows = 0
            counts = instances(template)
            for part in template['parts']:
                if part.get('loot') != 'proto':
                    continue
                rows += counts[part['id']]
                for cls in classes_of(part):
                    with self.subTest(template=name, part=part['id'], cls=cls):
                        self.assertTrue(self.classes[cls]['loot_group'], 'no installed loot prototype')
                        self.assertIn(family(cls), THEME_FAMILIES[template['loot_theme']])
                        self.assertNotEqual(part['op'], 'scatter')
            with self.subTest(template=name):
                if rows:
                    self.assertTrue(1 <= rows <= 4, rows)
                    self.assertNotIn('loot_none_reason', template)
                else:
                    self.assertIn('loot_none_reason', template)
                if 'zone_role' in template:
                    self.assertEqual(template['loot_theme'], 'military')

    def test_story_items_resolve(self):
        for name, template in self.templates.items():
            ids = {p['id']: p for p in template['parts']}
            items = template.get('story_items', {})
            with self.subTest(template=name):
                flagged = {p['id'] for p in template['parts'] if p.get('guard_post')}
                if 'ai' in items:
                    self.assertEqual(set(items['ai']['guard_posts']), flagged)
                else:
                    self.assertFalse(flagged)
                if 'note' in items:
                    holder = ids[items['note']['on']]
                    self.assertTrue(any('table' in c.lower() for c in classes_of(holder)), 'a note sits on a table part')

    def test_density_and_budget(self):
        sites = objects = rows = 0
        stories = set()
        for name, template in self.templates.items():
            density = template['density']
            counts = instances(template)
            template_objects = sum(counts.values())
            with self.subTest(template=name):
                self.assertGreaterEqual(density['min_same_m'], density['min_any_m'])
                self.assertLessEqual(template_objects, MAX_TEMPLATE_OBJECTS)
                self.assertEqual(density.get('count_basis') == 'holdout', name == 'farm-holdout')
                self.assertNotIn(template['story'], stories)
            stories.add(template['story'])
            if density.get('count_basis') != 'holdout':
                sites += density['max_per_map']
                objects += density['max_per_map'] * template_objects
                rows += density['max_per_map'] * sum(
                    counts[p['id']] for p in template['parts'] if p.get('loot') == 'proto')
        self.assertLessEqual(sites, MAX_SITES)
        self.assertGreaterEqual(sites, 60)
        self.assertLessEqual(objects, MAX_OBJECTS)
        self.assertLessEqual(rows, MAX_ROWS)

    def test_docs_cover_every_archetype_and_operator(self):
        text = DOC.read_text(encoding='utf-8')
        for name, template in self.templates.items():
            with self.subTest(template=name):
                self.assertIn('`' + name + '`', text)
                self.assertIn(template['story'], text)
        for op in OPERATORS:
            with self.subTest(operator=op):
                self.assertIn('`' + op + '`', text)


if __name__ == '__main__':
    unittest.main()
