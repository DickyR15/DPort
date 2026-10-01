from __future__ import annotations

import argparse
import hashlib
import json
import os
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
    """Wait for the exact parent PID to exit without relying on tasklist parsing."""
    if os.name == "nt":
        try:
            import ctypes

            SYNCHRONIZE = 0x00100000
            kernel32 = ctypes.windll.kernel32
            kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
            kernel32.OpenProcess.restype = ctypes.c_void_p
            kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
            kernel32.WaitForSingleObject.restype = ctypes.c_uint32
            kernel32.CloseHandle.argtypes = [ctypes.c_void_p]

            handle = kernel32.OpenProcess(SYNCHRONIZE, 0, int(pid))
            if handle:
                result = kernel32.WaitForSingleObject(handle, int(timeout * 1000))
                kernel32.CloseHandle(handle)
                if result == 0:
                    return
        except Exception:
            pass

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
                fields = [x.strip().strip('"') for x in line.split('","')]
                if len(fields) >= 2 and fields[1] == str(pid):
                    alive = True
                    break
            if not alive:
                return
        except Exception:
            pass
        time.sleep(0.5)
    raise TimeoutError("等待舊版 DPort 關閉逾時")


def _wait_for_new_version(version: str, port: int, timeout: int = 120) -> None:
    """Wait until the new DPort server reports the requested version."""
    url = f"http://127.0.0.1:{int(port)}/pymobiledevice3/status"
    deadline = time.time() + timeout

    while time.time() < deadline:
        try:
            req = urllib.request.Request(
                url + f"?ts={int(time.time() * 1000)}",
                headers={"Cache-Control": "no-cache", "Pragma": "no-cache"},
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            current = str(payload.get("current_version") or "")
            if current == str(version):
                return
        except Exception:
            pass
        time.sleep(0.5)

    raise TimeoutError(f"DPort-{version} 啟動逾時：localhost:{port} 沒有回報新版本")




def _start_detached(exe: Path, arguments: list[str], restarted: bool = False) -> subprocess.Popen:
    env = os.environ.copy()
    if restarted:
        env["DPORT_RESTARTED"] = "1"
    startupinfo = None
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0  # SW_HIDE

    return subprocess.Popen(
        [str(exe), *arguments],
        cwd=str(exe.parent),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        startupinfo=startupinfo,
        creationflags=(
            getattr(subprocess, "CREATE_NO_WINDOW", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
            | getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        ),
        close_fds=True,
        env=env,
    )

def _schedule_cleanup(folder: Path) -> None:
    """Silently delete the updater temp folder after the updater exits."""
    folder = folder.resolve()
    parent = folder.parent.resolve()

    # Do not use cmd.exe, timeout.exe, rmdir.exe, or a .vbs file. Those
    # approaches can briefly flash a console or leave a cleanup script behind.
    # Use an inline hidden Windows PowerShell process instead.
    powershell = Path(
        os.environ.get("WINDIR", r"C:\\Windows")
    ) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"

    def ps_escape(value: str) -> str:
        return str(value).replace("'", "''")

    folder_ps = ps_escape(folder)
    parent_ps = ps_escape(parent)

    command = (
        "Start-Sleep -Milliseconds 1000; "
        f"for ($i=0; $i -lt 24; $i++) {{ "
        f"Remove-Item -LiteralPath '{folder_ps}' -Recurse -Force -ErrorAction SilentlyContinue; "
        f"if (-not (Test-Path -LiteralPath '{folder_ps}')) {{ break }}; "
        "Start-Sleep -Milliseconds 500 }; "
        f"Get-ChildItem -LiteralPath '{parent_ps}' -Filter 'DPort-cleanup-*.vbs' "
        "-File -ErrorAction SilentlyContinue | "
        "Remove-Item -Force -ErrorAction SilentlyContinue"
    )

    try:
        encoded = __import__("base64").b64encode(
            command.encode("utf-16le")
        ).decode("ascii")

        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0  # SW_HIDE

        subprocess.Popen(
            [
                str(powershell),
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-WindowStyle",
                "Hidden",
                "-EncodedCommand",
                encoded,
            ],
            cwd=str(parent),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            startupinfo=startupinfo,
            creationflags=(
                getattr(subprocess, "CREATE_NO_WINDOW", 0)
                | getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
            ),
            close_fds=True,
        )
    except Exception as exc:
        # Never fall back to cmd.exe or a visible script host.
        LOGGER.debug("Unable to start silent cleanup process: %s", exc)


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

        # The new DPort executable is downloaded directly beside the running version.
        # Therefore downloaded and new_target MUST be the same file.
        # Do not copy the file onto itself.
        if downloaded.resolve() != new_target.resolve():
            raise RuntimeError(
                f"新版下載路徑錯誤：{downloaded}；預期：{new_target}"
            )
        if not new_target.exists():
            raise RuntimeError(f"DPort-{args.version}.exe 沒有成功建立")
        log(f"新版 EXE 已位於應用程式資料夾：{new_target}")

        # Start the new DPort version before removing the old one.
        _start_detached(new_target, relaunch_args, restarted=True)
        # Do not use process.poll() as the success criterion. DPort may
        # self-elevate through UAC and replace the bootstrap process.
        _wait_for_new_version(args.version, args.port or 54321, timeout=120)
        log(f"DPort-{args.version}.exe 已回報新版本並成功啟動")

        # Only now is it safe to remove the old executable.
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
