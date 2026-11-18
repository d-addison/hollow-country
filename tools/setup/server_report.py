"""Redacted Hollow Country server report for a friend's Windows server.

Reads the newest server log (.RPT), the newest script log and counts from the Hollow Country profile state,
and writes one Markdown file that is safe to publish in a public repository: Steam64 ids, BattlEye GUIDs, IP
addresses and ports, player names, Windows user paths and any line that mentions a credential are removed
before anything is classified, a final safety net refuses to write a report that still holds one, and the file
is never larger than 512 KB. Profile state is summarised as counts only. It reads files and writes one new
file; it never contacts a network, never starts or stops a process and never reads .ADM player logs.
"""
import argparse
import collections
import datetime
import os
from pathlib import Path
import re
import sys

MAX_BYTES = 512 * 1024
HC_LINE_CAP = 300
SCRIPT_BLOCK_CAP = 40
AI_LINE_CAP = 100
CE_LINE_CAP = 60
CRASH_LINE_CAP = 10
STORE_CAP = 20000
MAX_LINE = 400
RAW_LINE_CAP = 1000
READ_CAP = 200 * 1024 * 1024
CONTEXT_BEFORE = 2
CONTEXT_AFTER = 3
REMEMBER_FILE = 'hollow-country-server-root.txt'
DROPPED = '[line removed by redaction]'
REPORT_PREFIX = 'hollow-country-report-'
PROFILE_ROOTS = ('HollowCountry', 'ExpansionMod')
BUNDLE_ROOT = Path(__file__).resolve().parents[2]


class Unsafe(Exception):
    """The report text still holds something that must not be published."""


# ---------------------------------------------------------------------------------------------------------
# Redaction

_DROP = re.compile(r'(?i)password|passwd|rcon|secret|token|privatekey|\bkey\b|_key\b')
_WIN_PATH = re.compile(r'(?i)(?<![A-Za-z])([A-Z]):[\\/]+Users[\\/]+[^\\/"\'\r\n]+(?:[\\/][^\s"\']*)?')
_POSIX_PATH = re.compile(r'(?i)(?<![\w.])(/(?:mnt/[a-z]|home|Users))/([^/"\'\r\n]+)(?:/[^\s"\']*)?')
_UNC_PATH = re.compile(r'(?<![\\\w:.])\\\\[^\\\s"\']+(?:\\[^\s"\']*)?')
_EMAIL = re.compile(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+')
_HOSTNAME = re.compile(r'(?i)\b(hostname\s*=\s*)"[^"]*"')
_PLAYER_QUOTED = re.compile(r'(?i)\bPlayer\s*"[^"]*"')
# The name after "Player" / "player #N" runs up to the next structural word, a "(" or the end of the line, so a
# name with spaces goes whole. Applied only on connect-style, #N and death lines (see _PLAYER_GATE).
_PLAYER_GATE = re.compile(r'(?i)\bplayer\s*#\s*\d+|\b(?:died|killed|dead|suicide|respawned)\b')
_NAME_END = (r'(?=\s*\(|\s+(?:has\s+been\s+|has\s+|was\s+|is\s+|just\s+)?(?:dis)?connected\b|\s+has\b|\s+is\b'
             r'|\s+was\b|\s+died\b|\s+killed\b|\s+kicked\b|\s+banned\b|\s*[,;:]|\s+-\s|$)')
_PLAYER_NAME = re.compile(r'(?i)\b(player(?:\s*#\s*\d+)?)\s+(?!<name>)(?!#)(?!connect\b|connected\b|disconnected\b|count\b'
                          r'|slots?\b)(?:[^\s(]+)(?:\s+[^\s(]+)*?' + _NAME_END)
_PLAYER_EQ = re.compile(r'(?i)\b(player(?:name|_name)?)(\s*=\s*)(?!<)(?:"[^"]*"|.+?(?=\s+\w+\s*=|[,;)\]]|$))')
_EVENT = re.compile(r'(?i)\b(?:dis)?connected\b|\bkicked\b|\bbanned\b|\bhas joined\b|\bhas left\b')
_QUOTED = re.compile(r'"[^"]*"')
_PARENS_ID = re.compile(r'(?i)\((?:id|guid|uid)\s*=[^)]*\)')
_POS = re.compile(r'(?i)\bpos\s*=\s*<[^>]*>')
_FIELD = re.compile(r'(?i)\b(identity|steamid|steam_id|guid|beguid|uid|username)'
                    r'(\s*=\s*)("[^"]*"|[^\s,;)\]]+)')
_LONG_ID = re.compile(r'(?i)\b(id\s*=\s*)[A-Za-z0-9+/=_-]{20,}')
_STEAM64 = re.compile(r'(?<!\d)7656\d{13}(?!\d)')
_GUID = re.compile(r'(?<![0-9a-fA-F])[0-9a-fA-F]{32}(?![0-9a-fA-F])')
_IPV4 = re.compile(r'(?<!\d)(?<!\d\.)(?:\d{1,3}\.){3}\d{1,3}(?:\:\d{1,5})?(?!\.?\d)')
_IPV6 = re.compile(r'(?<![\w.])\[?(?:[0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}\]?(?::\d{1,5})?(?![\w:])')
_PORT = re.compile(r'(?i)\b((?:steam|query|game|master|server|bind)*port)\b(\W{0,3})\d{2,5}\b')

_CHECK_IPV4 = re.compile(r'(?<!\d)(?<!\d\.)(?:\d{1,3}\.){3}\d{1,3}(?!\.?\d)')
_AFTER_VERSION = re.compile(r'(?i)\bversion\W{0,3}$')
_CHECK_WIN = re.compile(r'(?i)[A-Z]:[\\/]+Users[\\/]+(?!<user>)')
_CHECK_WORDS = re.compile(r'(?i)password|rcon|secret|token')


def _bump(counts, key, n=1):
    if counts is not None and n:
        counts[key] = counts.get(key, 0) + n


def _valid_ipv4(text):
    host = text.split(':', 1)[0]
    return all(int(part) <= 255 for part in host.split('.'))


def _is_version(text, match):
    """A four-part number right after the word version is a build number, not an address."""
    return ':' not in match.group(0) and bool(_AFTER_VERSION.search(text[max(0, match.start() - 12):match.start()]))


def _valid_ipv6(text):
    core = text.strip('[]')
    core = re.sub(r'\]:\d+$', '', core)
    colons = core.count(':')
    if '::' in core or colons >= 5:
        return True
    return colons >= 3 and bool(re.search(r'[a-fA-F]', core))


def redact(line, counts=None):
    """Return one log line with every identifier removed, or DROPPED when it mentions a credential."""
    if _DROP.search(line):
        _bump(counts, 'credential lines')
        return DROPPED
    text = line

    def sub(pattern, repl, key, current):
        found = pattern.findall(current)
        if found:
            _bump(counts, key, len(found))
            return pattern.sub(repl, current)
        return current

    text = sub(_WIN_PATH, lambda m: m.group(1).upper() + ':\\Users\\<user>\\...', 'user paths', text)
    text = sub(_POSIX_PATH, lambda m: m.group(1) + '/<user>/...', 'user paths', text)
    text = sub(_UNC_PATH, lambda m: '\\\\<host>\\...', 'user paths', text)
    text = sub(_EMAIL, '<email>', 'emails', text)
    text = sub(_HOSTNAME, lambda m: m.group(1) + '"<redacted>"', 'server names', text)
    text = sub(_PLAYER_QUOTED, 'Player <name>', 'player names', text)
    text = sub(_PLAYER_EQ, lambda m: m.group(1) + m.group(2) + '<redacted>', 'player fields', text)
    if _EVENT.search(text) or _PLAYER_GATE.search(text):
        text = sub(_PLAYER_NAME, lambda m: m.group(1) + ' <name>', 'player names', text)
    if _EVENT.search(text):
        text = sub(_QUOTED, '<name>', 'player names', text)
        text = sub(_PARENS_ID, '(id=<id>)', 'player ids', text)
        text = sub(_POS, 'pos=<redacted>', 'positions', text)
    text = sub(_FIELD, lambda m: m.group(1) + m.group(2) + '<redacted>', 'player fields', text)
    text = sub(_LONG_ID, lambda m: m.group(1) + '<id>', 'player ids', text)
    text = sub(_STEAM64, '<steam64>', 'steam64', text)
    text = sub(_GUID, '<guid>', 'guid', text)

    def ipv4(match):
        if _valid_ipv4(match.group(0)) and not _is_version(text, match):
            _bump(counts, 'ip')
            return '<ip>'
        return match.group(0)

    def ipv6(match):
        if _valid_ipv6(match.group(0)):
            _bump(counts, 'ip')
            return '<ip>'
        return match.group(0)

    text = _IPV4.sub(ipv4, text)
    text = _IPV6.sub(ipv6, text)
    found = _PORT.findall(text)
    if found:
        _bump(counts, 'ports', len(found))
        text = _PORT.sub(lambda m: m.group(1) + m.group(2) + '<port>', text)
    if not _HC.search(line) and (_EVENT.search(line) or _PLAYER_GATE.search(line)
                                 or _STEAM64.search(line) or _GUID.search(line)):
        # A player event, or a line pairing a name with a Steam64 id or GUID: names have no reliable end, so the
        # whole line goes (review P2). Event counts are taken from the raw line by the scanner.
        _bump(counts, 'player lines')
        return DROPPED
    if _EVENT.search(text) and '<name>' not in text and not _HC.search(text):
        # A connect, kick or ban line whose name could not be located: drop it rather than guess.
        _bump(counts, 'unparsed player lines')
        return DROPPED
    return text


def assert_clean(text):
    """Refuse text that still holds an identifier class; names the class, never the value."""
    if _STEAM64.search(text):
        raise Unsafe('steam64 id still present')
    if _GUID.search(text):
        raise Unsafe('GUID still present')
    for match in _CHECK_IPV4.finditer(text):
        if _valid_ipv4(match.group(0)) and not _is_version(text, match):
            raise Unsafe('IP address still present')
    for match in _IPV6.finditer(text):
        if _valid_ipv6(match.group(0)):
            raise Unsafe('IPv6 address still present')
    if _CHECK_WIN.search(text):
        raise Unsafe('Windows user path still present')
    if _CHECK_WORDS.search(text):
        raise Unsafe('credential word still present')


# ---------------------------------------------------------------------------------------------------------
# Time and files

def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


def parse_now(text):
    return datetime.datetime.strptime(text, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc)


def display(path):
    """A path for the screen with the home folder shown as ~."""
    text = str(path)
    home = str(Path.home())
    if home and (text == home or text.startswith(home + os.sep) or text.startswith(home + '/')):
        return '~' + text[len(home):]
    return text


def newest(folder, suffixes, prefix=None):
    best = None
    try:
        names = list(Path(folder).iterdir())
    except OSError:
        return None
    for path in names:
        if not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        if prefix and not path.name.lower().startswith(prefix):
            continue
        key = (path.stat().st_mtime, path.name)
        if best is None or key > best[0]:
            best = (key, path)
    return best[1] if best else None


def read_lines(path):
    """Yield text lines, each cut to RAW_LINE_CAP characters; reads at most the last READ_CAP bytes."""
    size = path.stat().st_size
    with open(path, 'rb') as handle:
        if size > READ_CAP:
            handle.seek(size - READ_CAP)
            handle.readline()
        for raw in handle:
            text = raw.decode('utf-8', errors='replace').rstrip('\r\n')
            yield text[:RAW_LINE_CAP] + ('...' if len(text) > RAW_LINE_CAP else '')


_STAMP = re.compile(r'^\s*\d{1,2}:\d{2}:\d{2}(?:\.\d+)?\s+')


def split_stamp(line):
    match = _STAMP.match(line)
    if not match:
        return '', line.strip()
    return match.group(0).strip(), line[match.end():].strip()


def clip(text):
    return text if len(text) <= MAX_LINE else text[:MAX_LINE] + '...'


# ---------------------------------------------------------------------------------------------------------
# Scanning

_HC = re.compile(r'\[HC [^\]]*\]|\[HollowCountry\]')
_SEARCH_REFUSED = re.compile(r'\[HC (?:Search Houses|Refusal)\] refused reason=(\w+)')
_SCRIPT_E = re.compile(r"SCRIPT\s*\(E\)|Can't compile|Compile error")
_AI = re.compile(r'\[HC (?:XAI|Expansion AI|AI)[^\]]*\]')
_AI_ERR = re.compile(r'(?i)(?:expansion\s*ai|\beAI\w*|\bHCX\b)')
_CE = re.compile(r'\[CE\]|\bEconomy\b|cfgeconomycore|\btypes\.xml|\bevents\.xml|Central Economy')
_CRASH = re.compile(r'(?i)\bcrash|\bfatal\b|unhandled exception|access violation|assertion failed|'
                    r'application terminated|segmentation fault')
_BUILD = re.compile(r'^(?:Exe timestamp|Current time|DayZ Server version|.*\bVersion\b)')
_PLAYER_ENABLED = re.compile(r'(?i)Player connect enabled')
_MOD = re.compile(r'(?i)(?:^|[\s"])-(servermod|mod)=([^"\s]+)')
_MOD_NAME = re.compile(r'^[@\w.\- ]{1,120}$')


class Scan:
    def __init__(self):
        self.counts = {}
        self.lines = 0
        self.build = collections.OrderedDict()
        self.mods = []
        self.servermods = []
        self.hc = collections.OrderedDict()
        self.hc_total = 0
        self.hc_overflow = 0
        self.script_total = 0
        self.script_blocks = collections.OrderedDict()
        self.script_overflow = 0
        self.refusals = collections.Counter()
        self.ai = collections.OrderedDict()
        self.ai_total = 0
        self.ce = collections.OrderedDict()
        self.ce_total = 0
        self.crash = collections.OrderedDict()
        self.crash_total = 0
        self.player_enabled = False
        self.player_events = 0
        self.sources = []

    @staticmethod
    def _add(store, key, stamp, overflow_attr, owner):
        entry = store.get(key)
        if entry is not None:
            entry[1] += 1
            return
        if len(store) >= STORE_CAP:
            setattr(owner, overflow_attr, getattr(owner, overflow_attr, 0) + 1)
            return
        store[key] = [stamp, 1]


def _clean_mod(name):
    name = name.strip()
    if not name or not _MOD_NAME.match(name) or redact(name) != name:
        return '<redacted>'
    return name


def scan_file(path, scan):
    scan.sources.append(path.name)
    before = collections.deque(maxlen=CONTEXT_BEFORE)
    pending = []
    for raw in read_lines(path):
        scan.lines += 1
        mod = _MOD.search(raw)
        if mod:
            names = [_clean_mod(n) for n in mod.group(2).split(';') if n.strip()]
            (scan.servermods if mod.group(1).lower() == 'servermod' else scan.mods).extend(
                n for n in names if n not in (scan.servermods if mod.group(1).lower() == 'servermod' else scan.mods))
        line = redact(raw, scan.counts)
        for block in pending:
            block['lines'].append(line)
            block['left'] -= 1
        pending = [block for block in pending if block['left'] > 0]
        if line != DROPPED:
            _classify(line, scan, before, pending)
        else:
            # The text is withheld, but the verdict still counts it (counts only, no text).
            if _SCRIPT_E.search(raw):
                scan.script_total += 1
            if _CRASH.search(raw) and not _HC.search(raw):
                scan.crash_total += 1
            if _EVENT.search(raw) and not _DROP.search(raw):
                scan.player_events += 1
        before.append(line)


def _classify(line, scan, before, pending):
    stamp, body = split_stamp(line)
    if _BUILD.match(body) and len(scan.build) < 20:
        scan.build.setdefault(clip(body), [stamp, 1])
    if _HC.search(body):
        scan.hc_total += 1
        Scan._add(scan.hc, clip(body), stamp, 'hc_overflow', scan)
        refused = _SEARCH_REFUSED.search(body)
        if refused:
            scan.refusals[refused.group(1)] += 1
    if _SCRIPT_E.search(body):
        scan.script_total += 1
        key = clip(body)
        block = scan.script_blocks.get(key)
        if block is not None:
            block['count'] += 1
        elif len(scan.script_blocks) >= STORE_CAP:
            scan.script_overflow += 1
        else:
            block = {'count': 1, 'lines': list(before) + [line], 'left': CONTEXT_AFTER}
            scan.script_blocks[key] = block
            pending.append(block)
    if _AI.search(body) or (_AI_ERR.search(body) and re.search(r'(?i)error|fail|exception|cannot|can\'t|warn', body)):
        scan.ai_total += 1
        Scan._add(scan.ai, clip(body), stamp, 'ai_overflow', scan)
    if _CE.search(body):
        scan.ce_total += 1
        Scan._add(scan.ce, clip(body), stamp, 'ce_overflow', scan)
    if _CRASH.search(body) and not _HC.search(body):
        scan.crash_total += 1
        Scan._add(scan.crash, clip(body), stamp, 'crash_overflow', scan)
    if _PLAYER_ENABLED.search(body):
        scan.player_enabled = True
    elif _EVENT.search(body) and (re.search(r'(?i)\bplayer\b', body) or '<name>' in body):
        scan.player_events += 1


def minidumps(profiles):
    names = []
    try:
        for path in sorted(Path(profiles).iterdir()):
            if path.is_file() and path.suffix.lower() in ('.mdmp', '.dmp'):
                names.append(path.name)
    except OSError:
        pass
    return names


def json_entries(path):
    import json
    try:
        if path.stat().st_size > 5 * 1024 * 1024:
            return None
        value = json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return None
    if isinstance(value, (list, dict)):
        return len(value)
    return 1


def profile_state(profiles):
    """Rows of (folder, files, entries, unparsed, bytes) per folder holding JSON files; counts only."""
    rows = []
    for root_name in PROFILE_ROOTS:
        root = Path(profiles) / root_name
        if not root.is_dir():
            continue
        folders = collections.OrderedDict()
        for path in sorted(root.rglob('*.json')):
            if not path.is_file():
                continue
            rel = path.parent.relative_to(Path(profiles)).as_posix()
            row = folders.setdefault(rel, [0, 0, 0, 0])
            row[0] += 1
            entries = json_entries(path)
            if entries is None:
                row[2] += 1
            else:
                row[1] += entries
            row[3] += path.stat().st_size
        for rel, (files, entries, unparsed, size) in folders.items():
            rows.append((rel, files, entries, unparsed, size))
    return rows


# ---------------------------------------------------------------------------------------------------------
# Rendering

def _fence(rows):
    body = '\n'.join(rows).replace('```', "'''")
    return '```text\n%s\n```' % body


def _dedup_section(store, total, cap, overflow=0, note='lines'):
    if not store:
        return ['None logged.']
    shown = list(store.items())[:cap]
    rows = ['x%d  %s  %s' % (entry[1], entry[0] or '-', key) for key, entry in shown]
    hidden = len(store) - len(shown) + overflow
    out = [_fence(rows)]
    if hidden > 0:
        out.append('%d further distinct %s not shown (%d occurrences in total).' % (hidden, note, total))
    return out


def render(scan, info, profiles, now, hc_cap, script_cap, rpt_name, script_name, mdmp_names, state_rows):
    lines = ['# Hollow Country server report', '',
             'Generated: %s' % now.strftime('%Y-%m-%d %H:%M:%S UTC'),
             'Source log: %s' % rpt_name]
    if script_name:
        lines.append('Script log: %s' % script_name)
    lines.append('')
    attention = []
    if scan.script_total:
        attention.append('%d script error line(s)' % scan.script_total)
    if mdmp_names:
        attention.append('%d minidump file(s)' % len(mdmp_names))
    if scan.crash_total:
        attention.append('%d crash-like log line(s)' % scan.crash_total)
    lines += ['## Summary', '',
              '- Verdict: %s' % ('needs attention: ' + ', '.join(attention) if attention
                                 else 'no script errors, crash lines or minidumps found'),
              '- Log lines read: %d' % scan.lines,
              '- Mods in -mod list: %d' % len(scan.mods),
              '- Hollow Country lines: %d (%d distinct)' % (scan.hc_total, len(scan.hc) + scan.hc_overflow),
              '- Script errors: %d (%d distinct)' % (scan.script_total, len(scan.script_blocks) + scan.script_overflow),
              '- Refusals (search and actions): %d' % sum(scan.refusals.values()),
              '- AI lines: %d' % scan.ai_total,
              '- Player connect enabled: %s' % ('yes' if scan.player_enabled else 'no'),
              '- Minidump files: %d' % len(mdmp_names),
              '- Economy (CE) lines: %d' % scan.ce_total,
              '']
    lines += ['## Build and version', '']
    lines += _dedup_section(scan.build, len(scan.build), 20) if scan.build else ['No build or version lines found.']
    lines += ['', '## Mod list', '']
    if scan.mods:
        lines.append('-mod=%s' % ';'.join(scan.mods))
        lines.append('')
        lines += ['- %s' % name for name in scan.mods]
    else:
        lines.append('No -mod list found in the log.')
    if scan.servermods:
        lines += ['', '-servermod=%s' % ';'.join(scan.servermods)]
    lines += ['', '## Hollow Country lines', '',
              'Every distinct [HC ...] line once with its count (x3 means three times), first seen time first.', '']
    lines += _dedup_section(scan.hc, scan.hc_total, hc_cap, scan.hc_overflow)
    lines += ['', '## Script errors', '']
    if scan.script_blocks:
        rows = []
        for key, block in list(scan.script_blocks.items())[:script_cap]:
            rows.append('x%d  %s' % (block['count'], key))
            rows += ['    %s' % clip(item) for item in block['lines']]
            rows.append('')
        lines.append(_fence(rows))
        hidden = len(scan.script_blocks) - min(len(scan.script_blocks), script_cap) + scan.script_overflow
        if hidden > 0:
            lines.append('%d further distinct script errors not shown (%d occurrences in total).'
                         % (hidden, scan.script_total))
    else:
        lines.append('No SCRIPT (E) lines logged.')
    lines += ['', '## Refusals (search and actions)', '']
    if scan.refusals:
        lines += ['| reason | count |', '| --- | --- |']
        lines += ['| %s | %d |' % (reason, n) for reason, n in sorted(scan.refusals.items(), key=lambda i: (-i[1], i[0]))]
    else:
        lines.append('No refusals logged.')
    lines += ['', '## AI', '', 'Lines tagged [HC XAI] or [HC Expansion AI], and Expansion AI lines that read as errors.', '']
    lines += _dedup_section(scan.ai, scan.ai_total, AI_LINE_CAP, getattr(scan, 'ai_overflow', 0))
    lines += ['', '## Player connect', '',
              '| item | value |', '| --- | --- |',
              '| Player connect enabled | %s |' % ('yes' if scan.player_enabled else 'no'),
              '| Connect and disconnect events | %d |' % scan.player_events,
              '', 'Counts only; no names or ids are kept.']
    lines += ['', '## Crash and minidumps', '',
              '| item | value |', '| --- | --- |',
              '| Minidump files | %d |' % len(mdmp_names),
              '| Crash-like log lines | %d |' % scan.crash_total]
    if mdmp_names:
        lines += ['', _fence([redact(n) for n in mdmp_names[:10]])]
    if scan.crash:
        lines += ['', _fence(['x%d  %s  %s' % (e[1], e[0] or '-', k) for k, e in list(scan.crash.items())[:CRASH_LINE_CAP]])]
    lines += ['', '## Economy (CE) load', '']
    lines += _dedup_section(scan.ce, scan.ce_total, CE_LINE_CAP, getattr(scan, 'ce_overflow', 0))
    lines += ['', '## Profile state summary', '',
              'Counts only: files, entries (top-level list items or object keys) and size. No contents.', '']
    if state_rows:
        lines += ['| folder | files | detail |', '| --- | --- | --- |']
        for rel, files, entries, unparsed, size in state_rows:
            detail = 'entries %d, %.1f KB' % (entries, size / 1024.0)
            if unparsed:
                detail += ', %d unreadable' % unparsed
            lines.append('| %s | %d | %s |' % (redact(rel), files, detail))
    else:
        lines.append('No Hollow Country or Expansion profile folders found.')
    counts = scan.counts
    lines += ['', '## Redaction', '',
              'Removed before anything was classified: Steam64 ids, BattlEye GUIDs, IP addresses and ports, player '
              'names, player ids, positions in connect lines, Windows user paths, e-mail addresses and the server '
              'name. Any line that mentions a credential is dropped whole. A final check refuses to write the file '
              'if an identifier is still present. The report is cut to %d KB at most.' % (MAX_BYTES // 1024), '']
    if counts:
        lines += ['| removed | count |', '| --- | --- |']
        lines += ['| %s | %d |' % (name, counts[name]) for name in sorted(counts)]
    else:
        lines.append('Nothing needed removing.')
    return '\n'.join(lines) + '\n'


def enforce_limit(text, limit=None):
    limit = MAX_BYTES if limit is None else limit
    data = text.encode('utf-8')
    if len(data) <= limit:
        return text
    notice = '\n[report truncated at %d bytes]\n' % limit
    cut = data[:limit - len(notice.encode('utf-8'))].decode('utf-8', errors='ignore')
    if '\n' in cut:
        cut = cut[:cut.rindex('\n')]
    return cut + notice


def build_report(profiles, now=None):
    """Return (markdown text, info dict) for one profiles folder."""
    profiles = Path(profiles)
    rpt = newest(profiles, ('.rpt',))
    if rpt is None:
        raise FileNotFoundError('no server RPT')
    script_log = newest(profiles, ('.log',), prefix='script')
    scan = Scan()
    scan_file(rpt, scan)
    if script_log is not None:
        scan_file(script_log, scan)
    mdmp = minidumps(profiles)
    state_rows = profile_state(profiles)
    now = now or utc_now()
    hc_cap, script_cap = HC_LINE_CAP, SCRIPT_BLOCK_CAP
    while True:
        text = render(scan, None, profiles, now, hc_cap, script_cap, rpt.name,
                      script_log.name if script_log else None, mdmp, state_rows)
        if len(text.encode('utf-8')) <= MAX_BYTES or (hc_cap == 0 and script_cap == 0):
            break
        hc_cap //= 2
        script_cap //= 2
    text = enforce_limit(text)
    info = {'source': rpt.name, 'script_log': script_log.name if script_log else None,
            'lines': scan.lines, 'hc_lines': scan.hc_total, 'script_errors': scan.script_total,
            'search_refusals': dict(scan.refusals), 'ai_lines': scan.ai_total, 'ce_lines': scan.ce_total,
            'player_connect_enabled': scan.player_enabled, 'player_events': scan.player_events,
            'minidumps': len(mdmp), 'redactions': dict(scan.counts), 'bytes': len(text.encode('utf-8'))}
    return text, info


# ---------------------------------------------------------------------------------------------------------
# Command line

def remembered_root():
    for folder in (Path.cwd(), BUNDLE_ROOT):
        try:
            value = (folder / REMEMBER_FILE).read_text(encoding='utf-8').strip()
        except OSError:
            continue
        if value:
            return Path(value)
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(prog='server_report', description=__doc__.split('\n\n')[0])
    parser.add_argument('--profiles', help='server profiles folder holding the .RPT files')
    parser.add_argument('--server-root', help='DayZ server folder; profiles is read from <root>/profiles')
    parser.add_argument('--out', help='folder for the report (default: the current folder)')
    args = parser.parse_args(argv)
    if args.profiles:
        profiles = Path(args.profiles).expanduser()
    else:
        root = Path(args.server_root).expanduser() if args.server_root else remembered_root()
        if root is None and sys.stdin is not None and sys.stdin.isatty():
            typed = input('DayZ server folder (the one holding DayZServer_x64.exe): ').strip().strip('"')
            root = Path(typed).expanduser() if typed else None
        if root is None:
            print('refused: server_root_required: pass --server-root or --profiles, or run '
                  'install-hollow-country.bat first so the folder is remembered', file=sys.stderr)
            return 2
        profiles = root / 'profiles'
    if not profiles.is_dir():
        print('refused: profiles_missing: %s is not a folder' % display(profiles), file=sys.stderr)
        return 2
    try:
        text, info = build_report(profiles)
    except FileNotFoundError:
        print('refused: no server RPT found in %s; start the server once and let it run, then try again'
              % display(profiles), file=sys.stderr)
        return 2
    try:
        assert_clean(text)
    except Unsafe as error:
        print('refused: report_unsafe: %s; nothing was written, please tell the mod author' % error, file=sys.stderr)
        return 2
    out = Path(args.out).expanduser() if args.out else Path.cwd()
    name = REPORT_PREFIX + utc_now().strftime('%Y%m%dT%H%M%SZ') + '.md'
    target = out / name
    out.mkdir(parents=True, exist_ok=True)
    try:
        with open(target, 'x', encoding='utf-8', newline='\n') as handle:
            handle.write(text)
    except FileExistsError:
        print('refused: report_exists: %s already exists and is never overwritten; wait a second and run again'
              % display(target), file=sys.stderr)
        return 2
    print('Wrote %s (%.1f KB, %d redactions)' % (display(target), info['bytes'] / 1024.0,
                                                 sum(info['redactions'].values())))
    print('Read it once if you like, then upload that one file; see reports/friend-server/README.md.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
