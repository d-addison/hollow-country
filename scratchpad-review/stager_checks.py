"""Explicit synthetic staging refusals in scratch only."""
from pathlib import Path
import sys
import tempfile
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parent / 'baseline'))
from tests.unit import test_weather_probe as f
from tools.setup import weather_probe as p, diagnostic_mission as dm, probe_runtime as rt

def scenario(name, prepare=None, registry=None, **extra):
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp); source=f.write_source_runtime(root/'source'); dest=root/'weather-test'
        if prepare: extra.update(prepare(root))
        with mock.patch.dict(dm._PURPOSES):
            if registry=='missing': dm._PURPOSES.pop(p.PURPOSE)
            elif registry is not None: dm._PURPOSES[p.PURPOSE]=registry
            before=dict(dm._PURPOSES)
            try:
                result=p.stage(source,dest,battleye_sha256=f.SYNTH_BE_SHA,_wsl_parent=root,**extra)
                print(name, 'ACCEPTED',result['probe']['cfgweather']['variant'],
                      'source_verified=',(result['probe']['cfgweather']['candidate'] or {}).get('source_verified'))
            except ValueError as exc:
                print(name,'REFUSED',str(exc),'destination_exists=',dest.exists())
            print('registry unchanged:',before==dm._PURPOSES)

scenario('stock')
scenario('valid reconstructed candidate',lambda root:{'candidate':f.write_candidate(root/'candidate')})
def drift(root):
    candidate=f.write_candidate(root/'candidate')
    f.StagerTests().tamper(candidate,lambda tree:tree.find('fog/limits').set('max','0.5'))
    return {'candidate':candidate}
scenario('rehashed unreported fog drift',drift)
scenario('missing purpose',registry='missing')
scenario('fixed hook substitution',registry=dm._PURPOSES['selftests'])
scenario('wrong generated metadata',registry=('disposable-wrong',None,['wrong']))
with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp); candidate=f.write_candidate(root/'candidate')
    try: p.reconstruct_candidate(candidate,f.STOCK_XML,'0'*64)
    except ValueError as exc: print('candidate changed between reads: REFUSED',str(exc))
print('actual launcher row:',rt.LAUNCHER_PROBES[p.PLAN_KIND])
print('actual purpose row:',dm._PURPOSES[p.PURPOSE])
