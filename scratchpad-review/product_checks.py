"""Writer checks on read-only stock XML and explicitly synthetic selections/census."""
from pathlib import Path
import sys,random,copy,hashlib,collections,xml.etree.ElementTree as ET,subprocess
sys.path.insert(0,str(Path(__file__).resolve().parent/'source-copy'))
from tests.unit import test_interior_points as f
from tools.audit import interior_points as p
stock=Path('/mnt/d/HollowCountryLocal/vanilla-p0-001/stock-backup/mpmissions/dayzOffline.chernarusplus/mapgroupproto.xml').read_bytes()
d=f.full_census();fixture,report=p.build_treatment(f.encode(d),f.STOCK,.4)
selections={name:report['classes'][name]['points'] for name in p.TENEMENT_CLASSES}
first=p.write_treatment(stock,selections)
print('real stock writer + explicit synthetic selections: bytes',len(first),'hash',hashlib.sha256(first).hexdigest(),'changed',report['treatment']['groups_changed'])
print('outside bytes identical',p._outside_groups(stock,p.TENEMENT_CLASSES).encode()==p._outside_groups(first,p.TENEMENT_CLASSES).encode())
variants=[]
for seed in range(10):
 trial=copy.deepcopy(d);rng=random.Random(seed);rng.shuffle(trial['placements'])
 for row in trial['placements']:rng.shuffle(row['hits'])
 result,rep=p.build_treatment(f.encode(trial),f.STOCK,.4)
 sels={name:rep['classes'][name]['points'] for name in p.TENEMENT_CLASSES}
 variants.append(result==fixture and p.write_treatment(stock,sels)==first)
print('10 seeded permutations of placements/hits produce identical treatment:',all(variants),variants)
root=ET.fromstring(first)
for name in p.TENEMENT_CLASSES:
 g=next(g for g in root.iter('group') if g.get('name')==name)
 pts=g.findall('.//point');coords=[pt.get('pos') for pt in pts]
 print(name,'points',len(pts),'unique coordinates',len(set(coords)),'group lootmax',g.get('lootmax'),'containers',[(c.get('name'),c.get('lootmax'),len(c.findall('point'))) for c in g.findall('container')])
print('builder source changed by commit:',bool(subprocess.check_output(['git','diff','9816612^','9816612','--','tools/audit/interior_points.py'])))
