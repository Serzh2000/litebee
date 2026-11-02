"""Lists the Russian texts of the interface that go through tr(): what the English table has to know.

    python -X utf8 tools/i18n_keys.py [--missing]

With --missing only the texts without an English entry are printed (the entries are read from desktop/src/core/i18n/*.ts).
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'desktop', 'src')
CYR = re.compile('[А-Яа-яЁё]')


def used():
    keys = {}
    for f in glob.glob(os.path.join(SRC, '**', '*.ts*'), recursive=True):
        norm = f.replace(os.sep, '/')
        if '/core/i18n/' in norm:
            continue
        s = open(f, encoding='utf8').read()
        for m in re.finditer(r"\btr\(\s*'((?:[^'\\]|\\.)*)'", s):
            text = m.group(1).replace("\\'", "'").replace('\\\\', '\\')
            if CYR.search(text):
                keys.setdefault(text, os.path.basename(f))
    return keys


def known():
    have = set()
    for f in glob.glob(os.path.join(SRC, 'core', 'i18n', '*.ts')):
        s = open(f, encoding='utf8').read()
        for m in re.finditer(r"\[\s*'((?:[^'\\]|\\.)*)'\s*,", s):
            have.add(m.group(1).replace("\\'", "'").replace('\\\\', '\\'))
        for m in re.finditer(r'\[\s*"((?:[^"\\]|\\.)*)"\s*,', s):
            have.add(m.group(1))
    return have


if __name__ == '__main__':
    keys = used()
    if '--missing' in sys.argv:
        have = known()
        keys = {k: v for k, v in keys.items() if k not in have}
    print(len(keys), 'texts', file=sys.stderr)
    for k, v in keys.items():
        print(f'{v}\t{k}')
