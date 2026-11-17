"""Opt-in, fixed actor-free startup control on an isolated normal server/Wine.

Run with python3 -B -m tools.setup.native_startup_runner --help. No arbitrary
mission, executable, hook, shell command or entity fixture is accepted. Default
total budget 90s; explicit --seconds 15..180, including staging/cleanup/logs.
Native watchdog 60s. SYSTEM callbacks cannot preempt blocked native startup;
keep an external wall-clock supervisor for OS/filesystem stalls. Success is
startup-control ONLY, including ce-disabled-control; never gameplay acceptance.
Final logs, changed evidence, surviving processes or exceeded deadlines revoke
admission. Final cleanup cannot admit receipts that arrived too late.

Report consumers must use read_report(), and require this run's zero exit code.
A .pending sibling makes even success-shaped JSON untrusted. Publication uses
verified staging and a same-directory atomic rename, then final verification
before removing that guard. No fsync/crash durability, engine authentication,
or immunity to later external modification is claimed. An external supervisor
is still required for blocking OS calls, including the final guard removal.
"""
import argparse
import json
import os
import re
from pathlib import Path
import secrets
import shutil
import subprocess
import time

from tools.package import pbo
from tools.setup import native_startup_probe as probe
from tools.setup import wine_compile_probe as wine
from tools.setup.fuel_probe_runner import (
    _Budget, _Expired, _safe, _write, _disabled_settings, WINE,
    CLEANUP_RESERVE_SECONDS,
)

REPORT='native-startup-report.json'
SUCCESS='startup-control-completed'

MAX_REPORT_BYTES = 1024 * 1024
REPORT_PROTOCOL = 'pending-guard-v1'


def read_report(path):
    """Read a published report; status alone is not publication evidence."""
    path = _safe(path)
    guard = path.with_name(path.name + '.pending')
    if guard.exists():
        raise ValueError('report publication incomplete')
    data = probe._read(path, MAX_REPORT_BYTES)
    row = probe._decode_json(data)
    if (guard.exists() or row.get('publication_protocol') != REPORT_PROTOCOL
            or type(row.get('schema')) is not int or row['schema'] != 1
            or type(row.get('run_id')) is not str
            or not re.fullmatch('[0-9a-f]{32}', row['run_id'])):
        raise ValueError('unverified report publication')
    return row


def _publish_report(path, report, budget):
    """Leave the guard on every failure, including an undeletable final file."""
    path = _safe(path)
    guard = path.with_name(path.name + '.pending')
    temporary = path.with_name(path.name + '.tmp')
    if path.exists() or guard.exists() or temporary.exists():
        raise FileExistsError('fresh report publication paths required')
    report['publication_protocol'] = REPORT_PROTOCOL
    payload = probe._encode(report)
    if len(payload) > MAX_REPORT_BYTES:
        raise ValueError('report byte budget exceeded')
    published = False
    try:
        _write(guard, probe._encode(dict(schema=1, run_id=report['run_id'])))
        _write(temporary, payload)
        if probe._read(temporary, MAX_REPORT_BYTES) != payload:
            raise ValueError('staged report readback mismatch')
        if report['status'] == SUCCESS and budget.now() > budget.deadline:
            raise _Expired('report staging exceeded outer deadline')
        os.replace(temporary, path)
        published = True
        if probe._read(path, MAX_REPORT_BYTES) != payload:
            raise ValueError('published report readback mismatch')
        if report['status'] == SUCCESS and budget.now() > budget.deadline:
            raise _Expired('report verification exceeded outer deadline')
        # Last publication operation: failed verification can never remove the
        # guard. A reader checks it both before and after reading report bytes.
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


def _verify_final_inputs(mission, manifest_hash, launch_inputs):
    probe.validate_mission(mission, expected_sha256=manifest_hash)
    for path, limit, digest in launch_inputs:
        if probe._sha(probe._read(path, limit)) != digest:
            raise ValueError('launch input drift: ' + path.name)


def run(server_root,source_pbo,experiment,prefix,scripts_root,*,mode='stock-ce',
        seconds=90,execute=False):
    if execute is not True: raise ValueError('explicit execute=True / --execute required')
    if type(seconds) is not int or not 15<=seconds<=180 or mode not in probe.MODES:
        raise ValueError('fixed mode and explicit total budget 15..180 seconds required')
    budget=_Budget(seconds); run_id=secrets.token_hex(16)
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
    if not prefix.is_dir() or not WINE.is_file() or not shutil.which('xvfb-run'):
        raise ValueError('existing isolated prefix, Wine64 and xvfb-run required')
    report=dict(schema=1,kind='actor-free-native-startup-run',run_id=run_id,mode=mode,
        environment='actual-DayZ-normal-server-under-Wine',runtime_acceptance='pending',
        gameplay_acceptance=False,production_acceptance=False,signature_verified=False,
        client_count=0,owned_entity_count=0,status='not-run',timed_out=False,
        receipt=None,receipt_error=None,outer_budget_seconds=seconds,
        cleanup_reserve_seconds=CLEANUP_RESERVE_SECONDS,
        process_budget_seconds=seconds-CLEANUP_RESERVE_SECONDS,launched=False,
        process_cleanup_confirmed=False,forced_stop=False,cleanup_error=None,
        engine_error_observed=False,initialized_observed=False,receipt_present_final=False,
        requested_gameplay_bind='127.0.0.1:2402',steam_query_may_bind_wildcard=True)
    process=None; admitted=None; owned=False
    profiles=experiment/'profiles'; mission=experiment/'startup.chernarusplus'
    receipt_path=profiles/probe.RESULT
    try:
        budget.check()
        existing=subprocess.run(['pgrep','-f',r'(^|/)DayZ(Server|Diag)_x64\.exe( |$)'],
            capture_output=True,timeout=min(2,budget.process_deadline-budget.now()))
        if existing.returncode!=1: raise ValueError('another native server or process discovery failure')
        budget.check()
        blob=probe._read(source,pbo.MAX_BYTES+21); pbo.parse(blob); budget.check()
        server_hash=probe._sha(probe._read(executable,256*1024*1024)); budget.check()
        be_blob=probe._read(native_be,16*1024*1024); budget.check()
        experiment.mkdir(parents=True,exist_ok=False); owned=True
        for name in ('profiles','storage','battleye','@HollowCountry/addons','profiles/HollowCountry'):
            (experiment/name).mkdir(parents=True,exist_ok=False)
        settings=_disabled_settings(); _write(profiles/'HollowCountry/settings.json',settings)
        _write(experiment/'battleye/BEServer_x64.dll',be_blob)
        addon=experiment/'@HollowCountry/addons/hollowcountry.pbo'; _write(addon,blob)
        config=experiment/'serverDZ.cfg'; config_blob=wine.configuration().encode(); _write(config,config_blob)
        budget.check()
        manifest=probe.prepare_probe(stock,mission,scripts,mode=mode,run_id=run_id)
        if manifest['run_id']!=run_id or manifest['mode']!=mode: raise ValueError('mission correlation mismatch')
        manifest_hash=probe._sha(probe._read(mission/probe.MARKER,probe.MAX_JSON_BYTES))
        report.update(mission=manifest,mission_manifest_sha256=manifest_hash,
            pbo_sha256=probe._sha(blob),server_sha256=server_hash,
            settings_sha256=probe._sha(settings),config_sha256=probe._sha(config_blob),
            battleye_sha256=probe._sha(be_blob))
        launch_inputs = (
            (addon, len(blob), report['pbo_sha256']),
            (config, len(config_blob), report['config_sha256']),
            (profiles/'HollowCountry/settings.json', len(settings), report['settings_sha256']),
            (executable, 256*1024*1024, server_hash),
            (experiment/'battleye/BEServer_x64.dll', len(be_blob), report['battleye_sha256']),
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
            while True:
                budget.check()
                text,_,skipped=wine.collect_logs(profiles); budget.check()
                classified=wine.classify(text)
                report['initialized_observed'] |= classified=='initialized'
                if classified in {'compiler-error','settings-rejected'}:
                    report['status']=classified; report['engine_error_observed']=classified=='compiler-error'; break
                if process.poll() is not None: report['status']='process-exited'; break
                if '[HC Startup Probe] FAIL' in text:
                    report['status']='startup-control-failed'; report['receipt_error']='native FAIL marker'; break
                if receipt_path.exists():
                    try:
                        snapshot=probe._read(receipt_path,probe.MAX_JSON_BYTES)
                        candidate=probe._decode_json(snapshot)
                    except (OSError,ValueError) as exc:
                        report['receipt_error']=str(exc)[:512]; candidate={}
                    budget.check()
                    # Native JsonSerializer emits bool as 0/1, Python fixtures as bool.
                    terminal=any(type(candidate.get(k)) in (bool,int) and candidate[k]==1 for k in ('complete','failed'))
                    if terminal:
                        try:
                            admitted=probe.validate_result(receipt_path,mission,outer_timed_out=False,
                                outer_elapsed_seconds=budget.now()-budget.started,_snapshot=snapshot)
                            if admitted['run_id']!=run_id or admitted['mode']!=mode or admitted['mission_manifest_sha256']!=manifest_hash:
                                raise ValueError('receipt/staged manifest correlation mismatch')
                        except (OSError,ValueError) as exc:
                            admitted=None; report['status']='startup-control-failed'; report['receipt_error']=str(exc)[:512]; break
                        budget.check()
                        if process.poll() is not None: admitted=None; report['status']='process-exited'; break
                        budget.check()  # even the last process poll can cross the deadline
                        if skipped: admitted=None; report['status']='log-collection-incomplete'; break
                        report['receipt']=admitted; report['status']=SUCCESS; break
                time.sleep(min(.25,max(0,budget.process_deadline-budget.now())))
    except _Expired:
        admitted=None; report.update(status='timeout',timed_out=True,receipt=None)
    except Exception as exc:
        admitted=None; report.update(status='probe-error',receipt=None,error=type(exc).__name__+': '+str(exc)[:512])
    finally:
        if process is not None:
            try:
                try: remaining=max(0,budget.deadline-budget.now())
                except ValueError: remaining=0
                report['forced_stop']=wine.stop_group(process,grace=max(0,min(5,remaining-5.5)))
                report['process_cleanup_confirmed']=not wine.group_alive(process.pid) and process.returncode is not None
                if not report['process_cleanup_confirmed']: report['status']='cleanup-incomplete'
            except Exception as exc:
                report['status']='cleanup-failed'; report['cleanup_error']=type(exc).__name__+': '+str(exc)[:512]
        report['launcher_exit_code']=process.returncode if process else None
        if owned:
            try:
                text,report['logs'],report['skipped_logs']=wine.collect_logs(experiment)
                classified=wine.classify(text)
                report['engine_error_observed'] |= classified=='compiler-error'
                report['receipt_present_final']=receipt_path.exists()
                if report['engine_error_observed']: report['status']='compiler-error'
                elif classified=='settings-rejected': report['status']='settings-rejected'
                elif '[HC Startup Probe] FAIL' in text and report['status']==SUCCESS: report['status']='startup-control-failed'
                if admitted is not None and report['status']==SUCCESS:
                    if report['skipped_logs']: report['status']='log-collection-incomplete'
                    elif probe._sha(probe._read(receipt_path,probe.MAX_JSON_BYTES))!=admitted['receipt_sha256']:
                        report['status']='receipt-changed-after-admission'
                    elif probe._sha(probe._read(mission/probe.MARKER,probe.MAX_JSON_BYTES))!=manifest_hash:
                        report['status']='manifest-drift'
                    elif probe._sha(probe._read(profiles/'HollowCountry/settings.json',16384))!=report['settings_sha256']:
                        report['status']='settings-drift'
                    else:
                        try:
                            _verify_final_inputs(mission, manifest_hash, launch_inputs)
                        except (OSError, ValueError) as exc:
                            report['status'] = 'input-drift'
                            report['input_error'] = str(exc)[:512]
            except Exception as exc:
                report['status']='log-collection-error'; report['collection_error']=type(exc).__name__+': '+str(exc)[:512]
        try:
            report['total_elapsed_seconds']=budget.now()-budget.started
            report['outer_budget_exceeded']=report['total_elapsed_seconds']>seconds
        except ValueError as exc:
            report['status']='probe-error'; report['clock_error']=str(exc); report['outer_budget_exceeded']=False
        if report['outer_budget_exceeded']: report.update(status='outer-budget-exceeded',timed_out=True)
        report['receipt_admitted_before_cleanup']=admitted is not None
        if report['status']!=SUCCESS: report['receipt']=None
        if owned:
            report_path=experiment/REPORT
            try:
                _publish_report(report_path, report, budget)
            except _Expired as exc:
                report.update(status='outer-budget-exceeded', timed_out=True,
                    receipt=None, outer_budget_exceeded=True,
                    report_path_untrusted=True, report_error=str(exc)[:512])
            except Exception as exc:
                report.update(status='report-write-error', receipt=None,
                    report_path_untrusted=True,
                    report_error=type(exc).__name__+': '+str(exc)[:512])
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for field in ('server-root','source-pbo','experiment','prefix','scripts-root'):
        parser.add_argument('--'+field,type=Path,required=True)
    parser.add_argument('--mode',choices=probe.MODES,default='stock-ce')
    parser.add_argument('--seconds',type=int,default=90)
    parser.add_argument('--execute',action='store_true')
    report=run(**vars(parser.parse_args(argv)))
    print(json.dumps(report,sort_keys=True,indent=2,allow_nan=False))
    return 0 if report['status']==SUCCESS else 1


if __name__=='__main__': raise SystemExit(main())
