from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
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
RELEASES_API = f"https://api.github.com/repos/{REPO}/releases?per_page=100"
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
_VERSION_RE = re.compile(
    r"^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:[-+.]([0-9A-Za-z.-]+))?$"
)


def _version_key(value: str) -> tuple[int, int, int, str]:
    m = _VERSION_RE.match(str(value).strip())
    if not m:
        return (0, 0, 0, "")
    return (
        int(m.group(1)),
        int(m.group(2) or 0),
        int(m.group(3) or 0),
        m.group(4) or "",
    )


def _is_newer(current: str, latest: str) -> bool:
    return _version_key(latest) > _version_key(current)


def get_status() -> dict[str, Any]:
    with _LOCK:
        return dict(_STATE)


def _set_state(**values: Any) -> dict[str, Any]:
    with _LOCK:
        _STATE.update(values)
        return dict(_STATE)


def _github_json(url: str) -> Any:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "DPort-Updater",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_latest_stable_release() -> dict[str, Any] | None:
    releases = _github_json(RELEASES_API)
    if not isinstance(releases, list):
        raise RuntimeError("GitHub releases API returned an unexpected response.")

    candidates: list[dict[str, Any]] = []
    for release in releases:
        if not isinstance(release, dict):
            continue
        if release.get("draft") or release.get("prerelease"):
            continue

        tag = str(release.get("tag_name", "")).strip()
        version = tag.lstrip("v")
        if not tag or not _VERSION_RE.match(tag):
            continue
        if _version_key(version) == (0, 0, 0, ""):
            continue
        candidates.append(release)

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda release: _version_key(
            str(release.get("tag_name", "")).lstrip("v")
        ),
    )


def _get_update_candidate(current: str) -> tuple[str, str, str, str] | None:
    release = _get_latest_stable_release()
    if not release:
        return None

    tag = str(release.get("tag_name", "")).lstrip("v")
    if not tag or not _is_newer(current, tag):
        return None

    assets = {str(a.get("name")): a for a in release.get("assets", [])}
    exe = assets.get(f"DPort-{tag}.exe")
    sha = assets.get(f"DPort-{tag}.exe.sha256")
    helper = assets.get("DPort-Updater.exe")
    helper_sha = assets.get("DPort-Updater.exe.sha256")
    if not exe or not sha or not helper or not helper_sha:
        return None

    return (
        tag,
        str(release.get("html_url") or ""),
        str(exe.get("browser_download_url") or ""),
        str(sha.get("browser_download_url") or ""),
    )

def _cleanup_restart_temp() -> None:
    if os.environ.get("DPORT_RESTARTED") != "1":
        return

    def cleanup() -> None:
        time.sleep(8.0)
        folder = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Temp" / ".dport-update"
        try:
            if folder.exists():
                shutil.rmtree(folder, ignore_errors=True)
        except Exception:
            LOGGER.debug("Unable to remove update temp directory", exc_info=True)


    threading.Thread(
        target=cleanup,
        name="DPort-update-cleanup",
        daemon=True,
    ).start()


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

        release = _get_latest_stable_release()
        latest = (
            str(release.get("tag_name", "")).lstrip("v")
            if release
            else VERSION
        )
        return _set_state(
            state="idle",
            message="Up to date" if not _is_newer(VERSION, latest) else "Update unavailable",
            current_version=VERSION,
            latest_version=latest,
            latest_url="",
            release_url=str(release.get("html_url") or "") if release else "",
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

    threading.Thread(
        target=runner,
        name="DPort-release-updater",
        daemon=True,
    ).start()


def bootstrap_dport_updater() -> None:
    _cleanup_restart_temp()
    start_background_update_check()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().lower()


def _download(url: str, destination: Path) -> None:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "DPort-Updater",
            "Accept": "*/*",
            "Cache-Control": "no-cache",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp, destination.open("wb") as out:
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)


def request_update() -> dict[str, Any]:
    # Explicit user action only.
    # Full order:
    # 1) download DPort-<latest>.exe into C:\Windows\Temp\.dport-update
    # 2) verify its SHA-256
    # 3) download + verify DPort-Updater.exe
    # 4) start the detached updater
    # 5) return; the /dport/update route shuts down DPort
    status = check_now()
    latest = str(status.get("latest_version") or VERSION)
    if status.get("state") != "update_available" or not _is_newer(VERSION, latest):
        return {"ok": False, "state": status.get("state"), "message": "目前沒有可用更新。"}

    exe_url = str(status.get("latest_url") or "")
    release_url = str(status.get("release_url") or "")
    if not exe_url:
        return {"ok": False, "state": "update_failed", "message": "找不到新版 DPort 安裝檔。"}

    current_exe = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve()
    if getattr(sys, "frozen", False):
        current_exe = current_exe.parent / f"DPort-{VERSION}.exe"

    windows_temp = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Temp"
    update_dir = windows_temp / ".dport-update"
    update_dir.mkdir(parents=True, exist_ok=True)

    # Remove leftovers from a previous failed update.
    for item in list(update_dir.iterdir()):
        try:
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            else:
                item.unlink(missing_ok=True)
        except Exception:
            pass

    # The new DPort executable is downloaded directly beside the currently
    # running DPort executable. This remains true even when the user launches
    # DPort from Desktop or any other folder.
    new_exe = current_exe.parent / f"DPort-{latest}.exe"
    sha_file = update_dir / f"DPort-{latest}.exe.sha256"
    helper = update_dir / "DPort-Updater.exe"
    helper_sha = update_dir / "DPort-Updater.exe.sha256"
    helper_url = f"https://github.com/{REPO}/releases/download/v{latest}/DPort-Updater.exe"
    helper_sha_url = f"https://github.com/{REPO}/releases/download/v{latest}/DPort-Updater.exe.sha256"

    try:
        _set_state(
            state="updating",
            message=f"正在下載 DPort {latest}…",
            latest_version=latest,
            release_url=release_url,
            restart_required=True,
        )

        # 1. Download new DPort EXE directly into the same folder as
        #    the current DPort EXE, BEFORE any EXIT.
        _download(exe_url, new_exe)

        # 2. Verify new DPort EXE before any EXIT.
        sha_url = exe_url.rsplit("/", 1)[0] + f"/DPort-{latest}.exe.sha256"
        _download(sha_url, sha_file)
        expected_exe = sha_file.read_text(
            encoding="utf-8", errors="replace"
        ).strip().split()[0].lower()
        actual_exe = _sha256(new_exe)
        if actual_exe != expected_exe:
            raise RuntimeError(f"DPort-{latest}.exe SHA-256 驗證失敗。")

        # 3. Download and verify the standalone updater before EXIT.
        _download(helper_url, helper)
        _download(helper_sha_url, helper_sha)
        helper_expected = helper_sha.read_text(
            encoding="utf-8", errors="replace"
        ).strip().split()[0].lower()
        if _sha256(helper) != helper_expected:
            raise RuntimeError("DPort-Updater.exe SHA-256 驗證失敗。")

        # 4. Start standalone updater. It performs all post-EXIT file operations.
        port = os.environ.get("DPORT_PORT") or "54321"
        updater_args = [
            str(helper),
            "--pid", str(os.getpid()),
            "--target", str(current_exe),
            "--new-exe", str(new_exe),
            "--version", latest,
            "--port", str(port),
            "--no-browser",
        ]
        # PyInstaller --onefile extracts DPort into _MEIxxxxx. The hard-exit
        # path can bypass bootloader cleanup, so pass the old extraction
        # directory to the standalone updater for post-update cleanup.
        mei_dir = getattr(sys, "_MEIPASS", None)
        if mei_dir:
            try:
                mei_path = Path(mei_dir).resolve()
                if mei_path.is_dir():
                    updater_args.extend(["--mei-dir", str(mei_path)])
            except Exception:
                pass
        flags = (
            getattr(subprocess, "CREATE_NO_WINDOW", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
            | getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
            | 0x01000000
        )
        subprocess.Popen(
            updater_args,
            cwd=str(update_dir),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
            close_fds=True,
        )

        _set_state(
            state="restarting",
            message=f"下載完成，正在關閉 DPort 並啟動 {latest}…",
            latest_version=latest,
            release_url=release_url,
            restart_required=True,
            updated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )
        return {
            "ok": True,
            "state": "restarting",
            "version": latest,
            "message": f"下載完成，正在關閉 DPort 並啟動 {latest}…",
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
]
