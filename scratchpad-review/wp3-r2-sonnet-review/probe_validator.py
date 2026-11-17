import sys, json, copy, tempfile, io, contextlib
from pathlib import Path
from unittest import mock
sys.path.insert(0,'/code/hc-worktrees/wp3-integ')
from tests.unit.test_taped_light_probe import make_source_runtime, SYNTH_BE_SHA
from tests.unit.test_infected_competence import synthetic_receipt, CACHE
from tools.setup import diagnostic_mission as dm, probe_runtime as rt, infected_competence_probe as probe
tmp=Path(tempfile.mkdtemp(dir='/tmp/claude-1000/-code-dayzsa-mods/c2f49688-a754-49e7-ae80-940623b5a25a/scratchpad'))
src=make_source_runtime(tmp/'vanilla')
cfg=b'hostname = "SYNTHETIC";\nmaxPlayers = 6;\n'
(src/'serverDZ.cfg').write_bytes(cfg)
sp=json.loads((src/'launch-plan.json').read_text()); sp['config_sha256']=rt.sha256(cfg); (src/'launch-plan.json').write_text(json.dumps(sp))
dest=tmp/'d'
print('registered unpatched?', dm._PURPOSES.get(probe.PURPOSE)==probe.PURPOSE_ROW)
probe.stage(src,dest,native_scripts=CACHE,battleye_sha256=SYNTH_BE_SHA,_wsl_parent=tmp)
plan=json.loads((dest/probe.PLAN_NAME).read_text())
def write(r):
    d=dest/'profiles/HCInfectedCompetence'; d.mkdir(parents=True,exist_ok=True)
    (d/'observations.json').write_text(json.dumps(r)); (d/'complete.txt').write_text('status=complete\n')
def attempt(name,mut):
    r=synthetic_receipt(plan); mut(r); write(r)
    try: probe.validate(dest); print('ACCEPTED',name)
    except Exception as e: print('REFUSED ',name,'->',e)
attempt('baseline',lambda r:None)
def f(r): 
    for t in r['trials']:
        for s in t['samples']: s['position']='0 0 0'
attempt('sample positions at 0 0 0 (far from spawn / surface_y)',f)
def f(r):
    for t in r['trials']:
        if t['status']=='completed': t['anchor_surface_y']='-5000'; t['spawn_surface_y']='99999'
attempt('absurd surface_y',f)
def f(r):
    for t in r['trials']:
        if t['status']=='completed': t['reason']='totally fabricated reason'
attempt('arbitrary reason on completed',f)
def f(r):
    for t in r['trials']:
        if t['status']=='completed': t['elapsed_ms']=5000
    r['trials'][0]['status']='inconclusive';r['trials'][0]['observed']=False;r['trials'][0]['reason']='trial_time_budget';r['trials'][0]['elapsed_ms']=10
attempt('trial_time_budget with elapsed 10ms',f)
def f(r):
    r['trials'][0]['status']='inconclusive';r['trials'][0]['observed']=False;r['trials'][0]['reason']='footprint_ray_hit';r['trials'][0]['geometry']=[0,0,0,0]
attempt('footprint_ray_hit with all-zero rays',f)
def f(r):
    r['trials'][0]['status']='inconclusive';r['trials'][0]['observed']=False;r['trials'][0]['reason']='structure_missing_ambiguous_or_query_budget';r['trials'][0]['spawned']=1;r['trials'][0]['samples']=r['trials'][0]['samples']
attempt('structure_missing but spawned=1 and samples present',f)
def f(r):
    r['trials'][0]['samples'][0]['mind']=5; r['trials'][0]['samples'][1]['mind']=77
attempt('mind arbitrary 77',f)
def f(r):
    for t in r['trials']:
        if t['kind'] in('limb_damage','crawl_health_only'): t['samples'][0]['left']='9999999'
attempt('left before >10000',f)
def f(r):
    for t in r['trials']:
        if t['kind']=='limb_damage': t['samples'][0]['left']='100'; t['samples'][1]['left']='99.9'
attempt('limb fell by 0.1 only',f)
def f(r):
    for t in r['trials']:
        if t['kind']=='spawn_lifecycle': t['samples'][1]['crawling']=True; t['samples'][1]['alive']=True
attempt('crawling true on non-injury trial',f)
def f(r):
    for t in r['trials']:
        if t['kind']=='limb_damage': t['samples'][1]['alive']=True; t['samples'][1]['left']='-5'
attempt('negative leg',f)
def f(r):
    r['trials'][0]['elapsed_ms']=6000
    r['trials'][1]['elapsed_ms']=5000
attempt('elapsed 6000 completed ',f)
def f(r):
    r['version']='build 1.30.164289'
attempt('version-with-prefix',f)
def f(r):
    for t in r['trials']:
        if t['status']=='completed':
            t['anchor_authored_y']='0.009'
attempt('authored y within 0.01',f)
print(json.dumps(probe.validate(dest) if False else {}, indent=0))
