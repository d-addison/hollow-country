"""Fixed-purpose normal-server fuel probe under Wine; launch opt-in REQUIRED.

run(server_root,source_pbo,experiment,prefix,scripts_root,*,x,z,car_class,
vessel_class,rate_ml,cap_ml,fuel_liters,actor_class='SurvivorM_Mirek',seconds=90,
execute=False). Fresh external experiment/profiles/storage/mission only. Existing
isolated Wine prefix may be reused, with no other DayZ server running. This tool
does not build/sign addons or enable production features. All HC settings flags
are explicitly false; only the generated fixture receives the one-shot permit.

The monotonic budget starts before staging, <=180 seconds INCLUDING startup and
observed cleanup/log collection. Default remains 90; longer allowances require
an explicit seconds argument / --seconds. Twelve seconds are reserved for the shared
bounded TERM/KILL/wait helper. A clock/IO/cleanup overrun cannot retain success.
Report consumers must use read_report() and require this run's zero exit code.
A .pending sibling makes even success-shaped JSON untrusted. Publication uses
verified staging, rename and final readback; no fsync/crash durability is claimed.
An external wall-clock supervisor remains required for OS/filesystem stalls that
Python cannot preempt; do not treat a requested timeout as observed completion.

Success requires a receipt admitted while the owned launcher is still live and
BEFORE the process deadline. Actual nonce, staged source hashes, callback count,
replay refusal, exact conservation and observed fixture deletion are checked by
fuel_siphon_probe.validate_result. Initialization alone never succeeds. Final
collection can revoke acceptance but never admit a late receipt. A surviving
process group or cleanup exception also revokes success. Original evidence stays
in the private external experiment. No native Windows/client/durability claim.

TDD: 14 tests initially RED (module absent); tests use synthetic subprocesses,
clocks, declarations and receipts exclusively. No engine is run by development.
An additional actual RED reproduced admission after a slow final process poll
crossed the deadline ('fuel-probe-completed' instead of 'timeout'); recheck the
clock immediately before admission. GREEN command: PYTHONDONTWRITEBYTECODE=1
python3 -m unittest tests.unit.test_fuel_probe_runner -v.
Fresh-directory race regression also failed: finalization wrote into a directory
created by another owner after preflight. Finalize only our successful mkdir.

Startup allowance rationale: normal run 044 initialized at approximately 76s;
043 and 045 exhausted their earlier startup allowances before fixture execution.
045 timed out at 83.028s with no initialization or receipt. An explicit allowance
up to 180s accommodates cold startup alongside the unchanged <=60s native
fixture watchdog, 2s deletion window and 12s process-cleanup reserve. Previous
timeouts remain failures; this does not relax receipt or conservation checks.
"""
import argparse
import json
import math
import os
import re
from pathlib import Path
import secrets
import shutil
import subprocess
import time

from tools.package import pbo
from tools.setup import fuel_siphon_probe as fuel
from tools.setup import wine_compile_probe as wine
from tools.validate.runtime import FLAGS, validate_settings

MAX_OUTER_SECONDS = fuel.MAX_OUTER_SECONDS
CLEANUP_RESERVE_SECONDS = 12
REPORT = 'fuel-probe-report.json'
MAX_REPORT_BYTES = 1024 * 1024
REPORT_PROTOCOL = 'pending-guard-v1'
WINE = Path('/usr/lib/wine/wine64')


class _Expired(Exception):
    pass


class _Budget:
    def __init__(self, seconds):
        self.started=time.monotonic(); self.last=self.started
        self.deadline=self.started+seconds
        self.process_deadline=self.deadline-CLEANUP_RESERVE_SECONDS

    def now(self):
        value=time.monotonic()
        if not math.isfinite(value) or value<self.last:
            raise ValueError('monotonic clock invalid/rolled back')
        self.last=value
        return value

    def check(self):
        if self.now()>=self.process_deadline: raise _Expired('process deadline expired')


def _safe(path):
    return fuel._safe(wine.safe(path))


def _write(path, data):
    _safe(path)
    with path.open('xb') as stream: stream.write(data)
    if fuel._read(path,len(data))!=data: raise ValueError('staged readback mismatch')


def read_report(path):
    """Read a guarded report; consumers must also require this run's zero exit."""
    path = _safe(path)
    guard = path.with_name(path.name + '.pending')
    if guard.exists():
        raise ValueError('report publication incomplete')
    row = fuel._decode_json(fuel._read(path, MAX_REPORT_BYTES))
    if (guard.exists() or row.get('publication_protocol') != REPORT_PROTOCOL
            or row.get('kind') != 'owned-fuel-probe-run'
            or type(row.get('schema')) is not int or row['schema'] != 1
            or type(row.get('run_id')) is not str
            or not re.fullmatch('[0-9a-f]{32}', row['run_id'])):
        raise ValueError('unverified report publication')
    return row


def _publish_report(path, report, budget):
    """Readback/rename protocol, not fsync or crash-durable publication."""
    path = _safe(path)
    guard = path.with_name(path.name + '.pending')
    temporary = path.with_name(path.name + '.tmp')
    if path.exists() or guard.exists() or temporary.exists():
        raise FileExistsError('fresh report publication paths required')
    report['publication_protocol'] = REPORT_PROTOCOL
    payload = fuel._encode(report)
    if len(payload) > MAX_REPORT_BYTES:
        raise ValueError('report byte budget exceeded')
    published = False
    try:
        _write(guard, fuel._encode(dict(schema=1, run_id=report['run_id'])))
        _write(temporary, payload)
        if fuel._read(temporary, MAX_REPORT_BYTES) != payload:
            raise ValueError('staged report readback mismatch')
        if report['status'] == 'fuel-probe-completed' and budget.now() > budget.deadline:
            raise _Expired('report staging exceeded outer deadline')
        os.replace(temporary, path)
        published = True
        if fuel._read(path, MAX_REPORT_BYTES) != payload:
            raise ValueError('published report readback mismatch')
        if report['status'] == 'fuel-probe-completed' and budget.now() > budget.deadline:
            raise _Expired('report verification exceeded outer deadline')
        guard.unlink()
    except Exception:
        if published:
            try:
                path.unlink()
            except OSError:
                pass
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _disabled_settings():
    result=dict(SchemaVersion=1,TickIntervalMs=1000,MaxTickWorkItems=32,
        MaxActiveHordes=2,MaxActiveHordeMembers=24,MaxActiveInteriors=12,MaxPropsPerInterior=5)
    result.update({flag:False for flag in FLAGS})
    if validate_settings(result): raise ValueError('disabled settings contract changed')
    return fuel._encode(result)


def run(server_root, source_pbo, experiment, prefix, scripts_root, *, x, z,
        car_class, vessel_class, rate_ml, cap_ml, fuel_liters,
        actor_class='SurvivorM_Mirek', seconds=90, execute=False):
    if execute is not True: raise ValueError('explicit execute=True / --execute required')
    if type(seconds) is not int or not 15<=seconds<=MAX_OUTER_SECONDS:
        raise ValueError(f'total budget must be integer 15..{MAX_OUTER_SECONDS} seconds')
    budget=_Budget(seconds)
    run_id=secrets.token_hex(16)
    fuel._options(x,z,rate_ml,cap_ml,fuel_liters,car_class,vessel_class,actor_class,seconds,run_id)
    root,source,experiment,prefix,scripts=map(_safe,(server_root,source_pbo,experiment,prefix,scripts_root))
    for other in (root,prefix,scripts):
        if experiment==other or experiment in other.parents or other in experiment.parents:
            raise ValueError('experiment must be disjoint from server/prefix/scripts')
    if experiment.exists(): raise ValueError('fresh experiment required')
    if str(root).startswith('/mnt/'): raise ValueError('isolated Linux filesystem server required')
    executable=root/'DayZServer_x64.exe'
    stock=root/'mpmissions/dayzOffline.chernarusplus'
    native_be=root/'battleye/BEServer_x64.dll'
    if not executable.is_file() or not (stock/'init.c').is_file() or not native_be.is_file():
        raise ValueError('complete isolated normal server required')
    if not WINE.is_file() or not shutil.which('xvfb-run'): raise ValueError('Wine64 and xvfb-run required')
    # No shell, inherited command fragments, arbitrary executable or mission hook.
    report=dict(schema=1,kind='owned-fuel-probe-run',run_id=run_id,
        environment='actual-DayZ-normal-server-under-Wine',runtime_acceptance='pending',
        production_acceptance=False,durable_acceptance=False,signature_verified=False,
        client_count=0,status='not-run',timed_out=False,receipt=None,receipt_error=None,
        outer_budget_seconds=seconds,cleanup_reserve_seconds=CLEANUP_RESERVE_SECONDS,
        process_budget_seconds=seconds-CLEANUP_RESERVE_SECONDS,launched=False,
        process_cleanup_confirmed=False,forced_stop=False,cleanup_error=None,
        engine_error_observed=False,initialized_observed=False,receipt_present_final=False,
        requested_gameplay_bind='127.0.0.1:2402',steam_query_may_bind_wildcard=True)
    process=None; admitted=None; owned_experiment=False; profiles=experiment/'profiles'
    mission=experiment/'fuel.chernarusplus'; receipt_path=profiles/fuel.RESULT
    try:
        budget.check()
        existing=subprocess.run(['pgrep','-f',r'(^|/)DayZ(Server|Diag)_x64\.exe( |$)'],
            capture_output=True,timeout=min(2,budget.process_deadline-budget.now()))
        if existing.returncode!=1:
            raise ValueError('another native server is running or process discovery failed')
        budget.check()
        blob=fuel._read(source,pbo.MAX_BYTES+21); pbo.parse(blob); budget.check()
        server_hash=fuel._sha(fuel._read(executable,256*1024*1024)); budget.check()
        be_blob=fuel._read(native_be,16*1024*1024); budget.check()
        experiment.mkdir(parents=True,exist_ok=False)
        owned_experiment=True
        for name in ('profiles','storage','battleye','@HollowCountry/addons','profiles/HollowCountry'):
            (experiment/name).mkdir(parents=True,exist_ok=False)
        settings=_disabled_settings()
        _write(profiles/'HollowCountry/settings.json',settings)
        _write(experiment/'battleye/BEServer_x64.dll',be_blob)
        addon=experiment/'@HollowCountry/addons/hollowcountry.pbo'; _write(addon,blob)
        config=experiment/'serverDZ.cfg'; _write(config,wine.configuration().encode())
        budget.check()
        manifest=fuel.prepare_probe(stock,mission,scripts,x=x,z=z,rate_ml=rate_ml,
            cap_ml=cap_ml,fuel_liters=fuel_liters,car_class=car_class,vessel_class=vessel_class,
            actor_class=actor_class,outer_timeout_seconds=seconds,run_id=run_id)
        if manifest['run_id']!=run_id: raise ValueError('generated mission nonce mismatch')
        mission_snapshot=wine.snapshot_mission(mission)
        report.update(mission=manifest,pbo_sha256=fuel._sha(blob),server_sha256=server_hash,
            settings_sha256=fuel._sha(settings),config_sha256=fuel._sha(config.read_bytes()))
        launch_inputs=(
            (addon,len(blob),report['pbo_sha256']),
            (config,config.stat().st_size,report['config_sha256']),
            (executable,256*1024*1024,server_hash),
            (experiment/'battleye/BEServer_x64.dll',len(be_blob),fuel._sha(be_blob)),
        )
        command=['xvfb-run','-a',str(WINE),str(executable),'-ip=127.0.0.1','-port=2402',
            '-config='+wine.win(config),'-profiles='+wine.win(profiles),
            '-storage='+wine.win(experiment/'storage'),'-mod='+wine.win(addon.parent.parent),
            '-BEpath='+wine.win(experiment/'battleye'),'-mission='+wine.win(mission),
            '-doLogs','-adminLog','-noPause']
        report['command']=command
        environment=dict(os.environ,WINEPREFIX=str(prefix),WINEARCH='win64',WINEDEBUG='-all')
        budget.check()
        with (experiment/'wine-output.log').open('xb') as output:
            process=subprocess.Popen(command,cwd=root,env=environment,stdout=output,
                stderr=subprocess.STDOUT,start_new_session=True)
            report.update(launched=True,launcher_pid=process.pid,status='waiting-for-receipt')
            budget.check()
            while True:
                budget.check()
                text,_,skipped=wine.collect_logs(profiles)
                budget.check()
                result=wine.classify(text)
                report['initialized_observed'] |= result=='initialized'
                if result in {'compiler-error','settings-rejected'}:
                    report['status']=result
                    report['engine_error_observed']=result=='compiler-error'
                    break
                if process.poll() is not None:
                    report['status']='process-exited'; break
                if '[HC Siphon Probe] FAIL' in text:
                    report['status']='fuel-probe-failed'; report['receipt_error']='native FAIL marker'; break
                if receipt_path.exists():
                    # Partial checkpoints are expected; only complete/failed is terminal.
                    try: candidate=fuel._json(receipt_path)
                    except (OSError,ValueError) as exc:
                        report['receipt_error']=str(exc)[:512]; candidate={}
                    budget.check()
                    terminal=False
                    if candidate:
                        try:
                            failed=fuel._native_bool(candidate.get('failed'))
                            complete=fuel._native_bool(candidate.get('complete'))
                            terminal=failed or complete
                        except ValueError as exc:
                            report['status']='fuel-probe-failed'; report['receipt_error']=str(exc)[:512]; break
                    if terminal:
                        try:
                            admitted=fuel.validate_result(receipt_path,mission,outer_timed_out=False,
                                outer_elapsed_seconds=budget.now()-budget.started)
                            if admitted['run_id']!=run_id: raise ValueError('receipt nonce mismatch')
                        except (OSError,ValueError) as exc:
                            report['status']='fuel-probe-failed'; report['receipt_error']=str(exc)[:512]; break
                        budget.check()
                        if process.poll() is not None:
                            admitted=None; report['status']='process-exited'; break
                        budget.check()
                        if skipped:
                            admitted=None; report['status']='log-collection-incomplete'; break
                        report['receipt']=admitted; report['status']='fuel-probe-completed'; break
                time.sleep(min(0.25,max(0,budget.process_deadline-budget.now())))
    except _Expired:
        admitted=None; report.update(status='timeout',timed_out=True,receipt=None)
    except Exception as exc:
        admitted=None; report.update(status='probe-error',receipt=None,error=type(exc).__name__+': '+str(exc)[:512])
    finally:
        # Cleanup is attempted even after launch/poll/I/O errors or expiry.
        if process is not None:
            try:
                try: remaining=max(0,budget.deadline-budget.now())
                except ValueError: remaining=0
                report['forced_stop']=wine.stop_group(process,grace=max(0,min(5,remaining-5.5)))
                report['process_cleanup_confirmed']=not wine.group_alive(process.pid) and process.returncode is not None
                if not report['process_cleanup_confirmed']: report['status']='cleanup-incomplete'
            except Exception as exc:
                report['status']='cleanup-failed'
                report['cleanup_error']=type(exc).__name__+': '+str(exc)[:512]
        report['launcher_exit_code']=process.returncode if process else None
        if owned_experiment:
            try:
                text,report['logs'],report['skipped_logs']=wine.collect_logs(experiment)
                final_result=wine.classify(text)
                report['engine_error_observed'] |= final_result=='compiler-error'
                report['receipt_present_final']=receipt_path.exists()
                report['late_complete_marker_observed']=admitted is None and '[HC Siphon Probe] COMPLETE' in text
                if report['engine_error_observed']: report['status']='compiler-error'
                elif final_result=='settings-rejected': report['status']='settings-rejected'
                elif '[HC Siphon Probe] FAIL' in text and report['status']=='fuel-probe-completed':
                    report['status']='fuel-probe-failed'
                if admitted is not None and report['status']=='fuel-probe-completed':
                    if report['skipped_logs']: report['status']='log-collection-incomplete'
                    elif fuel._sha(fuel._read(receipt_path,256*1024))!=admitted['receipt_sha256']:
                        report['status']='receipt-changed-after-admission'
                    elif fuel._sha(fuel._read(profiles/'HollowCountry/settings.json',16384))!=report['settings_sha256']:
                        report['status']='settings-drift'
                    else:
                        try:
                            wine.verify_final_inputs(mission,mission_snapshot,launch_inputs)
                        except (OSError,ValueError) as exc:
                            report['status']='input-drift'
                            report['input_error']=str(exc)[:512]
            except Exception as exc:
                report['status']='log-collection-error'
                report['collection_error']=type(exc).__name__+': '+str(exc)[:512]
        try:
            report['total_elapsed_seconds']=budget.now()-budget.started
            report['outer_budget_exceeded']=report['total_elapsed_seconds']>seconds
        except ValueError as exc:
            report['status']='probe-error'; report['clock_error']=str(exc)
            report['outer_budget_exceeded']=False
        if report['outer_budget_exceeded']:
            report.update(status='outer-budget-exceeded',timed_out=True)
        report['receipt_admitted_before_cleanup']=admitted is not None
        if report['status']!='fuel-probe-completed': report['receipt']=None
        if owned_experiment:
            report_path=experiment/REPORT
            try:
                _publish_report(report_path,report,budget)
            except _Expired as exc:
                report.update(status='outer-budget-exceeded',timed_out=True,receipt=None,
                    outer_budget_exceeded=True,total_elapsed_seconds=budget.now()-budget.started,
                    report_path_untrusted=True,report_error=str(exc)[:512])
            except Exception as exc:
                report.update(status='report-write-error',receipt=None,report_path_untrusted=True,
                    report_error=type(exc).__name__+': '+str(exc)[:512])
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for field in ('server-root','source-pbo','experiment','prefix','scripts-root'):
        parser.add_argument('--'+field,type=Path,required=True)
    for field in ('x','z','rate-ml','cap-ml','fuel-liters'):
        parser.add_argument('--'+field,type=float,required=True)
    for field in ('car-class','vessel-class'): parser.add_argument('--'+field,required=True)
    parser.add_argument('--actor-class',default='SurvivorM_Mirek')
    parser.add_argument('--seconds',type=int,default=90)
    parser.add_argument('--execute',action='store_true',help='explicitly authorize the one fixed native experiment')
    args=vars(parser.parse_args(argv))
    report=run(**args)
    print(json.dumps(report,sort_keys=True,indent=2,allow_nan=False))
    return 0 if report['status']=='fuel-probe-completed' else 1


if __name__=='__main__': raise SystemExit(main())
