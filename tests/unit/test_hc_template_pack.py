"""HC-24 synthetic pack IO; offline counts never establish DayZ admission or fit.

Actual initial RED (2026-11-18): ValueError: index.json: size outside limits.
Command (RED and GREEN): PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit
python3 -m unittest test_hc_template_pack -v.
Trace: HC-24 (docs/OUTSTANDING.md); master spec/plan/tasks owned by HC-11.
"""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from tools.package import interiors_profile as ip
from tests.unit.test_interior_templates_runtime import pack


def synthetic_build(directory, count, source_count=8):
    """Explicit synthetic schema-2 input: many covered classes, zero furniture."""
    docs = pack()
    original = docs['t-0000.json']
    sources = docs['index.json']['Sources']
    sources.update({key: 'a' * 64 for key in ip.TEMPLATE_SOURCES})
    while len(sources) < source_count:
        sources['census-' + format(len(sources), '032x')] = 'a' * 64
    files, rows = {}, []
    for number in range(count):
        cls = 'Land_Synthetic_Pack_' + str(number).zfill(4) + '_' + 'X' * 60
        template = copy.deepcopy(original)
        template['BuildingClass'] = cls
        template['TemplateId'] = 'synthetic-' + str(number)
        template['SearchSites'] = []
        files[f't-{number:04d}.json'] = ip._compact(template)
        rows.append(dict(BuildingClass=cls, Rooms='covered', Furniture='not_in_mapgrouppos', Search='no_ce_points'))
    for chunk, offset in enumerate(range(0, len(rows), 100)):
        files[f'classes-{chunk:03d}.json'] = ip._compact(dict(SchemaVersion=2, Chunk=chunk, Rows=rows[offset:offset+100]))
    manifest = dict(SchemaVersion=2, Kind='hc-interior-templates-build', PackId='b'*32,
                    Provisional=True, Frame='rot90', Sources=sources,
                    Files=[dict(File=n, Sha256=ip.sha(raw), Bytes=len(raw)) for n, raw in sorted(files.items())])
    directory.mkdir()
    for name, raw in files.items():
        (directory / name).write_bytes(raw)
    (directory / 'build-manifest.json').write_bytes(ip._compact(manifest))
    return files


class TemplatePackTests(unittest.TestCase):
    def test_complete_bounded_pack_refuses_damage_and_migrates_without_gameplay_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            authored = synthetic_build(root / 'build', 180)
            report = ip.templates_assemble(root / 'build', root / 'pack')
            files = {p.name: p.read_bytes() for p in (root / 'pack/templates').iterdir()}
            self.assertEqual(len(report['index']['TemplateFiles']), 180)
            self.assertEqual(report['summary']['furnish_props'], 0)
            self.assertEqual(report['summary']['rooms']['covered'], 180)
            self.assertTrue(all(len(raw) <= ip.MEASURED_TEXT_LIMIT for raw in files.values()))
            self.assertEqual(json.loads(files['index.json'])['SchemaVersion'], 3)
            self.assertGreater(len(ip._compact(report['index'])), ip.MEASURED_TEXT_LIMIT)
            for name, raw in authored.items():
                self.assertEqual(files[name], raw)
            page = json.loads(files['index.json'])['IndexFiles'][0]['File']
            for name in (page, 't-0179.json', 'classes-001.json'):
                with self.subTest(missing=name):
                    damaged = dict(files)
                    del damaged[name]
                    with self.assertRaises(ValueError):
                        ip._validate_templates(damaged)
                with self.subTest(corrupt=name):
                    damaged = dict(files, **{name: files[name] + b' '})
                    with self.assertRaisesRegex(ValueError, 'Sha256'):
                        ip._validate_templates(damaged)
            # Execute the authored staged reader through synthetic native ports.
            # Reserved strict schema-table edits are supplied in memory, pending native integration.
            runtime = pack_reader(files)
            job = runtime['HCInteriorPackJob']()
            self.assertTrue(runtime['HCStart'](job, 'synthetic/'))
            budget = SyntheticBudget(False)
            before = len(runtime['reads'])
            self.assertEqual(runtime['HCStep'](job, budget), 1)
            self.assertEqual(len(runtime['reads']), before)
            budget.allowed = True
            while runtime['HCStep'](job, budget) == 1:
                pass
            self.assertTrue(job.Ready)
            self.assertEqual(job.Index.TemplateFiles.Count(), 180)
            self.assertEqual(job.Index.PackId, report['index']['PackId'])
            last = job.Index.TemplateFiles[-1]
            loaded = runtime['HCReadChunk'](job, last.FileName, 'template', last.Sha256)
            self.assertEqual(json.loads(loaded)['BuildingClass'], last.BuildingClass)
            runtime['HCReceipt'](job, 180, True)
            self.assertIn('classes=180 state=ready refused=none', runtime['logs'][-1])
            self.assertEqual(runtime['HCReadChunk'](job, '../escape.json', 'template', 'a'*64), '')
            self.assertEqual(job.Reason, 'chunk_before_index_or_pin')
            runtime['HCReset'](job)
            self.assertFalse(job.Started)
            runtime['HCReceipt'](job, 0, False)
            self.assertIn('state=off', runtime['logs'][-1])
            self.assertEqual(job.Files, 0)
            for name in (page, 't-0179.json'):

                damaged = dict(files)
                del damaged[name]
                ports = pack_reader(damaged)
                failed = ports['HCInteriorPackJob']()
                ports['HCStart'](failed, 'synthetic/')
                while ports['HCStep'](failed, budget) == 1:
                    pass
                if name.startswith('t-'):
                    binding = failed.Index.TemplateFiles[-1]
                    self.assertEqual(ports['HCReadChunk'](failed, name, 'template', binding.Sha256), '')
                self.assertFalse(failed.Ready)
                self.assertIn('file_size_or_read', failed.Reason)
            for change, reason in [('malformed', 'index_page_strict'), ('oversize', 'file_size_or_read')]:
                damaged = dict(files)
                damaged[page] = b'{' if change == 'malformed' else b' ' * 32768
                ports = pack_reader(damaged)
                failed = ports['HCInteriorPackJob']()
                ports['HCStart'](failed, 'synthetic/')
                self.assertEqual(ports['HCStep'](failed, budget), 2)
                self.assertIn(reason, failed.Reason)
                reads = len(ports['reads'])
                self.assertFalse(ports['HCStart'](failed, 'synthetic/'))
                self.assertEqual(len(ports['reads']), reads)
            damaged = dict(files)
            duplicate = json.loads(damaged[page])
            duplicate['SourcePins'].append(duplicate['SourcePins'][0])
            damaged[page] = ip._compact(duplicate)
            root_index = json.loads(damaged['index.json'])
            root_index['IndexFiles'][0]['Sha256'] = ip.sha(damaged[page])
            damaged['index.json'] = ip._compact(root_index)
            with self.assertRaisesRegex(ValueError, 'index_source_duplicate'):
                ip._validate_templates(damaged)
            ports = pack_reader(damaged)
            failed = ports['HCInteriorPackJob']()
            ports['HCStart'](failed, 'synthetic/')
            self.assertEqual(ports['HCStep'](failed, budget), 2)
            self.assertEqual(failed.Reason, 'index_source_duplicate_or_pin')
            # Stopped-server receipt protocol includes every page; rollback keeps unrelated state.
            target = root / 'HollowCountry'
            target.mkdir()
            (target / 'operator.txt').write_bytes(b'synthetic operator bytes')
            ip.templates_install(root / 'pack', target, server_stopped=True)
            self.assertEqual((target / 'templates' / page).read_bytes(), files[page])
            ip.templates_rollback(target, server_stopped=True)
            self.assertEqual({p.name for p in target.iterdir()}, {'operator.txt'})
            # Explicit legacy migration preserves identity, source pins and exact leaf bytes.
            small = synthetic_build(root / 'small', 1)
            old = ip.templates_assemble(root / 'small', root / 'old')
            migrated = ip.templates_migrate(root / 'old', root / 'migrated')
            self.assertEqual(old['index'], migrated['index'])
            for name, raw in small.items():
                self.assertEqual((root / 'migrated/templates' / name).read_bytes(), raw)
            self.assertEqual(json.loads((root / 'migrated/templates/index.json').read_bytes())['SchemaVersion'], 3)
            legacy_files = {p.name:p.read_bytes() for p in (root / 'old/templates').iterdir()}
            legacy = pack_reader(legacy_files)
            legacy_job = legacy['HCInteriorPackJob']()
            self.assertTrue(legacy['HCStart'](legacy_job, 'synthetic/'))
            self.assertEqual(legacy['HCStep'](legacy_job, budget), 0)
            self.assertEqual(legacy_job.Index.PackId, old['index']['PackId'])
            # Maximum template/source counts still page; these are unchanged contract caps.
            synthetic_build(root / 'full', 512, source_count=520)
            maximum = ip.templates_assemble(root / 'full', root / 'full-pack')
            self.assertEqual(len(maximum['index']['TemplateFiles']), 512)
            self.assertEqual(len(maximum['index']['Sources']), 520)
            maximum_files = {p.name:p.read_bytes() for p in (root / 'full-pack/templates').iterdir()}
            ports = pack_reader(maximum_files)
            full_job = ports['HCInteriorPackJob']()
            self.assertTrue(ports['HCStart'](full_job, 'synthetic/'))
            while ports['HCStep'](full_job, budget) == 1:
                pass
            self.assertTrue(full_job.Ready)
            self.assertEqual(full_job.Index.TemplateFiles.Count(), 512)
            self.assertEqual(full_job.Index.Sources.Count(), 520)


class SyntheticBudget:
    def __init__(self, allowed): self.allowed = allowed
    def HCContinue(self): return self.allowed


def pack_reader(files):
    """Restricted Enforce execution; IO/config/strict integration are explicit ports.

    No Python placement/loading policy. This executes the authored job, merge and
    refusal bodies. Native deserialization is a stand-in and strict-schema additions
    are applied in memory; exact-source DayZ compile remains pending.
    """
    import re
    from types import SimpleNamespace as NS
    from tests.unit.test_group_server import EArray, body
    from tests.unit.test_interior_measured_catalog import statements
    from tests.unit.test_interior_templates_runtime import EMap, authored, fixture
    source = (ip.ENFORCE_SOURCES / 'HCInteriorPackIndex.c').read_text()
    class Map(EMap):
        def Contains(self, key): return key in self
    env = dict(EArray=EArray, EMap=Map, len=len, reads=[], logs=[])
    env.update({k: v for k, v in authored().items() if k.startswith('HCInteriorTemplate')})
    for match in re.finditer(r'class (HCInteriorPack\w+)\s*\{', source):
        fields = re.findall(r'^\s*(?:ref )?([\w<>, ]+?) (\w+)(?:\s*=\s*([^;]+))?;', body(source, match.end()), re.M)
        def make(fields=fields):
            obj = NS()
            for typ, key, initial in fields:
                value = EArray() if 'array<' in typ else EMap() if 'map<' in typ else (
                    env[typ]() if initial and initial.startswith('new ') else
                    json.loads(initial) if initial else {'string':'', 'int':0, 'bool':False}.get(typ))
                setattr(obj, key, value)
            return obj
        env[match[1]] = make
    base_index = env['HCInteriorTemplateIndex']
    def make_index():
        value = base_index()
        value.Sources = Map()
        return value
    env['HCInteriorTemplateIndex'] = make_index
    # Native byte count/length is an explicit synthetic port, including oversize and truncation.
    def read(path, cap):
        env['reads'].append(path)
        raw = files.get(path.removeprefix('synthetic/'), b'')[:cap]
        return len(raw), raw.decode('ascii')
    env.update(OpenFile=lambda path, mode: path, FileMode=NS(READ=0), CloseFile=lambda handle: None,
               NativeRead=read, Print=env['logs'].append)
    # Exercise the actual authored token/remap parser with ONLY the lead's
    # three schema-table additions supplied in memory. No reserved file is edited.
    existing, *_ = fixture()
    old_keys, old_child, old_cap = existing['Keys'], existing['Child'], existing['ArrayCap']
    existing['Keys'] = lambda schema: ip._TEMPLATE_KEYS[schema] if schema.startswith('pack-') else old_keys(schema)
    existing['Child'] = lambda schema, key: (
        '@file' if key == 'IndexFiles' else '@pack-source' if key == 'SourcePins' else old_child(schema, key))
    existing['ArrayCap'] = lambda schema: 520 if schema == '@pack-source' else old_cap(schema)
    env['HCInteriorTemplatesStrict'] = NS(NativeText=existing['NativeText'],
        SourceName=existing['SourceName'], Hex=existing['Hex'])
    env['HCSearchRules'] = NS(PinValid=ip.hash_ok)
    env['HCInteriorTemplates'] = NS(IndexValid=existing['IndexValid'], Numbered=existing['Numbered'])
    def load(typ, raw, target):
        try:
            doc = json.loads(raw)
        except ValueError:
            return False
        def convert(value):
            if isinstance(value, list): return EArray(convert(v) for v in value)
            if isinstance(value, dict): return NS(**{k:convert(v) for k,v in value.items()})
            return value
        for key, value in doc.items():
            setattr(target, key, EMap(value) if key == 'Sources' else convert(value))
        return True
    env['NativeLoad'] = load
    source = re.sub(r'//[^\n]*', '', source)
    for match in re.finditer(r'static ([\w<> ]+?) (HC\w+)\(([^)]*)\)\s*\{', source):
        name = match[2]
        args = [arg.strip().split()[-1] for arg in re.sub(r'<[^>]*>', '', match[3]).split(',') if arg.strip()]
        lines, indent = [f'def {name}({", ".join(args)}):'], 1
        for token in statements(body(source, match.end())):
            token = token.strip()
            if not token or token == ';': continue
            if token == '{': indent += 1; continue
            if token == '}': indent -= 1; continue
            literals = []
            def protect(m): literals.append(m[0]); return f'__LITERAL_{len(literals)-1}__'
            token = re.sub(r'"(?:\\.|[^"\\])*"', protect, token)
            token = re.sub(r'JsonFileLoader<(\w+)>\.LoadData\(([^,]+), ([^,]+), [^)]+\)', r'NativeLoad("\1", \2, \3)', token)
            token = re.sub(r'int (\w+) = ReadFile\(([^,]+), (\w+), ([^)]+)\)', r'\1, \3 = NativeRead(\2, \4)', token)
            token = re.sub(r'new (HC\w+)(?:\(\))?', r'\1()', token)
            token = re.sub(r'(?:HC\w+|int|float|bool|string|FileHandle)\s+(?=\w+\s*=)', '', token)
            bare = re.fullmatch(r'(int|bool|string|HC\w+) (\w+)', token)
            if bare: token = bare[2]+' = '+{'int':'0','bool':'False','string':"''"}.get(bare[1],'None')
            token = re.sub(r'([\w.]+)\.Length\(\)\.ToString\(\)', r'str(len(\1))', token)
            token = re.sub(r'([\w.]+)\.Length\(\)', r'len(\1)', token)
            token = re.sub(r'([\w.]+)\.ToString\(\)', r'str(\1)', token)
            token = token.replace('&&', ' and ').replace('||', ' or ')
            token = re.sub(r'!(?!=)', 'not ', token)
            for old, new in [('true','True'), ('false','False'), ('null','None')]:
                token = re.sub(r'\b'+old+r'\b', new, token)
            if token.startswith(('if (','while (')):
                prefix, condition = token.split(' (',1); token = prefix+' '+condition[:-1]+':'
            elif token.startswith('foreach ('):
                loop = re.fullmatch(r'foreach \(\w+ (\w+) : (.+)\)', token)
                token = f'for {loop[1]} in {loop[2]}:'
            elif token == 'else': token += ':'
            for index, literal in enumerate(literals): token = token.replace(f'__LITERAL_{index}__', literal)
            lines.append('    '*indent+token)
        exec(compile('\n'.join(lines), 'authored-pack-index:'+name, 'exec'), env)
    return env


if __name__ == '__main__':
    unittest.main()
