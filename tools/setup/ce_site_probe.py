"""Stage or ingest a disposable native HC Central Economy site survey; never launch."""
import argparse
import datetime
import json
import math
from pathlib import Path
import re
import secrets
import tempfile
import xml.etree.ElementTree as ET

from tools.package import hc_events as hc
from tools.setup import probe_runtime as rt

PLAN_NAME = 'ce-site-probe-plan.json'
HARD_CAP = 400
CHUNK = 16
MAX_RPT_BYTES = 128 * 1024 * 1024


def targets(source=hc.SOURCE):
    result = []
    for relative, cache in (('ce/hc-eventspawns.xml', False), ('events/cache-eventspawns.xml', True)):
        root = hc.economy.xml(hc.economy.read_plain(source, relative), 'eventposdef')
        for event in root:
            for index, pos in enumerate(event.findall('pos'), 1):
                x, z = (float(pos.get(a)) for a in ('x', 'z'))
                base = event.get('name')
                result.append(dict(id='%s:site%03d' % (base, index), x=x, z=z))
                if cache:
                    for radius in (4, 8, 12):
                        for bearing in range(8):
                            angle = bearing * math.pi / 4
                            result.append(dict(id='%s:ring%02d_%d' % (base, radius, bearing),
                                               x=round(x + radius * math.cos(angle), 6),
                                               z=round(z + radius * math.sin(angle), 6)))
    if not result or len(result) > HARD_CAP or len({r['id'] for r in result}) != len(result):
        raise ValueError('invalid targets or target hard cap exceeded')
    if any(not all(math.isfinite(r[a]) and 0 < r[a] < 15360 for a in ('x', 'z')) for r in result):
        raise ValueError('invalid target coordinates')
    return result


def stock_digest(records):
    return rt.sha256(json.dumps({n: r['source_sha256'] for n, r in records.items()},
                               sort_keys=True, separators=(',', ':')).encode())


def binding(target_rows, treatment, stock_sha, run_id=""):
    return rt.sha256(json.dumps([target_rows, treatment, stock_sha, rt.SERVER_EXE_SHA256, run_id],
                               sort_keys=True, separators=(',', ':')).encode())


HOOK = r'''
// Native cache 1.30.164289 references (relative file:line):
// 3_Game/Global/Game.c:1176 SurfaceY, :1188 SurfaceGetNormal,
// :1196-1197 SurfaceIsSea/SurfaceIsPond, :1333 IsBoxColliding (geometry only).
// IsBoxColliding returns colliders, including large objects whose origin is outside
// the box. Conservative square clearance: half-width @@RADIUS@@ m, height 2 m.
// 1_Core/proto/EnMath.c:379 Acos, :16 RAD2DEG; :540 Clamp, :553 Min.
// 3_Game/Global/Game.c:1120 IsServer, :1550 GetCallQueue;
// 2_GameLib/tools.c:61 CallLater.
// 3_Game/Entities/Object.c:287 GetPosition, :467 GetType.
// 1_Core/proto/EnConvert.c:196 vector.Distance, :30 int.ToString, :115 float.ToString.
// 5_Mission/mission/missionServer.c:85 OnInit.
// 1_Core/proto/EnScript.c:380 Count, :399 Get, :407 Insert (array).
// 1_Core/proto/EnDebug.c:96 Print; 1_Core/proto/EnSystem.c:525 MakeDirectory,
// :417 OpenFile, :481 FPrintln, :443 CloseFile. No gameplay mutation.
class HCDisposableDiagnosticMission : CustomMission
{
    protected ref array<string> m_SiteIds = new array<string>;
    protected ref array<vector> m_SitePositions = new array<vector>;
    protected int m_SiteCursor = 0;
    protected bool m_SiteStarted = false;
    override void OnInit()
    {
        super.OnInit();
        if (!GetGame().IsServer() || m_SiteStarted)
            return;
        m_SiteStarted = true;
@@LOAD@@
        Print("[HC SiteProbe] begin binding=@@BINDING@@");
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(SiteStep, 1000, false);
    }
    void SiteAdd(string ident, float x, float z)
    {
        m_SiteIds.Insert(ident);
        m_SitePositions.Insert(Vector(x, 0, z));
    }
@@METHODS@@
    void SiteStep()
    {
        int stop = Math.Min(m_SiteCursor + @@CHUNK@@, m_SiteIds.Count());
        while (m_SiteCursor < stop)
        {
            SiteSample(m_SiteCursor);
            m_SiteCursor = m_SiteCursor + 1;
        }
        if (m_SiteCursor < m_SiteIds.Count())
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(SiteStep, 250, false);
        else
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(SiteFinish, @@HOLD@@, false);
    }
    void SiteSample(int index)
    {
        vector pos = m_SitePositions.Get(index);
        float height = GetGame().SurfaceY(pos[0], pos[2]);
        vector normal = GetGame().SurfaceGetNormal(pos[0], pos[2]);
        float slope = Math.Acos(Math.Clamp(normal[1], -1, 1)) * Math.RAD2DEG;
        int water = 0;
        if (GetGame().SurfaceIsSea(pos[0], pos[2]) || GetGame().SurfaceIsPond(pos[0], pos[2]))
            water = 1;
        pos[1] = height + 1;
        array<Object> excluded = new array<Object>;
        array<Object> collided = new array<Object>;
        GetGame().IsBoxColliding(pos, "0 0 0", "@@WIDTH@@ 2 @@WIDTH@@", excluded, collided);
        string nearest = "none";
        float distance = -1;
        int limit = Math.Min(collided.Count(), 512);
        for (int i = 0; i < limit; i++)
        {
            Object obj = collided.Get(i);
            if (!obj)
                continue;
            float d = vector.Distance(pos, obj.GetPosition());
            if (distance < 0 || d < distance)
            {
                distance = d;
                nearest = obj.GetType();
                if (nearest == "")
                    nearest = "unnamed";
            }
        }
        string row = "[HC SiteProbe] id=" + m_SiteIds.Get(index);
        row = row + " x=" + pos[0].ToString();
        row = row + " z=" + pos[2].ToString();
        row = row + " y=" + height.ToString();
        row = row + " slope_deg=" + slope.ToString();
        row = row + " water=" + water.ToString();
        row = row + " blockers=" + collided.Count().ToString();
        row = row + " nearest=" + nearest + "@" + distance.ToString();
        Print(row);
    }
    void SiteFinish()
    {
        string done = "[HC SiteProbe] done targets=" + m_SiteIds.Count().ToString();
        Print(done);
        if (!MakeDirectory("$profile:HCCESiteProbe"))
            return;
        FileHandle handle = OpenFile("$profile:HCCESiteProbe/complete.txt", FileMode.WRITE);
        if (!handle)
            return;
        FPrintln(handle, done);
        CloseFile(handle);
    }
}
'''


def render_hook(rows, token, hold_seconds=240):
    methods, calls = [], []
    for offset in range(0, len(rows), CHUNK):
        name = 'SiteLoad%d' % offset
        calls.append('        %s();' % name)
        body = ['        SiteAdd("%s", %.6f, %.6f);' % (r['id'], r['x'], r['z'])
                for r in rows[offset:offset + CHUNK]]
        methods.append('    void %s()\n    {\n%s\n    }' % (name, '\n'.join(body)))
    text = HOOK
    for key, value in dict(LOAD='\n'.join(calls), METHODS='\n'.join(methods), BINDING=token,
                           CHUNK=CHUNK, HOLD=hold_seconds * 1000, RADIUS=hc.BLOCKER_RADIUS_M,
                           WIDTH=hc.BLOCKER_RADIUS_M * 2).items():
        text = text.replace('@@' + key + '@@', str(value))
    return text.encode('ascii')


def stage(source_runtime, destination, *, source=hc.SOURCE, treatment='current', measured=None,
          native_scripts=None, hold_seconds=240, wait_minutes=10, dry_run=False):
    if treatment not in ('current', 'measured') or (treatment == 'measured') != (measured is not None):
        raise ValueError('measured treatment requires --measurements; current refuses it')
    if not 240 <= hold_seconds <= 3600 or not 5 <= wait_minutes <= 120 or wait_minutes * 60 < hold_seconds + 120:
        raise ValueError('hold must be 240..3600 seconds with at least 120 seconds timeout headroom')
    rows = targets(source)
    # Validate/apply via the existing generator and installer. A temporary source
    # snapshot keeps current independent of a later committed measurement file.
    with tempfile.TemporaryDirectory(prefix='hc-site-source-') as scratch:
        snapshot = Path(scratch)
        for name in hc.DATA:
            path = snapshot / 'ce' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(hc.economy.read_plain(source, 'ce/' + name))
        for name in hc.CACHE_DATA:
            path = snapshot / 'events' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(hc.economy.read_plain(source, 'events/' + name))
        if measured:
            (snapshot / hc.MEASUREMENTS).write_bytes(rt._read_bounded(measured, rt.MAX_PLAN_BYTES))
        hc.validate(snapshot)
        cache = native_scripts or Path.home() / '.cache/hollow-country/native-scripts/scripts-1.30.164289'
        native = rt.native_type_names(cache)
        # Dry-run validates data and generated hook without requiring a Windows install.
        if dry_run:
            hook = render_hook(rows, binding(rows, treatment, '0' * 64), hold_seconds)
            problems = rt.lint_hook(hook.decode(), native_types=native)
            if problems:
                raise ValueError('hook lint: ' + '; '.join(problems[:3]))
            return {'kind': 'ce-site-probe', 'status': 'inputs-validated-not-staged', 'targets': len(rows)}
        context = rt.begin(source_runtime, destination, parent=rt.WSL_PARENT, battleye_sha256=rt.BATTLEYE_SHA256)
        stock_sha = stock_digest(context['source']['records'])
        run_id = secrets.token_hex(16)
        token = binding(rows, treatment, stock_sha, run_id)
        hook = render_hook(rows, token, hold_seconds)
        problems = rt.lint_hook(hook.decode(), native_types=native)
        if problems:
            raise ValueError('hook lint: ' + '; '.join(problems[:3]))
        # Shared generic generated CE-hook purpose; no change to shared runtime scope.
        built = rt.build_runtime(context, hook, purpose='ce-probe')
        hc.install(snapshot, built['mission_dest'])
        built['staged'] = []
        for name in sorted(rt.dm.walk_plain(destination)):
            digest, size = rt._hash_file(Path(destination) / name)
            built['staged'].append(dict(path=name, sha256=digest, bytes=size))
        current = {r['path']: r['sha256'] for r in built['staged']}
        prefix = 'mpmissions/' + rt.MISSION_NAME + '/'
        for entry in built['mission_files']:
            entry['sha256'] = current[prefix + entry['path']]
            if entry['sha256'] != entry['source_sha256'] and entry['path'] != 'init.c':
                entry['origin'] = 'hc-ce-install'
        plan = rt.plan_header('ce-site-probe', None, after={'variant': treatment})
        plan.update(rt.plan_runtime_fields(context, built))
        plan.update(targets=rows, binding=token, run_id=run_id, stock_mission_sha256=stock_sha,
                    mission_files=built['mission_files'], staged_files=built['staged'],
                    probe=dict(wait_minutes=wait_minutes, hold_seconds=hold_seconds,
                               blocker_radius_m=hc.BLOCKER_RADIUS_M, hook_sha256=rt.sha256(hook)))
        # Reuse all shared launcher checks under its existing CE probe alias. The
        # actual fixed kind mapping is in Start-CEProbeServer.ps1.
        alias = dict(plan, kind='ce-probe')
        problems = rt.launcher_problems(alias, destination, 'ce-probe-plan.json')
        if problems:
            raise ValueError('launcher preflight: ' + '; '.join(problems[:3]))
        rt.new_file(Path(destination) / PLAN_NAME, (json.dumps(plan, indent=2) + '\n').encode())
        return plan


NUMBER = r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?'
ROW = re.compile(r'\[HC SiteProbe\] id=([A-Za-z0-9_:]+) x=(' + NUMBER + r') z=(' + NUMBER
                 + r') y=(' + NUMBER + r') slope_deg=(' + NUMBER + r') water=([01]) blockers=(\d+) nearest=([A-Za-z0-9_]+)@(' + NUMBER + r')')
FAILURE = re.compile(r'\[CE\]\[VehicleRespawner\].*?:: (Init|Respawning): "([A-Za-z0-9_]+)" - Failed to spawn the requested amount \((\d+) < (\d+)\) within (\d+) attempts\.')


def ingest(rpt, out, plan_path=None):
    rpt = Path(rpt)
    plan_path = Path(plan_path) if plan_path else rpt.parent.parent / PLAN_NAME
    plan_bytes = rt._read_bounded(plan_path, rt.MAX_PLAN_BYTES)
    plan = json.loads(plan_bytes)
    if not isinstance(plan, dict) or not isinstance(plan.get('targets'), list):
        raise ValueError('invalid probe plan document')
    rows = plan['targets']
    token = binding(rows, plan['variant'], plan['stock_mission_sha256'], plan['run_id'])
    if (plan.get('kind') != 'ce-site-probe' or plan.get('binding') != token
            or plan.get('server_exe_sha256') != rt.SERVER_EXE_SHA256
            or not 0 < len(rows) <= HARD_CAP or len({r['id'] for r in rows}) != len(rows)):
        raise ValueError('invalid probe plan')
    raw = rt._read_bounded(rpt, MAX_RPT_BYTES)
    text = raw.decode('utf-8', errors='replace')
    begins = re.findall(r'\[HC SiteProbe\] begin binding=([a-f0-9]{64})', text)
    dones = re.findall(r'\[HC SiteProbe\] done targets=(\d+)', text)
    if begins != [token] or dones != [str(len(rows))]:
        raise ValueError('incomplete probe or mismatched run binding')
    expected = {r['id']: r for r in rows}
    observed = {}
    in_survey = False
    finished = False
    for line in text.splitlines():
        if '[HC SiteProbe] begin binding=' in line:
            if finished:
                raise ValueError('probe marker ordering')
            in_survey = True
        if '[HC SiteProbe] done targets=' in line:
            if not in_survey:
                raise ValueError('probe marker ordering')
            in_survey = False
            finished = True
        if '[HC SiteProbe] id=' not in line:
            continue
        if not in_survey:
            raise ValueError('probe row outside survey')
        match = ROW.search(line)
        if not match:
            raise ValueError('malformed probe row')
        ident, x, z, y, slope, water, blockers, nearest, distance = match.groups()
        row = dict(id=ident, x=float(x), z=float(z), y=float(y), slope_deg=float(slope),
                   water=int(water), blockers=int(blockers), nearest=nearest, nearest_m=float(distance))
        if not math.isfinite(row['nearest_m']):
            raise ValueError('invalid nearest distance')
        hc.measurement_usable(row)  # validates even an unusable site, retained as evidence
        if ident not in expected or ident in observed:
            raise ValueError('unexpected or duplicate probe target')
        if any(abs(row[a] - expected[ident][a]) > 0.01 for a in ('x', 'z')):
            raise ValueError('probe coordinate drift')
        observed[ident] = row
    if observed.keys() != expected.keys():
        raise ValueError('incomplete probe targets')
    failures = [dict(phase=m[1], event=m[2], actual=int(m[3]), requested=int(m[4]), attempts=int(m[5]))
                for m in FAILURE.finditer(text)]
    result = dict(schema=1, blocker_radius_m=hc.BLOCKER_RADIUS_M,
                  provenance=dict(server_exe_sha256=plan['server_exe_sha256'],
                                  stock_mission_sha256=plan['stock_mission_sha256'],
                                  probe_plan_sha256=rt.sha256(plan_bytes), rpt_sha256=rt.sha256(raw),
                                  date=plan['staged_utc'], treatment=plan['variant'],
                                  ingested_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()),
                  targets=[observed[r['id']] for r in rows], ce_failures=failures,
                  ce_failure_counts={phase: sum(r['phase'] == phase for r in failures)
                                     for phase in ('Init', 'Respawning')})
    rt.new_file(out, (json.dumps(result, indent=2) + '\n').encode())
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    st = sub.add_parser('stage')
    st.add_argument('--destination', type=Path, required=True)
    st.add_argument('--source-runtime', default=rt.DEFAULT_SOURCE_RUNTIME)
    st.add_argument('--source', type=Path, default=hc.SOURCE)
    st.add_argument('--treatment', choices=('current', 'measured'), default='current')
    st.add_argument('--measurements', type=Path)
    st.add_argument('--native-scripts', type=Path)
    st.add_argument('--hold-seconds', type=int, default=240)
    st.add_argument('--wait-minutes', type=int, default=10)
    st.add_argument('--dry-run', action='store_true')
    ing = sub.add_parser('ingest')
    ing.add_argument('--rpt', type=Path, required=True)
    ing.add_argument('--out', type=Path, required=True)
    ing.add_argument('--plan', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'stage':
            result = stage(args.source_runtime, args.destination, source=args.source, treatment=args.treatment,
                           measured=args.measurements, native_scripts=args.native_scripts,
                           hold_seconds=args.hold_seconds, wait_minutes=args.wait_minutes, dry_run=args.dry_run)
            print(json.dumps({'status': result['status'], 'kind': result['kind']}))
        else:
            result = ingest(args.rpt, args.out, args.plan)
            print(json.dumps(result['ce_failure_counts'], sort_keys=True))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        # Never echo operator input paths or native log text into public output.
        reason = re.sub(r'(?:[A-Za-z]:)?[/\\][^\s;]*', '<path>', str(error)) if isinstance(error, ValueError) else type(error).__name__ + ' errno=' + str(getattr(error, 'errno', None))
        print('ce_site_probe refused: ' + reason)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
