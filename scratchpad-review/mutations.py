"""Independent source mutations: scratch copies, existing tests, no worker runner imported."""
from pathlib import Path
import sys, io, unittest, contextlib
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'source-copy'))
from tools.setup import interior_sampler as s
from tools.audit import interior_points as p
from tests.unit import test_interior_sampler as st, test_interior_points as pt
ORIG={m:Path(m.__file__).read_text() for m in (s,p)}
CASES=[
('control-self-loop',s,'HCProbePath(entranceSampled, farSampled, farSampled)','HCProbePath(farSampled, farSampled, farSampled)'),
('endpoint-five-cm',s,'m_HCProbeEndTolerance = 0.5','m_HCProbeEndTolerance = 0.05'),
('endpoint-disabled',s,'if (m_HCProbePathGap > m_HCProbeEndTolerance)','if (false)'),
('snap-distance-disabled',s,'if (vector.Distance(candidate, floorPos) > m_HCProbeSnapLimit)','if (false)'),
('wall-ray-disabled',s,'if (HCProbeBlocked(Vector(floorPos[0], waistY, floorPos[2]), Vector(candidate[0], waistY, candidate[2])))','if (false)'),
('small-snap-no-exemption',s,'shiftX * shiftX + shiftZ * shiftZ > 0.000001','shiftX * shiftX + shiftZ * shiftZ > 0.0'),
('nonowner-blocks',s,'if (result == 0)\n            return false;\n        return true;','if (result == 2)\n            return true;\n        if (result == 0)\n            return false;\n        return true;'),
('open-sky-disabled',s,'if (!HCProbeOpenSky(entranceSampled))','if (false)'),
('projected-seed-validation-disabled',s,'if (!HCProbeOutsideBox(m_HCProbeSampledModel, m_HCProbeProjectedMargin))','if (false)'),
('raw-seed-validation-disabled',s,'if (HCProbeOutsideBox(m_HCProbeSeed, m_HCProbeSeedMargin))','if (true)'),
('path-budget-disabled',s,'if (m_HCProbeBuildingPaths >= m_HCProbePathLimit)','if (false)'),
('nonowner-clearance-skip-50cm',s,'startY = hitY + offset;','startY = hitY + 0.5;'),
('floor-owner-disabled',s,'if (found.Find(m_HCProbeBuilding) != -1)','if (true)'),
('barracks-calibration-omitted',p,'for name in CALIBRATION_CLASSES:','for name in CALIBRATION_CLASSES[:1]:'),
('calibration-threshold-disabled',p,'if coverage < min_calibration - EPSILON:','if False:'),
('calibration-xz-instead-3d',p,'coverage = min(entry["v3_coverage"] for entry in calibration.values())','coverage = min(entry["xz_coverage"] for entry in calibration.values())'),
('clearance-pick-highest-first',p,'(clearance, y) > (best[key][1], best[key][0])','(y, clearance) > (best[key][0], best[key][1])'),
('height-first-not-mean',p,'sum(v[0] for v in values) / len(values)','values[0][0]'),
('height-spread-disabled',p,'"height_ok": spread <= HEIGHT_SPREAD_BOUND + EPSILON','"height_ok": True'),
('reach-agreement-disabled',p,'and c["reach_agreement"] >= min_agreement - EPSILON','and True'),
('reach-known-disabled',p,'and c["reachable"] is True','and True'),
('lootmax-floor',p,'math.ceil(count * loot_ratio - EPSILON)','math.floor(count * loot_ratio + EPSILON)'),
('outside-bytes-guard-disabled',p,'if _outside_groups(stock, edited) != _outside_groups(output, edited):','if False:'),
('preexisting-point-refusal-disabled',p,'group.get("lootmax") != "0" or group.findall(".//point") or len(containers) != 1','group.get("lootmax") != "0" or False or len(containers) != 1'),
]
# Additional independent mutations of the new mechanisms, not the worker mutation runner.
CASES += [
 ('floor-cap-all-hits',s,'            action = 0;\n            if (rel == 1)','            action = 0;\n            floors = floors + 1;\n            if (rel == 1)'),
 ('floor-cap-disabled',s,'if (floors >= m_HCProbeHitLimit)','if (false)'),
 ('step-cap-disabled',s,'step < m_HCProbeStepLimit','step < 1024'),
 ('rehit-never-detected',s,'if (drop < 0.02)','if (false)'),
 ('rehit-no-doubling',s,'offset = usedOffset * 2.0;','offset = 0.05;'),
 ('rehit-max-raised',s,'if (offset > 0.8)\n                    offset = 0.8;','if (offset > 8.0)\n                    offset = 8.0;'),
 ('clearance-no-doubling',s,'offset = offset * 2.0;','offset = 0.05;'),
 ('clearance-no-cap',s,'attempt < 16','attempt < 100'),
 ('ladder-one-attempt',s,'attempt < 30','attempt < 1'),
 ('ladder-no-progress',s,'standoff = standoff + 1.0;','standoff = standoff;'),
 ('ladder-door-altitude',s,'float ground = GetGame().SurfaceY(seedWorld[0], seedWorld[2]);','float ground = seedWorld[1];'),
 ('far-door-altitude',s,'float farGround = GetGame().SurfaceY(farWorld[0], farWorld[2]);','float farGround = farWorld[1];'),
 ('nonowner-clear',s,'if (result == 0)\n            return false;\n        return true;','if (result != 1)\n            return false;\n        return true;'),
 ('unknown-ray-clear',s,'if (result == 0)\n            return false;\n        return true;','if (result <= 0)\n            return false;\n        return true;'),
 ('final-gap-ray-disabled',s,'if (gapX * gapX + gapZ * gapZ > 0.000001)','if (false)'),
 ('final-gap-sloped-height',s,'Vector(finalPoint[0], waistY, finalPoint[2])','Vector(finalPoint[0], finalPoint[1] + m_HCProbeWaistHeight, finalPoint[2])'),
 ('old-small-snap-exemption',s,'shiftX * shiftX + shiftZ * shiftZ > 0.000001','shiftX * shiftX + shiftZ * shiftZ > 0.0025'),
 ('sky-foreign-clear',s,'if (m_HCProbeSkyResult == 0)\n            return true;','if (m_HCProbeSkyResult != 1)\n            return true;'),
 ('relation-proxy-disabled',s,'if (found.Get(index).GetParent() == m_HCProbeBuilding)','if (false)'),
 ('reach-success-wrong-stage',s,'if (stage == 12)','if (stage == 11)'),
]
def flatten(ts):
 for t in ts:
  if isinstance(t,unittest.TestSuite):yield from flatten(t)
  else:yield t
def run(label):
 ts=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m) for m in (st,pt))
 ts=unittest.TestSuite(t for t in flatten(ts) if not t.id().endswith('test_every_mutated_condition_is_detected'))
 stream=io.StringIO()
 with contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
  res=unittest.TextTestRunner(stream=stream).run(ts)
 (HERE/'mutation-logs'/f'{label}.log').write_text(stream.getvalue())
 bad=[t.id().split('.')[-1] for t,_ in res.failures+res.errors]
 print(f'{label}: '+('KILLED' if bad else 'SURVIVED')+f'; tests={res.testsRun}; failures/errors={len(bad)}; '+', '.join(bad),flush=True)
 return bad
(HERE/'mutation-logs').mkdir(exist_ok=True)
assert not run('baseline')
for label,module,old,new in CASES:
 source=ORIG[module]
 assert source.count(old)==1,(label,source.count(old))
 mutated=source.replace(old,new,1)
 path=HERE/'mutation-logs'/f'{label}.py';path.write_text(mutated)
 exec(compile(mutated,str(path),'exec'),module.__dict__)
 run(label)
 exec(compile(source,module.__file__,'exec'),module.__dict__)
