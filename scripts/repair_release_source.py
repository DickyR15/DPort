from __future__ import annotations

import argparse
import io
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path


KNOWN_GOOD_COMMIT = "49d5c17cbd70225ad6187c7ec45bd0dd2b68d547"
ROOT_NAME = "DPort-6.9.0"


SAFE_UPDATER = r'''from __future__ import annotations

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

    current_exe = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve()
    current_exe = current_exe.parent / f"DPort-{VERSION}.exe" if getattr(sys, "frozen", False) else current_exe
    target_exe = current_exe.parent / f"DPort-{latest}.exe"

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
            """param([int]$Pid,[string]$NewExe,[string]$OldExe,[string]$TargetExe)
$ErrorActionPreference = 'Stop'
while (Get-Process -Id $Pid -ErrorAction SilentlyContinue) { Start-Sleep -Milliseconds 300 }

if (Test-Path -LiteralPath $TargetExe) {
    Remove-Item -LiteralPath $TargetExe -Force
}

$moveOk = $false
for ($i = 0; $i -lt 40; $i++) {
    try {
        Move-Item -LiteralPath $NewExe -Destination $TargetExe -Force
        $moveOk = $true
        break
    } catch {
        Start-Sleep -Milliseconds 300
    }
}
if (-not $moveOk -or -not (Test-Path -LiteralPath $TargetExe)) {
    throw "Unable to place the new DPort executable."
}

$started = Start-Process -FilePath $TargetExe -PassThru
Start-Sleep -Seconds 2
if ($started.HasExited) {
    throw "The updated DPort executable exited immediately with code $($started.ExitCode)."
}

if ((Test-Path -LiteralPath $OldExe) -and ($OldExe -ne $TargetExe)) {
    Remove-Item -LiteralPath $OldExe -Force -ErrorAction SilentlyContinue
}

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
                "-OldExe", str(current_exe),
                "-TargetExe", str(target_exe),
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
'''




BRAND_STATUS_LAYOUT_FIX = """
<style id="dport-brand-meta-row-stack-final">
/* Keep the live DPort update status fully visible in the narrow brand column.
   Caption and update status intentionally occupy separate rows so the GPX card
   can never cover the orange update text. */
.dport-brand-meta-row{
    display:grid!important;
    grid-template-columns:minmax(0,1fr)!important;
    grid-template-rows:auto auto!important;
    align-items:center!important;
    gap:2px!important;
    width:100%!important;
    min-width:0!important;
    max-width:100%!important;
    margin:0!important;
    padding:0!important;
    overflow:hidden!important;
}
.dport-brand-meta-row .dport-caption,
.dport-brand-meta-row #dport-pm3-status{
    grid-column:1!important;
    min-width:0!important;
    width:100%!important;
    max-width:100%!important;
    margin:0!important;
    padding:0!important;
    box-sizing:border-box!important;
    white-space:nowrap!important;
    overflow:hidden!important;
    text-overflow:ellipsis!important;
}
.dport-brand-meta-row .dport-caption{grid-row:1!important;}
.dport-brand-meta-row #dport-pm3-status{
    grid-row:2!important;
    display:block!important;
    font-size:10px!important;
    line-height:1.15!important;
}
</style>
"""



BRAND_HEADER_HEIGHT_FIX = r'''
<style id="dport-brand-header-height-final">
/* Give the brand column enough vertical room for all four text rows. */
@media (min-width:1600px){
  .dport-hero{
    height:112px!important;
    min-height:112px!important;
    max-height:112px!important;
  }
  .dport-brand{
    height:100px!important;
    min-height:100px!important;
    max-height:100px!important;
    align-self:center!important;
  }
  .dport-brand-text{
    max-height:100px!important;
    overflow:hidden!important;
  }
  .dport-brand-meta-row{row-gap:3px!important;}
  .dport-brand-meta-row #dport-pm3-status{
    line-height:1.2!important;
    min-height:12px!important;
  }
}
@media (min-width:2200px){
  .dport-hero{
    height:116px!important;
    min-height:116px!important;
    max-height:116px!important;
  }
  .dport-brand{
    height:104px!important;
    min-height:104px!important;
    max-height:104px!important;
  }
  .dport-brand-text{max-height:104px!important;}
}
</style>
'''

UPDATE_UI = r'''
<style id="dport-user-update-dialog-override">
/* The legacy pymobiledevice3 update overlay is display-only and must never block
   the explicit user-choice DPort update dialog. */
.dport-pm3-update-modal,
#dport-pm3-update-modal{
  display:none!important;
  visibility:hidden!important;
  pointer-events:none!important;
}
#dport-update-dialog{
  z-index:2147483647!important;
}
</style>
<style id="dport-user-update-dialog">
#dport-update-dialog{
  position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);
  z-index:99999;width:min(520px,calc(100vw - 36px));
  padding:22px 24px;border-radius:16px;
  background:#1f2632;color:#f5f7fb;border:1px solid #56647a;
  box-shadow:0 22px 60px rgba(0,0,0,.45);display:none;
  font-family:inherit;
}
#dport-update-dialog.show{display:block}
#dport-update-dialog h3{margin:0 0 10px;font-size:20px}
#dport-update-dialog p{margin:0;line-height:1.55;color:#c9d2df}
#dport-update-dialog .dport-update-actions{
  display:flex;justify-content:flex-end;gap:10px;margin-top:18px
}
#dport-update-dialog button{
  min-width:92px;height:40px;border-radius:10px;border:1px solid #697991;
  background:#313b4b;color:#f5f7fb;font-weight:700;cursor:pointer
}
#dport-update-dialog button.primary{background:#5669e7;border-color:#697bf4}
#dport-update-dialog button:disabled{opacity:.5;cursor:wait}
</style>
<div id="dport-update-dialog" role="dialog" aria-modal="true">
  <h3>發現 DPort 新版本</h3>
  <p id="dport-update-message"></p>
  <div class="dport-update-actions">
    <button type="button" id="dport-update-later">稍後</button>
    <button type="button" id="dport-update-now" class="primary">立即更新</button>
  </div>
</div>
<script id="dport-user-update-dialog-script">
(function(){
  if(window.__dportUpdateDialogLoaded) return;
  window.__dportUpdateDialogLoaded=true;

  function parts(v){
    return String(v||'0').replace(/^v/i,'').split('.').map(function(x){
      var m=x.match(/^\d+/); return m ? parseInt(m[0],10) : 0;
    });
  }
  function newer(a,b){
    var A=parts(a),B=parts(b);
    for(var i=0;i<3;i++){
      if((A[i]||0)!==(B[i]||0)) return (A[i]||0)>(B[i]||0);
    }
    return false;
  }
  function show(current,latest){
    if(window.__dportUpdatePrompted || !newer(latest,current)) return;
    window.__dportUpdatePrompted=true;
    var box=document.getElementById('dport-update-dialog');
    var msg=document.getElementById('dport-update-message');
    if(!box || !msg) return;
    msg.textContent='目前版本 '+current+'，GitHub 已有正式版 '+latest+'。要現在升級嗎？';
    box.classList.add('show');
  }
  function rememberUpdate(current,latest){
    var el=document.getElementById('dport-pm3-status');
    if(!el) return;
    if(newer(latest,current)){
      el.dataset.dportUpdateCurrent=String(current);
      el.dataset.dportUpdateLatest=String(latest);
      el.classList.add('dport-update-clickable');
      el.setAttribute('title','點擊重新開啟更新確認');
      el.setAttribute('role','button');
      el.setAttribute('tabindex','0');
    }else{
      delete el.dataset.dportUpdateCurrent;
      delete el.dataset.dportUpdateLatest;
      el.classList.remove('dport-update-clickable');
      el.removeAttribute('title');
      el.removeAttribute('role');
      el.removeAttribute('tabindex');
    }
  }

  function showFromStatus(){
    var el=document.getElementById('dport-pm3-status');
    if(!el) return;
    var current=el.dataset.dportUpdateCurrent;
    var latest=el.dataset.dportUpdateLatest;
    if(current && latest && newer(latest,current)){
      var box=document.getElementById('dport-update-dialog');
      var msg=document.getElementById('dport-update-message');
      if(!box || !msg) return;
      msg.textContent='目前版本 '+current+'，GitHub 已有正式版 '+latest+'。要現在升級嗎？';
      box.classList.add('show');
    }
  }

  function check(){
    fetch('/pymobiledevice3/status?ts='+Date.now(),{cache:'no-store'})
      .then(function(r){return r.json();})
      .then(function(s){
        if(s && s.current_version && s.latest_version){
          rememberUpdate(s.current_version,s.latest_version);
          show(s.current_version,s.latest_version);
        }
      }).catch(function(){});
  }
  function closeDialog(){
    var box=document.getElementById('dport-update-dialog');
    if(box) box.classList.remove('show');
  }
  function start(){
    var btn=document.getElementById('dport-update-now');
    if(!btn) return;
    btn.disabled=true;
    btn.textContent='更新中…';
    fetch('/dport/update?confirm=1',{cache:'no-store'})
      .then(function(r){return r.json();})
      .then(function(result){
        if(result && result.ok){
          var msg=document.getElementById('dport-update-message');
          if(msg) msg.textContent='正在更新到 DPort '+result.version+'，程式即將重新啟動…';
        }else{
          btn.disabled=false;
          btn.textContent='立即更新';
          var msg=document.getElementById('dport-update-message');
          if(msg) msg.textContent=(result && result.message) ? result.message : '更新失敗，請稍後再試。';
        }
      }).catch(function(){
        btn.disabled=false;
        btn.textContent='立即更新';
      });
  }

  document.addEventListener('DOMContentLoaded',function(){
    var later=document.getElementById('dport-update-later');
    var now=document.getElementById('dport-update-now');
    var status=document.getElementById('dport-pm3-status');
    if(later) later.addEventListener('click',closeDialog);
    if(now) now.addEventListener('click',start);
    if(status){
      status.addEventListener('click',showFromStatus);
      status.addEventListener('keydown',function(e){
        if(e.key==='Enter' || e.key===' '){ e.preventDefault(); showFromStatus(); }
      });
    }
    setTimeout(check,1500);
    setTimeout(check,12000);
  });
})();
</script>
'''


def get_good_zip() -> bytes:
    return subprocess.check_output(
        ["git", "show", f"{KNOWN_GOOD_COMMIT}:DPort-source-6.9.0.zip"],
        shell=False,
    )


def patch_main(main_text: str) -> str:
    # The updater exports bootstrap_dport_updater(). Older source referenced a
    # non-existent bootstrap symbol and caused immediate startup ImportError.
    main_text = re.sub(
        r"from dport_release_updater import bootstrap\s+as\s+bootstrap_dport_updater",
        "from dport_release_updater import bootstrap_dport_updater",
        main_text,
    )

    if "/dport/update" in main_text:
        return main_text

    match = re.search(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*Flask\(", main_text, flags=re.M)
    if not match:
        raise RuntimeError("Could not find Flask app variable in main.py")
    app_name = match.group(1)

    route = f'''\n\n# DPort user-confirmed updater endpoint: never called automatically.\n@{app_name}.get("/dport/update")\ndef _dport_user_confirmed_update():\n    try:\n        return dport_release_updater.request_update()\n    except Exception as exc:\n        return {{"ok": False, "state": "update_failed", "message": str(exc)}}, 500\n\n'''

    anchor = re.search(r"^\s*if\s+__name__\s*==\s*[\"']__main__[\"']\s*:", main_text, flags=re.M)
    if anchor:
        insert_at = anchor.start()
    else:
        run_match = re.search(rf"^\s*{re.escape(app_name)}\.run\(", main_text, flags=re.M)
        if not run_match:
            raise RuntimeError("Could not find main Flask run block in main.py")
        insert_at = run_match.start()

    if "import dport_release_updater" not in main_text:
        main_text = "import dport_release_updater\n" + main_text
        insert_at += len("import dport_release_updater\n")

    return main_text[:insert_at] + route + main_text[insert_at:]


def patch_zip(source_zip: bytes, version: str, pm3: str, output: Path) -> None:
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        with zipfile.ZipFile(io.BytesIO(source_zip), "r") as zin:
            zin.extractall(td_path)

        root = td_path / ROOT_NAME
        if not root.exists():
            raise RuntimeError(f"Source root missing: {root}")

        version_file = root / "src" / "dport_version.py"
        req_file = root / "requirements-build.txt"
        updater_file = root / "src" / "dport_release_updater.py"
        main_file = root / "src" / "main.py"
        map_file = root / "src" / "templates" / "map.html"

        for required in (version_file, req_file, updater_file, main_file, map_file):
            if not required.exists():
                raise RuntimeError(f"Required source file missing: {required}")

        version_file.write_text(f'DPORT_VERSION="{version}"\n', encoding="utf-8")

        req = req_file.read_text(encoding="utf-8", errors="replace")
        req2, count = re.subn(
            r"(?mi)^\s*pymobiledevice3\s*==\s*[^\r\n#]+",
            f"pymobiledevice3=={pm3}",
            req,
        )
        if count != 1:
            raise RuntimeError("Expected exactly one pymobiledevice3 pin")
        req_file.write_text(req2, encoding="utf-8")

        updater_file.write_text(SAFE_UPDATER, encoding="utf-8")

        main_text = main_file.read_text(encoding="utf-8", errors="replace")
        main_file.write_text(patch_main(main_text), encoding="utf-8")

        map_text = map_file.read_text(encoding="utf-8", errors="replace")
        if "dport-user-update-dialog" not in map_text:
            if "</body>" in map_text:
                map_text = map_text.replace("</body>", UPDATE_UI + "\n</body>", 1)
            else:
                map_text += UPDATE_UI
        if "dport-brand-meta-row-stack-final" not in map_text:
            if "</body>" in map_text:
                map_text = map_text.replace("</body>", BRAND_STATUS_LAYOUT_FIX + "\n</body>", 1)
            else:
                map_text += BRAND_STATUS_LAYOUT_FIX

        if "dport-brand-header-height-final" not in map_text:
            if "</body>" in map_text:
                map_text = map_text.replace("</body>", BRAND_HEADER_HEIGHT_FIX + "\n</body>", 1)
            else:
                map_text += BRAND_HEADER_HEIGHT_FIX

        map_text = map_text.replace("（準備自動更新）", "（可手動更新）")

        manual_css = """
<style id="dport-manual-update-status-final">
#dport-pm3-status.dport-update-clickable{
    cursor:pointer!important;
    text-decoration:underline!important;
    text-underline-offset:2px!important;
}
#dport-pm3-status.dport-update-clickable:hover{
    filter:brightness(1.18)!important;
}
</style>
"""
        if "dport-manual-update-status-final" not in map_text:
            if "</body>" in map_text:
                map_text = map_text.replace("</body>", manual_css + "\n</body>", 1)
            else:
                map_text += manual_css

        map_file.write_text(map_text, encoding="utf-8")

        if output.exists():
            output.unlink()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            for path in root.rglob("*"):
                if path.is_file():
                    zout.write(path, (Path(ROOT_NAME) / path.relative_to(root)).as_posix())


def main() -> int:
    global KNOWN_GOOD_COMMIT
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--pm3", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--source-commit", default=KNOWN_GOOD_COMMIT)
    args = parser.parse_args()

    KNOWN_GOOD_COMMIT = args.source_commit

    source_zip = get_good_zip()
    patch_zip(source_zip, args.version, args.pm3, Path(args.output))
    print(f"Prepared repaired source: DPort {args.version}, pymobiledevice3 {args.pm3}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
