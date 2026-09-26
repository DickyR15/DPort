from __future__ import annotations

from pathlib import Path
import re

UPDATER = Path('src/dport_release_updater.py')
HELPER = Path('src/dport_updater_helper.py')

if not UPDATER.exists():
    raise SystemExit(f'Missing updater source: {UPDATER}')
if not HELPER.exists():
    raise SystemExit(f'Missing updater helper source: {HELPER}')

text = UPDATER.read_text(encoding='utf-8')
original = text

def add_import(source: str, import_line: str) -> str:
    if import_line not in source:
        return import_line + '\n' + source
    return source

text = add_import(text, 'import hashlib')
text = add_import(text, 'import sys')

state_old = '    "current_version": None,\n    "latest_version": None,\n'
state_new = '    "current_version": None,\n    "latest_version": None,\n'
# State fields are intentionally not changed; SHA is calculated on demand.

current_sha_fn = '''def _current_exe_sha256() -> str:
    """Return the SHA-256 of the running DPort EXE, or empty in source mode."""
    if not getattr(sys, 'frozen', False):
        return ''
    try:
        path = Path(sys.executable).resolve()
        digest = hashlib.sha256()
        with path.open('rb') as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                digest.update(chunk)
        return digest.hexdigest()
    except Exception as exc:
        LOGGER.debug('Unable to calculate current DPort SHA-256: %s', exc)
        return ''


def _release_exe_sha256(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'DPort-Updater', 'Cache-Control': 'no-cache', 'Pragma': 'no-cache'},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode('utf-8', errors='replace')
    for token in raw.split():
        if len(token) == 64 and all(ch in '0123456789abcdefABCDEF' for ch in token):
            return token.lower()
    raise RuntimeError('Release SHA-256 checksum file is invalid')
'''

if 'def _current_exe_sha256(' not in text:
    marker = 'def _github_json('
    if marker not in text:
        raise SystemExit('Could not find _github_json insertion point.')
    text = text.replace(marker, current_sha_fn + '\n\n' + marker, 1)

# Rename the existing version-only candidate implementation once.
if 'def _get_update_candidate_version_only(' not in text:
    old = 'def _get_update_candidate('
    if old not in text:
        raise SystemExit('Existing _get_update_candidate function not found.')
    text = text.replace(old, 'def _get_update_candidate_version_only(', 1)

wrapper = '''def _get_update_candidate(current: str, current_sha256: str = '') -> tuple[str, str, str, str] | None:
    # First preserve the original newer-version behavior unchanged.
    candidate = _get_update_candidate_version_only(current)
    if candidate is not None:
        return candidate

    # Same-version build refresh: only when the running EXE hash is known.
    if not current_sha256:
        return None

    data = _github_json(RELEASE_API + f'?dport_cache_bust={time.time_ns()}')
    if data.get('draft') or data.get('prerelease'):
        return None
    release = _find_release_assets(data)
    if release is None:
        return None
    tag, exe_url, sha_url = release
    if _version_key(tag) != _version_key(current):
        return None
    remote_sha256 = _release_exe_sha256(sha_url)
    if remote_sha256 == current_sha256:
        return None
    return tag.lstrip('v'), exe_url, sha_url, str(data.get('html_url') or '')
'''

if 'def _get_update_candidate(current: str, current_sha256: str = \'\')' not in text:
    marker = 'def check_now('
    if marker not in text:
        marker = 'def run_update('
    if marker not in text:
        raise SystemExit('Could not find updater runtime insertion point.')
    text = text.replace(marker, wrapper + '\n\n' + marker, 1)

# Modify check_now so the wrapper receives the local EXE hash.
pattern = re.compile(r'current\s*=\s*_bundled_version\(\)\s*\n\s*try:\s*\n\s*candidate\s*=\s*_get_update_candidate\(current\)')
replacement = 'current = _bundled_version()\n    current_sha256 = _current_exe_sha256()\n    try:\n        candidate = _get_update_candidate(current, current_sha256)'
text, hits = pattern.subn(replacement, text, count=1)
if hits != 1:
    raise SystemExit('Could not connect SHA-aware candidate check to check_now().')

UPDATER.write_text(text, encoding='utf-8')

print(f'Updater changed: {text != original}')
print('SHA-aware same-version update support installed.')
print('Normal newer-version update logic remains delegated to the original candidate function.')