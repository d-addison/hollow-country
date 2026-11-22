"""Stage or ingest a disposable Interiors resolve experiment; never launch DayZ."""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import re
import secrets

from tools.setup import diagnostic_mission as dm
from tools.setup import probe_runtime as rt

CATALOG = Path(__file__).resolve().parents[2] / 'mission/hollow-country/interiors/templates'
PLAN_NAME = 'interior-resolve-probe.json'
CLASSES = (
    'Land_Tenement_Small', 'Land_House_2B04', 'Land_Village_Pub',
    'Land_CementWorks_ExpeditionA', 'Land_Mil_Barracks3', 'Land_Mil_Barracks4',
    'Land_House_2B01', 'Land_City_Stand_News1', 'Land_Shed_Closed2', 'Land_Garage_Row_Big',
)
# Candidate families and references are documented in INTERIOR_RESOLVE_PROBE.md.
APIS = ('query2d_small', 'query2d_tile', 'query3d_zero', 'query3d_small', 'query3d_current',
        'ray_geom', 'ray_view', 'ray_proxy', 'box', 'box_geom', 'box_proxy',
        'bullet_ray', 'bullet_sphere', 'sphere_overlap', 'box_overlap',
        'cylinder_overlap', 'capsule_overlap', 'sphere_query', 'trace_move')
MAX_RPT_BYTES = 128 * 1024 * 1024


def targets(catalog=CATALOG, per_class=3):
    if type(per_class) is not int or not 1 <= per_class <= 16:
        raise ValueError('per-class must be 1..16')
    grouped = defaultdict(dict)
    pins = {}
    for path in sorted(Path(catalog).glob('furnish-*.json')):
        raw = rt._read_bounded(path, 4 * 1024 * 1024)
        pins[path.name] = rt.sha256(raw)
        for row in json.loads(raw)['Rows']:
            name, pos = row['BuildingClass'], row['Position']
            if name not in CLASSES:
                continue
            if len(pos) != 3 or any(type(v) not in (int, float) or not math.isfinite(v) for v in pos):
                raise ValueError('invalid catalog position')
            grouped[name][tuple(pos)] = row
    templates = {}
    for path in sorted(Path(catalog).glob('t-*.json')):
        raw = rt._read_bounded(path, 4 * 1024 * 1024)
        doc = json.loads(raw)
        if doc['BuildingClass'] in CLASSES:
            pins[path.name] = rt.sha256(raw)
            templates[doc['BuildingClass']] = doc
    result = []
    for name in CLASSES:
        rows = sorted(grouped[name].values(), key=lambda r: tuple(r['Position']))
        if len(rows) < per_class:
            raise ValueError('insufficient catalog instances for ' + name)
        for index in range(per_class):
            row = rows[index * len(rows) // per_class]
            template = templates[name]
            local = [(lo + hi) / 2 for lo, hi in zip(template['Box']['Min'], template['Box']['Max'])]
            if template['Rooms']:
                local = template['Rooms'][0]['Anchor']
            angle = math.radians(row['Yaw'])
            x, y, z = local
            origin = row['Position']
            ray_pos = [origin[0] + x * math.cos(angle) + z * math.sin(angle),
                       origin[1] + y,
                       origin[2] - x * math.sin(angle) + z * math.cos(angle)]
            result.append(dict(index=len(result), **{'class': name}, pos=origin, ray_pos=ray_pos,
                               ray_source='room_anchor' if template['Rooms'] else 'box_center'))
    return result, pins


HOOK = r'''
// DISPOSABLE measurement only. Cache references: docs/tools/INTERIOR_RESOLVE_PROBE.md.
class HCResolveOverlap : CollisionOverlapCallback
{
    ref array<Object> objects = new array<Object>;
    override bool OnContact(IEntity other, Contact contact)
    {
        if (objects.Count() < 257)
            objects.Insert(Object.Cast(other));
        return true;
    }
}
class HCDisposableDiagnosticMission : CustomMission
{
    ref array<string> m_Classes = new array<string>;
    ref array<vector> m_Positions = new array<vector>;
    ref array<vector> m_RayPositions = new array<vector>;
    ref array<string> m_Apis = new array<string>;
    int m_Target = 0;
    int m_Order = 0;
    int m_Pair = 0;
    int m_Count = 0;
    float m_Wait = 0;
    bool m_Started = false;
    bool m_Finished = false;
    override void OnInit()
    {
        super.OnInit();
        if (!GetGame().IsServer() || m_Started)
            return;
        m_Started = true;
@@LOAD@@
        Print("[HC ResolveProbe] begin run=@@RUN@@");
    }
    override void OnUpdate(float timeslice)
    {
        super.OnUpdate(timeslice);
        if (!m_Started || m_Finished || !GetGame().IsServer())
            return;
        m_Wait = m_Wait + timeslice;
        if (m_Wait < @@DELAY@@)
            return;
        // Exactly one timed native call per server update. Repeat is next update.
        int apiIndex = (m_Order + m_Target) % m_Apis.Count();
        string api = m_Apis.Get(apiIndex);
        Measure(api);
        m_Count = m_Count + 1;
        m_Pair = m_Pair + 1;
        if (m_Pair == 2)
        {
            m_Pair = 0;
            m_Order = m_Order + 1;
        }
        if (m_Order == m_Apis.Count())
        {
            m_Order = 0;
            m_Target = m_Target + 1;
        }
        if (m_Target == m_Positions.Count())
        {
            m_Finished = true;
            Print("[HC ResolveProbe] summary run=@@RUN@@ measurements=" + m_Count.ToString());
        }
    }
    bool Exact(Object obj, vector pos, string kind)
    {
        return obj && obj.GetType() == kind && vector.DistanceSq(obj.GetPosition(), pos) <= 0.5625;
    }
    void Measure(string api)
    {
        vector pos = m_Positions.Get(m_Target);
        string kind = m_Classes.Get(m_Target);
        vector rayPos = m_RayPositions.Get(m_Target);
        vector top = rayPos + "0 60 0";
        vector bottom = rayPos - "0 30 0";
        array<Object> objects = new array<Object>;
        array<CargoBase> cargos = new array<CargoBase>;
        array<Object> excluded = new array<Object>;
        set<Object> hits = new set<Object>;
        array<ref RaycastRVResult> proxies = new array<ref RaycastRVResult>;
        array<ref BoxCollidingResult> boxes = new array<ref BoxCollidingResult>;
        RaycastRVParams params = new RaycastRVParams(top, bottom);
        params.type = ObjIntersectGeom;
        BoxCollidingParams boxParams = new BoxCollidingParams;
        boxParams.SetParams(pos, "0 0 0", "0.1 0.1 0.1", ObjIntersectGeom, ObjIntersectGeom, false);
        HCResolveOverlap overlap = new HCResolveOverlap;
        vector contactPos;
        vector contactDir;
        int component;
        Object hitObject;
        float fraction;
        vector transform[4];
        Math3D.MatrixIdentity4(transform);
        transform[3] = pos;
        IEntity sphereEntities[257];
        int sphereCount = 0;
        TraceParam traceParams = new TraceParam;
        traceParams.Start = top;
        traceParams.End = bottom;
        traceParams.Flags = TraceFlags.ENTS;
        IEntity traceEntity;
        float tracePlane[4];
        int traceSurface;
        int ticks = 0;
        // Start AFTER allocation/parameter preparation; stop BEFORE result filtering/logging.
@@CALLS@@
        bool capped = objects.Count() > 256 || hits.Count() > 256 || proxies.Count() > 256;
        capped = capped || boxes.Count() > 256 || overlap.objects.Count() > 256;
        capped = capped || sphereCount >= 257 || sphereCount < 0;
        bool found = false;
        set<Object> exactObjects = new set<Object>;
        if (!capped)
        {
            foreach (Object candidate : objects)
            {
                if (Exact(candidate, pos, kind))
                {
                    exactObjects.Insert(candidate);
                }
            }
            foreach (Object rayObject : hits)
            {
                if (Exact(rayObject, pos, kind))
                {
                    exactObjects.Insert(rayObject);
                }
            }
            foreach (RaycastRVResult proxyHit : proxies)
            {
                Object proxyObject = proxyHit.obj;
                if (Exact(proxyHit.parent, pos, kind))
                    proxyObject = proxyHit.parent;
                if (Exact(proxyObject, pos, kind))
                {
                    exactObjects.Insert(proxyObject);
                }
            }
            foreach (BoxCollidingResult boxHit : boxes)
            {
                Object boxObject = boxHit.obj;
                if (Exact(boxHit.parent, pos, kind))
                    boxObject = boxHit.parent;
                if (Exact(boxObject, pos, kind))
                {
                    exactObjects.Insert(boxObject);
                }
            }
            foreach (Object overlapObject : overlap.objects)
            {
                if (Exact(overlapObject, pos, kind))
                {
                    exactObjects.Insert(overlapObject);
                }
            }
            for (int sphereIndex = 0; sphereIndex < sphereCount; sphereIndex++)
            {
                Object sphereObject = Object.Cast(sphereEntities[sphereIndex]);
                if (Exact(sphereObject, pos, kind))
                    exactObjects.Insert(sphereObject);
            }
            Object tracedObject = Object.Cast(traceEntity);
            if (Exact(tracedObject, pos, kind))
                exactObjects.Insert(tracedObject);
            if (Exact(hitObject, pos, kind))
                exactObjects.Insert(hitObject);
        }
        found = exactObjects.Count() == 1 && !capped;
        string row = "[HC ResolveProbe] run=@@RUN@@ target=" + m_Target.ToString();
        row = row + " class=" + kind + " api=" + api;
        row = row + " order=" + m_Order.ToString() + " pair=" + m_Pair.ToString();
        row = row + " ticks=" + ticks.ToString() + " found=" + found.ToString();
        row = row + " capped=" + capped.ToString();
        Print(row);
    }
}
'''

CALLS = {
    'query2d_small': 'GetGame().GetObjectsAtPosition(pos, 0.05, objects, cargos);',
    'query2d_tile': 'GetGame().GetObjectsAtPosition(pos, 0.531, objects, cargos);',
    'query3d_zero': 'GetGame().GetObjectsAtPosition3D(pos, 0, objects, cargos);',
    'query3d_small': 'GetGame().GetObjectsAtPosition3D(pos, 0.05, objects, cargos);',
    'query3d_current': 'GetGame().GetObjectsAtPosition3D(pos, 0.75, objects, cargos);',
    'ray_geom': 'DayZPhysics.RaycastRV(top, bottom, contactPos, contactDir, component, hits, null, null, false, false, ObjIntersectGeom);',
    'ray_view': 'DayZPhysics.RaycastRV(top, bottom, contactPos, contactDir, component, hits, null, null, false, false, ObjIntersectView);',
    'ray_proxy': 'DayZPhysics.RaycastRVProxy(params, proxies);',
    'box': 'GetGame().IsBoxColliding(pos, "0 0 0", "0.1 0.1 0.1", excluded, objects);',
    'box_geom': 'GetGame().IsBoxCollidingGeometry(pos, "0 0 0", "0.1 0.1 0.1", ObjIntersectGeom, ObjIntersectGeom, excluded, objects);',
    'box_proxy': 'GetGame().IsBoxCollidingGeometryProxy(boxParams, excluded, boxes);',
    'bullet_ray': 'DayZPhysics.RayCastBullet(top, bottom, PhxInteractionLayers.BUILDING, null, hitObject, contactPos, contactDir, fraction);',
    'bullet_sphere': 'DayZPhysics.SphereCastBullet(top, bottom, 0.05, PhxInteractionLayers.BUILDING, null, hitObject, contactPos, contactDir, fraction);',
    'sphere_query': 'sphereCount = SphereQuery(pos, 0.05, sphereEntities, 257, -1);',
    'trace_move': 'TraceMove(traceParams, traceEntity, tracePlane, traceSurface, null);',
    'box_overlap': 'DayZPhysics.BoxOverlapBullet(transform, "0.05 0.05 0.05", PhxInteractionLayers.BUILDING, overlap);',
    'cylinder_overlap': 'DayZPhysics.CylinderOverlapBullet(transform, "0.05 0.05 0.05", PhxInteractionLayers.BUILDING, overlap);',
    'capsule_overlap': 'DayZPhysics.CapsuleOverlapBullet(transform, 0.05, 0.1, PhxInteractionLayers.BUILDING, overlap);',
    'sphere_overlap': 'DayZPhysics.SphereOverlapBullet(pos, 0.05, PhxInteractionLayers.BUILDING, overlap);',
}


def render_hook(rows, apis, run, delay=60):
    load = []
    for api in apis:
        load.append('        m_Apis.Insert("%s");' % api)
    # Small bounded loaders avoid the native expression/function complexity limit.
    methods = []
    for offset in range(0, len(rows), 10):
        load.append('        Load%d();' % offset)
        body = []
        for row in rows[offset:offset + 10]:
            body.append('        m_Classes.Insert("%s");' % row['class'])
            body.append('        m_Positions.Insert(Vector(%.6f, %.6f, %.6f));' % tuple(row['pos']))
            body.append('        m_RayPositions.Insert(Vector(%.6f, %.6f, %.6f));' % tuple(row['ray_pos']))
        methods.append('    void Load%d()\n    {\n%s\n    }' % (offset, '\n'.join(body)))
    calls = []
    for api in apis:
        calls.append('        if (api == "%s")\n        {\n            int mark_%s = TickCount(0);\n            %s\n            ticks = TickCount(mark_%s);\n        }' % (api, api, CALLS[api], api))
    hook = HOOK.replace('@@LOAD@@', '\n'.join(load)).replace('@@CALLS@@', '\n'.join(calls))
    hook = hook.replace('@@RUN@@', run).replace('@@DELAY@@', str(delay))
    hook = hook.replace('    bool Exact(', '\n'.join(methods) + '\n    bool Exact(')
    return hook.encode('ascii')


def diag_plan(tag):
    """Vanilla isolated Diag plan: omit gameplay addons so they cannot pre-touch targets."""
    from tools.setup import diag_session as ds
    plan = ds.make_plan(tag, core_only=True)
    plan.items = []
    plan.sources = {}
    return plan


def stage(tag, *, per_class=3, api='all', native=None, dry_run=False):
    from tools.setup import diag_session as ds
    from tools.release.host_lock import host_lock
    rows, pins = targets(per_class=per_class)
    apis = list(APIS) if api == 'all' else [api]
    if any(name not in APIS for name in apis):
        raise ValueError('unknown API')
    run = secrets.token_hex(16)
    hook = render_hook(rows, apis, run)
    issues = rt.lint_hook(hook.decode(), native_types=rt.native_type_names(native or Path.home() / '.cache/hollow-country/native-scripts/scripts-1.30.164289'))
    if issues:
        raise ValueError('generated hook failed lint: ' + '; '.join(issues[:3]))
    doc = dict(schema=1, kind='interior-resolve-probe', run=run, targets=rows, apis=apis,
               catalog_sha256=pins, hook_sha256=rt.sha256(hook), delay_seconds=60,
               ticks_per_ms=10000, tick_scale='provisional host observation; override at ingest',
               status='validated-not-staged' if dry_run else 'staged-not-launched')
    if dry_run:
        return doc
    with host_lock('diag_session'):
        plan = diag_plan(tag)
        ds.stage(plan)
        init = plan.runtime / 'mpmissions' / ds.MISSION / 'init.c'
        original = rt._read_bounded(init, dm.MAX_INIT_BYTES)
        instrumented = dm._instrument(original, purpose='ce-probe', hook=hook)
        dm.unlink_at(init)
        rt.new_file(init, instrumented)
        doc['stock_init_sha256'] = rt.sha256(original)
        doc['staged_init_sha256'] = rt.sha256(instrumented)
        rt.new_file(plan.runtime / PLAN_NAME, (json.dumps(doc, indent=2) + '\n').encode())
    return doc


def staged_plan(tag):
    """Lead-only prelaunch check; returns a diag_session Plan and never launches it."""
    from tools.setup import diag_session as ds
    plan = diag_plan(tag)
    ds.guard_idle(plan.runtime)
    document = json.loads(rt._read_bounded(plan.runtime / PLAN_NAME, 4 * 1024 * 1024))
    init = rt._read_bounded(plan.runtime / 'mpmissions' / ds.MISSION / 'init.c',
                            dm.MAX_INIT_BYTES + dm.MAX_HOOK_BYTES)
    if (document['kind'] != 'interior-resolve-probe' or document['status'] != 'staged-not-launched'
            or rt.sha256(init) != document['staged_init_sha256']):
        raise ValueError('staged mission provenance mismatch')
    return plan


ROW = re.compile(r'\[HC ResolveProbe\] run=([a-f0-9]{32}) target=(\d+) class=(\w+) api=(\w+) order=(\d+) pair=([01]) ticks=(\d+) found=(true|false|[01]) capped=(true|false|[01])\s*$')


def ingest(rpt, plan_path, out, *, ticks_per_ms=10000):
    if not math.isfinite(ticks_per_ms) or ticks_per_ms <= 0:
        raise ValueError('invalid tick scale')
    raw = rt._read_bounded(rpt, MAX_RPT_BYTES)
    plan_bytes = rt._read_bounded(plan_path, 4 * 1024 * 1024)
    plan = json.loads(plan_bytes)
    if plan['kind'] != 'interior-resolve-probe' or plan['schema'] != 1:
        raise ValueError('wrong plan kind/schema')
    rows, apis, run = plan['targets'], plan['apis'], plan['run']
    if (not 1 <= len(rows) <= len(CLASSES) * 16 or not apis
            or any(a not in APIS for a in apis) or len(set(apis)) != len(apis)
            or [r['index'] for r in rows] != list(range(len(rows)))
            or {r['class'] for r in rows} != set(CLASSES)
            or not re.fullmatch('[a-f0-9]{32}', run)):
        raise ValueError('invalid plan targets/APIs')
    expected = [(r['index'], r['class'], apis[(order + r['index']) % len(apis)], order, pair)
                for r in rows for order in range(len(apis)) for pair in (0, 1)]
    measured = []
    started = finished = False
    for line in raw.decode('utf-8', errors='replace').splitlines():
        if '[HC ResolveProbe]' not in line:
            continue
        if line.rstrip().endswith('[HC ResolveProbe] begin run=' + run):
            if started:
                raise ValueError('duplicate run begin')
            started = True
            continue
        if '[HC ResolveProbe] summary run=' + run in line:
            if finished or not started or not line.rstrip().endswith(' measurements=' + str(len(expected))):
                raise ValueError('invalid summary')
            finished = True
            continue
        match = ROW.search(line)
        if not match or match[1] != run or not started or finished:
            raise ValueError('malformed, mixed, or out-of-order probe log')
        _, target, kind, api, order, pair, ticks, found, capped = match.groups()
        key = (int(target), kind, api, int(order), int(pair))
        if len(measured) >= len(expected) or key != expected[len(measured)]:
            raise ValueError('duplicate, missing, or unexpected measurement')
        measured.append(dict(target=int(target), **{'class': kind}, api=api, order=int(order),
                             pair=int(pair), ticks=int(ticks), ms=int(ticks) / ticks_per_ms,
                             found=found in ('true', '1'), capped=capped in ('true', '1')))
    if not started or not finished or len(measured) != len(expected):
        raise ValueError('incomplete probe log')
    grouped = defaultdict(list)
    for item in measured:
        grouped[item['class'], item['api']].append(item)
    table = []
    for (kind, api), items in sorted(grouped.items()):
        first = [r for r in items if r['pair'] == 0]
        repeat = [r for r in items if r['pair'] == 1]
        table.append(dict(**{'class': kind}, api=api, instances=len(first),
                          first_ms=[r['ms'] for r in first], repeat_ms=[r['ms'] for r in repeat],
                          first_touch_ms=[r['ms'] for r in first if r['order'] == 0],
                          found=all(r['found'] for r in items),
                          found_first=[r['found'] for r in first], found_repeat=[r['found'] for r in repeat],
                          capped=any(r['capped'] for r in items)))
    eligible = [a for a in apis if all(r['found'] and not r['capped'] and max(r['first_ms'] + r['repeat_ms']) <= 20
                                     for r in table if r['api'] == a)]
    recommendation = 'No API resolves every sampled class within 20 ms; retain cursor unchanged.'
    if eligible:
        best = min(eligible, key=lambda a: max(max(r['first_ms'] + r['repeat_ms']) for r in table if r['api'] == a))
        recommendation = 'Candidate ' + best + ': all sampled resolves <=20 ms; confirm in fresh-process single-API runs and retail before changing cursor.'
    result = dict(schema=1, evidence='diag-only-unverified', ticks_per_ms=ticks_per_ms,
                  plan_sha256=rt.sha256(plan_bytes), rpt_sha256=rt.sha256(raw),
                  run=run, table=table, measurements=measured, recommendation=recommendation)
    rt.new_file(out, (json.dumps(result, indent=2) + '\n').encode())
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    st = sub.add_parser('stage')
    st.add_argument('--tag', required=True)
    st.add_argument('--per-class', type=int, default=3)
    st.add_argument('--api', choices=('all',) + APIS, default='all')
    st.add_argument('--native-scripts', type=Path, default=Path.home() / '.cache/hollow-country/native-scripts/scripts-1.30.164289')
    st.add_argument('--dry-run', action='store_true')
    ing = sub.add_parser('ingest')
    ing.add_argument('--rpt', type=Path, required=True)
    ing.add_argument('--plan', type=Path, required=True)
    ing.add_argument('--out', type=Path, required=True)
    ing.add_argument('--ticks-per-ms', type=float, default=10000)
    args = parser.parse_args(argv)
    try:
        if args.command == 'stage':
            result = stage(args.tag, per_class=args.per_class, api=args.api,
                           native=args.native_scripts, dry_run=args.dry_run)
            print(result['status'] + '; targets=' + str(len(result['targets'])))
        else:
            result = ingest(args.rpt, args.plan, args.out, ticks_per_ms=args.ticks_per_ms)
            print(result['recommendation'])
        return 0
    except (OSError, ValueError, KeyError, TypeError):
        # Input/interop exceptions can contain private paths. Never echo them.
        print('Interior resolve probe refused: invalid/incomplete input, failed lint, busy host, or existing output.')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
