"""Stage/ingest a disposable native overlay survey; never launch DayZ.

Lead: stage --destination <empty-runtime>, run the staged mission with the shared
native host lock, then ingest --rpt <RPT> --plan <ce-probe-plan.json>
--out <measured-heights.json>. The existing Start-CEProbeServer.ps1 -Kind ce-probe
launcher accepts this plan; probe_kind distinguishes the overlay survey.
No authored overlay or measurement is overwritten.
The stock diagnostic mission contains no HC overlays. Each temporary local prop
is deleted before the next sample. Collision uses a fixed 2 m geometry-only box,
not the model footprint. Orientation readback verifies SetOrientation only;
candidate CE rpy/a conversion and slopelandcontact still require native review.
"""
import argparse
import datetime
import json
import math
from pathlib import Path
import re
import secrets

from tools.package import map_overlay as overlay
from tools.setup import probe_runtime as rt

PLAN_NAME = 'ce-probe-plan.json'
HARD_CAP = 7000
CHUNK = 4
MAX_RPT_BYTES = 128 * 1024 * 1024
IDENT = re.compile(r'[A-Za-z0-9_-]+:[A-Za-z0-9_-]+')


def targets(source=overlay.SOURCE):
    source = overlay.load_source(source)
    overlay.check(source)
    rows = []
    for layer in overlay.enabled_layers(source):
        for obj in overlay.expand_layer(source, layer):
            rows.append(dict(id=layer['id'] + ':' + obj['id'], **{
                'class': obj['class'], 'x': obj['pos'][0], 'z': obj['pos'][2],
                'authored_y': obj['pos'][1], 'yaw': obj['yaw'], 'loot': obj['loot']}))
    validate_targets(rows)
    return rows


def validate_targets(rows):
    if not isinstance(rows, list) or not 0 < len(rows) <= HARD_CAP:
        raise ValueError('invalid target count')
    seen = set()
    for row in rows:
        if (not isinstance(row, dict) or not IDENT.fullmatch(row.get('id', ''))
                or row['id'] in seen or not re.fullmatch(r'[A-Za-z0-9_]+', row.get('class', ''))
                or any(not overlay.finite(row.get(k)) for k in ('x', 'z', 'authored_y', 'yaw'))
                or any(not 0 < row[k] < 15360 for k in ('x', 'z'))):
            raise ValueError('invalid or duplicate target')
        seen.add(row['id'])


def binding(rows, stock_sha, run_id):
    return rt.sha256(overlay.canonical([rows, stock_sha, run_id, rt.SERVER_EXE_SHA256]))


HOOK = r'''
// Native snapshot 1.30.164289: 3_Game/Global/Game.c SurfaceY:1176,
// SurfaceGetNormal:1188, IsBoxColliding:1333, CreateObject:693, ObjectDelete:705;
// 3_Game/Entities/Object.c GetOrientation:305, SetOrientation:311.
// Diagnostic only: local non-physics props, no loot/persistence, one at a time.
class HCDisposableDiagnosticMission : CustomMission
{
    protected ref array<string> m_Ids = new array<string>;
    protected ref array<string> m_Classes = new array<string>;
    protected ref array<vector> m_Positions = new array<vector>;
    protected ref array<float> m_Yaws = new array<float>;
    protected int m_Cursor = 0;
    protected bool m_Started = false;
    override void OnInit()
    {
        super.OnInit();
        if (!GetGame().IsServer() || m_Started)
            return;
        m_Started = true;
@@LOAD@@
        Print("[HC OverlayProbe] begin binding=@@BINDING@@");
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(OverlayStep, 1000, false);
    }
    void OverlayAdd(string ident, string type, float x, float z, float yaw)
    {
        m_Ids.Insert(ident);
        m_Classes.Insert(type);
        m_Positions.Insert(Vector(x, 0, z));
        m_Yaws.Insert(yaw);
    }
@@METHODS@@
    void OverlayStep()
    {
        int stop = Math.Min(m_Cursor + @@CHUNK@@, m_Ids.Count());
        while (m_Cursor < stop)
        {
            OverlaySample(m_Cursor);
            m_Cursor = m_Cursor + 1;
        }
        if (m_Cursor < m_Ids.Count())
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(OverlayStep, 250, false);
        else
            OverlayFinish();
    }
    void OverlayFinish()
    {
        string done = "[HC OverlayProbe] done targets=" + m_Ids.Count().ToString();
        Print(done);
        if (!MakeDirectory("$profile:HCCEProbe"))
            return;
        FileHandle handle = OpenFile("$profile:HCCEProbe/complete.txt", FileMode.WRITE);
        if (!handle)
            return;
        FPrintln(handle, done);
        CloseFile(handle);
    }
    void OverlaySample(int index)
    {
        vector pos = m_Positions.Get(index);
        pos[1] = GetGame().SurfaceY(pos[0], pos[2]);
        vector normal = GetGame().SurfaceGetNormal(pos[0], pos[2]);
        float slope = Math.Acos(Math.Clamp(normal[1], -1, 1)) * Math.RAD2DEG;
        vector orientation = Vector(m_Yaws.Get(index), 0, 0);
        // Test existing scenery before creating our temporary prop.
        vector center = pos;
        center[1] = center[1] + 1;
        array<Object> excluded = new array<Object>;
        array<Object> collided = new array<Object>;
        bool blocked = GetGame().IsBoxColliding(center, orientation, "2 2 2", excluded, collided);
        int hit = 0;
        if (blocked)
            hit = 1;
        int spawned = 0;
        Object prop = GetGame().CreateObject(m_Classes.Get(index), pos, true, false, false);
        if (prop)
        {
            spawned = 1;
            prop.SetOrientation(orientation);
            orientation = prop.GetOrientation();
            GetGame().ObjectDelete(prop);
        }
        string row = "[HC OverlayProbe] id=" + m_Ids.Get(index);
        row = row + " x=" + pos[0].ToString();
        row = row + " z=" + pos[2].ToString();
        row = row + " y=" + pos[1].ToString();
        row = row + " nx=" + normal[0].ToString();
        row = row + " ny=" + normal[1].ToString();
        row = row + " nz=" + normal[2].ToString();
        row = row + " slope_deg=" + slope.ToString();
        row = row + " collision=" + hit.ToString();
        row = row + " blockers=" + collided.Count().ToString();
        row = row + " spawned=" + spawned.ToString();
        row = row + " yaw=" + orientation[0].ToString();
        row = row + " pitch=" + orientation[1].ToString();
        row = row + " roll=" + orientation[2].ToString();
        Print(row);
    }
}
'''


def render_hook(rows, token):
    validate_targets(rows)
    if not re.fullmatch(r'[a-f0-9]{64}', token):
        raise ValueError('invalid binding')
    calls, methods = [], []
    for offset in range(0, len(rows), 16):
        name = 'OverlayLoad%d' % offset
        calls.append('        %s();' % name)
        body = ['        OverlayAdd("%s", "%s", %.6f, %.6f, %.6f);' %
                (r['id'], r['class'], r['x'], r['z'], r['yaw']) for r in rows[offset:offset + 16]]
        methods.append('    void %s()\n    {\n%s\n    }' % (name, '\n'.join(body)))
    text = HOOK
    for key, value in dict(LOAD='\n'.join(calls), METHODS='\n'.join(methods),
                           BINDING=token, CHUNK=CHUNK).items():
        text = text.replace('@@' + key + '@@', str(value))
    return text.encode('ascii')


def stage(source_runtime, destination, *, source=overlay.SOURCE, native_scripts=None, dry_run=False):
    rows = targets(source)
    native = rt.native_type_names(native_scripts or Path.home() /
                                  '.cache/hollow-country/native-scripts/scripts-1.30.164289')
    run_id = secrets.token_hex(16)
    # Validate generated code before creating any runtime files.
    hook = render_hook(rows, binding(rows, '0' * 64, run_id))
    problems = rt.lint_hook(hook.decode(), native_types=native, explicit_numbers=True)
    if problems:
        raise ValueError('generated hook failed static lint')
    if dry_run:
        return dict(kind='ce-overlay-probe', status='inputs-validated-not-staged', targets=len(rows))
    context = rt.begin(source_runtime, destination, parent=rt.WSL_PARENT,
                       battleye_sha256=rt.BATTLEYE_SHA256)
    stock_sha = rt.sha256(overlay.canonical({k: v['source_sha256']
                                          for k, v in context['source']['records'].items()}))
    token = binding(rows, stock_sha, run_id)
    hook = render_hook(rows, token)
    built = rt.build_runtime(context, hook, purpose='ce-probe')
    plan = rt.plan_header('ce-probe', None, after={'variant': 'overlay-survey'})
    plan['probe_kind'] = 'ce-overlay-probe'
    plan.update(rt.plan_runtime_fields(context, built))
    plan.update(targets=rows, binding=token, run_id=run_id, stock_mission_sha256=stock_sha,
                mission_files=built['mission_files'], staged_files=built['staged'],
                probe=dict(hook_sha256=rt.sha256(hook), chunk=CHUNK, wait_minutes=10,
                           collision_box_m=[2, 2, 2]))
    rt.write_plan(destination, PLAN_NAME, plan)
    return plan


NUMBER = r'([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)'
FIELDS = ('x', 'z', 'y', 'nx', 'ny', 'nz', 'slope_deg', 'collision', 'blockers',
          'spawned', 'yaw', 'pitch', 'roll')
ROW = re.compile(r'\[HC OverlayProbe\] id=([A-Za-z0-9_:-]+)' +
                 ''.join(' ' + field + '=' + NUMBER for field in FIELDS) + r'\s*$')


def tolerance(value):
    return max(.01, .5 * 10 ** (math.floor(math.log10(abs(value))) - 5) + .002) if value else .01


def ingest(rpt, out, plan_path):
    plan_bytes = rt._read_bounded(plan_path, rt.MAX_PLAN_BYTES * 8)
    plan = json.loads(plan_bytes)
    rows = plan['targets']
    validate_targets(rows)
    token = binding(rows, plan['stock_mission_sha256'], plan['run_id'])
    if (plan.get('kind') != 'ce-probe' or plan.get('probe_kind') != 'ce-overlay-probe'
            or plan.get('binding') != token
            or plan.get('server_exe_sha256') != rt.SERVER_EXE_SHA256):
        raise ValueError('invalid probe plan binding')
    raw = rt._read_bounded(rpt, MAX_RPT_BYTES)
    expected = {r['id']: r for r in rows}
    observed = {}
    state = 'before'
    for line in raw.decode('utf-8', errors='replace').splitlines():
        if '[HC OverlayProbe]' not in line:
            continue
        marker = line[line.index('[HC OverlayProbe]'):]
        if marker == '[HC OverlayProbe] begin binding=' + token and state == 'before':
            state = 'survey'
            continue
        if marker == '[HC OverlayProbe] done targets=' + str(len(rows)) and state == 'survey':
            state = 'done'
            continue
        match = ROW.fullmatch(marker)
        if not match or state != 'survey':
            raise ValueError('malformed row or probe marker ordering')
        ident = match[1]
        if ident not in expected or ident in observed:
            raise ValueError('unexpected or duplicate probe target')
        sample = dict(zip(FIELDS, map(float, match.groups()[1:])))
        if not all(math.isfinite(v) for v in sample.values()):
            raise ValueError('nonfinite measurement')
        for key in ('collision', 'spawned'):
            if sample[key] not in (0, 1):
                raise ValueError('invalid native flag')
        if (sample['blockers'] < 0 or not sample['blockers'].is_integer()
                or bool(sample['collision']) != bool(sample['blockers'])
                or not -1000 <= sample['y'] <= 10000 or not 0 <= sample['slope_deg'] <= 180):
            raise ValueError('invalid native measurement')
        normal = [sample[k] for k in ('nx', 'ny', 'nz')]
        if abs(sum(v * v for v in normal) - 1) > .01:
            raise ValueError('invalid terrain normal')
        slope = math.degrees(math.acos(max(-1, min(1, normal[1]))))
        if abs(slope - sample['slope_deg']) > .1:
            raise ValueError('inconsistent terrain slope')
        if any(abs(sample[k] - expected[ident][k]) > tolerance(expected[ident][k]) for k in ('x', 'z')):
            raise ValueError('probe coordinate drift')
        ypr = [sample[k] for k in ('yaw', 'pitch', 'roll')] if sample['spawned'] else None
        observed[ident] = dict(expected[ident], y=sample['y'], normal=normal,
                              slope_deg=sample['slope_deg'], collision=bool(sample['collision']),
                              blockers=int(sample['blockers']), spawned=bool(sample['spawned']),
                              ypr=ypr, rpy=([ypr[2], ypr[1], overlay.wrap(90 - ypr[0])]
                                            if ypr else None), a=(ypr[0] if ypr else None))
    if state != 'done' or observed.keys() != expected.keys():
        raise ValueError('incomplete probe')
    result = dict(schema=1, kind='ce-overlay-measured-heights',
                  collision_box_m=[2, 2, 2], orientation_mapping='candidate-unverified',
                  provenance=dict(server_exe_sha256=plan['server_exe_sha256'],
                                  stock_mission_sha256=plan['stock_mission_sha256'], binding=token,
                                  probe_plan_sha256=rt.sha256(plan_bytes), rpt_sha256=rt.sha256(raw),
                                  staged_utc=plan['staged_utc'],
                                  ingested_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()),
                  targets=[observed[r['id']] for r in rows])
    rt.new_file(out, (json.dumps(result, indent=2) + '\n').encode())
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    st = sub.add_parser('stage')
    st.add_argument('--destination', type=Path, required=True)
    st.add_argument('--source-runtime', default=rt.DEFAULT_SOURCE_RUNTIME)
    st.add_argument('--source', type=Path, default=overlay.SOURCE)
    st.add_argument('--native-scripts', type=Path)
    st.add_argument('--dry-run', action='store_true')
    ing = sub.add_parser('ingest')
    ing.add_argument('--rpt', type=Path, required=True)
    ing.add_argument('--plan', type=Path, required=True)
    ing.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'stage':
            result = stage(args.source_runtime, args.destination, source=args.source,
                           native_scripts=args.native_scripts, dry_run=args.dry_run)
            print(json.dumps(dict(kind=result['kind'], status=result['status'],
                                  targets=(result['targets'] if args.dry_run else len(result['targets'])))))
        else:
            result = ingest(args.rpt, args.out, args.plan)
            print(json.dumps(dict(targets=len(result['targets']))))
        return 0
    except (ValueError, OSError, KeyError, TypeError):
        # Never echo paths, operator input or raw native log text in public output.
        print('ce_overlay_probe refused: invalid or unsafe input; no native launch attempted')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
