"""Configurable source wiring census. Static evidence never establishes engine behavior."""
import argparse
import ast
import copy
from collections import Counter, defaultdict
import fnmatch
import io
import json
from pathlib import Path
import pickle
import re
import sys
import xml.etree.ElementTree as ET

from tools.audit import pbo_config

ROOT = Path(__file__).resolve().parents[2]
CHECKS = ('W001', 'W001b', 'W002', 'W003', 'W004', 'W005', 'W006', 'W007', 'W008', 'W009', 'W010')
# Keep offsets and newlines intact: comments cannot create references or move locations.
LEX = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*.*?\*/', re.S)
CLASS = re.compile(r'\b(?:(modded)\s+)?class\s+(\w+)(?:\s*(?::|extends)\s*(\w+))?\s*\{')
WORD = re.compile(r'\b[A-Za-z_]\w*\b')
DEFAULTS = {
    'vanilla_mission': '~/.cache/hollow-country/wine-server-20261116/mpmissions/dayzOffline.chernarusplus',
    'zeroed_items': 'config/zeroed-items.json',
    'schema': 1, 'checks': {key: True for key in CHECKS},
    'roots': {'configs': ['mods/*/config.cpp'], 'scripts': ['mods/*/scripts/**/*.c'],
              'data': ['mission/**/*.xml', 'mission/**/*.json', 'config/*.json'],
              'audit_data': ['mission/hollow-country/**/*'], 'tools': ['tools/**/*.py']},
    'ignore_patterns': [], 'allowlists': {key: {} for key in CHECKS},
    'config_roots': ['CfgVehicles', 'CfgWeapons', 'CfgMagazines', 'CfgAmmo'],
    'generated_blocks': [['// BEGIN HC inventory sizes', '// END HC inventory sizes']],
    'settings_mirror': 'tools/validate/shared_settings.json',
    'registry_call': 'HCAdd', 'settings_registry_class': 'HCOperatorSettingsRegistry', 'setting_read_helpers': ['HCGet\\w*', 'GetBool', 'GetInt', 'GetFloat', 'GetString'],
    'setting_metadata_owners': ['HCOperatorSettingsRegistry', 'HCJsonFields'],
    'setting_write_only_variables': ['settings', 'defaults', 'decoded'],
    'minimum_path_literal_length': 5,
    'setting_metadata_helpers': ['HCValid', 'HCDefault', 'HCMinimum', 'HCMaximum', 'Has', 'HasKey'],
    'module_base': 'HCModule', 'module_register': 'Register', 'module_registry_class': 'HCModuleRegistry',
    'readiness_base_patterns': ['HCModuleReadiness.HCPrint('],
    'readiness_dispatch_patterns': ['.HCReadyCapture(', '.HCReadyReport('],
    'rpc_definition_pattern': r'\b(\w+)\s*=\s*(485\d{4})\b',
    'rpc_send_calls': ['Send', 'RPCSingleParam', 'RPC'],
    'rpc_receive_variables': ['rpcType', 'rpc_type'],
    'spawn_calls': ['CreateObject', 'CreateObjectEx', 'CreateInInventory'],
    'ce_type_patterns': ['mission/**/*types*.xml'],
    'bundle_profile_catalogue': True,
    'reference_exclude_patterns': ['config/wiring-audit.json', 'config/zeroed-items.json', 'tools/validate/wiring_audit_baseline.json'],
    'class_sources': [], 'workshop_manifest': 'tools/setup/workshop_mods.json',
    'baseline': 'tools/validate/wiring_audit_baseline.json',
    'baseline_reason': 'Reviewed static candidate; inspect documented limitations before treating as a runtime defect.'
}


def mask(text, strings=False):
    return LEX.sub(lambda m: ''.join('\n' if c == '\n' else ' ' for c in m[0])
                   if strings or m[0].startswith(('/', "'")) else m[0], text)


def literals(text):
    return [m[0][1:-1].replace('\\\\', '/').replace('\\"', '"')
            for m in LEX.finditer(mask(text)) if m[0].startswith('"')]


def line(text, offset):
    return text.count('\n', 0, offset) + 1


def classes(text):
    """Script declarations with balanced bodies; no Enforce translation/evaluation."""
    clean = mask(text, strings=True)
    for m in CLASS.finditer(clean):
        depth, end = 1, m.end()
        while end < len(clean) and depth:
            depth += (clean[end] == '{') - (clean[end] == '}')
            end += 1
        if depth:
            raise ValueError('unbalanced class body: ' + m[2])
        yield {'name': m[2], 'parent': m[3], 'modded': bool(m[1]),
               'start': m.start(), 'end': end, 'line': line(text, m.start()),
               'body_start': m.end(), 'body': text[m.end():end - 1]}


class PrimitiveUnpickler(pickle.Unpickler):
    """Legacy local config cache: disallow globals, constructors and persistent IDs."""
    def find_class(self, module, name):
        raise ValueError('non-primitive pickle cache')

    def persistent_load(self, pid):
        raise ValueError('persistent pickle reference')


class Audit:
    def __init__(self, rules):
        self.rules, self.findings, self.notes = rules, [], []
        self.cache_root = (Path.home() / '.cache/hollow-country').resolve()
        self.profile_sources = {}

    def safe(self, path):
        path = Path(path).expanduser().resolve()
        if not (path.is_relative_to(ROOT) or path.is_relative_to(self.cache_root)):
            raise ValueError('input escapes repository and approved cache')
        return path

    def display(self, path):
        path = self.safe(path)
        return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else '~/.cache/hollow-country/' + path.relative_to(self.cache_root).as_posix()

    def read(self, path):
        path = self.safe(path)
        if path.stat().st_size > 64 * 1024 * 1024:
            raise ValueError('input exceeds 64 MiB budget: ' + self.display(path))
        return path.read_text(encoding='utf-8-sig')

    def paths(self, patterns):
        found = set()
        for pattern in patterns:
            if Path(pattern).is_absolute() or '..' in Path(pattern).parts:
                raise ValueError('repository glob must be relative')
            for path in ROOT.glob(pattern):
                if path.is_file():
                    self.safe(path)
                    rel = path.relative_to(ROOT).as_posix()
                    if not any(fnmatch.fnmatchcase(rel, p) for p in self.rules['ignore_patterns']):
                        found.add(path)
        return sorted(found)

    def add(self, check, subject, path, number, why):
        if not self.rules['checks'][check]:
            return
        for pattern, reason in ({} if check in ('W009', 'W010') else self.rules['allowlists'].get(check, {})).items():
            if fnmatch.fnmatchcase(subject, pattern):
                if not isinstance(reason, str) or not reason.strip():
                    raise ValueError('allowlist requires a reason')
                return
        self.findings.append({'id': check, 'subject': subject, 'file': self.display(path),
                              'line': number, 'why': why})

    def run(self):
        r = self.rules
        scripts = {p: mask(self.read(p)) for p in self.paths(r['roots']['scripts'])}
        if not scripts:
            raise ValueError('no script inputs')
        script_literals = {p: literals(t) for p, t in scripts.items()}
        script_classes = [(p, c) for p, t in scripts.items() for c in classes(t)]
        all_script = '\n'.join(scripts.values())
        if r['bundle_profile_catalogue']:
            # Pure repo-source catalogue; no profile reads, git calls, or bundle builds.
            from tools.setup.friend_bundle import repo_profile_sources
            # Generated baseline profiles are inline bytes, not repository files.
            self.profile_sources = {rel: source for rel, source in repo_profile_sources().items()
                                    if not isinstance(source, bytes)}
            for p in self.profile_sources.values():
                if not self.safe(p).is_file():
                    raise ValueError('bundle profile source missing: ' + self.display(p))
        data_paths = sorted(set(self.paths(r['roots']['data'])) | set(self.profile_sources.values()))
        # Configuring the audit must never wire up gameplay through its own allowlists.
        data = {p: self.read(p) for p in data_paths if not any(
            fnmatch.fnmatchcase(self.display(p), pattern) for pattern in r['reference_exclude_patterns'])}
        for p, t in data.items():
            if p.suffix == '.json':
                json.loads(t)
            elif p.suffix == '.xml':
                ET.fromstring(t)
        definitions, known, coverage = self.config_index()
        inherited = {row.get('parent', '').lower() for row in definitions.values() if row.get('parent')}
        nominal = defaultdict(list)
        ce_refs = set()
        ce_paths = self.paths(r['ce_type_patterns'])
        for p in ce_paths:
            t = data.get(p, self.read(p))
            tree = ET.fromstring(t)
            if tree.tag != 'types':
                continue
            for node in tree.iter('type'):
                name = node.get('name')
                if name:
                    n = node.findtext('nominal')
                    nominal[name.lower()].append((p, int(n) if n is not None else None))
                    if name.lower() not in known:
                        at = re.search(r'<type\b[^>]*\bname\s*=\s*["\']' + re.escape(name) + r'["\']', t)
                        self.add('W007', name, p, line(t, at.start()) if at else 1,
                                 'CE type absent from indexed configs; ' + coverage)
        for p, t in data.items():
            if p.suffix == '.xml':
                ce_refs.update(w.lower() for w in WORD.findall(re.sub(r'<!--.*?-->', '', t, flags=re.S)))
        routes, admin_routes = self.spawn_routes(data, scripts, script_classes)
        for key, row in sorted(definitions.items()):
            if key not in routes and not (row['scope'] is not None and row['scope'] < 2 and (key in inherited or row['inherited'])):
                self.add('W001', row['name'], row['path'], row['line'],
                         'No statically resolved production creation route' + ('; admin-only route present' if key in admin_routes else ''))
        for key, rows in sorted(nominal.items()):
            if key not in ce_refs or not all(n == 0 for _, n in rows):
                continue
            for root, indexed in self.indexed.items():
                if key in indexed and pbo_config.resolve_scope(indexed, key) == 2:
                    name, p, n = self.origins[(root, key)]
                    self.add('W001b', name, p, n,
                             'Public CE-referenced class has nominal=0 in every HC types row; event/attachment routes require review')
                    break
        self.zeroed_check(routes)
        self.bundle_check()
        self.data_check(script_literals)
        self.settings_check(scripts, script_classes)
        token_files = defaultdict(set)
        for p, t in scripts.items():
            for token in WORD.findall(t):
                token_files[token].add(p)
        for p, c in script_classes:
            if not c['modded'] and not token_files[c['name']] - {p}:
                self.add('W004', c['name'], p, c['line'], 'No reference outside definition file (engine/config callbacks may be intentional)')
        self.module_check(scripts, script_classes)
        self.rpc_check(scripts, script_classes)
        spawn = re.compile(r'\b(?:' + '|'.join(map(re.escape, r['spawn_calls'])) + r')\s*\(\s*"([^"\n]+)"')
        for p, t in scripts.items():
            for m in spawn.finditer(t):
                if m[1].lower() not in known:
                    self.add('W008', m[1], p, line(t, m.start()), 'Hard-coded spawn class absent from indexed configs; ' + coverage)
        unique = {(f['id'], f['subject'], f['file']): f for f in self.findings}
        return sorted(unique.values(), key=lambda f: (f['id'], f['subject'], f['file']))

    def spawn_routes(self, data, scripts, script_classes):
        """Creation evidence, not arbitrary class-name mentions or catalogues."""
        routes, admin = set(), set()
        data = dict(data)
        for rel in ('cfgspawnabletypes.xml', 'db/events.xml', 'cfgrandompresets.xml'):
            p = self.safe(self.rules['vanilla_mission']) / rel
            if p.is_file():
                data[p] = self.read(p)
        # Use the production transform, including its pinned-stock and conserved
        # child-budget checks. Policy strings alone are not CE creation evidence.
        from tools.package import infected_variety
        policy = json.loads(self.read(infected_variety.POLICY))
        if policy['production_enabled']:
            stock_events = self.safe(self.rules['vanilla_mission']) / infected_variety.TARGET
            self.read(stock_events)  # enforce the input size/path bounds before bytes
            stock = stock_events.read_bytes()
            data[stock_events] = infected_variety.substitute(stock, stock, policy).decode('utf-8-sig')
        for p, text in data.items():
            if p.suffix != '.xml':
                continue
            root = ET.fromstring(text)
            if root.tag == 'types':
                routes.update(n.get('name', '').lower() for n in root.findall('type')
                              if int(n.findtext('nominal') or 0) > 0)
            elif root.tag in ('events', 'spawnabletypes', 'randompresets'):
                routes.update(n.get('type', n.get('name', '')).lower() for n in root.iter()
                              if n.tag in ('child', 'item') and float(n.get('chance', '1')) > 0)
        # Native object-spawner JSON and the layer schema consumed by map_overlay.
        from tools.package import map_overlay
        overlay = map_overlay.load_source(ROOT / 'config/map-overlays')
        for layer in map_overlay.enabled_layers(overlay):
            routes.update(row['class'].lower() for row in map_overlay.expand_layer(overlay, layer))
        for p, text in data.items():
            if p.suffix == '.json':
                doc = json.loads(text)
                registered = any(p.name in self.read(g) for g in self.paths(['mission/**/cfggameplay*.json']))
                if registered and isinstance(doc, dict) and isinstance(doc.get('Objects'), list):
                    routes.update(row['name'].lower() for row in doc['Objects'] if 'name' in row)
        spawn = re.compile(r'\b(?:CreateObject\w*|SpawnEntity\w*|CreateInInventory)\s*\(\s*("[^"\n]+"|[\w.]+)')
        for p, c in script_classes:
            body = c['body']
            for m in spawn.finditer(body):
                target = admin if '/Admin/' in p.as_posix() else routes
                if m[1].startswith('"'):
                    # An uncalled static factory is a diagnostic candidate, not a
                    # production route (notably HCSpawnSitting).
                    prefix = body[:m.start()]
                    methods = list(re.finditer(r'\bstatic\s+\w+\s+(\w+)\s*\([^{};]*\)\s*\{', prefix))
                    if methods:
                        method = methods[-1]
                        tail = mask(prefix[method.end():], strings=True)
                        if tail.count('{') == tail.count('}'):
                            caller = re.compile(r'\.\s*' + re.escape(method[1]) + r'\s*\(')
                            if not any(caller.search(t) for sp, t in scripts.items() if '/Admin/' not in sp.as_posix()):
                                target = admin
                    target.add(m[1][1:-1].lower())
                else:
                    # JSON list member, or a local selected from that list,
                    # must feed the dynamic class argument in this consumer.
                    fields = {m[1].rsplit('.', 1)[-1]} if '.' in m[1] else set()
                    for assignment in re.finditer(r'\b' + re.escape(m[1]) + r'\s*=(?!=)\s*([^;]+)', body):
                        fields.update(re.findall(r'\.(\w+)(?=\[|\.(?:Get|GetRandomElement)\s*\()', assignment[1]))
                    if not fields:
                        continue
                    for value in literals(body):
                        rel = value.replace('$mission:', 'mission/').replace('$profile:', '')
                        candidate = ROOT / rel
                        if not rel.endswith('.json') or not candidate.is_file():
                            continue
                        if not re.search(r'\b(?:Load\w*|Read\w*)\s*\([^;]*"' + re.escape(value) + '"', body):
                            continue
                        def collect(node):
                            if isinstance(node, dict):
                                for k, v in node.items():
                                    if k in fields:
                                        def strings(value):
                                            if isinstance(value, str):
                                                target.add(value.lower())
                                            elif isinstance(value, list):
                                                for item in value:
                                                    strings(item)
                                        strings(v)
                                    collect(v)
                            elif isinstance(node, list):
                                for v in node:
                                    collect(v)
                        collect(json.loads(self.read(candidate)))
        # Follow simple string returns/assignments and uniquely named local
        # factory parameters to the actual creation call. A diagnostic return
        # literal alone supplies no route.
        methods = []
        method_pattern = re.compile(r'\b(?:(static)\s+)?\w+\s+(\w+)\s*\(([^{};]*)\)\s*\{')
        for p, c in script_classes:
            for m in method_pattern.finditer(mask(c['body'], strings=True)):
                depth, end = 1, m.end()
                clean = mask(c['body'], strings=True)
                while end < len(clean) and depth:
                    depth += (clean[end] == '{') - (clean[end] == '}')
                    end += 1
                params = [part.strip().split()[-1] for part in m[3].split(',') if part.strip()]
                methods.append((p, m[2], bool(m[1]), params, c['body'][m.end():end - 1], c['name']))
        constants = {}
        for _, c in script_classes:
            for name, value in re.findall(r'\bconst\s+string\s+(\w+)\s*=\s*"([^"\n]+)"\s*;', c['body']):
                constants[(c['name'], name)] = value.lower()
        byname = defaultdict(list)
        for i, (_, name, _, _, _, _) in enumerate(methods):
            byname[name].append(i)
        qualified = {(m[5], m[1]): i for i, m in enumerate(methods)}
        def resolve(name, caller):
            parts = name.split('.')
            key = (parts[-2] if len(parts) > 1 else methods[caller][5], parts[-1])
            if key in qualified:
                return qualified[key]
            matches = byname[parts[-1]]
            return matches[0] if len(matches) == 1 else None
        expression = r'(?:"[^"\n]*"|\b\w+(?:\.\w+)*(?:\([^();]*\))?)'
        calls = re.compile(r'\b((?:\w+\.)*\w+)\s*\(([^();]*)\)')
        for diagnostic in (False, True):
            active = {i for i, (p, _, static, _, _, _) in enumerate(methods)
                      if ('/Admin/' in p.as_posix()) == diagnostic and not static}
            # Module/engine instance methods are roots; static helpers require
            # a caller from that lane before their literals can count.
            for _ in range(len(methods)):
                added = set()
                for i in active:
                    for call in calls.finditer(methods[i][4]):
                        callee = resolve(call[1], i)
                        if callee is not None:
                            added.add(callee)
                if added <= active:
                    break
                active.update(added)
            variables, returned = defaultdict(set), defaultdict(set)
            def names(expr, i):
                expr = expr.strip()
                if expr.startswith('"') and expr.endswith('"'):
                    return {expr[1:-1].lower()}
                call = re.fullmatch(r'((?:\w+\.)*\w+)\([^()]*\)', expr)
                if call:
                    callee = resolve(call[1], i)
                    if callee is not None:
                        return returned[callee]
                parts = expr.split('.')
                constant = constants.get((parts[-2] if len(parts) > 1 else methods[i][5], parts[-1]))
                return {constant} if constant is not None else variables[(i, expr)]
            for _ in range(12):
                count = sum(map(len, variables.values())) + sum(map(len, returned.values()))
                for i in active:
                    p, name, _, params, body, owner = methods[i]
                    for m in re.finditer(r'\b(\w+)\s*=(?!=)\s*(' + expression + r')\s*;', body):
                        variables[(i, m[1])].update(names(m[2], i))
                    for m in re.finditer(r'\breturn\s+(' + expression + r')\s*;', body):
                        returned[i].update(names(m[1], i))
                    for call in calls.finditer(body):
                        args = call[2].split(',')
                        if re.fullmatch(r'CreateObject\w*|SpawnEntity\w*|CreateInInventory', call[1].rsplit('.', 1)[-1]):
                            (admin if diagnostic else routes).update(names(args[0], i))
                        elif call[1].rsplit('.', 1)[-1] in ('ProcessDirectDamage', 'CloseCombatDamage') and len(args) >= 4:
                            # Native damage descriptors occupy argument four, not
                            # an inventory creation slot (Object.c / DamageSystem).
                            (admin if diagnostic else routes).update(names(args[3], i))
                        else:
                            callee = resolve(call[1], i)
                            if callee is None:
                                continue
                            for param, arg in zip(methods[callee][3], args):
                                variables[(callee, param)].update(names(arg, i))
                if count == sum(map(len, variables.values())) + sum(map(len, returned.values())):
                    break
            # Installed vanilla LightHeavy.EvaluateHit_Common consumes this
            # callback's out ammoType via CloseCombatDamage. An arbitrary output
            # parameter or diagnostic ammo string cannot establish that route.
            for i in active:
                p, name, _, params, body, owner = methods[i]
                if owner == 'DayZPlayerMeleeFightLogic_LightHeavy' and name == 'DummyHitSelector' and len(params) == 2:
                    for assignment in re.finditer(r'\b' + re.escape(params[1]) + r'\s*=(?!=)\s*(' + expression + r')\s*;', body):
                        (admin if diagnostic else routes).update(names(assignment[1], i))
        self.notes.append(f'Creation routes: production={len(routes)} admin-only={len(admin - routes)}')
        return routes, admin

    def zeroed_check(self, routes):
        """Inspect actual row transforms, without installing or faking verification."""
        from tools.package import economy, firearms, datamined_items, loot_boost
        from tools.package import snafu_optional, tactical_flava_optional
        source = self.safe(self.rules['vanilla_mission'])
        stock_path = source / 'db/types.xml'
        stock = economy._unique(ET.fromstring(self.read(stock_path)).findall('type'))
        # This must be a stock source: an already installed HC tree is not a baseline.
        core = ET.fromstring(self.read(source / 'cfgeconomycore.xml'))
        if any(n.get('folder', '').startswith('hollow-country') for n in core.findall('ce')):
            raise ValueError('W009 vanilla_mission contains installed HC overlays')
        limits = ET.fromstring(self.read(source / 'cfglimitsdefinition.xml'))
        usage = economy._unique(limits.findall('./usageflags/usage'))
        values = economy._unique(limits.findall('./valueflags/value'))
        authored = ROOT / 'mission/hollow-country/ce/types.xml'
        owned = {n.get('name', '').lower() for n in ET.fromstring(self.read(authored))}
        roster_path = ROOT / 'tools/package/firearms_roster.json'
        roster = firearms.selected_roster(json.loads(self.read(roster_path)))
        invalid = False
        for entry in roster['entries']:
            budget = entry['set']
            if budget['min'] > budget['nominal']:
                self.add('W009', entry['class'], roster_path, 1,
                         f"previous nominal={int(stock[entry['class']].findtext('nominal') or 0) if entry['class'] in stock else 'unknown'}; min exceeds nominal in generator input; build refuses this row")
                invalid = True
        if invalid:
            return  # The build rejects these rows before the pure transforms.
        changed, _, _ = firearms.roster_items(stock, usage, values, roster, True)
        # economy.generate excludes authored owners from the roster delta.
        generated = [n for n in changed if n.get('name', '').lower() not in owned]
        layers = [(stock_path, list(stock.values()), False), (roster_path, generated, True)]
        profile_path = ROOT / 'mission/hollow-country/economy-profiles/contextual-pilot.json'
        profile = json.loads(self.read(profile_path))
        layers.append((profile_path, [copy.deepcopy(stock[name]) for name in profile['add_usage']], True))
        rows, _ = datamined_items.supply_rows(datamined_items.load_rows(), datamined_items.load_supply_dispositions())
        layers.append((datamined_items.DATA, datamined_items.type_rows(stock, usage, rows=rows, include_new=True, floor=True), True))
        # Include every committed HC types fragment, not spawnabletypes documents.
        for p in self.paths(self.rules['ce_type_patterns']):
            tree = ET.fromstring(self.read(p))
            if tree.tag == 'types':
                layers.append((p, list(tree), True))
        previous = {k.lower(): int(n.findtext('nominal') or 0) for k, n in stock.items()}
        for module in (snafu_optional, tactical_flava_optional):
            path = ROOT / 'tools/package' / (module.__name__.rsplit('.', 1)[-1].replace('_optional', '_allowlist') + '.json')
            allowlist = json.loads(self.read(path))
            # Same pure row pipeline as generate(); do not invent pack verification.
            entries, _, _ = snafu_optional._scaled_entries(allowlist['entries'], allowlist.get('test_abundance_multiplier', 1), None)
            layers.append((path, [module._new_type(e) for e in entries], True))
            previous.update({e['class'].lower(): e['set']['nominal'] for e in allowlist['entries']})
        reasons = json.loads(self.read(ROOT / self.rules['zeroed_items']))
        if not isinstance(reasons, dict) or any(not isinstance(v, str) or not v.strip() or '\n' in v for v in reasons.values()):
            raise ValueError('zeroed-items must map exact class names to one-line reasons')
        exempt = {k.lower(): v for k, v in reasons.items()}
        effective, shipped_count = {}, 0
        for p, nodes, shipped in layers:
            root = ET.Element('types')
            root.extend(copy.deepcopy(nodes))
            scaled, _ = loot_boost.scale_types(ET.tostring(root), loot_boost.default_multiplier(),
                                               frozenset(e['class'].lower() for e in roster['entries']))
            for node in ET.fromstring(scaled):
                name = node.get('name')
                key = name.lower()
                nominal = int(node.findtext('nominal') or 0)
                minimum = int(node.findtext('min') or 0)
                effective[key] = nominal
                if shipped:
                    shipped_count += 1
                    if minimum > nominal or (nominal == 0 and key not in exempt):
                        why = f'previous nominal={previous.get(key, "unknown")}; shipped nominal={nominal} min={minimum}; '
                        why += 'min exceeds nominal' if minimum > nominal else 'zeroed spawnable has no exact reason in config/zeroed-items.json'
                        match = re.search(r'[\"\']' + re.escape(name) + r'[\"\']', self.read(p))
                        self.add('W009', name, p, line(self.read(p), match.start()) if match else 1, why)
        # Stock rows stay shipped by the installer; absence from an HC fragment
        # alone is not lost supply. Compare against the complete effective image.
        for key, nominal in previous.items():
            if nominal > 0 and key not in effective and key not in routes and key not in exempt:
                self.add('W009', key, authored, 1, f'previous nominal={nominal}; no shipped row or other spawn path')
        if not (ROOT / 'tools/package/military_loot.py').exists():
            self.notes.append('No military_loot.py in this checkout; native military quantity policy is in firearms_roster.json')
        self.notes.append(f'W009 stock={len(stock)} shipped fragment rows={shipped_count}; pure firearm/datamined/pack/loot-boost row transforms; native spawning unverified')

    def bundle_check(self):
        """AST-only transitive local imports and repository data closure."""
        from tools.setup import friend_bundle
        shipped = {ROOT / 'tools/package' / n for n in friend_bundle.BUNDLE_TOOLS}
        shipped.update(ROOT / 'tools/setup' / n for n in friend_bundle.SETUP_TOOLS)
        shipped.update(ROOT / rel for rel in getattr(friend_bundle, 'BUNDLE_EXTRA_FILES', ()))
        # Also discover explicit portable helpers appended outside the catalogues.
        for node in ast.walk(ast.parse(self.read(Path(friend_bundle.__file__)))):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == 'append' and node.args and isinstance(node.args[0], ast.Tuple)):
                dest = node.args[0].elts[0]
                if isinstance(dest, ast.Constant) and isinstance(dest.value, str) and dest.value.startswith('tools/'):
                    shipped.add(ROOT / dest.value)
        shipped.update(self.paths(['mission/hollow-country/**/*', friend_bundle.MAP_OVERLAY_CONFIG + '/**/*.json']))
        pending = sorted(p for p in shipped if p.suffix == '.py')
        seen = set()
        exists = {}
        def is_file(path):
            if path not in exists:
                exists[path] = path.is_file()
            return exists[path]
        while pending:
            p = pending.pop()
            if p in seen:
                continue
            seen.add(p)
            tree = ast.parse(self.read(p), filename=self.display(p))
            env = {}
            def value(node):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    return node.value
                if isinstance(node, ast.Name):
                    return env.get(node.id, '' if node.id in ('ROOT', 'REPO_ROOT') else None)
                if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.Add)):
                    a, b = value(node.left), value(node.right)
                    if a is not None and b is not None:
                        return (a.rstrip('/') + '/' + b).lstrip('/') if isinstance(node.op, ast.Div) else a + b
                if isinstance(node, ast.Call) and node.args:
                    if isinstance(node.func, ast.Name) and node.func.id in ('Path', 'str'):
                        return value(node.args[0])
                    if isinstance(node.func, ast.Attribute) and node.func.attr == 'with_name':
                        name = value(node.args[0])
                        if name:
                            return str(p.parent.relative_to(ROOT) / name)
                return None
            for _ in range(4):
                for node in ast.walk(tree):
                    if isinstance(node, ast.Assign):
                        v = value(node.value)
                        if v is not None:
                            for target in node.targets:
                                if isinstance(target, ast.Name):
                                    env[target.id] = v
            dependencies = []
            docstrings = {id(n.value) for n in ast.walk(tree) if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)}
            for node in ast.walk(tree):
                if id(node) in docstrings:
                    continue
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith('tools.'):
                            dependencies.append((alias.name, node.lineno))
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ''
                    if node.level:
                        package = p.parent.relative_to(ROOT).parts
                        module = '.'.join(package[:len(package) - node.level + 1]) + ('.' + module if module else '')
                    if module.startswith('tools'):
                        base = ROOT / (module.replace('.', '/') + '.py')
                        if is_file(base):
                            dependencies.append((module, node.lineno))
                        else:
                            dependencies.extend((module + '.' + alias.name, node.lineno) for alias in node.names)
                # Only path expressions, never prose/docstrings. Resolve constants,
                # Path / joins and with_name JSON defaults as well as full literals.
                v = value(node)
                if v and v.startswith(('config/', 'mission/', 'tools/')) and v.endswith(('.json', '.xml')):
                    dep = ROOT / v
                    if is_file(dep) and dep not in shipped:
                        self.add('W010', v, p, getattr(node, 'lineno', 1), 'Install-time repository data is absent from bundle')
            for module, n in dependencies:
                dep = ROOT / (module.replace('.', '/') + '.py')
                if not is_file(dep):
                    if (ROOT / module.replace('.', '/')).is_dir():
                        continue  # namespace package
                    self.add('W010', module, p, n, 'Local import cannot resolve to repository module')
                    continue
                if dep not in shipped:
                    self.add('W010', self.display(dep), p, n, 'Transitive install-time local import is absent from bundle')
                pending.append(dep)
        self.notes.append(f'W010 inspected {len(seen)} transitive installer modules')

    def config_index(self):
        r = self.rules
        merged = {k: {} for k in r['config_roots']}
        self.origins = {}
        sources, indexed_roots = [], set()
        manifest = json.loads(self.read(ROOT / r['workshop_manifest']))
        dependencies = {str(m['id']) for m in manifest['mods'] if m.get('id') and not m.get('publish')}
        for source in r['class_sources']:
            dep = source.get('dependency')
            if dep and str(dep) not in dependencies:
                raise ValueError('class source dependency is not in Workshop manifest')
            p = self.safe(ROOT / source['path'] if not source['path'].startswith('~') else source['path'])
            if not p.is_file():
                if source.get('required', False):
                    raise ValueError('required class cache missing: ' + self.display(p))
                self.notes.append('Optional class source unavailable: ' + self.display(p))
                continue
            if source['format'] == 'primitive-pickle':
                if p.stat().st_size > 64 * 1024 * 1024:
                    raise ValueError('class cache exceeds budget')
                doc = PrimitiveUnpickler(io.BytesIO(p.read_bytes())).load()['cfg']
            elif source['format'] == 'json':
                doc = json.loads(self.read(p))
            elif source['format'] == 'config':
                doc = pbo_config.parse_text_config(self.read(p), r['config_roots'])
            elif source['format'] == 'rap':
                if p.stat().st_size > pbo_config.MAX_CONFIG_BYTES:
                    raise ValueError('rap cache exceeds budget')
                doc = pbo_config.parse_rap(p.read_bytes(), r['config_roots'])
            else:
                raise ValueError('unsupported class source format')
            for root, rows in doc.items():
                if root in merged:
                    indexed_roots.add(root)
                    for name, row in rows.items():
                        merged[root][name.lower()] = dict(row)
                        self.origins[(root, name.lower())] = (name, p, 1)
            sources.append(source.get('label', self.display(p)))
        self.notes.append('Class index sources: ' + (', '.join(sources) or 'repo only'))
        missing = sorted(set(r['config_roots']) - indexed_roots)
        coverage = 'cache absence is not proof of an undefined engine class'
        if missing:
            self.notes.append('External class-index roots missing: ' + ', '.join(missing))
        cached_deps = {str(s['dependency']) for s in r['class_sources'] if s.get('dependency') and
                       self.safe(s['path'] if s['path'].startswith('~') else ROOT / s['path']).is_file()}
        if dependencies - cached_deps:
            self.notes.append(f'Workshop class-index coverage incomplete: {len(dependencies - cached_deps)} declared dependencies lack a cache')
        definitions = {}
        config_paths = self.paths(r['roots']['configs'])
        if not config_paths:
            raise ValueError('no addon config inputs')
        for p in config_paths:
            text = self.read(p)
            for begin, end in r['generated_blocks']:
                if begin in text:
                    start = text.index(begin)
                    stop = text.find(end, start)
                    if stop < 0:
                        raise ValueError('unterminated generated block: ' + self.display(p))
                    stop += len(end)
                    text = text[:start] + re.sub(r'[^\n]', ' ', text[start:stop]) + text[stop:]
            parsed = pbo_config.parse_text_config(text, r['config_roots'])
            clean = mask(text, strings=True)
            for root, rows in parsed.items():
                for name, row in rows.items():
                    key = name.lower()
                    previous = merged[root].get(key, {})
                    merged[root][key] = {**previous, **{k: v for k, v in row.items() if v is not None}}
                    match = re.search(r'\bclass\s+' + re.escape(name) + r'\b[^;{]*\{', clean)
                    self.origins[(root, key)] = (name, p, line(text, match.start()) if match else 1)
                    definitions[key] = {**row, 'name': name, 'root': root, 'path': p,
                                        'line': line(text, match.start()) if match else 1}
        for rows in merged.values():
            for row in rows.values():
                if row.get('parent'):
                    row['parent'] = row['parent'].lower()
        all_parents = {row.get('parent') for rows in merged.values() for row in rows.values()}
        for key, row in definitions.items():
            row['inherited'] = key in all_parents
            row['scope'] = pbo_config.resolve_scope(merged[row['root']], key)
        self.indexed = merged
        return definitions, {k for rows in merged.values() for k in rows}, coverage

    def data_check(self, script_literals):
        r = self.rules
        # Both deployment and consumer references qualify. A shipped file need not be
        # loaded directly: indexes and native loaders can select it at runtime.
        tool_literals = [s for p in self.paths(r['roots']['tools']) if p != Path(__file__)
                         for s in literals(self.read(p))]
        evidence = [s.replace('\\', '/').lower() for ss in script_literals.values() for s in ss] + [s.lower() for s in tool_literals]
        profile_dest = {p: dest for dest, p in self.profile_sources.items()}
        for p in sorted(set(self.paths(r['roots']['audit_data'])) | set(profile_dest)):
            rel = self.display(p)
            aliases = [rel.lower(), rel.removeprefix('mission/').lower()]
            if p in profile_dest:
                aliases += ['$profile:' + profile_dest[p].lower(), profile_dest[p].lower()]
            found = False
            for s in evidence:
                s = s.rstrip('/')
                if not s or len(s) < r['minimum_path_literal_length']:
                    continue
                for alias in aliases:
                    # Exact filename, full/relative path, directory literal, or glob.
                    if s == p.name.lower() or alias == s or alias.startswith(s + '/') or fnmatch.fnmatchcase(alias, s):
                        found = True
                        break
                if found:
                    break
            if not found and p not in profile_dest:
                self.add('W002', rel, p, 1, 'No script literal, shipping-tool path/pattern or bundle profile catalogue entry')

    def settings_check(self, scripts, script_classes):
        r = self.rules
        registry = {}
        registered_owners = {}
        pattern = re.compile(r'\b' + re.escape(r['registry_call']) + r'\(\s*"([^"\n]+)"')
        for p, c in script_classes:
            if c['name'] != r['settings_registry_class']:
                continue
            for m in pattern.finditer(c['body']):
                registry[m[1]] = (p, line(scripts[p], c['body_start'] + m.start()))
                call = re.match(r'[^;]*?\)', c['body'][m.start():])
                if call:
                    args = literals(call[0])
                    if len(args) >= 3:
                        registered_owners[m[1]] = args[-1]
        mirror_path = ROOT / r['settings_mirror']
        for row in json.loads(self.read(mirror_path)):
            registry.setdefault(row['key'], (mirror_path, 1))
        owner_bodies = defaultdict(list)
        for p, c in script_classes:
            if not c['modded'] or c['name'] != r['settings_registry_class']:
                owner_bodies[c['name']].append(c['body'])
        mirror = {row['key']: row for row in json.loads(self.read(mirror_path))}
        # Remove registry/JSON-presence/default restoration lines: those do not
        # consume a gameplay setting. Keep RHS expressions and member reads.
        metadata = '|'.join(map(re.escape, r['setting_metadata_helpers']))
        metadata_owners = '|'.join(map(re.escape, r['setting_metadata_owners']))
        write_variables = '|'.join(map(re.escape, r['setting_write_only_variables']))
        consumers = {}
        for p, t in scripts.items():
            t = re.sub(r'^.*\b' + re.escape(r['registry_call']) + r'\s*\(.*$', '', t, flags=re.M)
            t = re.sub(r'\b(?:' + metadata_owners + r')\.(?:' + metadata + r')\s*\([^;\n]*', '', t)
            # DTO declarations, writes and generated assignment mirrors are not reads.
            t = re.sub(r'\b(?:bool|int|float|string|ref\s+\w+)\s+\w+\s*(?:=\s*(?:true|false|null|-?[0-9.]+|"[^"]*"))?\s*;', '', t)
            t = re.sub(r'\b(?:' + write_variables + r')\.\w+\s*=(?!=)[^;]*;', '', t)
            consumers[p] = t
        all_consumers = '\n'.join(consumers.values())
        consumer_code = mask(all_consumers, strings=True)
        helpers = '|'.join(r['setting_read_helpers'])
        getter_keys = set(re.findall(r'\b(?:' + helpers + r')\s*\(\s*"([^"\n]+)"', all_consumers))
        # Resolve reads per method so local names reused with different DTO types
        # in another method never contaminate a receiver's type.
        fields = defaultdict(dict)
        methods = []
        method_returns = defaultdict(set)
        method_pattern = re.compile(r'\b(\w+)\s+(\w+)\s*\(([^{};]*)\)\s*\{')
        for p, c in script_classes:
            clean = mask(c['body'], strings=True)
            occupied = []
            for m in method_pattern.finditer(clean):
                depth, end = 1, m.end()
                while end < len(clean) and depth:
                    depth += (clean[end] == '{') - (clean[end] == '}')
                    end += 1
                occupied.append((m.start(), end))
                method_returns[(c['name'], m[2])].add(m[1])
                methods.append((c['name'], m[2], m[3], c['body'][m.end():end - 1]))
            declarations = clean
            for start, end in reversed(occupied):
                declarations = declarations[:start] + ' ' * (end - start) + declarations[end:]
            for typ, name in re.findall(r'\b(\w+)\s+(\w+)\s*(?=[;=])', declarations):
                fields[c['name']].setdefault(name, set()).add(typ)
        resolved, ambiguous = set(), set()
        bare_fields = defaultdict(set)
        all_returns = defaultdict(set)
        for (_, name), types in method_returns.items():
            all_returns[name].update(types)
        for owner, method, params, raw in methods:
            if owner in r['setting_metadata_owners']:
                continue
            # Registry validation, schema-presence and decoded/default copy paths
            # are not gameplay consumers. Preserve RHS gameplay assignment reads.
            raw = re.sub(r'\b(?:' + metadata_owners + r')\.(?:' + metadata + r')\s*\([^;\n]*', '', raw)
            body = mask(raw, strings=True)
            symbols = {name: set(types) for name, types in fields[owner].items()}
            for typ, name in re.findall(r'\b(\w+)\s+(\w+)\s*(?=[;=,)])', params + ',' + body):
                symbols.setdefault(name, set()).add(typ)
            body = re.sub(r'\b(?:bool|int|float|string|ref\s+\w+)\s+\w+\b', '', body)
            body = re.sub(r'\b[\w.]+\s*=(?!=)', '', body)
            # Simplify only argument lists, retaining the method return chain.
            for _ in range(4):
                body = re.sub(r'\([^()]+\)(?=\s*\.)', '()', body)
            for m in re.finditer(r'\b(\w+(?:\(\))?(?:\.\w+(?:\(\))?)+)', body):
                chain = m[1].split('.')
                first = chain.pop(0)
                if first in ('decoded', 'defaults'):
                    continue
                owners = (all_returns.get(first[:-2], set()) if first.endswith('()') else
                          {owner} if first == 'this' else
                          {first} if first in fields else symbols.get(first, set()))
                for part in chain:
                    if part.endswith('()'):
                        name = part[:-2]
                        types = set().union(*(method_returns.get((o, name), set()) for o in owners)) if owners else set()
                        owners = types or all_returns.get(name, set())
                        continue
                    if len(owners) == 1:
                        resolved.add((next(iter(owners)), part))
                    else:
                        ambiguous.add(part)
                    owners = set().union(*(fields[o].get(part, set()) for o in owners)) if owners else set()
            bare_fields[owner].update(re.findall(r'(?<![\w.])\b(\w+)\b(?!\s*\()', body))
        for key, (p, n) in sorted(registry.items()):
            field = key.rsplit('.', 1)[-1]
            # Getter-key literals and member access are the explicit common paths.
            getter = key in getter_keys
            owner = registered_owners.get(key, mirror.get(key, {}).get('owner'))
            read_owners = {owner}
            for (method_owner, method_name), types in method_returns.items():
                if method_owner == owner and re.fullmatch('(?:' + helpers + '|HCConfig|GetSettings)', method_name):
                    read_owners.update(t for t in types if field in fields[t])
            member = any((read_owner, field) in resolved for read_owner in read_owners)
            bare = field in bare_fields.get(owner, set())
            if mirror.get(key, {}).get('type') == 'object':
                bare |= any(k.startswith(key + '.') for k in registry)
            if not (getter or member or bare):
                self.add('W003', key, p, n, 'Registered key has no resolved getter-key, member or owning-class field read' + ('; ambiguous receiver matches require review' if field in ambiguous else ''))

    def module_check(self, scripts, script_classes):
        r = self.rules
        byname = {c['name']: (p, c) for p, c in script_classes if not c['modded']}
        modules = {r['module_base']}
        while True:
            children = {name for name, (_, c) in byname.items() if c['parent'] in modules}
            if children <= modules:
                break
            modules.update(children)
        text = '\n'.join(scripts.values())
        register = re.compile(r'\b' + re.escape(r['module_register']) + r'\s*\(\s*new\s+(\w+)')
        registration_bodies = [(p, c['body']) for p, c in script_classes if c['name'] == r['module_registry_class']]
        registered = {m[1] for _, body in registration_bodies for m in register.finditer(body)}
        for p, body in registration_bodies:
            symbols = dict(re.findall(r'\b\w+\s+(\w+)\s*=\s*new\s+(\w+)', body))
            for variable in re.findall(r'\b' + re.escape(r['module_register']) + r'\s*\(\s*(\w+)\s*\)', body):
                if variable in symbols:
                    registered.add(symbols[variable])
            for factory_class in re.findall(r'\b' + re.escape(r['module_register']) + r'\s*\(\s*(\w+)\.\w+\s*\(', body):
                if factory_class in modules:
                    registered.add(factory_class)
        base = byname.get(r['module_base'])
        base_ready = bool(base) and all(p in base[1]['body'] for p in r['readiness_base_patterns'])
        dispatch_ready = all(pattern in text for pattern in r['readiness_dispatch_patterns'])
        # A constructed/registered subclass realizes the inherited base module too.
        constructed_names = set(re.findall(r'\bnew\s+(\w+)', text))
        for realized in (constructed_names, registered):
            while True:
                parents = {byname[name][1]['parent'] for name in realized if name in byname and byname[name][1]['parent'] in modules}
                if parents <= realized:
                    break
                realized.update(parents)
        for name in sorted(modules - {r['module_base']}):
            p, c = byname[name]
            constructed = name in constructed_names
            reasons = []
            if not constructed:
                reasons.append('HCModule subclass never constructed')
            if name not in registered:
                reasons.append('not passed to module registry')
            if not (base_ready and dispatch_ready):
                reasons.append('shared HCModuleReadiness capture/report path incomplete')
            if reasons:
                self.add('W005', name, p, c['line'], '; '.join(reasons))
        for p, t in registration_bodies:
            for m in register.finditer(t):
                if m[1] not in modules:
                    self.add('W005', m[1], p, line(t, m.start()), 'Registered constructor does not resolve to an HCModule subclass')

    def rpc_check(self, scripts, script_classes):
        r = self.rules
        pattern = re.compile(r['rpc_definition_pattern'])
        if pattern.groups != 2:
            raise ValueError('RPC definition regex must capture name and numeric id')
        scripts = {p: mask(t, strings=True) for p, t in scripts.items()}
        identities = defaultdict(list)
        for p, t in scripts.items():
            for m in pattern.finditer(t):
                owner = next((c['name'] for cp, c in script_classes if cp == p and c['start'] <= m.start() < c['end']), None)
                if owner is None:
                    # Enum declarations use the same balanced-body rule as classes.
                    before = mask(t[:m.start()], strings=True)
                    enums = list(re.finditer(r'\benum\s+(\w+)\s*\{[^}]*$', before, re.S))
                    owner = enums[-1][1] if enums else ''
                identities[(owner, m[1])].append((p, m, int(m[2])))
        send_calls = '|'.join(map(re.escape, r['rpc_send_calls']))
        receive_vars = '|'.join(map(re.escape, r['rpc_receive_variables']))
        for (owner, name), defs in sorted(identities.items()):
            sender = receiver = False
            numeric = str(defs[0][2])
            for p, t in scripts.items():
                # Qualified constants resolve across files; bare constants only in
                # the defining class/enum's file. Same short names are not conflated.
                choices = [re.escape(owner + '.' + name), numeric] if owner else [name, numeric]
                if any(dp == p for dp, _, _ in defs):
                    choices.append(re.escape(name))
                ref = r'(?<![\w.])(?:' + '|'.join(choices) + r')\b'
                sender |= bool(re.search(r'\b(?:' + send_calls + r')\s*\([^;{}]*' + ref, t, re.S))
                receiver |= bool(re.search(r'\b(?:' + receive_vars + r')\s*(?:==|!=)\s*' + ref, t) or
                                 re.search(ref + r'\s*(?:==|!=)\s*(?:' + receive_vars + r')\b', t) or
                                 re.search(r'\bcase\s+' + ref + r'\s*:', t))
            if sender != receiver or not sender:
                p, m, _ = defs[0]
                self.add('W006', (owner + '.' if owner else '') + name, p, line(scripts[p], m.start()),
                         f'RPC sender={str(sender).lower()} receiver={str(receiver).lower()}')


def identity(finding):
    return finding['id'], finding['subject'], finding['file']


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vanilla-mission', help='read-only stock mission under the approved cache or checkout')
    parser.add_argument('--json', action='store_true', help='machine-readable summaries, findings and coverage notes')
    parser.add_argument('--update-baseline', action='store_true', help='prune resolved baseline entries; new findings require explicit review')
    args = parser.parse_args(argv)
    try:
        path = ROOT / 'config/wiring-audit.json'
        supplied = json.loads(Audit(DEFAULTS).read(path))
        rules = {**DEFAULTS, **supplied}
        for key in ('roots', 'checks', 'allowlists'):
            rules[key] = {**DEFAULTS[key], **supplied.get(key, {})}
        if args.vanilla_mission:
            rules['vanilla_mission'] = args.vanilla_mission
        if rules['schema'] != 1 or set(rules['checks']) != set(CHECKS):
            raise ValueError('unsupported schema or check id')
        if not all(rules['checks'][c] for c in ('W009', 'W010')):
            raise ValueError('W009/W010 are mandatory checks')
        if any(type(v) is not bool for v in rules['checks'].values()):
            raise ValueError('check switches must be booleans')
        for entries in rules['allowlists'].values():
            if not isinstance(entries, dict) or any(not isinstance(v, str) or not v.strip() for v in entries.values()):
                raise ValueError('allowlists must map subject patterns to nonempty reasons')
        audit = Audit(rules)
        findings = audit.run()
        baseline_path = audit.safe(ROOT / rules['baseline'])
        if not baseline_path.is_relative_to(ROOT):
            raise ValueError('baseline must be in repository')
        baseline = json.loads(audit.read(baseline_path)) if baseline_path.exists() else {'schema': 1, 'findings': []}
        if baseline.get('schema') != 1:
            raise ValueError('unsupported baseline schema')
        accepted = {}
        for f in baseline['findings']:
            if f['id'] in ('W009', 'W010'):
                raise ValueError('W009/W010 cannot be baselined')
            if not isinstance(f.get('reason'), str) or not f['reason'].strip() or f['id'] not in CHECKS:
                raise ValueError('baseline entries require a valid id and nonempty reason')
            if identity(f) in accepted:
                raise ValueError('duplicate baseline identity')
            accepted[identity(f)] = f['reason']
        if args.update_baseline:
            baseline = {'schema': 1, 'findings': [dict(f, reason=accepted.get(identity(f), rules['baseline_reason'])) for f in findings if identity(f) in accepted and f['id'] not in ('W009', 'W010')]}
            baseline_path.write_text(json.dumps(baseline, indent=2) + '\n')
            accepted = {identity(f): f['reason'] for f in baseline['findings']}
        for f in findings:
            f['new'] = f['id'] in ('W009', 'W010') or identity(f) not in accepted
            if not f['new']:
                f['reason'] = accepted[identity(f)]
        findings.sort(key=lambda f: (not f['new'], f['id'], f['subject'], f['file']))
        totals = Counter(f['id'] for f in findings)
        news = Counter(f['id'] for f in findings if f['new'])
        summary = {c: {'total': totals[c], 'new': news[c], 'enabled': rules['checks'][c]} for c in CHECKS}
        stale = len(set(accepted) - {identity(f) for f in findings})
        if args.json:
            print(json.dumps({'schema': 1, 'summary': summary, 'notes': audit.notes,
                              'stale_baseline_entries': stale, 'findings': findings}, indent=2))
        else:
            for c in CHECKS:
                print(f'{c} total={totals[c]} new={news[c]}' + ('' if rules['checks'][c] else ' disabled'))
            for note in audit.notes:
                print('NOTE ' + note)
            if stale:
                print(f'NOTE stale_baseline_entries={stale}; --update-baseline prunes resolved findings')
            for f in findings:
                print(f"{'NEW' if f['new'] else 'BASELINE'} {f['id']} {f['subject']} {f['file']}:{f['line']} {f['why']}")
        return int(any(news.values()))
    except (OSError, ValueError, SyntaxError, ImportError, TypeError, KeyError, AttributeError, re.error, ET.ParseError, pickle.UnpicklingError, EOFError, RecursionError) as error:
        # Paths from third-party exceptions can contain home directories.
        message = str(error).replace(str(Path.home()), '~')
        if args.json:
            print(json.dumps({'error': message, 'schema': 1}))
        else:
            print('wiring audit input error: ' + message, file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
