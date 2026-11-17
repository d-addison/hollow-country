"""Explicitly synthetic review probes. No DayZ behavior established."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
from unittest import mock

HERE=Path(__file__).resolve().parent
SOURCE=HERE/'source'
sys.path.insert(0,str(SOURCE))
from tools.audit import interior_points as pts
from tests.unit import test_interior_points as tp
from tests.unit import test_interior_sampler as ts

results=[]
def build(label, document, **kwargs):
    (HERE/(label+'-census.json')).write_bytes(tp.encode(document))
    try:
        treatment, report=pts.build_treatment(tp.encode(document),tp.STOCK,0.4,**kwargs)
        (HERE/(label+'-treatment.xml')).write_bytes(treatment)
        (HERE/(label+'-report.json')).write_text(json.dumps(report,indent=2)+'\n')
        results.append({'probe':label,'status':report['status'],'bytes':len(treatment),
                        'door_semantics':report['door_semantics']})
    except ValueError as e:
        results.append({'probe':label,'refused':str(e),'kind':getattr(e,'report',{}).get('refusal',{}).get('kind')})

build('baseline',tp.full_census())
for label, door in [('already-open',[0,0,0,0,1,1]),('locked-closed',[0,0,0,1,0,0]),
                     ('invalid-phase',[0,0,0,0,0,99]),('nonbinary-flags',[0,0,0,4,-2,0])]:
    doc=tp.full_census()
    for row in doc['placements']:
        row['door_run']['doors']=[door]
    build('forged-'+label,doc)

# The old generated hook declares a stalled physical close restored because it reads the wanted phase.
spec=importlib.util.spec_from_file_location('tools.setup.legacy_sampler_r5',HERE/'legacy_sampler_r5.py')
legacy=importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)
case=ts.Round6DoorPhaseTests()
case.hook=legacy.render_hook(ts.sampler_targets()).decode()
run, building=case.gated(stuck={0:{'close'}})
oldrow=run.row()
(HERE/'legacy-stalled-close-row.json').write_text(json.dumps(oldrow,indent=2)+'\n')
results.append({'probe':'legacy-stalled-close-hook','door_run':oldrow['door_run'],
                'actual_open':building.IsDoorOpened(0),'actual_closed':building.IsDoorClosed(0)})
doc=tp.full_census()
for row in doc['placements']:
    row['door_run']=oldrow['door_run']
build('legacy-stalled-close-accepted',doc)

# Player treatment has open codes; omit the as-found codes so door_semantics never examines these rows.
for label in ('missing','not-restored','open-stalled'):
    doc=tp.full_census()
    for row in doc['placements']:
        row['player_codes']=[h[5] for h in row['hits']]
        row['open_player_codes']=row['open_codes'][:]
        row['reach']['player']={'state':'tested'}
        if row['role']=='tenement':
            del row['player_codes']
            if label=='missing': del row['door_run']
            elif label=='not-restored': row['door_run'].update(restored=0,state='not-restored')
            else: row['door_run'].update(observed_open=0,state='open-stalled')
    build('player-skip-'+label,doc,reach_source='player')

# A malformed noncandidate row must not manufacture treatment, but does the run flag failure globally?
doc=tp.full_census()
doc['placements'][0]['door_run'].update(restored=0,state='not-restored')
doc['placements'][0]['entered']['strict']['open']='not-entered'
build('failed-restore-excluded-control',doc)

# Refusal output: reject static unsafe aliases and existing files; reproduce parent-directory swap.
inside=SOURCE/'review-probe-output'
inside.mkdir(exist_ok=True)
static=[]
for label,value in [('inside',inside/'static.json'),('dotdot',HERE/'outside'/'..'/'report.json')]:
    try: pts._output_path(str(value)); static.append([label,'ACCEPTED'])
    except ValueError: static.append([label,'refused'])
external=HERE/'parent-swap'
external.mkdir(exist_ok=True)
report=external/'refusal.json'
argv=['--radius','bad','--report',str(report)]
real_write=pts._write_refusal
saved=HERE/'parent-swap-original'
def swapped(path,error):
    external.rename(saved)
    external.symlink_to(inside,target_is_directory=True)
    real_write(path,error)
with mock.patch.object(pts,'_write_refusal',swapped),contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
    code=pts.main(argv)
results.append({'probe':'refusal-parent-swap','exit':code,'wrote_inside_checkout':(inside/'refusal.json').is_file(),'static':static})
# O_EXCL protects existing leaves even after the swap.
with contextlib.redirect_stderr(io.StringIO()):
    real_write(report,ValueError('must not replace'))
results.append({'probe':'refusal-existing-file-after-swap','preserved':json.loads((inside/'refusal.json').read_text())['refusal']['kind']=='invalid-input'})
(HERE/'adversarial-results.json').write_text(json.dumps(results,indent=2)+'\n')
for r in results:
    print(json.dumps({k:v for k,v in r.items() if k!='door_semantics'},sort_keys=True))
