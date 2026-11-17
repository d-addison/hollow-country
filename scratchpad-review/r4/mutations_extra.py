"""Independent in-memory mutations; all emitted sources/logs confined to r4. Synthetic tests only."""
from pathlib import Path
import sys,io,unittest,contextlib,json,time
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'source-copy'))
from tools.setup import interior_sampler as s
from tools.audit import interior_points as p
from tests.unit import test_interior_sampler as st,test_interior_points as pt
ORIG={m:Path(m.__file__).read_text() for m in (s,p)}
CASES=[
('snap-authorized',s,'return HCProbeReachResult(variant, 8, floorPos);','return HCProbeReachResult(variant, 7, floorPos);'),
('gap-authorized',s,'return HCProbeReachResult(variant, 9, floorPos);','return HCProbeReachResult(variant, 7, floorPos);'),
('free-clearance-disabled',s,'if (freeClear < m_HCProbeClearRequired)','if (false)'),
('owner-rehits-counted',s,'if (rel == 1 && drop >= 0.02)','if (rel == 1)'),
('column-cap-eligible',s,'if (capKind > 0)\n            return HCProbeReachResult(variant, 11, floorPos);','if (false)\n            return HCProbeReachResult(variant, 11, floorPos);'),
('samples-unbounded',s,'if (seen >= 8)','if (false)'),
('samples-one-short',s,'if (seen >= 8)','if (seen >= 7)'),
('player-budget-shared',s,'if (m_HCProbePlayerPaths >= m_HCProbePathLimit)','if (m_HCProbeBuildingPaths >= m_HCProbePathLimit)'),
('player-budget-disabled',s,'if (m_HCProbePlayerPaths >= m_HCProbePathLimit)','if (false)'),
('strict-budget-disabled',s,'if (m_HCProbeBuildingPaths >= m_HCProbePathLimit)','if (false)'),
('player-state-uses-strict',s,'state = m_HCProbePlayerState;\n            meshFilter','state = m_HCProbeReachState;\n            meshFilter'),
('player-path-uses-strict',s,'int stage = HCProbePath(entrance, candidate, floorPos, meshFilter);','int stage = HCProbePath(entrance, candidate, floorPos, m_HCProbeFilter);'),
('snap-vertical-disabled',s,'if (m_HCProbeDiagVSnap > m_HCProbeVerticalAllowance)','if (false)'),
('gap-vertical-disabled',s,'if (m_HCProbeDiagVGap > m_HCProbeVerticalAllowance)','if (false)'),
('unknown-ray-clear',s,'if (result == 0)\n            return false;\n        return true;','if (result <= 0)\n            return false;\n        return true;'),
('far-control-altitude',s,'float farGround = GetGame().SurfaceY(farWorld[0], farWorld[2]);','float farGround = farWorld[1];'),
('sloped-gap-ray',s,'Vector(finalPoint[0], waistY, finalPoint[2])','Vector(finalPoint[0], finalPoint[1] + m_HCProbeWaistHeight, finalPoint[2])'),
('clearance-no-doubling',s,'offset = offset * 2.0;','offset = 0.05;'),
('rehit-max-raised',s,'if (offset > 0.8)\n                    offset = 0.8;','if (offset > 8.0)\n                    offset = 8.0;'),
('unqualified-as-yes',p,'if value[3] == 3:\n                unqualified += 1','if value[3] == 3:\n                counts["yes"] += 1'),
('unqualified-denominator-removed',p,'counts["nonav"] + unqualified','counts["nonav"]'),
('player-source-uses-strict',p,'if reach_source == "strict":\n        return [hit[5] for hit in row["hits"]]','if True:\n        return [hit[5] for hit in row["hits"]]'),
('unknown-eligible',p,'and c["reachable"] is True and c["reach_agreement"]','and True and c["reach_agreement"]'),
('refusal-report-removed',p,'if path is None or report is None:', 'if True:'),
]
# Exclude the worker mutation meta-test. Broader behavioral tests exercise old survivors too.
CLASSES=[st.SafetyRegressionTests,st.DescentTests,st.DiagnosticsTests,st.ControlSeedTests,st.Round3DiagTests,st.Round3PlayerTests,st.Round3ControlDetailTests,st.Round3AddendumTests,pt.Round3CodeAndSourceTests,pt.Round3FunnelTests,pt.Round3ReportTests,pt.Round3CliTests,pt.ReachGateSurvivorTests]
OUT=HERE/'mutation-logs';OUT.mkdir(exist_ok=True)
def run(label):
 suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in CLASSES)
 stream=io.StringIO()
 with contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):r=unittest.TextTestRunner(stream=stream).run(suite)
 (OUT/(label+'.log')).write_text(stream.getvalue())
 bad=[t.id() for t,_ in r.failures+r.errors]
 result={'name':label,'status':'KILLED' if bad else 'SURVIVED','tests':r.testsRun,'failures':bad}
 print(json.dumps(result),flush=True);return result
results=[run('baseline')]
assert results[0]['status']=='SURVIVED'
for label,module,old,new in CASES[-2:]:
 source=ORIG[module]
 if source.count(old)!=1:
  print(json.dumps({'name':label,'status':'ANCHOR-MISMATCH','count':source.count(old)}),flush=True);continue
 mutated=source.replace(old,new,1)
 path=OUT/(label+'.py');path.write_text(mutated)
 exec(compile(mutated,str(path),'exec'),module.__dict__)
 results.append(run(label))
 exec(compile(source,module.__file__,'exec'),module.__dict__)
(HERE/'mutation-results-extra.json').write_text(json.dumps(results,indent=2))
