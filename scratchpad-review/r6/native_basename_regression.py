"""Native-shaped backslash input is synthetic; optional correction changes generated text in memory only."""
import sys,json,unittest
from pathlib import Path
from unittest import mock
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/('parent' if '--parent' in sys.argv else 'head')))
from tools.setup import taped_light_probe as p
from tools.audit import taped_light_report as r
from tests.unit import test_taped_light_probe as f
FIX='--fixed' in sys.argv
class NativeBasename(unittest.TestCase):
    def test_backslash_selection_reads_the_basename_config_entry(self):
        types=f.proxy_types();types['AK74']['proxies']=(f.LIGHT_UNIVERSAL_PROXY.replace('/','\\'),);types['AK74']['view']=None
        world=f.World(types=types)
        real=p.render_hook
        def render(*args,**kwargs):
            raw=real(*args,**kwargs)
            before=b'string text = selectionName.Substring(6, selectionName.Length() - 6);'
            assert raw.count(before)==1
            return raw.replace(before,before+b'\n        text.Replace(m_HCTLSlash, "/");') if FIX else raw
        with mock.patch.object(p,'render_hook',side_effect=render):f.run_hook(world,slots=f._NoSelectionSlots)
        obs=f.observations_of(world);item=f.host_row(obs,'AK74')['proxies'][0]
        result=r.build_report(f.classification(),obs)
        slot=next(h for h in result['hosts'] if h['class']=='AK74')['lights']['UniversalLight']['slots']['weaponFlashlight']
        print('BACKSLASH',json.dumps({'fixed_in_memory':FIX,'revision':'691b115' if '--parent' in sys.argv else '0c9f4ec','cfg_class':item['cfg_class'],'cfg_exists':item['cfg_exists'],'verdict':slot['verdict'],'reason':slot['reason'],'live':len(world.live())}),flush=True)
        self.assertEqual('Proxyweaponlight_universal',item['cfg_class'])
        self.assertTrue(item['cfg_exists'])
        self.assertEqual(('pending','view_lod_missing'),(slot['verdict'],slot['reason']))
if __name__=='__main__':unittest.main(argv=[sys.argv[0]],verbosity=2)
