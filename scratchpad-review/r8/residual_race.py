"""Synthetic concurrent rename/replacement; no engine and no external writes."""
import sys,tempfile,shutil,json
from pathlib import Path
from unittest import mock
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'head'));tempfile.tempdir=str(ROOT/'tmp')
from tools.setup import taped_light_probe as p,probe_runtime as rt,diagnostic_mission as dm
from tests.unit import test_taped_light_probe as f
with tempfile.TemporaryDirectory() as td:
 root=Path(td);src=f.make_source_runtime(root/'vanilla');dest=root/'taped-light-test';moved=root/'moved-battleye'
 real_child=dm._open_child_dir;real_new=rt.new_file;state={'writing':False,'done':False}
 def child(fd,name):
  opened=real_child(fd,name)
  if state['writing'] and name=='battleye' and not state['done']:
   state['done']=True;(dest/'battleye').rename(moved);(dest/'battleye').mkdir()
  return opened
 def write(path,data):
  state['writing']=Path(path).name=='BEServer_x64.dll'
  try:real_new(path,data)
  finally:state['writing']=False
  if Path(path).name=='BEServer_x64.dll' and state['done']:
   # A concurrent writer supplies the same bytes at the requested path after the redirected write.
   shutil.copyfile(moved/'BEServer_x64.dll',path)
 try:
  with mock.patch.object(dm,'_open_child_dir',side_effect=child),mock.patch.object(rt,'new_file',side_effect=write):
   plan=p.stage(src,dest,f.classification(),battleye_sha256=f.SYNTH_BE_SHA,_wsl_parent=root)
  outcome=plan['status']
 except Exception as e:outcome=type(e).__name__+': '+str(e)
 print(json.dumps(dict(outcome=outcome,outside_written=(moved/'BEServer_x64.dll').exists(),outside_bytes=(moved/'BEServer_x64.dll').stat().st_size,plan_exists=(dest/p.PLAN_NAME).exists(),symlinks=[str(x.relative_to(dest)) for x in dest.rglob('*') if x.is_symlink()]),sort_keys=True))
