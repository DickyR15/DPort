import argparse
import re
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory


def bump_patch(version: str) -> str:
    parts = version.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError(f"Invalid DPort version: {version}")
    parts[2] = str(int(parts[2]) + 1)
    return ".".join(parts)



def disable_same_version_sha_update(updater: Path) -> None:
    import re

    text = updater.read_text(encoding="utf-8")

    text = text.replace(
        '    "current_version": None,\n'
        '    "current_sha256": None,\n'
        '    "latest_version": None,\n'
        '    "latest_sha256": None,\n',
        '    "current_version": None,\n'
        '    "latest_version": None,\n',
        1,
    )

    text = re.sub(
        r'\n\ndef _current_exe_sha256\(\) -> str:\n.*?\n\ndef _github_json',
        '\n\ndef _github_json',
        text,
        flags=re.S,
    )

    text = re.sub(
        r'\n\ndef _read_release_sha256\(url: str\) -> str:\n.*?(?=\n\ndef |\Z)',
        '\n',
        text,
        flags=re.S,
    )

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

    text = re.sub(
        r'''        else:
            version, exe_url, sha_url, release_url, remote_sha256 = candidate
            same_version_build = _version_key\(version\) == _version_key\(current\)
            with _LOCK:
                _STATE\["state"\] = "update_available"
                _STATE\["latest_version"\] = version
                _STATE\["latest_sha256"\] = remote_sha256
                _STATE\["latest_url"\] = release_url
                _STATE\["message"\] = \(
                    f"DPort v\{version\} 有新的修正版，準備自動更新…"
                    if same_version_build
                    else f"發現 DPort 新版 v\{version\}，準備自動更新…"
                \)
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
        '            _STATE["current_sha256"] = current_sha256 or None\n',
        '',
    )
    text = text.replace(
        '                _STATE["latest_sha256"] = current_sha256 or None\n',
        '',
    )

    updater.write_text(text, encoding="utf-8")

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
        raise RuntimeError("Same-version SHA updater code remains: " + ", ".join(leftovers))



def replace_pm3(text: str, version: str) -> str:
    pattern = r"(?mi)^\s*pymobiledevice3\s*==\s*[^\s#]+"
    if not re.search(pattern, text):
        raise RuntimeError("pymobiledevice3 pin not found")
    return re.sub(pattern, f"pymobiledevice3=={version}", text)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True)
    parser.add_argument("--latest-pm3", required=True)
    parser.add_argument("--output-version", required=True)
    args = parser.parse_args()

    zip_path = Path(args.zip)
    if not zip_path.exists():
        raise SystemExit(f"Missing source ZIP: {zip_path}")

    root_name = "DPort-6.9.0"

    with TemporaryDirectory() as td:
        td = Path(td)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(td)

        root = td / root_name
        version_file = root / "src" / "dport_version.py"
        req_file = root / "requirements-build.txt"
        if not version_file.exists():
            raise SystemExit("Source ZIP is missing src/dport_version.py")
        if not req_file.exists():
            raise SystemExit("Source ZIP is missing requirements-build.txt")

        current_text = version_file.read_text(encoding="utf-8", errors="replace")
        match = re.search(r'DPORT_VERSION\s*=\s*["\']([^"\']+)["\']', current_text)
        if not match:
            raise SystemExit("DPORT_VERSION not found in source package")

        current_version = match.group(1)
        expected = bump_patch(current_version)
        if expected != args.output_version:
            raise SystemExit(
                f"Version mismatch: source implies {expected}, requested {args.output_version}"
            )

        version_file.write_text(
            f'DPORT_VERSION="{args.output_version}"\n',
            encoding="utf-8",
        )

        req_text = req_file.read_text(encoding="utf-8", errors="replace")
        req_file.write_text(
            replace_pm3(req_text, args.latest_pm3),
            encoding="utf-8",
        )

        updater_file = root / "src" / "dport_release_updater.py"
        if not updater_file.exists():
            raise SystemExit("Source ZIP is missing src/dport_release_updater.py")
        disable_same_version_sha_update(updater_file)

        tmp_zip = zip_path.with_suffix(".new.zip")
        if tmp_zip.exists():
            tmp_zip.unlink()

        with zipfile.ZipFile(tmp_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in root.rglob("*"):
                if path.is_file():
                    arcname = Path(root_name) / path.relative_to(root)
                    zf.write(path, arcname.as_posix())

        tmp_zip.replace(zip_path)

    repo_req = Path("requirements-build.txt")
    if repo_req.exists():
        repo_text = repo_req.read_text(encoding="utf-8", errors="replace")
        repo_req.write_text(replace_pm3(repo_text, args.latest_pm3), encoding="utf-8")
    else:
        repo_req.write_text(f"pymobiledevice3=={args.latest_pm3}\n", encoding="utf-8")

    Path("src/dport_version.py").write_text(
        f'DPORT_VERSION="{args.output_version}"\n',
        encoding="utf-8",
    )

    print(f"Updated DPort to {args.output_version}")
    print(f"Updated pymobiledevice3 to {args.latest_pm3}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
