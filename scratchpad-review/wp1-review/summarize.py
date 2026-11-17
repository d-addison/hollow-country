from collections import Counter
from pathlib import Path
import re
OUT = Path(__file__).resolve().parent
for name in ['focused', 'discover', 'discover-copy', 'compile-shapes', 'review-checks', 'mutation-baseline']:
    text = (OUT / (name + '.log')).read_text()
    print(name + ':')
    for line in text.splitlines():
        if line.startswith(('Ran ', 'OK', 'FAILED (')): print('  ' + line)
    if name.startswith('discover'):
        errors = re.findall(r'^(?:[\w.]*Error|AssertionError): (.+)$', text, re.M)
        print('  terminal diagnostic frequencies (may include subtests):')
        for message, count in Counter(errors).most_common():
            print('   ', count, message[:200])
