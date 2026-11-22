"""Original compat stringtable.csv for GUI keys that dependencies reference but never define.

compat_strings.json holds only our own wording for each key. compat_addon.py packs
the generated stringtable.csv into the compat addon. No dependency text is copied.

Usage:
  python3 -B -m tools.package.compat_stringtable --out <new-file>
  python3 -B -m tools.package.compat_stringtable --rpt <RPT> [--rpt <RPT> ...]

The second form lists the STR_* keys an RPT reports as missing and which of them
compat_strings.json does not yet cover. It prints keys and counts only.
"""
import argparse
import csv
import io
import json
from pathlib import Path
import re
import sys

from tools.audit import rpt_config_audit

ROOT = Path(__file__).resolve().parents[2]
STRINGS = Path(__file__).with_name('compat_strings.json')
SCHEMA = 1
LOCALIZATION_CATEGORY = 12
KEY = re.compile(r'STR_[A-Za-z0-9_]+')
KEY_IN_LINE = re.compile(r'\$?(STR_[A-Za-z0-9_]+)', re.I)
MAX_KEYS = 4096
MAX_KEY = 128
MAX_TEXT = 512
# Header of the vanilla DayZ stringtable.csv; every language column carries our text.
LANGUAGES = ('original', 'english', 'czech', 'german', 'russian', 'polish', 'hungarian',
             'italian', 'spanish', 'french', 'chinese', 'japanese', 'portuguese', 'chinesesimp')
HEADER = ('Language',) + LANGUAGES


def load(path=STRINGS):
    """Return validated (key, text) pairs sorted by key; raise ValueError when invalid."""
    data = json.loads(Path(path).read_bytes())
    if not isinstance(data, dict) or data.get('schema') != SCHEMA:
        raise ValueError('compat strings: unsupported schema')
    rows = data.get('strings')
    if not isinstance(rows, list) or len(rows) > MAX_KEYS:
        raise ValueError('compat strings: strings must be a bounded list')
    seen, pairs = set(), []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'key', 'text'}:
            raise ValueError('compat strings: each row needs exactly key and text')
        key, text = row['key'], row['text']
        if not isinstance(key, str) or not KEY.fullmatch(key) or len(key) > MAX_KEY:
            raise ValueError('compat strings: invalid key')
        if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT:
            raise ValueError('compat strings: invalid text for ' + key)
        if any(ord(c) < 32 for c in text):
            raise ValueError('compat strings: control character in text for ' + key)
        if key.casefold() in seen:
            raise ValueError('compat strings: duplicate key ' + key)
        seen.add(key.casefold())
        pairs.append((key, text))
    return sorted(pairs, key=lambda pair: (pair[0].casefold(), pair[0]))


def render(pairs):
    """Deterministic stringtable.csv bytes (CRLF as the engine tools write), or None when empty."""
    if not pairs:
        return None
    out = io.StringIO(newline='')
    writer = csv.writer(out, quoting=csv.QUOTE_ALL, lineterminator='\r\n')
    writer.writerow(HEADER)
    for key, text in pairs:
        writer.writerow((key,) + (text,) * len(LANGUAGES))
    return out.getvalue().encode('utf-8')


def build(path=STRINGS):
    """Return (stringtable bytes or None, sorted keys)."""
    pairs = load(path)
    return render(pairs), [key for key, _ in pairs]


def missing_keys(rpt_paths):
    """STR_* keys named on RPT localization diagnostics (category 12), lower-cased."""
    rule = rpt_config_audit.category_rules()[LOCALIZATION_CATEGORY]
    found = {}
    for path in rpt_paths:
        with Path(path).open(encoding='utf-8-sig', errors='replace') as stream:
            while True:
                line = stream.readline(rpt_config_audit.MAX_LINE + 1)
                if not line:
                    break
                if len(line) > rpt_config_audit.MAX_LINE:
                    while line and not line.endswith('\n'):
                        line = stream.readline(rpt_config_audit.MAX_LINE + 1)
                    continue
                if not rule.search(line):
                    continue
                for key in KEY_IN_LINE.findall(line):
                    found.setdefault(key.casefold(), key)
                    if len(found) > MAX_KEYS:
                        raise ValueError('too many distinct missing keys')
    return sorted(found.values(), key=str.casefold)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--strings', type=Path, default=STRINGS)
    parser.add_argument('--out', type=Path, help='new stringtable.csv path; existing output is refused')
    parser.add_argument('--rpt', type=Path, action='append', default=[],
                        help='report missing keys that compat_strings.json does not cover')
    args = parser.parse_args(argv)
    if not args.out and not args.rpt:
        parser.error('give --out and/or --rpt')
    try:
        blob, keys = build(args.strings)
        if args.rpt:
            missing = missing_keys(args.rpt)
            covered = {key.casefold() for key in keys}
            uncovered = [key for key in missing if key.casefold() not in covered]
            print(f'compat_stringtable: missing={len(missing)} covered={len(missing) - len(uncovered)} '
                  f'uncovered={len(uncovered)}')
            for key in uncovered:
                print('uncovered ' + key)
        if args.out:
            if args.out.exists():
                parser.exit(1, 'compat_stringtable: output already exists\n')
            if blob is None:
                print('compat_stringtable: no strings defined; nothing written')
            else:
                args.out.write_bytes(blob)
                print(f'compat_stringtable: wrote {len(keys)} keys')
    except (OSError, ValueError) as error:
        reason = str(error) if isinstance(error, ValueError) else 'input/output failed'
        parser.exit(1, 'compat_stringtable: ' + reason + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
