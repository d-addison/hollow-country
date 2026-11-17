"""Execute authored clock methods with explicit synthetic native UTC reads.

The adapters provide only the native component output parameters. Python's UTC
calendar is an independent result oracle, not a replacement clock algorithm.
No test here establishes native timing, RPC or persistent-schema acceptance.
"""
from datetime import datetime, timezone
from calendar import monthrange
from pathlib import Path
import re
import unittest


SOURCE = (Path(__file__).resolve().parents[2] /
          'mods/HollowCountry/scripts/4_World/Groups/HCGroupService.c')


def method_body(text, start):
    depth, end = 1, start
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end-1]


class SyntheticUTC:
    def __init__(self, dates=(), times=()):
        self.dates = iter(dates)
        self.times = iter(times)
        self.calls = []

    def date(self):
        self.calls.append('date')
        return next(self.dates)

    def time(self):
        self.calls.append('time')
        return next(self.times)


def authored_clock(native):
    source = SOURCE.read_text(encoding='utf-8')
    start = re.search(r'class HCGroupClock\s*\{', source)
    source = re.sub(r'//[^\n]*', '', method_body(source, start.end()))
    env = {'GetYearMonthDayUTC': native.date,
           'GetHourMinuteSecondUTC': native.time}
    for field, value in re.findall(r'(?:protected )?static (?:const )?int (\w+)\s*=\s*(-?\d+)\s*;', source):
        env[field] = int(value)
    for match in re.finditer(r'static (?:bool|int) (\w+)\(([^)]*)\)\s*\{', source):
        args = [arg.strip().split()[-1] for arg in match[2].split(',') if arg.strip()]
        statements = method_body(source, match.end())
        # Expand the original implementation's C for loops as language syntax.
        statements = re.sub(r'for \(int (\w+) = (\d+); \1 < (\w+); \1\+\+\)',
                            r'foreach (int \1 : range(\2, \3))', statements)
        # Both old/native-facing implementations contain compact single guards.
        cursor = 0
        while True:
            guard = statements.find('if (', cursor)
            if guard < 0:
                break
            end, depth = guard + 4, 1
            while depth:
                depth += (statements[end] == '(') - (statements[end] == ')')
                end += 1
            following = end
            while statements[following].isspace():
                following += 1
            if statements[following] != '{':
                finish = statements.index(';', following) + 1
                statements = statements[:end] + ' {' + statements[end:finish] + ' }' + statements[finish:]
            cursor = end + 2
        lines = [f'def {match[1]}({", ".join(args)}):']
        fields = [key for key in env if key.startswith('s_')]
        if fields:
            lines.append('    global ' + ', '.join(fields))
        indent = 1
        for token in re.split(r'([{};])', statements):
            token = token.strip()
            if not token or token == ';':
                continue
            if token == '{':
                indent += 1
                continue
            if token == '}':
                indent -= 1
                continue
            declaration = re.fullmatch(r'int ([\w, ]+)', token)
            if declaration:
                token = ' = '.join(declaration[1].replace(' ', '').split(',')) + ' = 0'
            else:
                token = re.sub(r'\b(?:int|bool)\s+(?=\w+\s*=)', '', token)
            native_call = re.fullmatch(r'(GetYearMonthDayUTC|GetHourMinuteSecondUTC)\(([^)]+)\)', token)
            if native_call:
                token = native_call[2] + ' = ' + native_call[1] + '()'
            token = token.replace('HCGroupClock.', '').replace('&&', ' and ').replace('||', ' or ')
            token = re.sub(r'!(?!=)', 'not ', token)
            token = re.sub(r'\btrue\b', 'True', token)
            token = re.sub(r'\bfalse\b', 'False', token)
            token = re.sub(r'(\w+)\+\+$', r'\1 += 1', token)
            if token.startswith(('if (', 'while (')):
                prefix, expression = token.split(' (', 1)
                token = prefix + ' ' + expression[:-1] + ':'
            elif token.startswith('foreach ('):
                loop = re.fullmatch(r'foreach \(int (\w+) : (.+)\)', token)
                token = 'for ' + loop[1] + ' in ' + loop[2] + ':'
            elif token == 'else':
                token += ':'
            lines.append('    ' * indent + token)
        exec(compile('\n'.join(lines), str(SOURCE) + ':' + match[1], 'exec'), env)
    return env


def epoch(year, month, day, hour=0, minute=0, second=0):
    return int(datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc).timestamp())


class GroupClockTests(unittest.TestCase):
    def test_consistent_snapshot_reads_date_time_date_and_returns_exact_seconds(self):
        native = SyntheticUTC([(2026,11,16)] * 2, [(19,30,45)])
        self.assertEqual(epoch(2026,11,16,19,30,45), authored_clock(native)['Utc']())
        self.assertEqual(['date','time','date'], native.calls)

    def test_midnight_tear_retries_and_uses_new_complete_snapshot(self):
        for before,after in [((2028,2,28),(2028,2,29)),
                             ((2030,12,31),(2031,1,1))]:
            with self.subTest(before=before,after=after):
                native = SyntheticUTC([before,after,after,after],[(0,0,0),(0,0,1)])
                self.assertEqual(epoch(*after,0,0,1), authored_clock(native)['Utc']())
                self.assertEqual(['date','time','date'] * 2, native.calls)

    def test_midnight_retry_exhaustion_is_bounded_to_two_attempts(self):
        native = SyntheticUTC([(2026,11,16),(2026,11,17),(2026,11,17),(2026,11,18)],
                              [(0,0,0),(0,0,0)])
        self.assertEqual(-1, authored_clock(native)['Utc']())
        self.assertEqual(['date','time','date'] * 2, native.calls)

    def test_backward_date_inside_snapshot_fails_without_retry(self):
        native = SyntheticUTC([(2026,11,17),(2026,11,16)], [(23,59,59)])
        self.assertEqual(-1, authored_clock(native)['Utc']())
        self.assertEqual(['date','time','date'], native.calls)

    def test_rollback_between_calls_rejects_without_rewinding_watermark(self):
        native = SyntheticUTC([(2026,11,16)] * 8,
                              [(12,0,10),(12,0,9),(12,0,10),(12,0,11)])
        clock = authored_clock(native)
        self.assertEqual(epoch(2026,11,16,12,0,10), clock['Utc']())
        self.assertEqual(-1, clock['Utc']())
        self.assertEqual(epoch(2026,11,16,12,0,10), clock['Utc']())
        self.assertEqual(epoch(2026,11,16,12,0,11), clock['Utc']())

    def test_invalid_calendar_days_and_time_components_are_rejected(self):
        for date in [(2027,2,29),(2028,2,30),(2026,4,31),(2026,0,1),(2026,13,1),(2026,1,0),(2026,1,32)]:
            with self.subTest(date=date):
                native = SyntheticUTC([date,date], [(0,0,0)])
                self.assertEqual(-1, authored_clock(native)['Utc']())
        for time in [(-1,0,0),(24,0,0),(0,-1,0),(0,60,0),(0,0,-1),(0,0,60)]:
            with self.subTest(time=time):
                native = SyntheticUTC([(2026,11,16)] * 2, [time])
                self.assertEqual(-1, authored_clock(native)['Utc']())

    def test_invalid_or_backward_bracket_cannot_advance_accepted_watermark(self):
        native = SyntheticUTC([(2026,11,16),(2026,11,16),
                               (2026,11,17),(2026,11,16),
                               (2026,11,17),(2026,11,31),
                               (2026,11,16),(2026,11,16)],
                              [(12,0,10),(23,59,59),(23,59,59),(12,0,11)])
        clock = authored_clock(native)
        self.assertEqual(epoch(2026,11,16,12,0,10),clock['Utc']())
        self.assertEqual(-1,clock['Utc']())
        self.assertEqual(-1,clock['Utc']())
        self.assertEqual(epoch(2026,11,16,12,0,11),clock['Utc']())

    def test_gregorian_century_rules_and_all_admitted_month_ends(self):
        native = SyntheticUTC()
        clock = authored_clock(native)
        self.assertFalse(clock['LeapYear'](1900))
        self.assertTrue(clock['LeapYear'](2000))
        self.assertFalse(clock['LeapYear'](2100))
        for year in range(2026,2033):
            for month in range(1,13):
                day = monthrange(year,month)[1]
                self.assertEqual(day,clock['DaysInMonth'](year,month))
                self.assertEqual(epoch(year,month,day,23,59,59),
                                 clock['CalendarUtc'](year,month,day,23,59,59))
                self.assertEqual(-1,clock['CalendarUtc'](year,month,day+1,0,0,0))

    def test_positive_epoch_range_reaches_native_signed_int_ceiling(self):
        for stamp in (1, 86399, 86400, epoch(2000,2,29,12,34,56),
                      epoch(2025,12,31,23,59,59), epoch(2033,1,1),
                      1989999999, 1990000000, 1990000001, 2000000000,
                      2147483646, 2147483647):
            with self.subTest(stamp=stamp):
                date = datetime.fromtimestamp(stamp, timezone.utc)
                native = SyntheticUTC([(date.year,date.month,date.day)] * 2,
                                      [(date.hour,date.minute,date.second)])
                self.assertEqual(stamp, authored_clock(native)['Utc']())
        for stamp in (2147483648, 2147483649, epoch(2038,12,31)):
            with self.subTest(rejected_stamp=stamp):
                date = datetime.fromtimestamp(stamp, timezone.utc)
                native = SyntheticUTC([(date.year,date.month,date.day)] * 2,
                                      [(date.hour,date.minute,date.second)])
                self.assertEqual(-1, authored_clock(native)['Utc']())

    def test_epoch_zero_is_calendar_only_and_does_not_advance_watermark(self):
        native = SyntheticUTC([(1970,1,1)] * 6,
                              [(0,0,1),(0,0,0),(0,0,2)])
        clock = authored_clock(native)
        self.assertEqual(0, clock['CalendarUtc'](1970,1,1,0,0,0))
        self.assertEqual(1, clock['Utc']())
        self.assertEqual(-1, clock['Utc']())
        self.assertEqual(2, clock['Utc']())

    def test_all_admitted_calendar_month_ends_match_independent_utc(self):
        clock = authored_clock(SyntheticUTC())
        for year in range(1970,2039):
            for month in range(1,13):
                day = monthrange(year,month)[1]
                expected = epoch(year,month,day,23,59,59)
                if expected > 2147483647:
                    expected = -1
                self.assertEqual(expected, clock['CalendarUtc'](
                    year,month,day,23,59,59))
        for year in (-2147483648, -1, 0, 1969, 2039, 2147483647):
            self.assertEqual(-1, clock['CalendarUtc'](year,1,1,0,0,0))

    def test_upper_ceiling_does_not_poison_last_accepted_second(self):
        date = (2038,1,19)
        native = SyntheticUTC([date] * 8,
                              [(3,14,6),(3,14,8),(3,14,7),(3,14,7)])
        clock = authored_clock(native)
        self.assertEqual(2147483646, clock['Utc']())
        self.assertEqual(-1, clock['Utc']())
        self.assertEqual(2147483647, clock['Utc']())
        self.assertEqual(2147483647, clock['Utc']())

    def test_extended_range_keeps_bounded_midnight_retry(self):
        for before, after in (((1999,12,31),(2000,1,1)),
                              ((2032,12,31),(2033,1,1))):
            native = SyntheticUTC([before,after,after,after],
                                  [(0,0,0),(0,0,1)])
            self.assertEqual(epoch(*after,0,0,1),
                             authored_clock(native)['Utc']())
            self.assertEqual(['date','time','date'] * 2, native.calls)


if __name__ == '__main__':
    unittest.main()
