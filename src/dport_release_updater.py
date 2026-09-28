from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any

try:
    from .dport_version import DPORT_VERSION
except ImportError:
    from dport_version import DPORT_VERSION


LOGGER = logging.getLogger("DPort-Updater")
REPO = "DickyR15/DPort"
RELEASE_API = f"https://api.github.com/repos/{REPO}/releases/latest"
VERSION = str(DPORT_VERSION)
CHECK_INTERVAL = 1800.0
_STATE = {
    "state": "idle",
    "message": "",
    "current_version": VERSION,
    "latest_version": VERSION,
    "latest_url": "",
    "release_url": "",
    "checked_at": 0.0,
    "updated_at": "",
    "restart_required": False,
}
_LOCK = threading.Lock()
_STARTED = False
_VERSION_RE = __import__("re").compile(r"^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:[-+.]([0-9A-Za-z.-]+))?$")


def _version_key(value: str) -> tuple[int, int, int, str]:
    m = _VERSION_RE.match(str(value).strip())
    if not m:
        return (0, 0, 0, "")
    return (int(m.group(1)), int(m.group(2) or 0), int(m.group(3) or 0), m.group(4) or "")


def _is_newer(current: str, latest: str) -> bool:
    return _version_key(latest) > _version_key(current)


def get_status() -> dict[str, Any]:
    with _LOCK:
        return dict(_STATE)


def _set_state(**values: Any) -> dict[str, Any]:
    with _LOCK:
        _STATE.update(values)
        return dict(_STATE)


def _github_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "DPort-Updater",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_update_candidate(current: str) -> tuple[str, str, str, str] | None:
    release = _github_json(RELEASE_API)
    if release.get("draft") or release.get("prerelease"):
        return None

    tag = str(release.get("tag_name", "")).lstrip("v")
    if not tag or not _is_newer(current, tag):
        return None

    assets = {str(a.get("name")): a for a in release.get("assets", [])}
    exe_name = f"DPort-{tag}.exe"
    sha_name = f"DPort-{tag}.exe.sha256"
    exe = assets.get(exe_name)
    sha = assets.get(sha_name)
    if not exe or not sha:
        return None

    return (
        tag,
        str(release.get("html_url") or ""),
        str(exe.get("browser_download_url") or ""),
        str(sha.get("browser_download_url") or ""),
    )


def check_now() -> dict[str, Any]:
    try:
        candidate = _get_update_candidate(VERSION)
        if candidate:
            latest, release_url, exe_url, sha_url = candidate
            return _set_state(
                state="update_available",
                message=f"DPort {latest} available",
                current_version=VERSION,
                latest_version=latest,
                latest_url=exe_url,
                release_url=release_url,
                checked_at=time.time(),
                restart_required=False,
            )

        release = _github_json(RELEASE_API)
        latest = str(release.get("tag_name", "")).lstrip("v") or VERSION
        return _set_state(
            state="idle",
            message="Up to date" if not _is_newer(VERSION, latest) else "Update unavailable",
            current_version=VERSION,
            latest_version=latest,
            latest_url="",
            release_url=str(release.get("html_url") or ""),
            checked_at=time.time(),
            restart_required=False,
        )
    except Exception as exc:
        LOGGER.debug("DPort update check skipped: %s", exc)
        return _set_state(
            state="offline",
            message="Unable to check for updates",
            current_version=VERSION,
            latest_version=VERSION,
            checked_at=time.time(),
        )


def start_background_update_check() -> None:
    global _STARTED
    with _LOCK:
        if _STARTED:
            return
        _STARTED = True

    def runner() -> None:
        while True:
            check_now()
            time.sleep(CHECK_INTERVAL)

    threading.Thread(target=runner, name="DPort-release-updater", daemon=True).start()


def bootstrap_dport_updater() -> None:
    # Startup is check-only. Never launch an updater or replace/delete the running EXE.
    start_background_update_check()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().lower()


def _download(url: str, destination: Path) -> None:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "DPort-Updater", "Accept": "*/*"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp, destination.open("wb") as out:
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)


def request_update() -> dict[str, Any]:
    # Explicit user action only. No caller should invoke this during startup.
    status = check_now()
    latest = str(status.get("latest_version") or VERSION)
    if status.get("state") != "update_available" or not _is_newer(VERSION, latest):
        return {"ok": False, "state": status.get("state"), "message": "No update is available."}

    exe_url = str(status.get("latest_url") or "")
    release_url = str(status.get("release_url") or "")
    if not exe_url:
        return {"ok": False, "state": "update_failed", "message": "Update package URL is unavailable."}

    # Never overwrite the current executable in-place while it is running.
    current_exe = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve()
    if current_exe.name.lower() != f"DPort-{VERSION}.exe".lower() and getattr(sys, "frozen", False):
        current_exe = Path(sys.executable).resolve()

    temp_dir = Path(tempfile.mkdtemp(prefix="DPort-update-"))
    new_exe = temp_dir / f"DPort-{latest}.exe"
    sha_file = temp_dir / f"DPort-{latest}.exe.sha256"

    try:
        _set_state(state="updating", message=f"Downloading DPort {latest}")
        _download(exe_url, new_exe)

        sha_url = exe_url.rsplit("/", 1)[0] + f"/DPort-{latest}.exe.sha256"
        _download(sha_url, sha_file)
        expected = sha_file.read_text(encoding="utf-8", errors="replace").strip().split()[0].lower()
        actual = _sha256(new_exe)
        if expected != actual:
            raise RuntimeError("SHA-256 verification failed.")

        script = temp_dir / "DPort-update.ps1"
        script.write_text(
            """param([int]$Pid,[string]$NewExe,[string]$TargetExe)
$ErrorActionPreference = 'Stop'
while (Get-Process -Id $Pid -ErrorAction SilentlyContinue) { Start-Sleep -Milliseconds 300 }
Move-Item -LiteralPath $NewExe -Destination $TargetExe -Force
Start-Process -FilePath $TargetExe
Remove-Item -LiteralPath $MyInvocation.MyCommand.Path -Force -ErrorAction SilentlyContinue
""",
            encoding="utf-8",
        )

        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-File", str(script),
                "-Pid", str(os.getpid()),
                "-NewExe", str(new_exe),
                "-TargetExe", str(current_exe),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
            close_fds=True,
        )

        _set_state(
            state="restarting",
            message=f"Updating to DPort {latest}",
            latest_version=latest,
            release_url=release_url,
            restart_required=True,
            updated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )
        threading.Timer(0.8, os._exit, args=(0,)).start()
        return {
            "ok": True,
            "state": "restarting",
            "version": latest,
            "message": f"Updating to DPort {latest}",
        }
    except Exception as exc:
        LOGGER.exception("DPort update failed")
        return {"ok": False, "state": "update_failed", "message": str(exc)}


__all__ = [
    "bootstrap_dport_updater",
    "start_background_update_check",
    "check_now",
    "get_status",
    "request_update",
    "_get_update_candidate",
]
