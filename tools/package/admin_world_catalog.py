"""Generate admin-only map anchors from repository data and official stock CE.

Run from the repository root before packaging. No profile/installed server inputs.
Generation fetches the pinned upstream input in memory; only derived anchors ship.
The --check mode reuses its recorded SHA-256 and reads local repository inputs only.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
# Official Bohemia source; explicit revision is recorded beside the derived data.
UPSTREAM = 'https://raw.githubusercontent.com/BohemiaInteractive/DayZ-Central-Economy/7bfc95cb9f6fb676311cef76be80050314b2cc16/dayzOffline.chernarusplus/cfgeventspawns.xml'

CATALOG = Path('mods/HollowCountry/scripts/4_World/Admin/HCAdminWorldCatalog.c')
DATA = Path('mission/hollow-country/admin/world-catalog.json')
OUTPUTS = (str(CATALOG), str(DATA))
JSON_INPUTS = (
    'mission/hollow-country/ai/sites.json',
    'mission/hollow-country/events/story-sites.json',
    'mission/hollow-country/leads/localities.json',
    'mission/hollow-country/travel/auditshelter_scenes.json',
)

CE_INPUTS = (
    'mission/hollow-country/ce/hc-eventspawns.xml',
    'mission/hollow-country/events/cache-eventspawns.xml',
    'mission/hollow-country/vehicles/vehexp-eventspawns.xml',
)


def local_inputs(root):
    """The same ordered inputs feed generation and the offline package check."""
    names = list(JSON_INPUTS)
    names += [path.relative_to(root).as_posix()
              for path in sorted((root / 'config/map-overlays/layers').glob('*.json'))]
    names += [name for name in CE_INPUTS if (root / name).exists()]
    return {name: (root / name).read_bytes() for name in names}


def inputs_digest(inputs, stock_sha256):
    digest = hashlib.sha256()
    # Names and lengths frame each contribution, including optional input presence.
    for name, data in inputs.items():
        digest.update(name.encode() + b'\0' + str(len(data)).encode() + b'\0' + data)
    digest.update(UPSTREAM.encode() + b'\0' + stock_sha256.encode())
    return digest.hexdigest()


def check(root=ROOT):
    """Refuse stale/missing provenance without fetching or reading stock CE."""
    refusal = 'stale admin world catalog; regenerate with python3 -B -m tools.package.admin_world_catalog'
    try:
        header = (root / CATALOG).read_text(encoding='utf-8').splitlines()[:4]
        source = [line.removeprefix('// Official CE source: ') for line in header
                  if line.startswith('// Official CE source: ')]
        stock = [line.removeprefix('// Stock CE sha256: ') for line in header
                 if line.startswith('// Stock CE sha256: ')]
        recorded = [line.removeprefix('// Inputs digest: ') for line in header
                    if line.startswith('// Inputs digest: ')]
        if (source != [UPSTREAM] or len(stock) != 1 or len(recorded) != 1
                or not re.fullmatch('[0-9a-f]{64}', stock[0])
                or not re.fullmatch('[0-9a-f]{64}', recorded[0])
                or inputs_digest(local_inputs(root), stock[0]) != recorded[0]):
            raise ValueError(refusal)
        payload = (root / DATA).read_bytes()
        data = json.loads(payload)
        if (f'// Data sha256: {hashlib.sha256(payload).hexdigest()}' not in (root / CATALOG).read_text()
                or data['Version'] != int(recorded[0][:7], 16)
                or data['Count'] != len(data['Rows'])):
            raise ValueError(refusal)
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError(refusal) from exc


def generate(output=None):
    rows = []
    inputs = local_inputs(ROOT)

    def load(name):
        return json.loads(inputs[name])

    def add(layer, pos, label, detail):
        if len(pos) != 3 or not (0 <= pos[0] <= 15360 and 0 <= pos[2] <= 15360):
            raise ValueError('invalid catalog coordinate')
        rows.append((layer, pos, label, detail))

    for row in load('mission/hollow-country/ai/sites.json')['Sites']:
        add('ai-sites', (row.get('Waypoints') or [row['HousePosition']])[0], row['Id'], 'Authored AI site; faction=' + row['Faction'] + '; role=' + row['Kind'] + '; not live occupancy')
    for row in load('mission/hollow-country/events/story-sites.json')['Sites']:
        add('story-sites', row['Anchor'], row['Id'], 'Authored story candidate; not an active event')
    for row in load('mission/hollow-country/leads/localities.json')['Localities']:
        add('localities', row['Position'], row['Name'], 'Authored locality')
    shelters = load('mission/hollow-country/travel/auditshelter_scenes.json')
    for row in shelters['Scenes'] + shelters['AdditionalScenes']:
        add('shelter-sites', row['Position'], row['Name'], 'Authored shelter; native access/rain verification pending')
    for name in inputs:
        if not name.startswith('config/map-overlays/layers/'):
            continue
        data = load(name)
        layer = data['id'].rsplit('-v', 1)[0]
        for row in data.get('sites', []):
            add(layer, row['pos'], row['id'], 'Authored overlay: ' + row['composition'] + '; installation/placement not inferred')
        for index, row in enumerate(data.get('objects', [])):
            pos = row.get('pos')
            if pos:
                add(layer, pos, str(index), 'Authored object: ' + row.get('type', row.get('class', 'object')))
    # A pinned official-source derivation is reproducible without shipping a vanilla dump.
    with urllib.request.urlopen(UPSTREAM, timeout=45) as response:
        stock = response.read(4_000_000)
    stock_sha256 = hashlib.sha256(stock).hexdigest()
    digest = inputs_digest(inputs, stock_sha256)
    for event in ET.fromstring(stock).findall('event'):
        for pos in event.findall('pos'):
            add('vanilla-ce-spawns', [float(pos.attrib['x']), 0, float(pos.attrib['z'])], event.attrib['name'], 'Stock CE candidate; not a live event or vehicle')
    for name in CE_INPUTS:
        if name not in inputs:
            continue
        data = inputs[name]
        for event in ET.fromstring(data).findall('event'):
            for pos in event.findall('pos'):
                add('hc-ce-spawns', [float(pos.attrib['x']), 0, float(pos.attrib['z'])], event.attrib['name'], 'Packaged HC CE candidate; not live occupancy')
    if len(rows) > 8192:
        raise ValueError('catalog exceeds stream cap')
    version = int(digest[:7], 16)
    payload = render_data(rows, version)
    data_path = output.with_suffix(".json") if output is not None else ROOT / DATA
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(payload, encoding='utf-8')
    (output if output is not None else ROOT / CATALOG).write_text(render(rows, version, stock_sha256, digest), encoding='utf-8')
    print(f'Generated {len(rows)} anchors; version={version}; stock_sha256={stock_sha256}')


def render_data(rows, version):
    # Match the previous generated Vector precision and preserve exact wire order.
    marks = [dict(Layer=layer, Position=[float(f'{v:.3f}') for v in pos],
                  Label=label, Detail=detail) for layer, pos, label, detail in rows]
    return json.dumps(dict(Version=version, Count=len(marks), Rows=marks),
                      ensure_ascii=True, separators=(',', ':')) + '\n'


def render(rows, version, stock_sha256, digest):
    header = ['// Generated by tools.package.admin_world_catalog; derived anchors only, no raw stock dump.',
              '// Official CE source: ' + UPSTREAM,
              '// Stock CE sha256: ' + stock_sha256,
              '// Inputs digest: ' + digest,
              '// Data sha256: ' + hashlib.sha256(render_data(rows, version).encode()).hexdigest()]
    return '\n'.join(header) + '\n' + RUNTIME.replace('@VERSION@', str(version)).replace('@COUNT@', str(len(rows)))


RUNTIME = r'''// Lazy bounded array reader. No file opens until Step; at most 1024 bytes
// scanned/read per visit, one object decoded by the caller. Native inspected:
// EnSystem.c:417/425/443; EnString.c:113/448; JsonFileLoader.c:69.
class HCAdminJsonRows
{
    string Preamble;
    bool Done;
    bool Failed;
    protected string m_Path;
    protected int m_Limit;
    protected int m_Bytes;
    protected FileHandle m_File;
    protected bool m_Opened;
    protected bool m_HasFile;
    protected string m_Chunk;
    protected ref HCTextWindow m_Window;
    protected int m_Cursor;
    protected string m_Row;
    protected int m_Depth;
    protected bool m_Array;
    bool HCArrayStarted() { return m_Array; }
    protected bool m_Quoted;
    protected bool m_Escape;

    void HCAdminJsonRows(string path, int limit)
    {
        m_Path = path;
        m_Limit = limit;
    }
    void ~HCAdminJsonRows() { Close(); }
    void Close()
    {
        if (m_HasFile) { CloseFile(m_File); m_HasFile = false; }
    }
    void Fail()
    {
        Failed = true;
        Done = true;
        Close();
    }
    bool Step(out string row)
    {
        row = "";
        if (Done) { return false; }
        if (!m_Opened)
        {
            m_Opened = true;
            m_File = OpenFile(m_Path, FileMode.READ);
            if (m_File) { m_HasFile = true; }
            if (!m_HasFile) { Fail(); }
            return false;
        }
        if (m_Cursor >= m_Chunk.Length())
        {
            m_Chunk = "";
            m_Cursor = 0;
            int count = ReadFile(m_File, m_Chunk, 1024);
            m_Window = new HCTextWindow(m_Chunk);
            m_Bytes += count;
            if (count <= 0 || m_Bytes > m_Limit) { Fail(); }
            return false;
        }
        if (m_Chunk.Length() > 1024) { Fail(); return false; }
        // Chunk is <=1024 bytes: native Get never walks a growing full file.
        for (int visit = 0; visit < 1024 && m_Cursor < m_Chunk.Length(); visit++)
        {
            string ch = m_Window.At(m_Cursor);
            m_Cursor++;
            if (!m_Array) { Preamble += ch; }
            else if (m_Depth > 0) { m_Row += ch; }
            if (m_Quoted)
            {
                if (m_Escape) { m_Escape = false; }
                else if (ch == "\\") { m_Escape = true; }
                else if (ch == "\"") { m_Quoted = false; }
            }
            else if (ch == "\"") { m_Quoted = true; }
            else if (!m_Array && ch == "[") { m_Array = true; }
            else if (m_Array && ch == "{")
            {
                if (m_Depth == 0) { m_Row = "{"; }
                m_Depth++;
            }
            else if (m_Array && ch == "}")
            {
                m_Depth--;
                if (m_Depth == 0) { row = m_Row; m_Row = ""; return true; }
                if (m_Depth < 0) { Fail(); return false; }
            }
            else if (m_Array && m_Depth == 0 && ch == "]") { Done = true; Close(); return false; }
            if (Preamble.Length() > 4096 || m_Row.Length() > 32768) { Fail(); return false; }
        }
        return false;
    }
}
class HCAdminWorldCatalog
{
    static const int VERSION = @VERSION@;
    static const int COUNT = @COUNT@;
    static const string PATH = "$mission:hollow-country/admin/world-catalog.json";
    protected ref HCAdminJsonRows m_Stream = new HCAdminJsonRows(PATH, 4194304);
    protected bool m_Checked;
    protected int m_Count;
    bool Failed;
    void Close() { m_Stream.Close(); }
    // Called only by the authenticated subscription's retained static job.
    bool Step(HCAdminWorldCapture capture)
    {
        string text;
        bool found = m_Stream.Step(text);
        string error;
        if (!m_Checked && m_Stream.HCArrayStarted())
        {
            HCAdminWorldCatalogHeader header;
            if (!JsonFileLoader<HCAdminWorldCatalogHeader>.LoadData(m_Stream.Preamble + "]}", header, error) || !header || header.Version != VERSION || header.Count != COUNT)
            {
                m_Stream.Fail();
            }
            m_Checked = true;
        }
        if (found && !m_Stream.Failed)
        {
            HCAdminMark mark;
            if (!JsonFileLoader<HCAdminMark>.LoadData(text, mark, error) || !mark || m_Count >= COUNT) { m_Stream.Fail(); }
            else { capture.Put(mark.Layer, mark.Position, mark.Label, mark.Detail); m_Count++; }
        }
        Failed = m_Stream.Failed;
        if (m_Stream.Done && (!m_Checked || m_Count != COUNT)) { Failed = true; }
        return m_Stream.Done;
    }
}
'''


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--check', action='store_true', help='check local inputs offline; do not regenerate')
    parser.add_argument('--out', type=Path, help='generated catalogue destination')
    args = parser.parse_args(argv)
    try:
        if args.check:
            check()
            print('Admin world catalog inputs are current (offline check)')
        else:
            generate(args.out)
    except (ValueError, OSError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
