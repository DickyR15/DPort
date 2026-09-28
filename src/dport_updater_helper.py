from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path


def _download(url: str, target: Path) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "DPort-Updater", "Cache-Control": "no-cache"})
    digest = hashlib.sha256()
    with urllib.request.urlopen(req, timeout=120) as resp, target.open("wb") as out:
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
            digest.update(chunk)
    return digest.hexdigest()


def _read_expected_sha256(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "DPort-Updater", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        text = resp.read().decode("utf-8", errors="replace")
    for token in text.replace("\r", " ").replace("\n", " ").split():
        if len(token) == 64 and all(c in "0123456789abcdefABCDEF" for c in token):
            return token.lower()
    raise RuntimeError("SHA-256 checksum file is invalid")


def _wait_for_pid_exit(pid: int, timeout: int = 180) -> None:
    """Wait until the exact Windows process ID is gone.

    tasklist's default table output starts with the image name, not the PID,
    so checking startswith(pid) can falsely report that a live DPort process
    has already exited. Use CSV output and match the second column exactly.
    """
    deadline = time.time() + timeout
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    while time.time() < deadline:
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=5, creationflags=flags,
            )
            alive = False
            for line in result.stdout.splitlines():
                parts = [p.strip().strip('"') for p in line.split('","')]
                if len(parts) >= 2 and parts[1] == str(pid):
                    alive = True
                    break
            if not alive:
                return
        except Exception:
            # Keep waiting if tasklist is temporarily unavailable.
            pass
        time.sleep(0.5)


def _install_new_version(downloaded: Path, old_target: Path, new_target: Path) -> None:
    """Install the new version under its own versioned filename.

    Do not overwrite the 6.9.0 file in-place. The expected on-disk result is
    DPort-6.9.0.exe -> DPort-6.9.1.exe, with the old file removed only after
    the new process has started successfully.
    """
    new_target.parent.mkdir(parents=True, exist_ok=True)

    for _ in range(40):
        try:
            if new_target.exists():
                os.replace(new_target, new_target.with_name(new_target.name + ".old"))
                try:
                    new_target.with_name(new_target.name + ".old").unlink(missing_ok=True)
                except Exception:
                    pass
            os.replace(downloaded, new_target)
            if new_target.exists():
                return
        except Exception:
            time.sleep(0.5)

    raise RuntimeError("無法將新版 DPort 放入應用程式資料夾，舊版本已保留")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--exe-url", required=True)
    parser.add_argument("--sha256-url")
    parser.add_argument("--args-json", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    target = Path(args.target).resolve()
    new_target = target.parent / f"DPort-{args.version}.exe"
    log_file = target.parent / "DPort-update.log"

    def log(message: str) -> None:
        try:
            with log_file.open("a", encoding="utf-8") as fp:
                fp.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
        except Exception:
            pass
    # Keep the downloaded EXE on the same volume as the installed DPort EXE.
    # os.replace() cannot atomically replace a file across different drives.
    work_dir = target.parent / ".dport-update"
    work_dir.mkdir(parents=True, exist_ok=True)
    downloaded = work_dir / f"DPort-{args.version}-download-{os.getpid()}.exe"
    if args.args_json:
        relaunch_args = json.loads(args.args_json)
        if not isinstance(relaunch_args, list):
            relaunch_args = []
    else:
        relaunch_args = []
        if args.port is not None:
            relaunch_args.extend(["--port", str(args.port)])
        if args.no_browser:
            relaunch_args.append("--no-browser")

    def relaunch() -> None:
        env = os.environ.copy()
        env["DPORT_RESTARTED"] = "1"
        env["DPORT_UPDATE_TARGET"] = str(target)
        subprocess.Popen(
            [str(new_target), *[str(x) for x in relaunch_args]],
            cwd=str(new_target.parent),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=(
                getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                | getattr(subprocess, "CREATE_NO_WINDOW", 0)
                | getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
            ),
            close_fds=True,
            env=env,
        )

    try:
        log(f"Updater started: target={target}, version={args.version}, parent_pid={args.pid}")
        actual = _download(args.exe_url, downloaded)
        log("Downloaded new executable.")
        if not args.sha256_url:
            raise RuntimeError("Release 缺少 SHA-256 checksum")
        expected = _read_expected_sha256(args.sha256_url)
        if actual.lower() != expected:
            raise RuntimeError("DPort EXE SHA-256 驗證失敗")
        log("SHA-256 verified.")
        # Wait for the running DPort process to terminate before replacing its EXE.
        time.sleep(1)
        _wait_for_pid_exit(args.pid, timeout=180)
        log("Parent DPort process exited.")
        _install_new_version(downloaded, target, new_target)
        log(f"New executable installed as {new_target}.")
        relaunch()
        time.sleep(3)

        # Only delete 6.9.0 after the new version has actually started.
        if target.exists() and target != new_target:
            try:
                target.unlink()
                log(f"Old executable removed: {target}")
            except Exception as exc:
                log(f"Old executable could not be removed yet: {exc!r}")

        log("New DPort process launched successfully.")
        return 0
    except Exception as exc:
        log(f"Updater failed: {exc!r}")
        try:
            downloaded.unlink(missing_ok=True)
        except Exception:
            pass
        # Never leave the user without DPort after a failed update.
        try:
            _wait_for_pid_exit(args.pid, timeout=10)
            if target.exists():
                relaunch()
        except Exception:
            pass
        return 30


if __name__ == "__main__":
    raise SystemExit(main())
