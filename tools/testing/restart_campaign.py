"""Lead-only, targeted multi-boot restart/persistence evidence; plan never launches anything."""
import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

from tools.testing import soak_campaign as soak
from tools.release import rpt_summary
from tools.release.host_lock import host_lock, LockRefused
from tools.setup.winproc import InteropError

STATE = Path.home() / '.cache/hollow-country/restart-campaign'
STORES = {'world': 'world.json', 'custody': 'ai-custody.json', 'intent': 'search-refresh.json'}
READ_MODULES = {'world': 'World', 'custody': 'Materializer', 'intent': 'LootRefresh'}
VME = re.compile(r'\bVME\b|Virtual Machine Exception', re.I)  # release_gate.py:312
USE = re.compile(r'\[HC Use\] module=([\w.-]+) feature=([\w.-]+) count=(\d+)')
BRIDGE = re.compile(r'\[HC XAI Bridge\] teardown retired_released=\d+ retained=\d+')
TEARDOWN = re.compile(r'\[HC Teardown\] shelters_skipped=\d+ pathgraph_skipped=\d+ callbacks_removed=\d+ packs_released=\d+ rpc_skipped=\d+')
DOMAINS = ('world store', 'custody', 'search refresh', 'groups', 'site ownership/cleared-at',
           'holdouts', 'leads', 'vehicles')
# Only fixed, non-identifying restore evidence is retained in the report. Missing save-side
# counts are deliberately unobservable, even when read_ok or a file hash proves a read.
RESTORES = {
    'world store': re.compile(r'\[HollowCountry\] V2 world loaded day=\d+ places=\d+ facts=\d+ factions=\d+'),
    'custody': re.compile(r'\[HC \w+\] custody_load file=ai-custody.json relocation_depth=\d+ loaded=(?:true|false|0|1)'),
}

SAVES = {
    'site ownership/cleared-at': re.compile(r'\[HC Expansion AI\] site police-chernogorsk cleared-at=\d+ saved=\d+'),
    'leads': re.compile(r'\[HC Leads\] open_save state=durable revision=\d+'),
}


@dataclass(frozen=True)
class Cycle:
    kind: str
    minutes: int
    join: bool = False
    xai: bool = True
    store: str = ''
    fault: bool = False


def cycle_plan(recover=(), exhaust=(), no_xai=False):
    cycles = [Cycle('A', 5, True) for _ in range(3)] + [Cycle('B', 5) for _ in range(2)]
    for store in recover:
        cycles.append(Cycle('C', 5, store=store, fault=True))
    for store in exhaust:
        cycles.extend((Cycle('D', 40, store=store, fault=True), Cycle('D-readback', 5)))
    if no_xai:
        cycles.append(Cycle('E', 1, xai=False))
    return cycles


def driver_script(first=False, ordinal=1):
    from tools.testing import driver_script as driver
    police = list(driver.resolve_waypoint(driver.AI_SITE))
    loot = list(driver.resolve_waypoint(driver.TOWN))
    steps = [dict(kind='wait', seconds=10)]
    if first:
        steps += [dict(kind='group', op='create_solo'), dict(kind='ping')]
    steps += [dict(kind='walk', to=police, gait='jog', arrive_m=12, timeout_s=45)]
    if first:
        steps += [dict(kind='stand', seconds=20), dict(kind='admin', cmd='fx_site_patrol_kill', value='')]
    steps += [dict(kind='walk', to=loot, gait='jog', arrive_m=12, timeout_s=60)]
    if first:
        steps += [dict(kind='search_site', site=driver.TOWN.split(':')[1], timeout_s=45),
                  dict(kind='admin', cmd='fx_car_side', value=''), dict(kind='stand', seconds=3),
                  dict(kind='action', name='flip', args={}, timeout_s=30),
                  dict(kind='vehicle', range_m=40, seconds=8, throttle=0.5, timeout_s=45)]
    steps += [dict(kind='stand', seconds=20)]
    for index, step in enumerate(steps, 1):
        step['id'] = 's%02d' % index
    result = dict(version=1, run_id='restart-%d' % ordinal, steps=steps)
    driver.validate_script(result)
    return result


def snapshot(folder):
    """Paths, not mtimes: a previous boot's touched files cannot become this boot's evidence."""
    return {p.relative_to(folder).as_posix() for p in Path(folder).rglob('*') if p.is_file()}


def launch_files(folder, before):
    return sorted(p for p in Path(folder).rglob('*') if p.is_file()
                  and p.relative_to(folder).as_posix() not in before
                  and (p.suffix.lower() in ('.rpt', '.log', '.mdmp', '.dmp', '.adm')))


def log_text(paths):
    return '\n'.join('\n'.join(soak.tail_lines(p, 0)[0]) for p in paths
                     if p.suffix.lower() in ('.rpt', '.log'))


def verdict(server, client='', *, xai=True, crash_files=False, diagnostics=''):
    text = server + '\n' + client + '\n' + diagnostics
    counters = {}
    for module, feature, count in USE.findall(text):
        key = module + '/' + feature
        counters[key] = max(counters.get(key, 0), int(count))
    reads = {s: counters.get(READ_MODULES[s] + '/' + s + '_read_ok', 0) > 0 for s in STORES}
    ready = [line for line in server.splitlines() if '[HC Ready]' in line]
    result = dict(crash=bool(crash_files or rpt_summary.CRASH.search(text) or re.search('0xc0000374', text, re.I)),
                  script_e=len(rpt_summary.SCRIPT_ERROR.findall(text)), vme=len(VME.findall(text)),
                  teardown_lines=TEARDOWN.findall(server), bridge_lines=BRIDGE.findall(server),
                  store_reads=reads,
                  store_restores={d: RESTORES[d].findall(server) if d in RESTORES else [] for d in DOMAINS},
                  store_saves={d: SAVES[d].findall(server) if d in SAVES else [] for d in DOMAINS},
                  store_rows={'world': [dict(zip(('places', 'facts', 'factions'), map(int, counts)))
                                       for counts in re.findall(r'V2 world loaded day=\d+ places=(\d+) facts=(\d+) factions=(\d+)', server)],
                              'custody': 'unobservable', 'intent': 'unobservable'},
                  counters_woken={k: n for k, n in counters.items() if n > 0},
                  ready=bool(ready) and all(re.search(r'\bready=true\b', line) for line in ready),
                  connect=soak.CONNECT_ENABLED in server)
    result['clean'] = (not result['crash'] and result['script_e'] == result['vme'] == 0
                       and result['connect'] and result['ready']
                       and (not xai or (len(result['bridge_lines']) == len(result['teardown_lines']) == 1)))
    return result


def round_trip(previous, current):
    rows = []
    for domain in DOMAINS:
        restore = current.get('store_restores', {}).get(domain, [])
        save = previous.get('store_saves', {}).get(domain, [])
        # Conditional save traces still cannot establish a comparable unconditional row count.

        rows.append(dict(domain=domain, save=save[-1] if save else None, restore=restore[0] if restore else None,
                         status='unobservable', proposed_line='[HC Persistence RoundTrip] domain=%s phase=save|restore rows=<n> revision=<n>' % domain))
    return rows


def lockout(killed_at, boot_at, text):
    if killed_at is None:
        return 'unobservable(no confirmed patrol death)'
    elapsed = max(0, boot_at - killed_at)
    if elapsed >= 600:
        return 'not_applicable(elapsed=%d)' % elapsed
    return 'passed' if 'spawn refused: raided site lockout' in text else 'failed(elapsed=%d)' % elapsed


def lock_path(profile, store):
    if store not in STORES:
        raise soak.Refused('unknown store')
    profile = Path(profile)
    if profile.name != soak.PROFILE_COPY:
        raise soak.Refused('lock requires staged soak-profiles')
    base = profile / 'HollowCountry'
    if base.is_symlink() or profile.is_symlink():
        raise soak.Refused('lock path escapes staged profile')
    path = base / STORES[store]
    if path.is_symlink() or not path.resolve().is_relative_to(base.resolve()):
        raise soak.Refused('lock path escapes staged profile')
    if not path.is_file():
        raise soak.Refused('lock requires an existing committed store')
    return path.resolve()


def store_hashes(profile):
    base = Path(profile) / 'HollowCountry'
    return {s + suffix: hashlib.sha256((base / (name + suffix)).read_bytes()).hexdigest()
            if (base / (name + suffix)).is_file() else None
            for s, name in STORES.items() for suffix in ('', '.bak', '.tmp')}


def locked_hashes(hashes, store):
    return {k: v for k, v in hashes.items() if k in (store, store + '.bak', store + '.tmp')}


def fault_observation(text, store):
    """Fresh/quarantine must win even if read_unavailable also appeared."""
    name = STORES[store]
    for line in text.splitlines():
        relevant = ('store=' + store in line or name in line or store + '_' in line
                    or re.search(r'\b' + store + r'\b', line, re.I))
        if relevant and re.search(r'quarantin|interrupted_pair|\bfresh\b|action=fresh|start_empty', line, re.I):
            return 'FileExist under share-none'
    unavailable = '[HC Persistence] store=%s read_unavailable' % store in text
    if not unavailable and any(feature == store + '_read_ok' and int(count) > 0
                               for _, feature, count in USE.findall(text)):
        # HCWorldStore.c:552-555 also emits read_ok on a silent Fresh branch.
        return 'FileExist under share-none'
    return 'read_unavailable' if unavailable else None


class ReadLock:
    """A self-expiring read-only share-none handle; never terminate the helper process."""
    def __init__(self, profile, store, host, win=soak.default_win):
        self.path = lock_path(profile, store)
        self.signal = self.path.parent / 'restart-lock.release'
        self.ready = self.path.parent / 'restart-lock.ready'
        self.closed = self.path.parent / 'restart-lock.closed'
        self.started = self.path.parent / 'restart-lock.started'
        self.host, self.win, self.process = host, win, None
        self.closed_ack = False

    def start(self):
        for marker in (self.signal, self.ready, self.closed, self.started):
            if marker.exists():
                raise soak.Refused('stale lock markers; restore before probing')
        q = lambda p: soak.ps_quote(self.win(p))
        # .NET host IO, not an Enforce API. FileShare.None is intentionally under native probe.
        script = ("$ErrorActionPreference='Stop'; $h=$null; try { "
                  "$h=[IO.File]::Open(%s,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::None); "
                  "[IO.File]::WriteAllText(%s,'ready'); $end=[DateTime]::UtcNow.AddMinutes(75); "
                  "while (-not [IO.File]::Exists(%s) -and [DateTime]::UtcNow -lt $end) { Start-Sleep -Seconds 1 } "
                  "} finally { if ($null -ne $h) { $h.Dispose() }; [IO.File]::WriteAllText(%s,'closed') }"
                  % (q(self.path), q(self.ready), q(self.signal), q(self.closed)))
        from tools.setup.winproc import SYSTEM32
        self.started.write_text('started', encoding='ascii')
        self.process = subprocess.Popen([str(SYSTEM32 / 'WindowsPowerShell/v1.0/powershell.exe'),
                                         '-NoProfile', '-NonInteractive', '-Command', soak.ps_encoded(script)],
                                        cwd='/mnt/c', stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = self.host.clock() + 30
        while not self.ready.is_file():
            if self.process.poll() is not None or self.host.clock() >= deadline:
                raise soak.Refused('read lock not acknowledged')
            self.host.sleep(1)

    def release(self):
        if self.process is None:
            return
        self.signal.write_text('release', encoding='ascii')
        deadline = self.host.clock() + 30
        while self.process.poll() is None:
            if self.host.clock() >= deadline:
                raise soak.Refused('lock helper did not close; leave staged and restore later')
            self.host.sleep(1)
        if not self.closed.exists():
            raise soak.Refused('lock helper close not acknowledged')
        self.closed_ack = True

    def gone(self):
        return self.process is None or (self.process.poll() is not None and (self.closed_ack or self.closed.exists()))

    def clean_markers(self):
        if not self.gone():
            raise soak.Refused('lock helper still running')
        for marker in (self.signal, self.ready, self.closed, self.started):
            marker.unlink(missing_ok=True)


def patch_inventory(folder):
    """Inspect every installed PBO config, including requiredAddons arrays (not parity hashes)."""
    from tools.audit import pbo_config
    from tools.package.inventory_sizes import _config_rows
    from tools.package.inventory_sources import text_rows
    result = {}
    files = [p for p in Path(folder).rglob('*') if p.is_file()]
    pbos = sorted(p for p in files if p.suffix.casefold() == '.pbo')
    if not pbos or any(p.suffix.casefold() == '.ebo' for p in files):
        raise soak.Refused('no-xai dependency inventory unavailable or encrypted')
    for pbo in pbos:
        index = pbo_config.read_pbo_index(pbo)
        for entry in index['entries']:
            name = entry['name'].replace('\\', '/').lower()
            if not name.endswith(('config.bin', 'config.cpp')):
                continue
            data = pbo_config.read_member(pbo, index, entry['name'])
            patches, _ = _config_rows(data) if data[:4] == b'\0raP' else text_rows(data, set())
            for patch, fields in patches.items():
                result.setdefault(patch.casefold(), set()).update(d.casefold() for d in fields.get('requiredAddons', []))
    if not result:
        raise soak.Refused('no-xai CfgPatches inventory empty')
    return result


def no_xai_mods(mods, inventories):
    removed = {soak.TEST_MOD, '@HollowCountryExpansionAI'}
    ai = {mod for mod in mods if 'dayzexpansion_ai_scripts' in inventories[mod]}
    if len(ai) != 1:
        raise soak.Refused('no-xai cannot identify the single Expansion AI dependency folder')
    removed |= ai
    retained = [m for m in mods if m not in removed]
    lost = set().union(*(set(inventories[m]) for m in removed if m in inventories))
    available = set().union(*(set(inventories[m]) for m in retained))
    lost -= available
    for mod in retained:
        for deps in inventories[mod].values():
            if deps & lost:
                raise soak.Refused('no-xai refused: remaining requiredAddons needs a removed addon ('
                                   + ','.join(sorted(dep for dep in deps & lost if re.fullmatch(r'[a-z0-9_]+', dep))) + ')')
    return retained


def restore_when_gone(stager, host, locks=()):
    soak.require_processes_stopped(host, 'restore')
    if any(not lock.gone() for lock in locks):
        raise soak.Refused('stop DayZ by hand, then run restore; lock helper must finish too')
    for lock in locks:
        lock.clean_markers()
    stager.restore(log=lambda _: None)
    # Stager also keeps an aggregate backup of logs; mark that directory targeted too.
    aggregate = stager.state / 'last-run'
    if aggregate.is_dir():
        (aggregate / 'selection.json').write_text(json.dumps(dict(targeted=True)), encoding='utf-8')


class RestartCampaign:
    def __init__(self, stager, host, cycles, evidence, addon_build, *, probe=False, log=print):
        self.stager, self.host, self.cycles = stager, host, cycles
        self.evidence, self.addon_build, self.probe, self.log = Path(evidence), addon_build, probe, log
        self.locks, self.rows, self.killed_at = [], [], None
        self.profile = stager.server / soak.PROFILE_COPY
        self.client = stager.client_parent / soak.CLIENT_PROFILE
        self.sources = (self.profile, self.client)
        self.extra_mission = stager.server / 'mpmissions/restartOffline.chernarusplus'

    def stop(self):
        # Never advance to the server until BOTH client images are confirmed gone.
        for image in (soak.CLIENT_IMAGE, soak.LAUNCHER_IMAGE):
            state = self.host.state(image)
            if state == 'running':
                self.host.stop(image)
            if self.host.state(image) != 'gone':
                raise soak.Refused('client stop failed; stop DayZ by hand, then run restore')
        state = self.host.state(soak.SERVER_IMAGE)
        if state == 'running':
            self.host.stop(soak.SERVER_IMAGE)
        soak.require_processes_stopped(self.host, 'stop')

    def stage(self, ordinal):
        soak.require_processes_stopped(self.host, 'stage')
        outputs = [self.stager.server / rel for rel in (soak.PROFILE_COPY, soak.TEST_MOD, soak.CFG_COPY, soak.BAT_COPY)]
        outputs.append(self.client)
        if any(path.exists() or path.is_symlink() for path in outputs):
            raise soak.Refused('shared staging paths already exist; restore their owning campaign first')
        self.stager.stage(self.addon_build(), driver_script(True, ordinal), log=lambda _: None)

    def stage_no_xai(self, ordinal):
        restore_when_gone(self.stager, self.host, self.locks)
        self.stage(ordinal)  # a NEW profile copy; never participate in A/B/C/D comparisons
        mods = soak.server_mods((self.stager.server / soak.BAT_COPY).read_bytes())
        inventories = {m: patch_inventory(self.stager.server / m) for m in mods}
        retained = no_xai_mods(mods, inventories)
        if self.extra_mission.exists():
            raise soak.Refused('separate no-xai mission already exists')
        # Journal the extra copy BEFORE creating it; restore uses a fixed path, not receipt paths.
        (self.stager.state / 'no-xai-mission').write_text('created', encoding='ascii')
        shutil.copytree(self.stager.mission, self.extra_mission,
                        ignore=shutil.ignore_patterns('storage_*'))
        cfg = self.stager.server / soak.CFG_COPY
        text = cfg.read_text(encoding='utf-8')
        pattern = r'(\btemplate\s*=\s*")[^"]+("\s*;)'
        if len(re.findall(pattern, text)) != 1:
            raise soak.Refused('no-xai mission template is not a single literal')
        cfg.write_text(re.sub(pattern, lambda m: m[1] + self.extra_mission.name + m[2], text), encoding='utf-8')
        bat = self.stager.server / soak.BAT_COPY
        raw = bat.read_text(encoding='utf-8')
        bat.write_text(raw.replace('"-mod=' + ';'.join(mods) + '"',
                                   '"-mod=' + ';'.join(retained) + '"'), encoding='utf-8')

    def collect(self, snapshots):
        return [launch_files(folder, before) for folder, before in zip(self.sources, snapshots)]

    def watch(self, snapshots, seconds, predicate=None, lock=None):
        deadline = self.host.clock() + seconds
        while True:
            paths = self.collect(snapshots)
            server, client = map(log_text, paths)
            text = server + '\n' + client
            if lock and (fault_observation(server, lock[0]) == 'FileExist under share-none' or
                         (not lock[1].closed_ack and any(feature == lock[0] + '_read_ok' and int(count) > 0
                          for _, feature, count in USE.findall(server)))):
                raise soak.Refused('FileExist under share-none: Fresh/quarantine on locked store')
            if rpt_summary.SCRIPT_ERROR.search(text) or VME.search(text) or rpt_summary.CRASH.search(text) or '0xc0000374' in text.lower():
                raise soak.Refused('cycle crash/script/VME observed')
            if any(p.suffix.lower() in ('.mdmp', '.dmp') or p.name.lower().startswith('crash_') for group in paths for p in group):
                raise soak.Refused('cycle crash file observed')
            if any(soak.kick_refusal(line) for line in text.splitlines()):
                raise soak.Refused('cycle client kick observed (identity withheld)')
            if predicate and predicate(server, client):
                return server, client
            if self.rows[-1].get('join') and self.host.state(soak.CLIENT_IMAGE) != 'running':
                raise soak.Refused('client exited or process state unknown')
            if self.host.state(soak.SERVER_IMAGE) != 'running':
                raise soak.Refused('server exited or process state unknown')
            if self.host.clock() >= deadline:
                if predicate:
                    raise soak.Refused('cycle evidence deadline exceeded')
                return server, client
            self.host.sleep(2)

    def archive(self, number, paths, cycle):
        folder = self.evidence / ('cycle-%02d-%s' % (number, cycle.kind))
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'selection.json').write_text(json.dumps(dict(targeted=True, fault=cycle.fault)), encoding='utf-8')
        for peer, files in zip(('server', 'client'), paths):
            dest = folder / peer
            dest.mkdir(exist_ok=True)
            for index, path in enumerate(files):
                # Names can carry host/user data; evidence names use only a fixed prefix and suffix.
                name = ('crash_' if path.name.lower().startswith('crash_') else 'log_') + str(index) + path.suffix.lower()
                shutil.copyfile(path, dest / name)
        return folder

    def run_cycle(self, number, cycle):
        soak.require_processes_stopped(self.host, 'cycle')
        for old_lock in self.locks:
            old_lock.clean_markers()
        script = driver_script(number == 1, number)
        (self.client / soak.STEP_REL).write_text(json.dumps(script), encoding='utf-8')
        row = dict(asdict(cycle), targeted=True, status='failed', stop=False, join=False)
        self.rows.append(row)
        before = store_hashes(self.profile)
        row['hashes_before'] = before
        if number > 1 and cycle.xai:
            row['profile_continuity'] = before == self.rows[-2].get('hashes_after')
            if not row['profile_continuity']:
                raise soak.Refused('profile bytes changed between boots')
        snapshots = [snapshot(p) for p in self.sources]
        lock, failure = None, None
        boot_at = time.time()
        boot_clock = self.host.clock()
        try:
            if cycle.fault:
                lock = ReadLock(self.profile, cycle.store, self.host, self.stager.win)
                self.locks.append(lock)
                lock.start()
            row['boot_at_utc'] = boot_at
            self.host.launch_server(self.stager.win(self.stager.server))
            # Reuse the bounded appearance wait; this does not select logs or stage anything.
            helper = soak.Campaign(self.stager, self.host, {}, addon_build=None, step_script=None)
            helper.appear(soak.SERVER_IMAGE, 'restart server')
            fault = (cycle.store, lock) if lock else None
            if lock:
                self.watch(snapshots, 180, lambda s, c: fault_observation(s, cycle.store) == 'read_unavailable', lock=fault)
                if not self.probe and cycle.kind == 'C':
                    self.watch(snapshots, 20, lock=fault)
                    row['hashes_at_unlock'] = store_hashes(self.profile)
                    if locked_hashes(before, cycle.store) != locked_hashes(row['hashes_at_unlock'], cycle.store):
                        raise soak.Refused('locked store changed before release')
                    lock.release()
                elif not self.probe:
                    self.watch(snapshots, 45 * 60, lambda s, c: re.search(
                        r'store=%s reason=%s_read_exhausted attempt=12 action=retain_retry_next_boot' % (cycle.store, cycle.store), s), lock=fault)
                    # D occupies at least 40 minutes, even if attempt 12 arrives earlier.
                    self.watch(snapshots, max(0, 2400 - (self.host.clock() - boot_clock)), lock=fault)
            self.watch(snapshots, soak.SERVER_READY_MINUTES * 60,
                       lambda s, c: soak.CONNECT_ENABLED in s, lock=fault)
            if cycle.join:
                mods = soak.server_mods((self.stager.server / soak.BAT_COPY).read_bytes())
                paths = soak.client_mods(mods, self.stager.server, self.stager.client_root / '!Workshop', Path)
                soak.require_dependency_parity(mods, self.stager.server, paths, self.log)
                args = soak.client_arguments([self.stager.win(p) for p in paths], self.stager.win(self.client))
                self.host.launch_client(self.stager.win(self.stager.client_root), args)
                helper.appear(soak.CLIENT_IMAGE, 'restart client')
                self.watch(snapshots, soak.CLIENT_JOIN_SECONDS, lambda s, c:
                           '[HC Driver] connect session start' in c and any(soak.SERVER_PLAYER_CONNECTED.search(l) for l in s.splitlines()))
                row['join'] = True
                joined_at = self.host.clock()
                server, client = self.watch(snapshots, 300, lambda s, c: any(
                    soak.DRIVER_DONE.search(l) and ('run=' + script['run_id'] + ' ') in l for l in c.splitlines()))
                if re.search(r'\[HC Driver\] done .*\b(?:refused|unsupported|timeout)=[1-9]', client):
                    raise soak.Refused('driver steps refused/unsupported/timed out')
                self.watch(snapshots, max(0, 180 - (self.host.clock() - joined_at)))
            elif not self.probe and cycle.kind != 'D':
                self.watch(snapshots, cycle.minutes * 60, lock=fault)
            if lock and cycle.kind == 'C' and not self.probe:
                self.watch(snapshots, 180, lambda s, c: '[HC Persistence] store=%s read_recovered attempt=' % cycle.store in s, lock=fault)
        except (Exception, KeyboardInterrupt) as error:
            failure = soak.describe_failure(error)
        finally:
            try:
                self.stop()
                row['stop'] = True
            except (Exception, KeyboardInterrupt):
                failure = failure or 'graceful stop failed'
            # A pending fault lock remains held through shutdown; never discard it while DayZ lives.
            gone = all(self.host.state(i) == 'gone' for i in soak.PROCESS_IMAGES)
            if lock and gone:
                try:
                    lock.release()
                except Exception:
                    failure = failure or 'lock helper did not finish'
            paths = self.collect(snapshots)
            server, client = map(log_text, paths)
            for peer, files, needed in zip(('server', 'client'), paths, (True, cycle.join)):
                rpt_count = sum(p.suffix.lower() == '.rpt' for p in files)
                if rpt_count != int(needed):
                    failure = failure or peer + ' per-launch RPT count is ambiguous or absent'
            folder = self.archive(number, paths, cycle)
            crash_files = any(p.suffix.lower() in ('.mdmp', '.dmp') or p.name.lower().startswith('crash_') for group in paths for p in group)
            # Lifecycle lines must occur once in the RPT, even if script logs repeat them.
            server, client = [log_text([p for p in group if p.suffix.lower() == '.rpt']) for group in paths]
            diagnostics = log_text([p for group in paths for p in group if p.suffix.lower() == '.log'])
            row.update(verdict(server, client, xai=cycle.xai, crash_files=crash_files, diagnostics=diagnostics))
            if cycle.fault and (self.probe or cycle.kind == 'D'):
                row['clean'] = (not row['crash'] and row['script_e'] == row['vme'] == 0
                                and row['connect'] and len(row['bridge_lines']) == len(row['teardown_lines']) == 1)
            row['crash_peers'] = [peer for peer, files in zip(('server', 'client'), paths)
                                  if any(p.suffix.lower() in ('.mdmp', '.dmp') or p.name.lower().startswith('crash_') for p in files)
                                  or rpt_summary.CRASH.search(log_text(files))
                                  or re.search('0xc0000374', log_text(files), re.I)]
            row['crash_summary'] = {peer: soak.crash_summary(folder / peer) for peer in row['crash_peers']}
            row['lockout'] = lockout(self.killed_at, boot_at, server) if number > 1 and cycle.xai else 'not_applicable'
            if number == 1:
                # The fixture is not proof of death; use the persisted real UTC cleared-at event.
                match = re.search(r'site police-chernogorsk cleared-at=(\d+) saved=\d+', server)
                if match:
                    self.killed_at = int(match[1])
                elif cycle.join:
                    failure = failure or 'initial patrol death UTC evidence absent'
            row['round_trip'] = round_trip(self.rows[-2], row) if number > 1 and cycle.xai else []
            try:
                row['hashes_after'] = store_hashes(self.profile)
            except OSError:
                failure = failure or 'post-cycle hashes unavailable; lock may still be held'
            if lock:
                row['fault_observation'] = fault_observation(server + '\n' + diagnostics, cycle.store)
                if not self.probe and not re.search(r'store=%s reason=%s_read_retrying action=retry_in_session' % (cycle.store, cycle.store),
                        re.sub(r' attempt=\d+', '', server + '\n' + diagnostics)):
                    failure = failure or 'read retry-in-session evidence absent'
                if row['fault_observation'] != 'read_unavailable':
                    failure = failure or 'read_unavailable absent or FileExist under share-none'
                if row.get('hashes_after') and locked_hashes(before, cycle.store) != locked_hashes(row['hashes_after'], cycle.store):
                    failure = failure or 'locked store changed during fault cycle'
                if any(re.search(r'\b(?:save|saved|save_ok|save_complete)\b', l, re.I) and
                       ('store=' + cycle.store in l or STORES[cycle.store] in l) and
                       not re.search(r'save_refused|save_read_pending', l) for l in (server + '\n' + diagnostics).splitlines()):
                    failure = failure or 'save line for locked store'
            if cycle.fault:
                row['expected_counters'] = {cycle.store + suffix: any(
                    key.endswith('/' + cycle.store + suffix) and count > 0
                    for key, count in row['counters_woken'].items())
                    for suffix in ('_read_recovered', '_save_read_pending')}
                if not self.probe and cycle.kind == 'C' and not row['expected_counters'][cycle.store + '_read_recovered']:
                    failure = failure or 'read_recovered counter absent'
                if not self.probe and cycle.kind == 'D' and not row['expected_counters'][cycle.store + '_save_read_pending']:
                    failure = failure or 'save_read_pending counter absent'
            if not row['clean'] or not row['stop'] or row['lockout'].startswith('failed'):
                failure = failure or 'cycle verdict failed'
            if cycle.xai and number > 1 and not cycle.fault and not all(row['store_reads'].values()):
                failure = failure or 'normal restart missing store read_ok'
            if cycle.kind == 'D-readback':
                saved = self.rows[-2]['hashes_before']
                store = self.rows[-2]['store']
                row['retained_readback_intact'] = (locked_hashes(before, store) == locked_hashes(saved, store)
                                                    and all(row['store_reads'].values()))
                if not row['retained_readback_intact']:
                    failure = failure or 'retained data readback mismatch'
            row['failure'] = failure
            row['status'] = 'failed' if failure else 'passed'
        if failure:
            raise soak.Refused(failure)

    def run(self):
        soak.require_processes_stopped(self.host, 'run')
        if self.stager.load() is not None or self.extra_mission.exists():
            raise soak.Refused('staged campaign exists; restore first')
        failure = None
        try:
            shutil.rmtree(self.evidence, ignore_errors=True)
            self.stage(1)
            self.evidence.mkdir(parents=True, exist_ok=True)
            for number, cycle in enumerate(self.cycles, 1):
                self.log('restart: cycle %d kind=%s xai=%s fault=%s' % (number, cycle.kind, cycle.xai, cycle.fault))
                if not cycle.xai:
                    self.stage_no_xai(number)
                self.run_cycle(number, cycle)
        except (Exception, KeyboardInterrupt) as error:
            failure = soak.describe_failure(error)
        finally:
            for cycle in self.cycles[len(self.rows):]:
                self.rows.append(dict(asdict(cycle), targeted=True, status='unrun'))
            try:
                restore_when_gone(self.stager, self.host, self.locks)
                restore_extra(self.stager)
            except Exception:
                failure = failure or 'restore refused'
                self.log('stop DayZ by hand, then run restore')
            write_report(self.evidence, self.rows, failure)
        return not failure


def restore_extra(stager):
    marker = stager.state / 'no-xai-mission'
    if marker.exists():
        path = stager.server / 'mpmissions/restartOffline.chernarusplus'
        if path.is_symlink():
            raise soak.Refused('no-xai mission unexpectedly linked')
        if path.exists():
            shutil.rmtree(path)
        marker.unlink()


def write_report(folder, rows, failure):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'selection.json').write_text(json.dumps(dict(targeted=True)), encoding='utf-8')
    (folder / 'report.json').write_text(json.dumps(dict(targeted=True, failure=failure, cycles=rows), indent=2) + '\n', encoding='utf-8')
    fields = ('kind', 'xai', 'fault', 'join', 'stop', 'crash', 'script_e', 'vme', 'bridge_lines',
              'teardown_lines', 'store_reads', 'store_rows', 'store_restores', 'round_trip', 'lockout', 'counters_woken', 'status')
    lines = ['# Restart campaign — targeted evidence', '', 'No multiplayer claim. Failure: ' + (failure or 'none'), '',
             '| cycle | ' + ' | '.join(fields) + ' |', '| --- | ' + ' | '.join('---' for _ in fields) + ' |']
    for number, row in enumerate(rows, 1):
        lines.append('| %d | %s |' % (number, ' | '.join(json.dumps(row.get(f, 'unrun')).replace('|', '/') for f in fields)))
    lines += ['', '| cycle | domain | save N-1 → restore N | status | proposed trace (not added) |',
              '| --- | --- | --- | --- | --- |']
    for number, row in enumerate(rows, 1):
        for domain in row.get('round_trip', []):
            lines.append('| %d | %s | %s → %s | %s | %s |' % (number, domain['domain'], domain['save'],
                         domain['restore'], domain['status'], domain['proposed_line'].replace('|', '/')))
    (folder / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main(argv=None, *, host=None, out=None):
    out = out or sys.stdout
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('plan', 'run', 'probe-lock', 'restore'))
    parser.add_argument('--yes', action='store_true', help='lead confirms the owner is not playing')
    parser.add_argument('--fault-recover', action='append', nargs='?', const='world', choices=STORES, default=[])
    parser.add_argument('--fault-exhaust', action='append', nargs='?', const='world', choices=STORES, default=[])
    parser.add_argument('--store', choices=STORES, default='world')
    parser.add_argument('--no-xai', action='store_true')
    parser.add_argument('--server-root', default=soak.SERVER_ROOT_DEFAULT)
    parser.add_argument('--client-root')
    args = parser.parse_args(argv)
    cycles = cycle_plan(args.fault_recover, args.fault_exhaust, args.no_xai)
    if args.mode == 'probe-lock':
        cycles = [Cycle('probe-lock', 3, store=args.store, fault=True)]
    if args.mode == 'plan':
        print('Restart campaign: targeted=true; writes nothing; boot/join/stop waits additional.', file=out)
        for number, cycle in enumerate(cycles, 1):
            print('%d. %s xai=%s client=%s fault=%s store=%s minutes=%d' % (
                number, cycle.kind, cycle.xai, cycle.join, cycle.fault, cycle.store or '-', cycle.minutes), file=out)
        print('Total planned minutes: %d (plus boot/join/stop waits)' % sum(c.minutes for c in cycles), file=out)
        return 0
    try:
        if args.mode != 'restore' and not args.yes:
            raise soak.Refused('lead only: pass --yes after confirming the owner is not playing')
        with host_lock('restart_campaign'):
            host = host or soak.WindowsHost()
            soak.require_processes_stopped(host, args.mode)
            server, client = soak.local_roots(args)
            stager = soak.Stager(server, client, STATE / 'staging')
            if args.mode == 'restore':
                # A helper from an interrupted Python run self-expires. Never remove its profile early.
                hc = server / soak.PROFILE_COPY / 'HollowCountry'
                if (hc / 'restart-lock.started').exists() and not (hc / 'restart-lock.closed').exists():
                    (hc / 'restart-lock.release').write_text('release', encoding='ascii')
                    raise soak.Refused('lock release signalled; wait for helper close then run restore again')
                restore_when_gone(stager, host)
                restore_extra(stager)
                return 0
            if client is None:
                raise soak.Refused('client install unavailable; pass --client-root')
            if args.mode == 'probe-lock':
                STATE.mkdir(parents=True, exist_ok=True)
                (STATE / ('probe-' + args.store + '.json')).write_text(json.dumps(dict(passed=False)), encoding='utf-8')
            if args.mode == 'run':
                for store in set(args.fault_recover + args.fault_exhaust):
                    proof = STATE / ('probe-' + store + '.json')
                    if not proof.is_file() or not json.loads(proof.read_text()).get('passed'):
                        raise soak.Refused('fault mode requires a successful native probe-lock --store ' + store)
            from tools.testing import test_addon
            campaign = RestartCampaign(stager, host, cycles, STATE / 'last-run',
                                       lambda: Path(test_addon.build()['path']), probe=args.mode == 'probe-lock',
                                       log=lambda text: print(text, file=out, flush=True))
            ok = campaign.run()
            if args.mode == 'probe-lock':
                (STATE / ('probe-' + args.store + '.json')).write_text(json.dumps(dict(passed=ok)), encoding='utf-8')
            print('restart: report.md and report.json written; targeted=true', file=out)
            return 0 if ok else 2
    except (OSError, ValueError, InteropError, LockRefused) as error:
        print('restart_campaign: ' + soak.describe_failure(error), file=out)
        return 2


if __name__ == '__main__':
    sys.exit(main())
