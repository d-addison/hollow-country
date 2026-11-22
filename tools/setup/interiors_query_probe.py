"""Generate a disposable mission init.c for the lead's native query A/B; never launch.

Usage: python3 -B -m tools.setup.interiors_query_probe --init STOCK_INIT \
    --positions MAPGROUPPOS_XML --output FRESH_INIT --native-scripts CACHE

Copy the generated init.c into a separately copied stock Chernarus mission with
fresh storage/profile. The lead runs it under the shared native host lock with
no clients and an outer timeout (180 s). Never replace a live mission. This tool
only emits a file; it does not stage a server, edit profiles, or launch anything.
Inspect [HC QueryProbe] begin/call/result/done in RPT. ticks are raw TickCount
units; the calibration line reports ticks_per_ms measured over a queued delay.
A result passes only when circle, tiled circle union, and sphere each resolve
one identical Object; missing/ambiguous/capped results fail even if equal. Each
call logs native-only ticks and result count, including each of the four tiles.
Alternating order reduces warm-cache bias; sample zero remains a cold observation,
not a guarantee. Repeat on a fresh server with --legacy-first to compare cold
orders. Native timing/binding and the production R2 soak remain pending.

Installed scripts-1.30.164289 APIs: Game.c:923/930 circle/sphere, :1550
GetCallQueue, :1120 IsServer, :914 GetTickTime; Object.c:287/467 position/type;
EnSystem.c:106 TickCount; EnScript.c:380/385/394/407 arrays; tools.c:61 CallLater.
The .75 m sphere is the smallest sphere containing the existing .75 m origin
acceptance region; a smaller exact-origin radius could silently miss ambiguity.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from tools.setup import probe_core, probe_runtime

CLASSES = (
    'Land_Tenement_Small', 'Land_Mil_Barracks3', 'Land_Mil_Barracks4',
    'Land_House_2B01', 'Land_House_2B04', 'Land_CementWorks_ExpeditionA',
)
MAX_INPUT = 32 * 1024 * 1024


def select_targets(data, instances=1):
    """Select deterministic exact stock origins, requiring every requested class."""
    if type(instances) is not int or not 1 <= instances <= 3:
        raise ValueError('instances must be in 1..3')
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_INPUT:
        raise ValueError('bounded XML bytes required')
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise ValueError('XML declarations refused')
    groups = {name: [] for name in CLASSES}
    for element in ET.fromstring(data).iter('group'):
        name = element.get('name')
        if name not in groups:
            continue
        position = [float(n) for n in element.get('pos', '').split()]
        if len(position) != 3 or not all(math.isfinite(n) and abs(n) <= 30000 for n in position):
            raise ValueError('invalid stock origin')
        if position not in groups[name] and len(groups[name]) < instances:
            groups[name].append(position)
    if any(len(rows) != instances for rows in groups.values()):
        raise ValueError('required building instances missing from stock positions')
    return [dict(building_class=name, position=position)
            for name, positions in groups.items() for position in positions]


def render_hook(targets, samples=4, *, legacy_first=False):
    if type(samples) is not int or not 2 <= samples <= 8:
        raise ValueError('samples must be in 2..8')
    if not targets or len(targets) > len(CLASSES) * 3:
        raise ValueError('bounded targets required')
    token = hashlib.sha256(json.dumps([targets, samples, legacy_first], sort_keys=True).encode()).hexdigest()
    inserts = []
    for row in targets:
        name, position = row['building_class'], row['position']
        if name not in CLASSES or len(position) != 3 or not all(
                type(n) in (int, float) and math.isfinite(n) and abs(n) <= 30000 for n in position):
            raise ValueError('invalid target')
        # Fixed decimal literals avoid Enforce's unsupported exponent literals.
        components = ', '.join(format(n, '.9f') for n in position)
        inserts += [f'        m_Types.Insert("{name}");',
                    f'        m_Positions.Insert(Vector({components}));']
    return HOOK.replace('@INSERTS@', '\n'.join(inserts)).replace('@SAMPLES@', str(samples)).replace('@TOKEN@', token).replace('@LEGACY_PARITY@', '0' if legacy_first else '1')


HOOK = r'''
// Generated observation-only probe. No actors, transforms or inventory writes.
class HCInteriorQueryProbeMission : CustomMission
{
    ref array<string> m_Types = new array<string>;
    ref array<vector> m_Positions = new array<vector>;
    ref array<Object> m_Tiled = new array<Object>;
    Object m_Circle;
    Object m_Sphere;
    int m_CircleMatches;
    int m_SphereMatches;
    bool m_Capped;
    int m_Target;
    int m_Sample;
    int m_Call;
    int m_Calibration;
    float m_CalibrationTime;

    override void OnInit()
    {
        super.OnInit();
        if (!GetGame().IsServer()) { return; }
@INSERTS@
        Print("[HC QueryProbe] begin binding=@TOKEN@");
        m_Calibration = TickCount(0);
        m_CalibrationTime = GetGame().GetTickTime();
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCCalibrate, 1000, false);
    }

    void HCCalibrate()
    {
        float elapsed = GetGame().GetTickTime() - m_CalibrationTime;
        float scale = TickCount(m_Calibration) / (elapsed * 1000);
        Print("[HC QueryProbe] ticks_per_ms=" + scale.ToString());
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCNext, 100, false);
    }

    void HCNext()
    {
        vector position = m_Positions[m_Target];
        // Alternate sphere/circle/tiles with tiles/circle/sphere each sample.
        int method = m_Call;
        if (m_Sample % 2 == @LEGACY_PARITY@) { method = 5 - m_Call; }
        vector centre = position;
        float radius = 0.75;
        if (method >= 2)
        {
            int tile = method - 2;
            int column = tile % 2;
            int line = tile / 2;
            centre = position + Vector(column * 0.75 - 0.375, 0, line * 0.75 - 0.375);
            radius = 0.531;
        }
        array<Object> objects = new array<Object>;
        array<CargoBase> cargos;
        int mark = TickCount(0);
        if (method == 0) { GetGame().GetObjectsAtPosition3D(centre, radius, objects, cargos); }
        else { GetGame().GetObjectsAtPosition(centre, radius, objects, cargos); }
        int ticks = TickCount(mark);
        string prefix = "[HC QueryProbe] call target=" + m_Target.ToString() + " sample=" + m_Sample.ToString();
        Print(prefix + " method=" + method.ToString() + " ticks=" + ticks.ToString() + " count=" + objects.Count().ToString());
        Object found;
        int matches;
        if (objects.Count() > 256) { m_Capped = true; }
        else
        {
            foreach (Object candidate : objects)
            {
                if (!candidate || candidate.GetType() != m_Types[m_Target]) { continue; }
                if (vector.DistanceSq(position, candidate.GetPosition()) > 0.5625) { continue; }
                if (method >= 2)
                {
                    if (m_Tiled.Find(candidate) < 0) { m_Tiled.Insert(candidate); }
                }
                else
                {
                    found = candidate;
                    matches = matches + 1;
                }
            }
        }
        if (method == 0) { m_Sphere = found; m_SphereMatches = matches; }
        if (method == 1) { m_Circle = found; m_CircleMatches = matches; }
        m_Call = m_Call + 1;
        if (m_Call == 6)
        {
            bool same = !m_Capped && m_CircleMatches == 1 && m_SphereMatches == 1 && m_Tiled.Count() == 1;
            if (same) { same = m_Circle == m_Sphere && m_Circle == m_Tiled[0]; }
            string result = "[HC QueryProbe] result target=" + m_Target.ToString() + " class=" + m_Types[m_Target];
            result = result + " sample=" + m_Sample.ToString() + " same=" + HCProbeBool(same);
            Print(result + " binding=@TOKEN@");
            m_Call = 0;
            m_Circle = null;
            m_Sphere = null;
            m_CircleMatches = 0;
            m_SphereMatches = 0;
            m_Capped = false;
            m_Tiled.Clear();
            m_Sample = m_Sample + 1;
            if (m_Sample == @SAMPLES@) { m_Sample = 0; m_Target = m_Target + 1; }
        }
        if (m_Target == m_Types.Count())
        {
            Print("[HC QueryProbe] done binding=@TOKEN@");
            return;
        }
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCNext, 100, false);
    }
@JSON@
}
'''.replace('@JSON@', probe_core.enforce_json_helpers())


def generate(init, positions, native_scripts, *, samples=4, instances=1, legacy_first=False):
    targets = select_targets(positions, instances)
    game = (Path(native_scripts) / '3_Game/Global/Game.c').read_text()
    for api in ('GetObjectsAtPosition(', 'GetObjectsAtPosition3D('):
        if api not in game:
            raise ValueError('required native query signature missing')
    hook = render_hook(targets, samples, legacy_first=legacy_first)
    problems = probe_runtime.lint_hook(hook, explicit_numbers=True)
    if problems:
        raise ValueError('generated hook lint: ' + '; '.join(map(str, problems)))
    source = init.decode('utf-8-sig')
    factory = re.compile(r'(return\s+new\s+)CustomMission(\s*\(\s*\)\s*;)')
    if len(factory.findall(source)) != 1:
        raise ValueError('one stock CustomMission factory required')
    source = factory.sub(r'\1HCInteriorQueryProbeMission\2', source)
    return (source + '\n' + hook).encode()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--init', type=Path, required=True)
    parser.add_argument('--positions', type=Path, required=True)
    parser.add_argument('--native-scripts', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--samples', type=int, default=4)
    parser.add_argument('--instances', type=int, default=1)
    parser.add_argument('--legacy-first', action='store_true')
    args = parser.parse_args(argv)
    # No paths are printed: source/profile paths can contain private host names.
    data = generate(probe_runtime._read_bounded(probe_core.safe(args.init), MAX_INPUT),
                    probe_runtime._read_bounded(probe_core.safe(args.positions), MAX_INPUT),
                    probe_core.safe(args.native_scripts), samples=args.samples, instances=args.instances, legacy_first=args.legacy_first)
    output = probe_core.safe(args.output)
    with output.open('xb') as stream:
        stream.write(data)
    print(json.dumps(dict(status='generated-only-not-launched', bytes=len(data))))


if __name__ == '__main__':
    main()
