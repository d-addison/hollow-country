"""Server report for the friend's Windows server: synthetic RPT, script log and profile trees only.

The report is uploaded to a PUBLIC repository, so every redaction rule below is tested with an explicit
synthetic line. Nothing here reads a real server, a real player or a real log, and nothing establishes any
DayZ behaviour; it checks what the report tool keeps, drops and counts.
"""
import contextlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest import mock

from tools.setup import server_report as sr
from tools.validate import hygiene

ROOT = Path(__file__).resolve().parents[2]
STEAM64 = '7656119' + '8000000001'          # synthetic 17-digit id, built so no fixture looks like a real one
GUID = 'a1b2c3d4e5f60718293a4b5c6d7e8f90'   # synthetic 32-hex BattlEye GUID
BASE64_ID = 'ZGVhZGJlZWZkZWFkYmVlZmRlYWRiZWVmZGVhZGJlZWY='
SYNTHETIC_IP = '203.0.113.' + '77'          # documentation range, never a real address


def win_home(name, tail=''):
    """A synthetic Windows home path assembled at run time so the source holds no literal home path."""
    return 'C:' + '\\' + 'Users' + '\\' + name + tail


def put(root, rel, data=''):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.encode() if isinstance(data, str) else data)
    return path


class RedactionTests(unittest.TestCase):
    def red(self, line):
        return sr.redact(line)

    def test_steam64_ids_are_removed_wherever_they_appear(self):
        for line in ('Player id %s joined queue' % STEAM64, 'file Players/%s.json missing' % STEAM64,
                     'owner=%s;' % STEAM64):
            out = self.red(line)
            self.assertNotIn(STEAM64, out, line)
            self.assertNotRegex(out, r'7656\d{13}')

    def test_battleye_guids_are_removed_in_either_case(self):
        for guid in (GUID, GUID.upper()):
            out = self.red('BE GUID: %s verified' % guid)
            self.assertNotIn(guid, out)
            self.assertNotRegex(out, r'[0-9a-fA-F]{32}')

    def test_ip_addresses_and_ports_are_removed(self):
        for line in ('connection from %s:2304' % SYNTHETIC_IP, 'Server bound to %s' % SYNTHETIC_IP,
                     'Steam query port 27016 opened', 'command -port=2302 -config=serverDZ.cfg',
                     'peer 2001:db8::1 timed out', 'peer [2001:db8:0:0:0:0:0:2]:2302 timed out'):
            out = self.red(line)
            self.assertNotIn(SYNTHETIC_IP, out, line)
            self.assertNotIn('2304', out, line)
            self.assertNotIn('27016', out, line)
            self.assertNotIn('2302', out, line)
            self.assertNotIn('2001:db8', out, line)

    def test_versions_and_clock_times_survive(self):
        line = ' 8:30:01.100 Version 1.30.164289 built 2026/10/01 08:30:11'
        self.assertEqual(self.red(line), line)

    def test_player_names_are_removed_from_connect_and_disconnect_lines(self):
        lines = ['10:01:02 Player "Alice Wonder" (id=%s) is connected' % BASE64_ID,
                 '10:01:02 Player Bob_77 connected (id=%s)' % STEAM64,
                 '10:05:00 Player "Alice Wonder"(id=%s pos=<1.0, 2.0, 3.0>) has been disconnected' % BASE64_ID,
                 '10:05:00 Player Bob_77 disconnected.',
                 '10:06:00 Player Carol(1) kicked: BattlEye',
                 '10:07:00 "Dave the Brave" has connected to the server']
        for line in lines:
            out = self.red(line)
            for name in ('Alice', 'Wonder', 'Bob_77', 'Carol', 'Dave', 'Brave'):
                self.assertNotIn(name, out, line)
            self.assertNotIn(BASE64_ID, out)
            self.assertNotIn(STEAM64, out)
        self.assertEqual(self.red(lines[0]), sr.DROPPED)
        self.assertEqual(self.red(lines[3]), sr.DROPPED)

    def test_player_and_identity_fields_are_removed_on_any_line(self):
        out = self.red('[HC Example] result=ok player="Eve Online" identity=ABCDEF steamid=%s' % STEAM64)
        self.assertNotIn('Eve', out)
        self.assertNotIn('ABCDEF', out)
        self.assertIn('[HC Example] result=ok', out)

    def test_windows_user_paths_lose_the_account_name(self):
        for line in ('Loading ' + win_home('Alice', '\\AppData\\Local\\DayZ\\x.RPT'),
                     'Loading ' + win_home('Alice', '/Documents/x').replace('\\', '/', 1)):
            out = self.red(line)
            self.assertNotIn('Alice', out, line)
            self.assertIn('<user>', out)
        self.assertNotIn('Alice', self.red('/mnt/c/' + 'Users/Alice/x and /ho' + 'me/alice/x'))
        self.assertNotIn('srvhost', self.red('read \\\\srvhost\\share\\profiles'))

    def test_an_ip_address_before_a_full_stop_or_comma_is_still_removed(self):
        for line in ('Connection from %s.' % SYNTHETIC_IP, 'Connection from %s, retrying' % SYNTHETIC_IP,
                     'peer (%s). done' % SYNTHETIC_IP, 'Connection from %s:2304.' % SYNTHETIC_IP):
            out = self.red(line)
            self.assertNotIn(SYNTHETIC_IP, out, line)
            self.assertIn('<ip>', out, line)
        with self.assertRaises(sr.Unsafe):
            sr.assert_clean('Connection from %s.' % SYNTHETIC_IP)

    def test_four_part_version_strings_after_the_word_version_are_not_ip_addresses(self):
        for line in ('DayZ Server Version 1.30.158.123 started', 'version: 1.30.158.123.'):
            self.assertEqual(self.red(line), line)
            sr.assert_clean(line)
        self.assertIn('<ip>', self.red('client version 1.30.1 from %s' % SYNTHETIC_IP))

    def test_windows_user_paths_with_spaces_in_the_account_name_lose_all_of_it(self):
        for line in ('Loading ' + win_home('Bob Smith', '\\Documents\\DayZ\\x.RPT'),
                     'Loading ' + win_home('Mary Jane Van Dyke', '\\AppData\\x.log'),
                     'cwd ' + win_home('Bob Smith')):
            out = self.red(line)
            for word in ('Bob', 'Smith', 'Mary', 'Jane', 'Dyke'):
                self.assertNotIn(word, out, line)
            self.assertIn('<user>', out)
        sr.assert_clean(self.red('Loading ' + win_home('Bob Smith', '\\Documents\\x')))

    def test_multi_word_unquoted_player_names_are_removed_in_every_known_format(self):
        lines = ['10:01:02 Player John Smith connected',
                 '10:01:02 BattlEye Server: Verified GUID (%s) of player #0 John Smith' % GUID,
                 '10:01:02 Player #0 John Smith (%s:2304) connected' % SYNTHETIC_IP,
                 '10:01:02 player "Bob Smith" died',
                 '10:01:02 player Bob Smith died',
                 '10:01:02 [HC Example] result=ok player=Bob Smith identity=ABC',
                 '10:01:02 Player #3 Mary Jane Van Dyke has been kicked by BattlEye: Admin Kick',
                 '10:01:02 Player Mary Jane disconnected.']
        for line in lines:
            out = self.red(line)
            for word in ('John', 'Smith', 'Bob', 'Mary', 'Jane', 'Dyke', 'ABC', GUID, SYNTHETIC_IP):
                self.assertNotIn(word, out, line + ' -> ' + out)
            sr.assert_clean(out)
            self.assertEqual(self.red(out), out, 'idempotent: ' + out)

    def test_a_connect_line_whose_name_cannot_be_parsed_is_dropped_whole(self):
        out = self.red('10:01:02 Dave the Brave has connected to the server')
        self.assertEqual(out, sr.DROPPED)
        self.assertEqual(self.red('10:01:02 Player connected: Alice Wonder'), sr.DROPPED)

    def test_player_lines_are_dropped_whole_not_guessed_at(self):
        # Review P2: the name heuristic leaked tails ("Dev", "(QA)", "the Great") and mod lines that pair a
        # name with a Steam64 id or GUID kept the name. Such lines are dropped; counts come from the raw line.
        lines = ['10:01:02 BattlEye Server: Player #0 Bob - Dev - GUID: %s (unverified)' % GUID,
                 '10:01:02 Player Bob, the Great connected',
                 '10:01:02 Player Bob (QA) is connected',
                 '10:01:02 [COT] Bob (%s) teleported' % STEAM64,
                 '10:01:02 Expansion: Bob GUID %s joined party' % GUID]
        for line in lines:
            self.assertEqual(self.red(line), sr.DROPPED, line)
        self.assertNotEqual(self.red('[HC Example] owner=%s ok' % STEAM64), sr.DROPPED)

    def test_ipv6_right_after_a_colon_is_removed(self):
        for line in ('connected from:2001:db8::1', 'ip:[2001:db8::1]:2302 timeout'):
            out = self.red(line)
            self.assertNotIn('2001', out, line)
            with self.assertRaises(sr.Unsafe):
                sr.assert_clean(line)
        self.assertEqual(self.red('10:01:02 [HC Doors] ready count=12'), '10:01:02 [HC Doors] ready count=12')

    def test_ordinary_player_words_and_hc_lines_are_not_over_redacted(self):
        for line in ('10:01:02 Player connect enabled', '[HC Groups] players online=3',
                     '[HC Events] player count changed to 2'):
            self.assertEqual(self.red(line), line)

    def test_password_rcon_and_key_lines_are_dropped_entirely(self):
        for line in ('password = "S3CRET-PASS-71";', 'passwordAdmin = S3CRET', 'RConPassword hunter2',
                     'rcon port set; rcon login ok', 'BattlEye key = abcd1234', 'api_key: abcd', 'secret=abc',
                     'steam token abcdef', 'Loaded biprivatekey hollow.biprivatekey', 'KEY = value'):
            out = self.red(line)
            self.assertEqual(out, sr.DROPPED, line)

    def test_key_file_names_and_ordinary_words_are_not_over_redacted(self):
        for line in ('Loaded hollowcountry.bikey from keys/', 'keyboard layout us', 'compass heading'):
            self.assertEqual(self.red(line), line)

    def test_hostname_and_email_values_are_removed(self):
        out = self.red('hostname = "Alice Private Server"; contact alice@example.org')
        self.assertNotIn('Alice', out)
        self.assertNotIn('example.org', out)

    def test_redaction_is_idempotent_and_counts_categories(self):
        counts = {}
        once = sr.redact('Player id %s from %s:2304 guid %s' % (STEAM64, SYNTHETIC_IP, GUID), counts)
        self.assertEqual(sr.redact(once), once)
        for category in ('steam64', 'ip', 'guid'):
            self.assertGreaterEqual(counts.get(category, 0), 1, counts)

    def test_the_final_safety_net_refuses_text_that_still_holds_an_identifier(self):
        for bad in ('x %s y' % STEAM64, 'x %s y' % GUID, 'x %s y' % SYNTHETIC_IP,
                    'x ' + win_home('Alice') + ' y', 'x password=1 y'):
            with self.assertRaises(sr.Unsafe, msg=bad):
                sr.assert_clean(bad)
        sr.assert_clean('x <steam64> <guid> <ip> ' + win_home('<user>') + ' y')


RPT = '''Exe timestamp: 2026/10/01 08:00:00
Current time:  2026/11/18 08:30:00
DayZ Server version 1.30.164289
 8:30:00.001 Dedicated host created.
 8:30:00.500 Command line: -config=serverDZ.cfg -port=2302 "-mod=@CF;@COT;@HollowCountry;@HollowCountryExpansionAI" -profiles=profiles
 8:30:01.000 Loading %(home)s
 8:30:02.000 [CE][Loader] types.xml loaded, 1203 items
 8:30:02.100 [CE][Loader] events.xml loaded
 8:30:02.200 Economy: cfgeconomycore.xml parsed
 8:30:03.000 [HC Events] feature ready state=idle
 8:30:04.000 [HC Events] feature ready state=idle
 8:30:05.000 [HC Events] feature ready state=idle
 8:30:06.000 [HC Doors] ready count=12
 8:30:06.100 [HollowCountry] V1 admission feature=doors result=admitted
 8:30:07.000 [HC Search Houses] refused reason=hands class=Land_House_1
 8:30:07.100 [HC Search Houses] refused reason=hands class=Land_House_2
 8:30:07.200 [HC Search Houses] refused reason=busy class=Land_House_3
 8:30:08.000 [HC XAI] patrol site=Berezino spawned=3
 8:30:08.500 [HC Expansion AI] lease granted site=Berezino
 8:30:09.000 ExpansionAI: eAIBase failed to find a path
 8:30:10.000 Player "Alice Wonder" (id=%(b64)s) is connected
 8:30:10.100 Player "Alice Wonder" BE GUID %(guid)s verified, peer %(ip)s:2304
 8:30:11.000 Player connect enabled
 8:30:12.000 Player Bob_77 disconnected.
 8:30:20.000 password = "S3CRET-PASS-71";
 8:30:30.000 before one
 8:30:30.100 before two
 8:30:30.200 SCRIPT    (E): Can't find variable 'x' in module 'HCDoors'
 8:30:30.300 Class:      'HCDoors'
 8:30:30.400 Entity id=%(steam)s
 8:30:30.500 after three
 8:30:40.000 SCRIPT    (E): Can't find variable 'x' in module 'HCDoors'
 8:30:40.100 Class:      'HCDoors'
 8:31:00.000 [HC Search Houses] refused reason=hands class=Land_House_4
'''


def rpt_text():
    return RPT % {'home': win_home('Alice', '\\Documents\\DayZ'), 'b64': BASE64_ID, 'guid': GUID,
                  'ip': SYNTHETIC_IP, 'steam': STEAM64}


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__('shutil').rmtree(self.tmp, ignore_errors=True))
        self.profiles = self.tmp / 'profiles'
        self.out = self.tmp / 'out'
        old = put(self.profiles, 'DayZServer_x64_2026-11-17_09-00-00.RPT', 'OLD RPT SHOULD NOT BE READ\n')
        os.utime(old, (1_000_000, 1_000_000))
        newest = put(self.profiles, 'DayZServer_x64_2026-11-18_08-30-00.RPT', rpt_text())
        os.utime(newest, (2_000_000, 2_000_000))
        put(self.profiles, 'script_2026-11-18_08-30-00.log', '8:30:09.000 [HC Reach] started radius=40\n')
        put(self.profiles, 'HollowCountry/settings.json', json.dumps({'owner': STEAM64, 'EnableX': True}))
        put(self.profiles, 'HollowCountry/Events/state/commit-1.json', json.dumps([{'p': STEAM64}, {'p': 2}]))
        put(self.profiles, 'HollowCountry/Events/state/commit-2.json', json.dumps({'a': 1, 'b': 2, 'c': 3}))
        put(self.profiles, 'HollowCountry/Groups/state/%s.json' % STEAM64, '{}')

    def report(self, now='2026-11-18T10:15:30Z', **kw):
        with mock.patch.object(sr, 'utc_now', return_value=sr.parse_now(now)):
            return sr.build_report(self.profiles, **kw)

    def test_the_newest_rpt_is_read_and_an_older_one_is_not(self):
        text, info = self.report()
        self.assertNotIn('OLD RPT SHOULD NOT BE READ', text)
        self.assertIn('DayZServer_x64_2026-11-18_08-30-00.RPT', text)
        self.assertEqual(info['source'], 'DayZServer_x64_2026-11-18_08-30-00.RPT')

    def test_summary_comes_first_then_every_section(self):
        text, _ = self.report()
        headings = re.findall(r'^## (.+)$', text, re.M)
        self.assertEqual(headings[0], 'Summary')
        for section in ('Build and version', 'Mod list', 'Hollow Country lines', 'Script errors',
                        'Search Houses refusals', 'AI', 'Player connect', 'Crash and minidumps',
                        'Economy (CE) load', 'Profile state summary', 'Redaction'):
            self.assertIn(section, headings)
        self.assertLess(text.index('## Summary'), text.index('## Build and version'))

    def test_build_version_and_mod_list_are_reported(self):
        text, _ = self.report()
        self.assertIn('DayZ Server version 1.30.164289', text)
        self.assertIn('Exe timestamp: 2026/10/01', text)
        self.assertIn('@CF;@COT;@HollowCountry;@HollowCountryExpansionAI', text)

    def test_hc_lines_are_deduplicated_with_counts_and_include_the_script_log(self):
        text, info = self.report()
        self.assertRegex(text, r'x3\b.*\[HC Events\] feature ready state=idle')
        self.assertEqual(text.count('[HC Events] feature ready state=idle'), 1)
        self.assertIn('[HC Doors] ready count=12', text)
        self.assertIn('[HollowCountry] V1 admission feature=doors', text)
        self.assertIn('[HC Reach] started', text)
        self.assertEqual(info['hc_lines'], 12)

    def test_the_hc_line_list_is_capped_and_says_how_many_were_left_out(self):
        many = ''.join(' 9:00:00.000 [HC Many] distinct line %d kind=%s\n' % (i, 'z' * (i % 7)) for i in range(2000))
        put(self.profiles, 'DayZServer_x64_2026-11-19_08-30-00.RPT', many)
        os.utime(self.profiles / 'DayZServer_x64_2026-11-19_08-30-00.RPT', (3_000_000, 3_000_000))
        text, info = self.report()
        shown = [line for line in text.splitlines() if '[HC Many]' in line]
        self.assertLessEqual(len(shown), sr.HC_LINE_CAP)
        self.assertRegex(text, r'\d+ further distinct')

    def test_script_errors_keep_context_lines_and_count_repeats(self):
        text, info = self.report()
        self.assertEqual(info['script_errors'], 2)
        self.assertIn("SCRIPT    (E): Can't find variable 'x' in module 'HCDoors'", text)
        self.assertIn('before two', text)
        self.assertIn('Class:      \'HCDoors\'', text)
        self.assertIn('after three', text)
        self.assertRegex(text, r'x2\b')

    def test_search_house_refusals_are_counted_by_reason(self):
        text, info = self.report()
        self.assertEqual(info['search_refusals'], {'hands': 3, 'busy': 1})
        self.assertRegex(text, r'hands\s*\|\s*3')
        self.assertRegex(text, r'busy\s*\|\s*1')

    def test_ai_lines_cover_hc_xai_and_expansion_ai_errors(self):
        text, info = self.report()
        self.assertIn('[HC XAI] patrol site=Berezino', text)
        self.assertIn('[HC Expansion AI] lease granted', text)
        self.assertIn('ExpansionAI: eAIBase failed to find a path', text)
        self.assertGreaterEqual(info['ai_lines'], 3)

    def test_a_script_error_whose_text_is_dropped_still_counts_in_the_verdict(self):
        put(self.profiles, 'DayZServer_x64_2026-11-18_09-00-00.RPT',
            '9:00:00.000 SCRIPT    (E): NULL pointer in ParseToken\n9:00:01.000 Crash in secret handler\n')
        os.utime(self.profiles / 'DayZServer_x64_2026-11-18_09-00-00.RPT', (3_000_000, 3_000_000))
        text, info = self.report()
        self.assertNotIn('ParseToken', text)
        self.assertGreaterEqual(info['script_errors'], 1)
        self.assertNotRegex(text, r'(?i)no script errors')

    def test_player_connect_enabled_and_player_event_counts_only(self):
        text, info = self.report()
        self.assertTrue(info['player_connect_enabled'])
        self.assertRegex(text, r'Player connect enabled\W+yes')
        self.assertEqual(info['player_events'], 2)
        self.assertNotIn('Alice', text)

    def test_player_connect_enabled_is_no_when_the_line_is_missing(self):
        put(self.profiles, 'DayZServer_x64_2026-11-19_08-30-00.RPT', ' 9:00:00.000 [HC Doors] ready\n')
        os.utime(self.profiles / 'DayZServer_x64_2026-11-19_08-30-00.RPT', (3_000_000, 3_000_000))
        text, info = self.report()
        self.assertFalse(info['player_connect_enabled'])
        self.assertRegex(text, r'Player connect enabled\W+no')

    def test_crash_and_minidump_presence(self):
        text, info = self.report()
        self.assertEqual(info['minidumps'], 0)
        put(self.profiles, 'DayZServer_x64_2026-11-18_08-30-00.mdmp', b'MDMP')
        put(self.profiles, 'crash_2026.dmp', b'MDMP')
        text, info = self.report()
        self.assertEqual(info['minidumps'], 2)
        self.assertRegex(text, r'Minidump files\W+2')
        self.assertNotIn('MDMP', text)

    def test_ce_economy_lines_are_reported(self):
        text, info = self.report()
        self.assertIn('[CE][Loader] types.xml loaded, 1203 items', text)
        self.assertIn('Economy: cfgeconomycore.xml parsed', text)
        self.assertGreaterEqual(info['ce_lines'], 3)

    def test_profile_state_summaries_are_counts_never_contents(self):
        text, _ = self.report()
        section = text.split('## Profile state summary')[1].split('\n## ')[0]
        self.assertIn('HollowCountry/Events/state', section)
        self.assertRegex(section, r'HollowCountry/Events/state\s*\|\s*2\s*\|')
        self.assertIn('entries 5', section)          # 2 list items + 3 dict keys, a number and nothing else
        self.assertNotIn('EnableX', text)
        self.assertNotIn('"p"', text)
        self.assertNotIn(STEAM64, text)

    def test_the_whole_report_is_free_of_every_identifier_class(self):
        text, info = self.report()
        for needle in (STEAM64, GUID, GUID.upper(), BASE64_ID, SYNTHETIC_IP, ':2304', 'Alice', 'Wonder',
                       'S3CRET', 'Documents\\DayZ'):
            self.assertNotIn(needle, text)
        self.assertNotRegex(text, r'7656\d{13}')
        self.assertNotRegex(text, r'(?<![0-9a-fA-F])[0-9a-fA-F]{32}(?![0-9a-fA-F])')
        self.assertNotRegex(text, r'(?i)[A-Z]:\\Users\\(?!<user>)')
        self.assertGreater(sum(info['redactions'].values()), 5)
        self.assertIn('## Redaction', text)

    def test_the_report_is_never_larger_than_512_kb(self):
        self.assertEqual(sr.MAX_BYTES, 512 * 1024)
        flood = ''.join(' 9:00:00.%03d [HC Flood] %s %d %s\n' % (i % 1000, 'q' * 280, i, STEAM64)
                        for i in range(6000))
        flood += ''.join(' 9:01:00.000 SCRIPT (E): flood error %d %s\n ctx %s\n' % (i, 'w' * 300, 'c' * 300)
                         for i in range(3000))
        put(self.profiles, 'DayZServer_x64_2026-11-19_08-30-00.RPT', flood)
        os.utime(self.profiles / 'DayZServer_x64_2026-11-19_08-30-00.RPT', (3_000_000, 3_000_000))
        with mock.patch.object(sr, 'HC_LINE_CAP', 50000), mock.patch.object(sr, 'SCRIPT_BLOCK_CAP', 50000):
            text, _ = self.report()
        self.assertLessEqual(len(text.encode('utf-8')), sr.MAX_BYTES)
        self.assertNotIn(STEAM64, text)
        self.assertIn('## Summary', text)

    def test_enforce_limit_truncates_on_a_line_boundary_and_says_so(self):
        big = ''.join('line %d %s\n' % (i, 'x' * 100) for i in range(20000))
        out = sr.enforce_limit(big)
        self.assertLessEqual(len(out.encode('utf-8')), sr.MAX_BYTES)
        self.assertIn('truncated', out.splitlines()[-1])
        small = 'short\n'
        self.assertEqual(sr.enforce_limit(small), small)

    def test_the_cap_is_a_hard_limit_even_for_one_gigantic_line(self):
        giant = 'SCRIPT (E): ' + 'g' * (3 * 1024 * 1024) + '\n'
        put(self.profiles, 'DayZServer_x64_2026-11-19_08-30-00.RPT', giant)
        os.utime(self.profiles / 'DayZServer_x64_2026-11-19_08-30-00.RPT', (3_000_000, 3_000_000))
        text, _ = self.report()
        self.assertLessEqual(len(text.encode('utf-8')), sr.MAX_BYTES)

    def test_cli_writes_a_dated_markdown_file_and_prints_no_home_folder(self):
        buf = io.StringIO()
        with mock.patch.object(sr, 'utc_now', return_value=sr.parse_now('2026-11-18T10:15:30Z')), \
                contextlib.redirect_stdout(buf):
            code = sr.main(['--profiles', str(self.profiles), '--out', str(self.out)])
        self.assertEqual(code, 0, buf.getvalue())
        written = sorted(p.name for p in self.out.iterdir())
        self.assertEqual(written, ['hollow-country-report-20261118T101530Z.md'])
        self.assertNotIn(str(Path.home()) + os.sep, buf.getvalue())
        body = (self.out / written[0]).read_text(encoding='utf-8')
        self.assertTrue(body.startswith('# Hollow Country server report'))

    def test_cli_reads_the_profiles_folder_from_a_server_root(self):
        server = self.tmp / 'server'
        server.mkdir()
        os.replace(self.profiles, server / 'profiles')
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = sr.main(['--server-root', str(server), '--out', str(self.out)])
        self.assertEqual(code, 0, buf.getvalue())

    def test_cli_refuses_without_a_server_log_and_writes_nothing(self):
        empty = self.tmp / 'empty'
        empty.mkdir()
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = sr.main(['--profiles', str(empty), '--out', str(self.out)])
        self.assertEqual(code, 2)
        self.assertIn('no server RPT', err.getvalue())
        self.assertFalse(self.out.exists())

    def test_cli_never_overwrites_an_existing_report(self):
        self.out.mkdir()
        put(self.out, 'hollow-country-report-20261118T101530Z.md', 'KEEP')
        err = io.StringIO()
        with mock.patch.object(sr, 'utc_now', return_value=sr.parse_now('2026-11-18T10:15:30Z')), \
                contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = sr.main(['--profiles', str(self.profiles), '--out', str(self.out)])
        self.assertEqual(code, 2)
        self.assertEqual((self.out / 'hollow-country-report-20261118T101530Z.md').read_text(), 'KEEP')

    def test_the_tool_has_no_network_or_process_control(self):
        source = (ROOT / 'tools/setup/server_report.py').read_text(encoding='utf-8')
        for word in ('socket', 'urllib', 'http.client', 'subprocess', 'taskkill', 'getpass', 'os.system'):
            self.assertNotIn(word, source)

    def test_both_launchers_call_the_module_and_the_runner_reads_a_remembered_folder_name(self):
        bat = (ROOT / 'tools/setup/server-report.bat').read_text(encoding='utf-8')
        self.assertIn('-m tools.setup.server_report', bat)
        self.assertIn('%*', bat)
        from tools.setup import friend_install as fi
        self.assertEqual(sr.REMEMBER_FILE, fi.REMEMBER_FILE)


class RepositoryAdmissionTests(unittest.TestCase):
    """reports/friend-server/ is admitted by hygiene: a redacted .md report passes, raw logs and dumps do not."""

    def make_repo(self):
        temp = tempfile.TemporaryDirectory(prefix='hc-synthetic-report-repo-')
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        subprocess.run(['git', '-C', str(root), 'init', '-q'], check=True)
        for name in ('README.md', 'docs/SOURCES.md', 'docs/MODULE_STATUS.md', 'docs/PROVENANCE_AND_LICENSES.md'):
            put(root, name, '# Explicitly synthetic governance fixture\n')
        put(root, 'LICENSE.md', ('Copyright (c) 2026 David Addison\nAll rights reserved.\n'
                                 'No open-source or public reuse license is granted.\n'
                                 "Third-party materials remain subject to their owners' terms.\n"))
        return root

    def test_a_generated_report_passes_hygiene_and_a_raw_rpt_does_not(self):
        profiles = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__('shutil').rmtree(profiles, ignore_errors=True))
        put(profiles, 'DayZServer_x64_2026-11-18_08-30-00.RPT', rpt_text())
        text, _ = sr.build_report(profiles)
        root = self.make_repo()
        put(root, 'reports/friend-server/hollow-country-report-20261118T101530Z.md', text)
        put(root, 'reports/friend-server/README.md', (ROOT / 'reports/friend-server/README.md').read_text('utf-8'))
        subprocess.run(['git', '-C', str(root), 'add', '-A'], check=True)
        result = hygiene.check_repository(root)
        self.assertTrue(result['valid'], result['errors'])
        put(root, 'reports/friend-server/DayZServer_x64.RPT', 'raw')
        subprocess.run(['git', '-C', str(root), 'add', '-A'], check=True)
        codes = [e['code'] for e in hygiene.check_repository(root)['errors']]
        self.assertIn('restricted_path', codes)

    def test_reports_are_not_git_ignored_and_the_readme_documents_the_format(self):
        for name in ('reports/friend-server/hollow-country-report-20261118T101530Z.md',
                     'reports/friend-server/README.md'):
            done = subprocess.run(['git', '-C', str(ROOT), 'check-ignore', '-q', name])
            self.assertEqual(done.returncode, 1, name + ' must not be ignored')
        readme = (ROOT / 'reports/friend-server/README.md').read_text('utf-8')
        for word in ('hollow-country-report-', 'Summary', 'Redaction', '512', 'server-report', 'Steam64'):
            self.assertIn(word, readme)


if __name__ == '__main__':
    unittest.main()
