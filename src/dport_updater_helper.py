from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path


def _download(url: str, target: Path) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "DPort-Updater",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
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
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "DPort-Updater", "Cache-Control": "no-cache"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        text = resp.read().decode("utf-8", errors="replace")

    for token in text.replace("\r", " ").replace("\n", " ").split():
        if len(token) == 64 and all(c in "0123456789abcdefABCDEF" for c in token):
            return token.lower()
    raise RuntimeError("SHA-256 checksum file is invalid")


def _wait_for_pid_exit(pid: int, timeout: int = 180) -> None:
    deadline = time.time() + timeout
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    while time.time() < deadline:
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=flags,
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
            pass

        time.sleep(0.5)

    raise TimeoutError("等待舊版 DPort 關閉逾時")


def _start_detached(exe: Path, arguments: list[str]) -> subprocess.Popen:
    return subprocess.Popen(
        [str(exe), *arguments],
        cwd=str(exe.parent),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=(
            getattr(subprocess, "CREATE_NO_WINDOW", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
            | getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
            | 0x01000000
        ),
        close_fds=True,
    )


def _schedule_cleanup(folder: Path) -> None:
    """Delete the temporary updater folder after this helper exits."""
    folder_q = str(folder).replace('"', '""')
    script = 'timeout /t 8 /nobreak >nul & rmdir /s /q "' + folder_q + '"'
    _start_detached(
        Path(os.environ.get("COMSPEC", "cmd.exe")),
        ["/d", "/s", "/c", script],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="DPort standalone updater")
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--new-exe")
    parser.add_argument("--exe-url")
    parser.add_argument("--sha256-url")
    parser.add_argument("--args-json", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    old_target = Path(args.target).resolve()
    app_dir = old_target.parent
    new_target = app_dir / f"DPort-{args.version}.exe"

    windows_temp = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Temp"
    windows_temp.mkdir(parents=True, exist_ok=True)
    work_dir = windows_temp / ".dport-update"
    work_dir.mkdir(parents=True, exist_ok=True)

    downloaded = Path(args.new_exe).resolve() if args.new_exe else work_dir / f"DPort-{args.version}.exe"
    checksum = work_dir / f"DPort-{args.version}.exe.sha256"
    log_file = work_dir / "DPort-update.log"

    def log(message: str) -> None:
        try:
            with log_file.open("a", encoding="utf-8") as fp:
                fp.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
        except Exception:
            pass

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

    try:
        log(f"開始更新：{old_target} -> {new_target}")
        log(f"暫存目錄：{work_dir}")

        if args.new_exe:
            if not downloaded.exists():
                raise FileNotFoundError(f"找不到已下載的 DPort-{args.version}.exe")
            log("使用 DPort 已在 EXIT 前下載並驗證的新版 EXE")
        else:
            if not args.exe_url or not args.sha256_url:
                raise RuntimeError("缺少新版 EXE 或 SHA-256 URL")
            actual = _download(args.exe_url, downloaded)
            expected = _read_expected_sha256(args.sha256_url)
            checksum.write_text(expected + "\n", encoding="ascii")
            if actual.lower() != expected:
                raise RuntimeError("DPort EXE SHA-256 驗證失敗")
            log("新版 EXE SHA-256 驗證成功")

        _wait_for_pid_exit(args.pid, timeout=180)
        log("舊版 DPort 已完全關閉")

        # The new EXE was downloaded and verified before EXIT.
        # Temp and the DPort folder may be on different drives, so copy it.
        shutil.copy2(downloaded, new_target)
        if not new_target.exists():
            raise RuntimeError(f"DPort-{args.version}.exe 沒有成功建立")
        log(f"新版 EXE 已建立：{new_target}")

        # Start 6.9.1 before removing 6.9.0.
        process = _start_detached(new_target, relaunch_args)
        time.sleep(5)
        if process.poll() is not None:
            raise RuntimeError(
                f"DPort-{args.version}.exe 啟動後立即結束，ExitCode={process.returncode}"
            )
        log("新版 DPort 已成功啟動")

        # Only now is it safe to remove 6.9.0.
        if old_target.exists() and old_target != new_target:
            old_target.unlink()
            log(f"舊版 EXE 已刪除：{old_target}")

        _schedule_cleanup(work_dir)
        return 0

    except Exception as exc:
        log(f"更新失敗：{exc!r}")

        # If possible, restore/relaunch the old DPort so the user is not left
        # without the application. Do not delete the old EXE on failure.
        try:
            if old_target.exists():
                _start_detached(old_target, relaunch_args)
                log("已重新啟動原本的 DPort")
        except Exception as restore_exc:
            log(f"原版重新啟動失敗：{restore_exc!r}")

        _schedule_cleanup(work_dir)
        return 30


if __name__ == "__main__":
    raise SystemExit(main())
