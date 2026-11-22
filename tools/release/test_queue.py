"""Local test-service queue for worker commits: preland, Workbench compile and the Wine compile gate.

The queue runs on the lead host. It tests only pinned commits, in clean detached worktrees, one
native job at a time under the shared host lock, and holds (never fails) while the owner's DayZ
client runs or another native tool owns the host. It never stops or kills any game process.
"""
import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from tools.release.host_lock import LockRefused, host_lock

ROOT = Path(__file__).resolve().parents[2]
CHECKS = ('preland', 'wb', 'gate')
MEMORY = {'preland': '3G', 'wb': '3G', 'gate': '12G'}
TIMEOUT = {'preland': 1800, 'wb': 1200, 'gate': 2700}
FINAL = ('passed', 'failed', 'oom')
OOM_CODES = (137, -9)
CLIENT_IMAGE = 'DayZ_x64.exe'
WORKTREES = Path('/code/hc-worktrees')
CALIBRATION_DOC = 'docs/tools/WORKBENCH_COMPILE.md'
CALIBRATED = (14, 14)
SHA = re.compile(r'[0-9a-f]{40}')


class Refused(ValueError):
    """Authored, path-free diagnostic."""


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def git(*arguments, cwd=None):
    return subprocess.run(['git', *arguments], cwd=cwd or ROOT, capture_output=True, text=True,
                          errors='replace', timeout=120)


def submit_line(root=None, sha=None):
    """The exact command a worker (or a needs-host-check gate) prints for the lead host."""
    if sha is None:
        try:
            result = git('rev-parse', 'HEAD', cwd=root)
            sha = result.stdout.strip() if result.returncode == 0 else ''
        except (OSError, subprocess.SubprocessError):
            sha = ''
    sha = sha if SHA.fullmatch(sha or '') else '<full commit sha>'
    return 'python3 -B -m tools.release.test_queue submit --commit %s --checks preland,wb,gate' % sha


def queue_dir():
    """Shared by every linked worktree: the main checkout's git-ignored .hc-queue."""
    if os.environ.get('HC_QUEUE_DIR'):
        return Path(os.environ['HC_QUEUE_DIR'])
    result = git('rev-parse', '--path-format=absolute', '--git-common-dir')
    if result.returncode:
        raise Refused('not inside a git checkout')
    return Path(result.stdout.strip()).parent / '.hc-queue'


def worktree_root():
    return Path(os.environ.get('HC_QUEUE_WORKTREES') or WORKTREES)


def client_state():
    """running / gone / unknown for the owner's client, via the repo's winproc query."""
    result = subprocess.run([sys.executable, '-B', '-m', 'tools.setup.winproc', 'query', CLIENT_IMAGE],
                            cwd=ROOT, capture_output=True, text=True, errors='replace', timeout=180)
    return {0: 'running', 1: 'gone'}.get(result.returncode, 'unknown')


def calibration():
    """(agreed, total) from the 'Calibration status: N/M' line of the Workbench doc, or None."""
    try:
        text = (ROOT / CALIBRATION_DOC).read_text(encoding='utf-8')
    except OSError:
        return None
    found = re.search(r'^Calibration status:\s*(\d+)\s*/\s*(\d+)', text, re.M)
    return (int(found[1]), int(found[2])) if found else None


def wb_calibrated():
    return calibration() == CALIBRATED


def run_command(argv, cwd, log_path, timeout):
    """Run one check with its output in a local log; return its exit code (124 on timeout)."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open('w', encoding='utf-8', errors='replace') as log:
        try:
            return subprocess.run(argv, cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
                                  timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            log.write('\ntest_queue: timeout after %d s\n' % timeout)
            return 124


def check_command(check, worktree, job):
    memory = MEMORY[check]
    if check == 'preland':
        inner = [sys.executable, '-B', '-m', 'tools.validate.preland', '--changed', job['base_sha']]
    elif check == 'wb':
        inner = [sys.executable, '-B', '-m', 'tools.release.wb_compile', '--tree', str(worktree),
                 '--commit', job['sha']]
    else:
        inner = [sys.executable, '-B', '-m', 'tools.release.compile_gate', '--tree', str(worktree)]
    return [os.environ.get('HC_AGENT_RUN', 'agent-run'), '--memory', memory, '--'] + inner


# ---- job store: one atomically replaced JSON file per job -------------------------------------

class Store:
    def __init__(self, directory):
        self.root = Path(directory)
        self.jobs = self.root / 'jobs'
        self.logs = self.root / 'logs'

    def path(self, job_id):
        return self.jobs / (job_id + '.json')

    def save(self, job):
        self.jobs.mkdir(parents=True, exist_ok=True)
        temporary = self.path(job['id']).with_suffix('.tmp')
        temporary.write_text(json.dumps(job, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        os.replace(temporary, self.path(job['id']))

    def create(self, job):
        self.jobs.mkdir(parents=True, exist_ok=True)
        with open(self.path(job['id']), 'x', encoding='utf-8') as handle:
            handle.write(json.dumps(job, indent=2, sort_keys=True) + '\n')

    def load(self, job_id):
        return json.loads(self.path(job_id).read_text(encoding='utf-8'))

    def all(self):
        if not self.jobs.is_dir():
            return []
        jobs = []
        for path in sorted(self.jobs.glob('*.json')):
            try:
                jobs.append(json.loads(path.read_text(encoding='utf-8')))
            except (OSError, ValueError):
                continue
        return jobs


def pending_checks(job):
    """Checks without a final result; a held record never counts as done."""
    last = {}
    for result in job['results']:
        last[result['check']] = result['status']
    return [check for check in job['checks'] if last.get(check) not in ('pass', 'fail', 'oom')]


def is_advisory(check):
    return check == 'wb' and not wb_calibrated()


# ---- commands -----------------------------------------------------------------------------

def submit(store, args):
    if not SHA.fullmatch(args.commit):
        raise Refused('--commit must be a full lowercase 40-character sha')
    checks = [c for c in CHECKS if c in {part.strip() for part in args.checks.split(',') if part.strip()}]
    unknown = {part.strip() for part in args.checks.split(',') if part.strip()} - set(CHECKS)
    if unknown or not checks:
        raise Refused('--checks takes a comma list of: ' + ', '.join(CHECKS))
    resolved = git('rev-parse', '--verify', '--end-of-options', args.commit + '^{commit}')
    if resolved.returncode or resolved.stdout.strip() != args.commit:
        raise Refused('commit does not exist in this repository')
    base = git('rev-parse', '--verify', '--end-of-options', args.base + '^{commit}')
    if base.returncode:
        raise Refused('base revision does not resolve; fetch it or pass --base')
    dirty = git('status', '--porcelain', '--untracked-files=no')
    if dirty.returncode or dirty.stdout.strip():
        raise Refused('this checkout has uncommitted tracked changes; commit first, the queue tests the pinned commit only')
    notes = []
    if 'gate' in checks and wb_calibrated() and not (args.wave or args.release):
        checks.remove('gate')
        notes.append('Wine gate dropped: wb_compile is calibrated 14/14, so the gate runs once per wave or release'
                     ' (resubmit with --wave or --release)')
    if not checks:
        raise Refused('no checks left to run')
    for job in store.all():
        if job['sha'] == args.commit and job['checks'] == checks and job['status'] not in FINAL:
            print('already queued id=%s' % job['id'])
            return 0
    stamp = time.strftime('%Y%m%dT%H%M%S', time.gmtime())
    micros = time.time_ns() // 1000 % 10 ** 6
    job = {'id': '%s%06d-%s' % (stamp, micros, args.commit[:8]), 'sha': args.commit,
           'base': args.base, 'base_sha': base.stdout.strip(), 'checks': checks, 'status': 'queued',
           'submitted': now(), 'results': [], 'notes': notes}
    store.create(job)
    for note in notes:
        print('note: ' + note)
    print('queued id=%s sha=%s checks=%s' % (job['id'], job['sha'][:8], ','.join(checks)))
    return 0


def add_result(job, check, rc, status, log, started, note='', advisory=False):
    job['results'].append({'sha': job['sha'], 'check': check, 'rc': rc, 'status': status, 'log': log,
                           'started': started, 'finished': now(), 'advisory': advisory, 'note': note})


def make_worktree(sha):
    """Clean detached worktree at the pinned sha; an existing one is reused only if clean and pinned."""
    path = worktree_root() / ('queue-' + sha[:8])
    if path.exists():
        head = git('rev-parse', 'HEAD', cwd=path)
        status = git('status', '--porcelain', '--untracked-files=all', cwd=path)
        if head.returncode or head.stdout.strip() != sha or status.returncode or status.stdout.strip():
            raise Refused('queue worktree exists and is dirty or not at the pinned commit; refused, remove it by hand')
        return path
    created = git('worktree', 'add', '--detach', str(path), sha)
    if created.returncode:
        raise Refused('git worktree add failed')
    head = git('rev-parse', 'HEAD', cwd=path)
    if head.returncode or head.stdout.strip() != sha:
        raise Refused('new worktree is not at the pinned commit')
    return path


def remove_worktree(path, job):
    """Never forced: a worktree that will not remove cleanly is kept and recorded."""
    removed = git('worktree', 'remove', str(path))
    if removed.returncode:
        job['worktree_kept'] = 'git worktree remove refused (needs force); kept as queue-' + job['sha'][:8]
    else:
        job.pop('worktree_kept', None)


def hold(store, job, reason):
    job['status'] = 'held'
    job['held_reason'] = reason
    job['held_at'] = now()
    store.save(job)
    print('held id=%s reason=%s' % (job['id'], reason))
    return 0


def process(store, job):
    worktree = None
    job['status'] = 'running'
    job.pop('held_reason', None)
    store.save(job)
    try:
        for check in pending_checks(job):
            state = client_state()
            if state != 'gone':
                return hold(store, job, 'owner client state=' + state)
            if worktree is None:
                try:
                    worktree = make_worktree(job['sha'])
                except Refused as error:
                    add_result(job, 'worktree', None, 'fail', '', now(), str(error))
                    job['status'] = 'failed'
                    store.save(job)
                    print('failed id=%s check=worktree note=%s' % (job['id'], error))
                    return 1
            started = now()
            log = store.logs / (job['id'] + '-' + check + '.log')
            advisory = is_advisory(check)
            rc = run_command(check_command(check, worktree, job), worktree, log, TIMEOUT[check])
            note = ''
            if rc in OOM_CODES:
                status, note = 'oom', 'killed at the %s memory cap; not retried, narrow the input' % MEMORY[check]
            elif rc == 124:
                status, note = 'fail', 'timeout'
            else:
                status = 'pass' if rc == 0 else 'fail'
            if advisory:
                note = (note + '; ' if note else '') + 'advisory: wb_compile is not calibrated 14/14 against the Wine gate'
            add_result(job, check, rc, status, str(log), started, note, advisory)
            store.save(job)
            print('%s id=%s check=%s rc=%s%s' % (status, job['id'], check, rc, ' (advisory)' if advisory else ''))
            if status in ('fail', 'oom') and not advisory:
                job['status'] = 'oom' if status == 'oom' else 'failed'
                store.save(job)
                return 1
        job['status'] = 'passed'
        job['finished'] = now()
        store.save(job)
        print('passed id=%s' % job['id'])
        return 0
    finally:
        if worktree is not None:
            remove_worktree(worktree, job)
            store.save(job)


def run_next(store, args=None):
    job = next((j for j in store.all() if j['status'] in ('queued', 'held', 'running')), None)
    if job is None:
        print('queue empty')
        return 0
    with ExitStack() as stack:
        try:
            stack.enter_context(host_lock('test_queue'))
        except LockRefused as error:
            current = store.load(job['id'])
            if current['status'] in ('queued', 'held'):
                return hold(store, current, str(error))
            print('running id=%s (another run-next owns it)' % job['id'])
            return 0
        # Holding the host lock means no live runner exists: a stored 'running' job is stale.
        current = store.load(job['id'])
        if current['status'] not in ('queued', 'held', 'running'):
            return 0
        return process(store, current)


def line(job):
    return '%s sha=%s status=%s checks=%s%s' % (
        job['id'], job['sha'][:8], job['status'], ','.join(job['checks']),
        (' held=' + job['held_reason']) if job['status'] == 'held' and job.get('held_reason') else '')


def show_status(store, args):
    jobs = store.all()
    if args.job:
        match = [j for j in jobs if j['id'] == args.job or j['id'].endswith(args.job)]
        if not match:
            raise Refused('no such job')
        print(json.dumps(match[0], indent=2, sort_keys=True))
        return 0
    counts = {}
    for job in jobs:
        counts[job['status']] = counts.get(job['status'], 0) + 1
    cal = calibration()
    if args.json:
        print(json.dumps({'counts': counts, 'wb_calibration': cal, 'wb_advisory': not wb_calibrated()}, sort_keys=True))
        return 0
    print('jobs: ' + (', '.join('%s=%d' % item for item in sorted(counts.items())) or 'none'))
    print('wb_compile: ' + ('calibrated %d/%d; Wine gate once per wave/release' % cal if wb_calibrated()
                            else 'advisory (calibration %s)' % ('%d/%d' % cal if cal else 'unrecorded')))
    for job in jobs:
        if job['status'] not in FINAL:
            print(line(job))
        if job.get('worktree_kept'):
            print('worktree kept: ' + job['id'] + ' ' + job['worktree_kept'])
    return 0


def list_jobs(store, args):
    jobs = store.all()
    if args.json:
        print(json.dumps(jobs, indent=2, sort_keys=True))
        return 0
    for job in jobs:
        print(line(job))
        for result in job['results']:
            print('  %s rc=%s %s%s log=%s' % (result['check'], result['rc'], result['status'],
                                              ' (advisory)' if result.get('advisory') else '',
                                              Path(result['log']).name if result['log'] else '-'))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    sub = commands.add_parser('submit', help='queue a pinned commit')
    sub.add_argument('--commit', required=True, help='full 40-character sha')
    sub.add_argument('--checks', default=','.join(CHECKS), help='comma list of preland,wb,gate')
    sub.add_argument('--base', default='origin/dev', help='diff base for preland --changed')
    sub.add_argument('--wave', action='store_true', help='integration wave: run the Wine gate even once wb is calibrated')
    sub.add_argument('--release', action='store_true', help='release: run the Wine gate even once wb is calibrated')
    commands.add_parser('run-next', help='run the oldest queued or held job (lead host only)')
    stat = commands.add_parser('status', help='queue summary, or one job by id')
    stat.add_argument('job', nargs='?')
    stat.add_argument('--json', action='store_true')
    lst = commands.add_parser('list', help='every job with its results')
    lst.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    try:
        store = Store(queue_dir())
        handler = {'submit': submit, 'run-next': run_next, 'status': show_status, 'list': list_jobs}[args.command]
        return handler(store, args)
    except Refused as error:
        print('test_queue: refused: ' + str(error))
        return 2
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        print('test_queue: failed (%s)' % type(error).__name__)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
