from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SK_PATTERN = re.compile(r"sk-[A-Za-z0-9_-]{10,}")
HIGH_ENTROPY_PATTERN = re.compile(r"\b[A-Za-z0-9_\-=/+]{30,}\b")
SKIP_FILES = {'.env.example', 'uv.lock'}
SKIP_PATTERNS = [
    re.compile(r'https?://'),
    re.compile(r'file://'),
    re.compile(r'^\s*(def |async def |class )'),
    re.compile(r'field\(default_factory'),
    re.compile(r'^\s*#'),
    re.compile(r'import '),
    re.compile(r'from '),
    re.compile(r'\w+:$'),
    re.compile(r'test_\w+'),
]


def staged_files() -> list[Path]:
    result = subprocess.run(
        ['git', 'diff', '--cached', '--name-only', '--diff-filter=ACMR'],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [ROOT / line.strip() for line in result.stdout.splitlines() if line.strip()]


def is_suspicious_line(line: str) -> bool:
    if SK_PATTERN.search(line):
        return True
    if any(p.search(line) for p in SKIP_PATTERNS):
        return False
    matches = HIGH_ENTROPY_PATTERN.findall(line)
    for token in matches:
        if token.startswith('http'):
            continue
        if '/' in token or ':' in token:
            continue
        if all(char in '0123456789abcdef' for char in token.lower()):
            continue
        return True
    return False


def main() -> None:
    flagged: list[str] = []
    for path in staged_files():
        if not path.is_file():
            continue
        if path.name in SKIP_FILES:
            continue
        try:
            text = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith('#'):
                continue
            if is_suspicious_line(stripped):
                flagged.append(f'{path.relative_to(ROOT)}:{lineno}')
    if flagged:
        raise SystemExit('Secret scan failed on: ' + ', '.join(flagged))
    print('secret scan OK')


if __name__ == '__main__':
    main()
