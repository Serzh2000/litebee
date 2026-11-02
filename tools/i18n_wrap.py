"""One-off helper of the translation work: wraps the obvious Russian texts of the components in tr().

    python -X utf8 tools/i18n_wrap.py desktop/src/renderer/src/components/Foo.tsx ...

It handles three safe shapes: an attribute (title="..." aria-label="..." placeholder="..."), a line that holds only text
between tags, and text right before or after an inline tag on one line. Everything else (strings in expressions, template
literals with ${}) is left and printed, to be done by hand.
"""
import re
import sys

CYR = r'[А-Яа-яЁё]'
ATTR = re.compile(r'\b(aria-label|title|placeholder|alt)="([^"{}]*' + CYR + r'[^"{}]*)"')


def q(text):
    return "tr('" + text.replace("\\", "\\\\").replace("'", "\\'") + "')"


def wrap_line(line, prev, nxt):
    s = line.strip()
    if not re.search(CYR, line) or s.startswith(('//', '*', '/*', '{/*', 'import ')):
        return line
    line = ATTR.sub(lambda m: f'{m.group(1)}={{{q(m.group(2))}}}', line)
    # text between tags on one line: >Текст<   (no braces inside)
    line = re.sub(r'>([^<>{}]*' + CYR + r'[^<>{}]*)<', lambda m: '>{' + q(m.group(1).strip()) + '}<' if m.group(1).strip() else m.group(0), line)
    # a text on its own line, a tag before it or after it
    s = line.strip()
    if re.search(CYR, s) and not re.search(r'[=;{}<>`$\']', s):
        before = prev.strip()
        after = nxt.strip()
        if (before.endswith('>') and not before.endswith('=>')) or after.startswith('<'):
            indent = line[: len(line) - len(line.lstrip())]
            return f'{indent}{{{q(s)}}}\n' if line.endswith('\n') else f'{indent}{{{q(s)}}}'
    # text, then an inline tag:   Открыть…<kbd>
    m = re.match(r'^(\s*)([^<>{}=;`$\']*' + CYR + r'[^<>{}=;`$\']*?)(<.*)$', line, re.S)
    if m and m.group(2).strip():
        return f'{m.group(1)}{{{q(m.group(2).strip())}}}{m.group(3)}'
    return line


def main(paths):
    for path in paths:
        lines = open(path, encoding='utf8').read().split('\n')
        out = []
        for i, line in enumerate(lines):
            out.append(wrap_line(line, lines[i - 1] if i else '', lines[i + 1] if i + 1 < len(lines) else ''))
        text = '\n'.join(out)
        if "from '@core/i18n'" not in text and 'tr(' in text:
            # the import goes after the last import line
            idx = max(m.end() for m in re.finditer(r'^import .*$', text, re.M))
            text = text[:idx] + "\nimport { tr } from '@core/i18n'" + text[idx:]
        open(path, 'w', encoding='utf8').write(text)
        left = [(n + 1, l.strip()) for n, l in enumerate(text.split('\n')) if re.search(CYR, l) and 'tr(' not in l and not l.strip().startswith(('//', '*', '/*'))]
        print(f'== {path}: {len(left)} lines left')
        for n, l in left:
            print(f'   {n}: {l[:130]}')


if __name__ == '__main__':
    main(sys.argv[1:])
