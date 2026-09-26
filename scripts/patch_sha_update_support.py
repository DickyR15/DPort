from __future__ import annotations

from pathlib import Path
import re

UPDATER = Path("src/dport_release_updater.py")
HELPER = Path("src/dport_updater_helper.py")

if not UPDATER.exists():
    raise SystemExit(f"Missing updater source: {UPDATER}")
if not HELPER.exists():
    raise SystemExit(f"Missing updater helper source: {HELPER}")

text = UPDATER.read_text(encoding="utf-8")
original = text

def replace_function(source: str, name: str, replacement: str) -> str:
    pattern = re.compile(rf"(?ms)^def {re.escape(name)}\b.*?(?=^def \w+\b|^class \w+\b|^if __name__|\Z)")
    match = pattern.search(source)
    if not match:
        raise SystemExit(f"Function not found: {name}")
    return source[:match.start()] + replacement.rstrip() + "\n\n" + source[match.end():]

for import_line in ("import hashlib", "import sys"):
    if import_line not in text:
        insert_at = text.find("\n") + 1
        text = text[:insert_at] + import_line + "\n" + text[insert_at:]

text = text.replace(
'''    "current_version": None,
    "latest_version": None,
''',
'''    "current_version": None,
    "current_sha256": None,
    "latest_version": None,
    "latest_sha256": None,
''',
1)

helper_functions = r'''def _current_exe_sha256() -> str:
    """Return the SHA-256 of the running DPort EXE."""
    if not getattr(sys, "frozen", False):
        return ""
    try:
        path = Path(sys.executable).resolve()
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except Exception as exc:
        LOGGER.debug("Unable to calculate current DPort SHA-256: %s", exc)
        return ""


def _read_release_sha256(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "DPort-Updater", "Cache-Control": "no-cache", "Pragma": "no-cache"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    for token in raw.replace("\\r", " ").replace("\\n", " ").split():
        if len(token) == 64 and all(c in "0123456789abcdefABCDEF" for c in token):
            return token.lower()
    raise RuntimeError("Release SHA-256 checksum file is invalid")
'''

if "def _current_exe_sha256" not in text:
    marker = "def _github_json("
    if marker not in text:
        raise SystemExit("Updater insertion point not found: _github_json")
    text = text.replace(marker, helper_functions + "\n\n" + marker, 1)

candidate = r'''def _get_update_candidate(current: str, current_sha256: str) -> tuple[str, str, str, str, str] | None:
    data = _github_json(RELEASE_API + f"?dport_cache_bust={time.time_ns()}")
    if data.get("draft") or data.get("prerelease"):
        return None

    release = _find_release_assets(data)
    if release is None:
        raise RuntimeError("最新正式 Release 沒有可用的 DPort EXE")

    tag, exe_url, sha_url = release
    remote_sha256 = _read_release_sha256(sha_url)
    latest_key = _version_key(tag)
    current_key = _version_key(current)

    if latest_key > current_key:
        return tag.lstrip("v"), exe_url, sha_url, str(data.get("html_url") or ""), remote_sha256

    if latest_key == current_key and current_sha256 and remote_sha256 != current_sha256:
        return tag.lstrip("v"), exe_url, sha_url, str(data.get("html_url") or ""), remote_sha256

    return None
'''
text = replace_function(text, "_get_update_candidate", candidate)

text = re.sub(
    r"current\s*=\s*_bundled_version\(\)\s*\n\s*try:\s*\n\s*candidate\s*=\s*_get_update_candidate\(current\)",
    "current = _bundled_version()\n    current_sha256 = _current_exe_sha256()\n    try:\n        candidate = _get_update_candidate(current, current_sha256)",
    text,
    count=1,
)

handling = r'''        if candidate is None:
            with _LOCK:
                _STATE["state"] = "latest"
                _STATE["latest_version"] = current
                _STATE["latest_sha256"] = current_sha256 or None
                _STATE["message"] = f"DPort v{current} 已是最新正式版"
                _STATE["restart_required"] = False
        else:
            version, exe_url, sha_url, release_url, remote_sha256 = candidate
            same_version_build = _version_key(version) == _version_key(current)
            with _LOCK:
                _STATE["state"] = "update_available"
                _STATE["latest_version"] = version
                _STATE["latest_sha256"] = remote_sha256
                _STATE["latest_url"] = release_url
                _STATE["message"] = (
                    f"DPort v{version} 有新的修正版，準備自動更新…"
                    if same_version_build
                    else f"發現 DPort 新版 v{version}，準備自動更新…"
                )
'''
pattern = re.compile(r"(?ms)^        if candidate is None:.*?(?=^        [A-Za-z_][A-Za-z0-9_]*\(|^def \w+\b|\Z)")
m = pattern.search(text)
if not m:
    raise SystemExit("Updater candidate handling block not found")
text = text[:m.start()] + handling.rstrip() + "\n" + text[m.end():]

if 'current_sha256 = _current_exe_sha256()' not in text:
    raise SystemExit('Current SHA integration was not inserted.')

text = text.replace(
'''            _STATE["current_version"] = current
            _STATE["checked_at"] = time.time()
''',
'''            _STATE["current_version"] = current
            _STATE["current_sha256"] = current_sha256 or None
            _STATE["checked_at"] = time.time()
''',
1)

UPDATER.write_text(text, encoding="utf-8")

helper_text = HELPER.read_text(encoding="utf-8")
helper_text = helper_text.replace(
    'raise RuntimeError("DPort EXE SHA-256 驗證失敗")',
    'raise RuntimeError("DPort EXE SHA-256 驗證失敗，已取消更新以保護現有版本")',
    1,
)
HELPER.write_text(helper_text, encoding="utf-8")

print(f"Updater changed: {text != original}")
print("SHA-aware same-version update support installed.")