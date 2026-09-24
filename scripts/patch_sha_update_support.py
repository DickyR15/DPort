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

# Persist the local EXE fingerprint in updater state.
text = text.replace(
'''    "current_version": None,
    "latest_version": None,
''',
'''    "current_version": None,
    "current_sha256": None,
    "latest_version": None,
    "latest_sha256": None,
''',
1,
)

# Add a local SHA-256 calculator after _bundled_version().
marker = '''def _github_json(url: str) -> dict[str, Any]:
'''
helper = '''def _current_exe_sha256() -> str:
    """Return the SHA-256 of the running DPort EXE.

    In a frozen build sys.executable is the DPort executable itself. In
    development/source mode, skip this check rather than hashing python.exe.
    """
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
        headers={
            "User-Agent": "DPort-Updater",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    for token in raw.replace("\r", " ").replace("\n", " ").split():
        if len(token) == 64 and all(c in "0123456789abcdefABCDEF" for c in token):
            return token.lower()
    raise RuntimeError("Release SHA-256 checksum file is invalid")


'''
if "_current_exe_sha256()" not in text and marker in text:
    text = text.replace(marker, helper + marker, 1)

# Replace the version-only candidate logic with version + SHA logic.
old_candidate = re.compile(
    r'''def _get_update_candidate\(current: str\) -> tuple\[str, str, str, str\] \| None:\n'''
    r'''    data = _github_json\(RELEASE_API \+ f"\?dport_cache_bust=\{time\.time_ns\(\)\}"\)\n'''
    r'''    if data\.get\("draft"\) or data\.get\("prerelease"\):\n'''
    r'''        return None\n'''
    r'''    release = _find_release_assets\(data\)\n'''
    r'''    if release is None:\n'''
    r'''        raise RuntimeError\("最新正式 Release 沒有可用的 DPort EXE"\)\n'''
    r'''    tag, exe_url, sha_url = release\n'''
    r'''    if _version_key\(tag\) <= _version_key\(current\):\n'''
    r'''        return None\n'''
    r'''    return tag\.lstrip\("v"\), exe_url, sha_url, str\(data\.get\("html_url"\) or ""\)\n'''
)
new_candidate = '''def _get_update_candidate(
    current: str,
    current_sha256: str,
) -> tuple[str, str, str, str, str] | None:
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

    # Normal upgrade: newer semantic version.
    if latest_key > current_key:
        return (
            tag.lstrip("v"),
            exe_url,
            sha_url,
            str(data.get("html_url") or ""),
            remote_sha256,
        )

    # Same version: treat a different Release EXE SHA-256 as a new build.
    # This lets Dicky republish v6.9.1 with fixes without forcing a version bump.
    if latest_key == current_key and current_sha256:
        if remote_sha256 != current_sha256:
            return (
                tag.lstrip("v"),
                exe_url,
                sha_url,
                str(data.get("html_url") or ""),
                remote_sha256,
            )

    return None
'''
text, candidate_hits = old_candidate.subn(new_candidate, text, count=1)
if candidate_hits != 1:
    raise SystemExit("Version-only update candidate block not found.")

# Add the local SHA calculation to check_now().
text = text.replace(
'''    current = _bundled_version()
    try:
        candidate = _get_update_candidate(current)
''',
'''    current = _bundled_version()
    current_sha256 = _current_exe_sha256()
    try:
        candidate = _get_update_candidate(current, current_sha256)
''',
1,
)

# Persist current SHA when checking.
text = text.replace(
'''            _STATE["current_version"] = current
            _STATE["checked_at"] = time.time()
''',
'''            _STATE["current_version"] = current
            _STATE["current_sha256"] = current_sha256 or None
            _STATE["checked_at"] = time.time()
''',
1,
)

# Same-version content update gets a distinct message.
text = text.replace(
'''        if candidate is None:
            with _LOCK:
                _STATE["state"] = "latest"
                _STATE["latest_version"] = current
                _STATE["message"] = f"DPort v{current} 已是最新正式版"
                _STATE["restart_required"] = False
        else:
            version, exe_url, sha_url, release_url = candidate
            with _LOCK:
                _STATE["state"] = "update_available"
                _STATE["latest_version"] = version
                _STATE["latest_url"] = release_url
                _STATE["message"] = f"發現 DPort 新版 v{version}，準備自動更新…"
''',
'''        if candidate is None:
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
''',
1,
)

# Offline status keeps the local fingerprint too.
text = text.replace(
'''            _STATE["checked_at"] = time.time()
            _STATE["current_version"] = current
''',
'''            _STATE["checked_at"] = time.time()
            _STATE["current_version"] = current
            _STATE["current_sha256"] = current_sha256 or None
''',
1,
)

UPDATER.write_text(text, encoding="utf-8")

# The helper already downloads in streaming chunks and verifies SHA-256, which
# is exactly what the same-version update needs. Add a clearer error message
# only; no behavior change is required.
helper_text = HELPER.read_text(encoding="utf-8")
helper_text = helper_text.replace(
    'raise RuntimeError("DPort EXE SHA-256 驗證失敗")',
    'raise RuntimeError("DPort EXE SHA-256 驗證失敗，已取消更新以保護現有版本")',
    1,
)
HELPER.write_text(helper_text, encoding="utf-8")

print(f"Updater changed: {text != original}")
print(f"Version+SHA candidate logic inserted: {candidate_hits}")
print("Same-version Release EXE SHA-256 differences now trigger updates.")
print("Existing helper continues to stream-download and verify the final EXE.")
