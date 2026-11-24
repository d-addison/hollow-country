"""Lead-only stock RPT acquisition and offline R3 ceiling proposals.

plan is read-only. stage/run/restore require the shared Windows host lease.
No downloads, mod arguments, security overrides, live profile edits or forced stops.
Only numeric classified category rows are printed or included in proposals.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import time
import uuid

from tools.audit import rpt_config_audit
from tools.release.host_lock import LockRefused, host_lock
from tools.setup.winproc import InteropError
from tools.testing import soak_campaign as soak

ROOT = Path(__file__).resolve().parents[2]
MISSION = 'mpmissions/dayzOffline.chernarusplus'
BACKUPS = 'hollow-country-install-backups'
# Inspected 2026-11-24: earliest pre-install journal, independently repeated by
# the next completed install. friend_install.inventory_digest(tree_inventory()).
STOCK_PIN = '4b66a2fb268b9890d23f2e2d60a829690fb504719d965586d1208dcd92cf53c9'
IMAGES = ('DayZ_x64.exe', 'DayZServer_x64.exe', 'DayZDiag_x64.exe', 'DayZ_BE.exe')
STAMP = re.compile(r'^\s*(\d{1,2}):(\d{2}):(\d{2})(?:[.,](\d+))?\s')
# tasklist through WSL interop sometimes returns no answer (state 'unknown').
# 2026-11-24: one unknown read aborted a 125-minute capture three minutes in,
# and the interop error in the stop that followed left the server running.
STATE_UNKNOWN_LIMIT = 6
STOP_ATTEMPTS = 3
STOP_SETTLE_SECONDS = 20


class Refused(ValueError):
    """Fixed vocabulary only: never include input text or underlying exceptions."""


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Refused('invalid arguments; use --help')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def plain(path):
    """Reject symlinks at every ancestor, including Windows junction-like escapes."""
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)) or path.resolve() != path:
        raise Refused('linked or redirected path refused')
    return path


def inventory(root):
    """Exact installer inventory encoding; persistence is never source material."""
    plain(root)
    rows = {'': 'dir'}
    for p in sorted(root.rglob('*')):
        plain(p)
        rel = p.relative_to(root)
        if any(x.casefold().startswith(('storage_', 'hollow-country')) for x in rel.parts):
            raise Refused('stock source contains persistence or HC folders')
        if p.is_dir():
            if rel.as_posix() not in ('db', 'env'):
                raise Refused('stock source has an unrecognized directory')
            rows[rel.as_posix()] = 'dir'
        elif p.is_file() and re.fullmatch(r'(?:(?:db|env)/)?[A-Za-z0-9_.-]+\.(?:xml|json|map|c)', rel.as_posix()):
            rows[rel.as_posix()] = digest(p)
        else:
            raise Refused('stock source has an unrecognized entry')
    return rows


def tree_digest(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()


def stock_source(server):
    from tools.setup import friend_install
    receipt = plain(server / friend_install.RECEIPT)
    if not receipt.is_file():
        raise Refused('stock proof unavailable: install receipt missing')
    try:
        friend_install.validate_receipt(json.loads(receipt.read_text(encoding='utf-8')))
    except Exception:
        raise Refused('stock proof unavailable: install receipt invalid') from None
    parent = plain(server / BACKUPS)
    if not parent.is_dir():
        raise Refused('stock proof unavailable: install backups missing')
    examined = 0
    for run in sorted(parent.iterdir()):
        plain(run)
        journal = plain(run / 'run-journal.json')
        if not journal.is_file():
            continue
        data = json.loads(journal.read_text(encoding='utf-8'))
        if data.get('schema') != 1 or data.get('state') not in ('complete', 'rolled-back'):
            continue
        for row in data.get('entries', []):
            if row.get('path') != MISSION or row.get('kind') != 'tree':
                continue
            examined += 1
            if row.get('sha256') != STOCK_PIN:
                continue
            source = plain(run / MISSION)
            rows = inventory(source)
            if tree_digest(rows) != STOCK_PIN:
                raise Refused('stock proof failed: pinned pre-install backup changed')
            required = ('init.c', 'cfgeconomycore.xml', 'cfggameplay.json', 'mapgrouppos.xml',
                        'db/types.xml', 'db/events.xml', 'cfgeventgroups.xml', 'cfgeventspawns.xml')
            if any(name not in rows for name in required):
                raise Refused('stock proof failed: required pre-install bytes missing')
            if re.search(r'hollow|\bHC\w*|#include', (source / 'init.c').read_text(encoding='utf-8'), re.I):
                raise Refused('stock proof failed: init hooks present')
            # Do not expose arbitrary backup names, even if a receipt was renamed.
            if not re.fullmatch(r'\d{8}T\d{6}Z-[a-z0-9_]+', run.name):
                raise Refused('stock proof failed: unexpected backup label')
            return source, rows, BACKUPS + '/' + run.name + '/' + MISSION
    raise Refused('no provable stock source: no matching pinned pre-install tree (%d examined); '
                  'repository vanilla-row checks are not whole-mission proof' % examined)


def targets():
    return json.loads((ROOT / 'config/acceptance-targets.json').read_text(encoding='utf-8'))


def minimum_minutes():
    return max(30, targets()['soak_minutes'], soak.load_phases()['min_idle_minutes'])


def stopped(host):
    if any(host.state(image) != 'gone' for image in IMAGES):
        raise Refused('host busy or process state unknown; all DayZ images must be stopped')


def graceful_stop(host):
    """Graceful close only, retried across interop losses; verified by a gone read."""
    for attempt in range(STOP_ATTEMPTS):
        if host.state(soak.SERVER_IMAGE) == 'gone':
            break
        try:
            host.stop(soak.SERVER_IMAGE)
        except (Refused, soak.Refused, InteropError):
            # The close may still be saving the world; re-read before asking again.
            host.sleep(STOP_SETTLE_SECONDS)
    else:
        if host.state(soak.SERVER_IMAGE) != 'gone':
            raise Refused('graceful stock server stop could not be verified; close it by hand, then run restore')
    stopped(host)


def uncomment(text):
    return re.sub(r'/\*.*?\*/|//[^\r\n]*', '', text, flags=re.S)


def config_copy(raw, template, port):
    text = raw.decode('utf-8-sig')
    active = uncomment(text)
    # Absent BattlEye uses the engine default (enabled); never insert a bypass.
    for key, expected in (('verifySignatures', '2'), ('BattlEye', '1')):
        values = re.findall(r'\b' + key + r'\s*=\s*(\d+)\s*;', active, re.I)
        if (key == 'verifySignatures' and values != [expected]) or any(v != expected for v in values):
            raise Refused('security settings unavailable or disabled; stock boot refused')
    pattern = r'\btemplate\s*=\s*"dayzOffline\.chernarusplus"\s*;'
    if len(re.findall(r'\btemplate\s*=', active, re.I)) != 1 or not re.search(pattern, active, re.I):
        raise Refused('expected one stock Chernarus mission template')
    # Replace only the active assignment (not a lookalike inside a comment).
    masked = re.sub(r'/\*.*?\*/|//[^\r\n]*', lambda m: ' ' * len(m[0]), text, flags=re.S)
    match = re.search(pattern, masked, re.I)
    text = text[:match.start()] + 'template="' + template + '";' + text[match.end():]
    masked = re.sub(r'/\*.*?\*/|//[^\r\n]*', lambda m: ' ' * len(m[0]), text, flags=re.S)
    ports = list(re.finditer(r'\bport\s*=\s*\d+\s*;', masked, re.I))
    live_port = int(ports[0][0].split('=')[1].strip(' ;')) if ports else 2302
    if port == live_port:
        raise Refused('scratch port must differ from the live server port')
    if len(ports) > 1:
        raise Refused('ambiguous server port')
    if ports:
        m = ports[0]
        text = text[:m.start()] + 'port=%d;' % port + text[m.end():]
    else:
        text += '\r\nport=%d;\r\n' % port
    return text.encode('utf-8-sig' if raw.startswith(b'\xef\xbb\xbf') else 'utf-8')


class Stage:
    def __init__(self, server):
        self.server = plain(server)
        self.base = plain(server.parent / 'stock-capture')
        self.receipt = plain(self.base / 'active.json')

    def load(self):
        if not self.receipt.exists():
            return None
        data = json.loads(self.receipt.read_text(encoding='utf-8'))
        if (data.get('schema') != 1 or not re.fullmatch(r'[0-9a-f]{32}', data.get('token', ''))
                or data.get('server') != str(self.server)):
            raise Refused('invalid staging receipt')
        return data

    def paths(self, data):
        token = data['token']
        template = 'stock_capture_' + token + '.chernarusplus'
        return plain(self.base / token), plain(self.server / 'mpmissions' / template), template

    def save(self, data):
        tmp = plain(self.base / 'active.tmp')
        tmp.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
        tmp.replace(self.receipt)

    def stage(self, port):
        if self.load() is not None:
            raise Refused('already staged; restore first')
        source, rows, label = stock_source(self.server)
        data = dict(schema=1, token=uuid.uuid4().hex, server=str(self.server), port=port,
                    source=label, stock_sha256=tree_digest(rows), ready=False, attempted=False)
        work, mission, template = self.paths(data)
        cfg = config_copy(plain(self.server / 'serverDZ.cfg').read_bytes(), template, port)
        if work.exists() or mission.exists():
            raise Refused('scratch destination exists')
        self.base.mkdir(exist_ok=True)
        self.save(data)  # write-ahead ownership, including partial copy failures
        work.mkdir()
        (work / 'profiles').mkdir()
        shutil.copytree(source, work / 'mission')
        if inventory(work / 'mission') != rows:
            raise Refused('source changed during staging')
        shutil.copytree(work / 'mission', mission)
        if inventory(mission) != rows:
            raise Refused('mission copy verification failed')
        (work / 'serverDZ.cfg').write_bytes(cfg)
        data.update(ready=True, config_sha256=digest(work / 'serverDZ.cfg'))
        self.save(data)

    def restore(self):
        data = self.load()
        if data is None:
            print('restore: nothing staged')
            return
        work, mission, _ = self.paths(data)
        # Inspect the entire deletion set first; never follow a redirected receipt path.
        for root in (work, mission):
            if root.exists():
                plain(root)
                for path in root.rglob('*'):
                    plain(path)
        for root in (mission, work):
            if root.exists():
                shutil.rmtree(root)
        self.receipt.unlink()
        print('restore: removed receipted scratch mission and profiles; captures retained')

    def run(self, host, minutes):
        data = self.load()
        if not data or not data['ready'] or data['attempted']:
            raise Refused('run needs a fresh completed stage')
        work, mission, _ = self.paths(data)
        plain(work / 'profiles')
        if (tree_digest(inventory(mission)) != STOCK_PIN or
                digest(plain(work / 'serverDZ.cfg')) != data['config_sha256'] or
                any((work / 'profiles').iterdir())):
            raise Refused('staged inputs changed')
        executable = plain(self.server / soak.SERVER_IMAGE)
        if not executable.is_file():
            raise Refused('stock server executable unavailable')
        arguments = ['-mission=' + soak.default_win(mission),
                     '-config=' + soak.default_win(work / 'serverDZ.cfg'),
                     '-profiles=' + soak.default_win(work / 'profiles'),
                     '-port=%d' % data['port'], '-doLogs', '-adminLog']
        # Match probe_runtime's absolute -mission/-config/-profiles arguments.
        # The copied config template names that same unique mpmissions tree;
        # cached native GetMissionPath is the path supplied by the engine.
        script = ("$ErrorActionPreference='Stop'; Start-Process -FilePath " + soak.ps_quote(soak.default_win(executable))
                  + ' -WorkingDirectory ' + soak.ps_quote(soak.default_win(self.server))
                  + ' -ArgumentList ' + ','.join(soak.ps_arg(a) for a in arguments)
                  + "; Write-Output 'HC launch acknowledged'")
        data['attempted'] = True
        self.save(data)
        try:
            host.launch(script, (soak.SERVER_IMAGE,), 'stock server')
            if not host.started((soak.SERVER_IMAGE,), 'stock server'):
                raise Refused('stock server did not boot; no security bypass will be attempted')
            deadline = time.monotonic() + minutes * 60
            unknown = 0
            while time.monotonic() < deadline:
                state = host.state(soak.SERVER_IMAGE)
                if state == 'gone':
                    raise Refused('stock server stopped; capture incomplete')
                if state == 'running':
                    unknown = 0
                else:
                    # Only a sustained unknown (about 3 minutes) ends the capture.
                    unknown += 1
                    if unknown >= STATE_UNKNOWN_LIMIT:
                        raise Refused('stock server state unknown for %d reads; capture incomplete' % unknown)
                time.sleep(min(30, max(0, deadline - time.monotonic())))
        finally:
            # A lost launch reply can still mean a process started. Always request
            # graceful close; never kill, restore or copy logs under a live server.
            graceful_stop(host)
        logs = sorted((work / 'profiles').glob('*.RPT'))
        if len(logs) != 1:
            raise Refused('expected exactly one stock RPT')
        plain(logs[0])
        validate_duration(logs[0], minutes)
        captures = plain(self.base / 'captures')
        captures.mkdir(exist_ok=True)
        output = plain(captures / ('stock-' + data['token'] + '.RPT'))
        with output.open('xb') as stream:
            stream.write(logs[0].read_bytes())
        metadata = dict(schema=1, minutes=minutes, rpt_sha256=digest(output),
                        stock_sha256=STOCK_PIN, graceful_stop=True)
        output.with_suffix('.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
        print('run: stock RPT=stock-capture/captures/stock-%s.RPT minutes=%d; duration receipt saved' % (
            data['token'], minutes))


def validate_duration(path, minutes):
    """Bounded timestamp scan; midnight supported, multiple boots refused."""
    first = last = None
    day = 0
    connected = boots = 0
    with path.open(encoding='utf-8-sig', errors='replace') as stream:
        while True:
            line = stream.readline(rpt_config_audit.MAX_LINE + 1)
            if not line:
                break
            if len(line) > rpt_config_audit.MAX_LINE:
                raise Refused('duration unavailable: oversized RPT line')
            connected += 'Player connect enabled' in line
            boots += bool(re.search(r'\bHost instance created\b', line))
            match = STAMP.match(line)
            if not match:
                continue
            h, m, s = map(int, match.group(1, 2, 3))
            if h > 23 or m > 59 or s > 59:
                raise Refused('invalid RPT timestamp')
            now = h * 3600 + m * 60 + s + day
            if last is not None and now < last:
                if last - now < 12 * 3600:
                    raise Refused('non-monotonic RPT timestamps')
                day += 86400
                now += 86400
            first = now if first is None else first
            last = now
    if first is None or connected != 1 or boots > 1 or last - first < minutes * 60:
        raise Refused('RPT lacks one successful boot or the declared observation length')
    # Allow only the bounded graceful shutdown window beyond the requested run,
    # never treat a much longer candidate as a same-length observation.
    if last - first > minutes * 60 + soak.STOP_WAIT_SECONDS + 60:
        raise Refused('RPT exceeds declared observation plus shutdown allowance; use full run length')
    return round((last - first) / 60, 3)


def pair(args):
    if not all((args.candidate_rpt, args.stock_rpt, args.output, args.candidate_minutes, args.stock_minutes)):
        raise Refused('pair requires both RPTs, both minute lengths and --output')
    paths = [plain(soak.default_linux(str(p))) for p in (args.candidate_rpt, args.stock_rpt, args.output)]
    candidate, stock, output = paths
    if len(set(paths)) != 3 or output.exists():
        raise Refused('pair output must be a new file distinct from both inputs')
    if candidate.samefile(stock):
        raise Refused('candidate and stock must be distinct captures')
    result = rpt_config_audit.totals_audit(candidate, stock)
    print('candidate_minutes=%d stock_minutes=%d required_minutes=%d' % (
        args.candidate_minutes, args.stock_minutes, minimum_minutes()))
    eligible = (args.candidate_minutes == args.stock_minutes and args.candidate_minutes >= minimum_minutes())
    if eligible:
        candidate_observed = validate_duration(candidate, args.candidate_minutes)
        stock_observed = validate_duration(stock, args.stock_minutes)
    ceilings = targets()['rpt_category_ceilings']
    rows = []
    for row in result['categories']:
        category, count, baseline = row['category'], row['count'], row['vanilla_count']
        proposal = max(count, baseline) if eligible and category in (2, 15) else None
        record = dict(category=category, candidate_count=count, stock_count=baseline,
                      excess=count - baseline, current_ceiling=ceilings[str(category)])
        extra = ''
        if category in (2, 15):
            record['proposed_ceiling'] = proposal
            extra = ' proposed_ceiling=' + json.dumps(proposal)
        rows.append(record)
        print('category=%d candidate=%d stock=%d excess=%d ceiling=%s%s' % (
            category, count, baseline, count - baseline, json.dumps(ceilings[str(category)]), extra))
    if not eligible:
        raise Refused('proposal requires equal release-candidate-length observations; no scaling')
    # Unknown diagnostics remain blockers. They are not silently assigned to 2/15.
    blockers = {key: result[key] for key in ('unclassified_count', 'vanilla_unclassified_count',
                                            'oversized_lines', 'vanilla_oversized_lines')}
    proposal = dict(schema=1, evidence='offline_only', lead_review_required=True,
                    census_complete=not any(blockers.values()), blockers=blockers,
                    candidate_minutes=args.candidate_minutes, stock_minutes=args.stock_minutes,
                    candidate_observed_minutes=candidate_observed, stock_observed_minutes=stock_observed,
                    candidate_sha256=digest(candidate), stock_sha256=digest(stock), categories=rows)
    with output.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(proposal, indent=2, sort_keys=True) + '\n')
    print('pair: proposal written; classify warnings and review before any manual ceiling change')


def main(argv=None):
    try:
        parser = Parser(description=__doc__)
        parser.add_argument('mode', nargs='?', default='plan', choices=('plan', 'stage', 'run', 'restore', 'pair'))
        parser.add_argument('--server-root', default=soak.SERVER_ROOT_DEFAULT)
        parser.add_argument('--port', type=int, default=2402)
        parser.add_argument('--minutes', type=int, default=minimum_minutes())
        parser.add_argument('--yes', action='store_true')
        parser.add_argument('--candidate-rpt', type=Path)
        parser.add_argument('--stock-rpt', type=Path)
        parser.add_argument('--candidate-minutes', type=int)
        parser.add_argument('--stock-minutes', type=int)
        parser.add_argument('--output', type=Path)
        args = parser.parse_args(argv)
        if args.mode == 'pair':
            pair(args)
            return 0
        if not 1024 <= args.port <= 65532 or args.minutes < minimum_minutes():
            raise Refused('port outside allowed range or minutes below release idle length')
        server = plain(soak.default_linux(args.server_root))
        stage = Stage(server)
        if args.mode == 'plan':
            print('Stock capture plan (writes nothing; never starts a server)')
            _, _, label = stock_source(server)
            print('stock source: ' + label)
            print('proof: pinned whole pre-install tree matches installer journal; no HC hooks/folders')
            print('stock inventory sha256=' + STOCK_PIN)
            print('scratch: sibling stock-capture; unique mpmissions copy; fresh profiles; port=%d minutes=%d' % (
                args.port, args.minutes))
            config_copy(plain(server / 'serverDZ.cfg').read_bytes(), 'stock_capture_plan.chernarusplus', args.port)
            print('security: signatures=2; BattlEye unchanged; Steam unchanged; no mods')
            return 0
        if args.mode == 'run' and not args.yes:
            raise Refused('run is lead-only; pass --yes')
        # A restore without a receipt is genuinely a no-op, even off the host.
        if args.mode == 'restore' and stage.load() is None:
            stage.restore()
            return 0
        with host_lock('stock_capture'):
            host = soak.WindowsHost()
            stopped(host)
            if args.mode == 'stage':
                stage.stage(args.port)
                print('stage: scratch stock mission, fresh profiles and config created; receipt saved')
            elif args.mode == 'restore':
                stage.restore()
            else:
                stage.run(host, args.minutes)
        return 0
    except (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError, RecursionError, InteropError):
        # No exception text: external input, interop and paths may contain private data.
        error = sys.exc_info()[1]
        print('stock_capture: refused: ' + (str(error) if isinstance(error, (Refused, LockRefused))
                                          else 'input, evidence or host operation unavailable (details withheld)'))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
