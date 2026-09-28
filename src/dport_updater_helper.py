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
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True, timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            alive = any(line.strip().startswith(str(pid)) for line in result.stdout.splitlines())
            if not alive:
                return
        except Exception:
            # If tasklist is temporarily unavailable, give the process time to terminate.
            pass
        time.sleep(0.5)


def _replace_file(downloaded: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    backup = target.with_name(target.name + ".update-backup")
    for _ in range(20):
        try:
            if backup.exists():
                backup.unlink()
            if target.exists():
                os.replace(target, backup)
            os.replace(downloaded, target)
            try:
                backup.unlink(missing_ok=True)
            except Exception:
                pass
            return
        except Exception:
            time.sleep(0.5)
    # Best-effort rollback if replacement never completed.
    if not target.exists() and backup.exists():
        try:
            os.replace(backup, target)
        except Exception:
            pass
    raise RuntimeError("無法替換 DPort 執行檔，原版本已保留")


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
            [str(target), *[str(x) for x in relaunch_args]],
            cwd=str(target.parent),
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
        _replace_file(downloaded, target)
        log("New executable copied into application folder.")
        relaunch()
        log("New DPort process launched.")
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
            relaunch()
        except Exception:
            pass
        return 30


if __name__ == "__main__":
    raise SystemExit(main())
