"""Synthetic source and destination races: no engine, only scratch files."""
import sys,tempfile,json,os,re
from pathlib import Path
from unittest import mock
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'head'))
tempfile.tempdir=str(ROOT/'tmp')
from tests.unit import test_taped_light_probe as f
from tools.setup import taped_light_probe as p,probe_runtime as rt,diagnostic_mission as dm

def run(label,patcher):
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);source=f.make_source_runtime(root/'vanilla');dest=root/'taped-light-test'
        try:
            with patcher(root,source,dest):
                p.stage(source,dest,f.classification(),battleye_sha256=f.SYNTH_BE_SHA,_wsl_parent=root)
            outcome='ACCEPTED'
        except Exception as e:outcome=type(e).__name__+': '+str(e)
        print(label+': '+outcome+'; destination_exists='+str(dest.exists())+'; plan_exists='+str((dest/p.PLAN_NAME).exists()))

def mutate_verified(action):
    def patcher(root,source,dest):
        real=rt.verify_source
        def after(*a,**kw):
            result=real(*a,**kw);action(root,source,dest);return result
        return mock.patch.object(rt,'verify_source',side_effect=after)
    return patcher

def existing_link(part):
    def patcher(root,source,dest):
        target=source/part;moved=root/('outside-'+target.name)
        target.rename(moved);target.symlink_to(moved,target_is_directory=moved.is_dir())
        return mock.patch.dict({}, {})
    return patcher

run('verified-runtime trailing-dot alias',lambda root,source,dest:mock.patch.object(rt,'windows_runtime_root',side_effect=lambda d,parent:rt.windows_runtime_root.__wrapped__(d,parent))) if False else None
for name in ('vanilla-p0-001.','CON','nul.txt','name.','a..b','a...b'):
    try:result=p.windows_runtime_root(Path('/synthetic')/name,Path('/synthetic'))
    except Exception as e:result=type(e).__name__+': '+str(e)
    # Emulate just the launcher's literal name predicate, no PowerShell execution.
    ps_accept=bool(rt.NAME_RULE.fullmatch(name)) and not rt.RESERVED_DEVICE.match(name) and '..' not in name and name.rstrip(' .').lower()!='vanilla-p0-001'
    print('NAME '+repr(name)+': Python='+result+'; PS1-text-predicate='+str(ps_accept))
for part in ('serverDZ.cfg','battleye/BEServer_x64.dll','launch-plan.json','battleye'):
    run('pre-existing symlink '+part,existing_link(part))
run('config changes after verification',mutate_verified(lambda root,s,d:(s/'serverDZ.cfg').write_bytes(b'SYNTHETIC-UNVERIFIED-CONFIG')))
run('sensitive mission file added after verification',mutate_verified(lambda root,s,d:(s/'stock-backup/mpmissions/dayzOffline.chernarusplus/credentials.json').write_bytes(b'SYNTHETIC-SECRET')))
run('mission bytes changed after verification',mutate_verified(lambda root,s,d:(s/'stock-backup/mpmissions/dayzOffline.chernarusplus/db/types.xml').write_bytes(b'<types>different</types>\n')))

def late_parent_link(root,s,d):
    real=rt._open_regular
    done=False
    def open_file(path):
        nonlocal done
        if Path(path)==s/'battleye/BEServer_x64.dll' and not done:
            done=True
            (s/'battleye').rename(root/'moved-battleye')
            (s/'battleye').symlink_to(root/'moved-battleye',target_is_directory=True)
        return real(path)
    return mock.patch.object(rt,'_open_regular',side_effect=open_file)
run('battleye parent swapped to symlink just before open',late_parent_link)

def late_destination_link(root,s,d):
    real=rt.new_file;done=False
    def write(path,data):
        nonlocal done
        if Path(path)==d/'battleye/BEServer_x64.dll' and not done:
            done=True
            (root/'redirected').mkdir()
            (d/'battleye').rmdir();(d/'battleye').symlink_to(root/'redirected',target_is_directory=True)
        real(path,data)
    return mock.patch.object(rt,'new_file',side_effect=write)
run('destination battleye changed to symlink before write',late_destination_link)

def corrupt(root,s,d):
    real=rt.new_file
    return mock.patch.object(rt,'new_file',side_effect=lambda path,data:real(path,data+b'CORRUPT'))
run('corrupted write-back',corrupt)
with tempfile.TemporaryDirectory() as td:
    root=Path(td);source=f.make_source_runtime(root/'vanilla');dest=root/'a..b'
    result=p.stage(source,dest,f.classification(),battleye_sha256=f.SYNTH_BE_SHA,_wsl_parent=root)
    print('FULL STAGE a..b: '+result['status']+'; plan_exists='+str((dest/p.PLAN_NAME).is_file()))
with tempfile.TemporaryDirectory() as td:
    root=Path(td);source=f.make_source_runtime(root/'vanilla');dest=root/'taped-light-test'
    try:
        with late_destination_link(root,source,dest):
            p.stage(source,dest,f.classification(),battleye_sha256=f.SYNTH_BE_SHA,_wsl_parent=root)
    except ValueError as e:
        outside=root/'redirected/BEServer_x64.dll'
        print('REDIRECTED WRITE: refused='+str(e)+'; outside_dest_written='+str(outside.exists())+'; outside_bytes='+str(outside.stat().st_size if outside.exists() else None))

def corrupt_mission(root,s,d):
    real=dm._reread_digest
    def corrupt_then_read(path):
        Path(path).write_bytes(Path(path).read_bytes()+b'CORRUPTED')
        return real(path)
    return mock.patch.object(dm,'_reread_digest',side_effect=corrupt_then_read)
run('mission write corrupted before independent reread',corrupt_mission)
with tempfile.TemporaryDirectory() as td:
    root=Path(td);source=f.make_source_runtime(root/'vanilla');dest=root/'mission-dest'
    verified=rt.verify_source(source,f.SYNTH_BE_SHA)
    real=dm._reread_digest;done=False
    def link_before_read(path):
        global done
        if not done:
            done=True
            Path(path).rename(root/'moved-staged.xml')
            Path(path).symlink_to(root/'moved-staged.xml')
        return real(path)
    with mock.patch.object(dm,'_reread_digest',side_effect=link_before_read):
        manifest=dm.prepare_diagnostic_mission(verified['mission'],dest,purpose='taped-light-probe',hook=p.render_hook(p.select_targets(f.classification())),admitted=verified['admitted'],entry_check=rt._check_mission_entry)
    print('STANDALONE ADMITTED MISSION destination symlink before reread: ACCEPTED; symlinks='+repr([x.relative_to(dest).as_posix() for x in dest.rglob('*') if x.is_symlink()])+'; marker_exists='+str((dest/dm.MARKER_NAME).exists()))
