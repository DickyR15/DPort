from __future__ import annotations

from pathlib import Path
import re


def remove_same_version_sha_update(updater: Path) -> bool:
    text = updater.read_text(encoding="utf-8")
    original = text

    # Remove the local/current SHA fields that were introduced solely for
    # same-version update detection.
    text = text.replace(
        '    "current_version": None,\n'
        '    "current_sha256": None,\n'
        '    "latest_version": None,\n'
        '    "latest_sha256": None,\n',
        '    "current_version": None,\n'
        '    "latest_version": None,\n',
        1,
    )

    # Remove SHA helpers if present.
    text = re.sub(
        r'\n\ndef _current_exe_sha256\(\) -> str:\n.*?\n\ndef _github_json',
        '\n\ndef _github_json',
        text,
        flags=re.S,
    )

    # Remove remote SHA reading helper if present.
    text = re.sub(
        r'\n\ndef _read_release_sha256\(url: str\) -> str:\n.*?(?=\n\ndef _github_json|\n\ndef [A-Za-z_] )',
        '\n',
        text,
        flags=re.S,
    )

    # Replace SHA-aware candidate function with version-only candidate logic.
    candidate = re.compile(
        r'def _get_update_candidate\([\s\S]*?\n(?=def |class |@|if __name__|\Z)',
        re.M,
    )

    version_only = '''def _get_update_candidate(current: str) -> tuple[str, str, str, str] | None:
    data = _github_json(RELEASE_API + f"?dport_cache_bust={time.time_ns()}")
    if data.get("draft") or data.get("prerelease"):
        return None

    release = _find_release_assets(data)
    if release is None:
        raise RuntimeError("最新正式 Release 沒有可用的 DPort EXE")

    tag, exe_url, sha_url = release
    if _version_key(tag) <= _version_key(current):
        return None

    return tag.lstrip("v"), exe_url, sha_url, str(data.get("html_url") or "")


'''
    match = candidate.search(text)
    if match and "current_sha256" in match.group(0):
        text = text[:match.start()] + version_only + text[match.end():]

    # Restore check_now() to version-only candidate call.
    text = text.replace(
        '    current = _bundled_version()\n'
        '    current_sha256 = _current_exe_sha256()\n'
        '    try:\n'
        '        candidate = _get_update_candidate(current, current_sha256)\n',
        '    current = _bundled_version()\n'
        '    try:\n'
        '        candidate = _get_update_candidate(current)\n',
        1,
    )

    text = text.replace(
        '            _STATE["current_version"] = current\n'
        '            _STATE["current_sha256"] = current_sha256 or None\n',
        '            _STATE["current_version"] = current\n',
    )
    text = text.replace(
        '            _STATE["checked_at"] = time.time()\n'
        '            _STATE["current_version"] = current\n'
        '            _STATE["current_sha256"] = current_sha256 or None\n',
        '            _STATE["checked_at"] = time.time()\n'
        '            _STATE["current_version"] = current\n',
    )

    # Replace the candidate handling with version-only behavior.
    text = re.sub(
        r'''        else:
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
        '''        else:
            version, exe_url, sha_url, release_url = candidate
            with _LOCK:
                _STATE["state"] = "update_available"
                _STATE["latest_version"] = version
                _STATE["latest_url"] = release_url
                _STATE["message"] = f"發現 DPort 新版 v{version}，準備自動更新…"
''',
        text,
        flags=re.S,
        count=1,
    )

    text = text.replace(
        '                _STATE["latest_version"] = current\n'
        '                _STATE["latest_sha256"] = current_sha256 or None\n'
        '                _STATE["message"] = f"DPort v{current} 已是最新正式版"\n',
        '                _STATE["latest_version"] = current\n'
        '                _STATE["message"] = f"DPort v{current} 已是最新正式版"\n',
        1,
    )

    updater.write_text(text, encoding="utf-8")
    return text != original


def main() -> int:
    updater = Path("src/dport_release_updater.py")
    if not updater.exists():
        raise SystemExit(f"Missing updater source: {updater}")

    changed = remove_same_version_sha_update(updater)

    # Hard guard: final source must not contain the same-version SHA candidate
    # branch or the current executable fingerprint helper.
    final = updater.read_text(encoding="utf-8")
    forbidden = [
        "_current_exe_sha256",
        "_read_release_sha256",
        "current_sha256",
        "latest_sha256",
        "same_version_build",
    ]
    leftovers = [token for token in forbidden if token in final]
    if leftovers:
        raise SystemExit("Same-version SHA update code still present: " + ", ".join(leftovers))

    print("Same-version SHA-aware auto-update removed.")
    print(f"Updater changed: {changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
