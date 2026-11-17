"""Exercise returning paths in generated hook against explicit synthetic world fixtures."""
import sys,json
from pathlib import Path
from unittest import mock
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'head'))
from tests.unit import test_taped_light_probe as f
from tools.setup import taped_light_probe as p
from tools.audit import taped_light_report as report

def variant_failure_world():
    class W(f.World):
        def __init__(self):super().__init__();self.ak_count=0
        def CreateObjectEx(self,type_name,position,flags):
            if type_name=='AK74':
                self.ak_count+=1
                if self.ak_count==2:return None
            return super().CreateObjectEx(type_name,position,flags)
    return W()

def go(label,w,**kw):
    f.run_hook(w,**kw);o=f.observations_of(w)
    guards=[e for e in w.entities if 'Hndgrd' in e.type_name]
    print(json.dumps({'case':label,'status':o['status'],'spawned':o['counters']['spawned'],'deleted':o['counters']['deleted'],
        'live_entities':[e.type_name for e in w.live()],'handguards':[(e.type_name,e.alive) for e in guards],
        'live_after_release':o['counters']['live_after_release'],'census_total':o['counters']['census_total'],
        'residual_probe_types':o['counters']['residual_probe_types'],'residual_other':o['counters']['residual_other'],
        'integrity':report.build_report(f.classification(),o)['integrity']['issues']},sort_keys=True))

go('normal',f.World())
t=f.catalogue();t.pop('AK_RailHndgrd');go('handguard creation refused',f.World(types=t))
go('variant host creation refused',variant_failure_world())
go('per-class timeout',f.World(spawn_ms=1500),per_class_ms=2000)
go('watchdog partial',f.World(spawn_ms=15000))
go('handguard delete refused by synthetic engine',f.World(stuck=('AK_RailHndgrd',)))
go('truncated census',f.World(background=p.CENSUS_SCAN_LIMIT+1))
