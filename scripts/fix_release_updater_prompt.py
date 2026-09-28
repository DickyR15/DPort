from pathlib import Path
import re
import sys

def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 match, found {count}")
    return text.replace(old, new, 1)

def patch_updater(path: Path) -> None:
    text = path.read_text(encoding='utf-8')
    old = '''            with _LOCK:
                _STATE["state"] = "update_available"
                _STATE["latest_version"] = version
                _STATE["latest_url"] = release_url
                _STATE["message"] = f"發現 DPort 新版 v{version}，準備自動更新…"
            _save_state()
            _launch_update(version, exe_url, sha_url, release_url)
'''
    new = '''            with _LOCK:
                _STATE["state"] = "update_available"
                _STATE["latest_version"] = version
                _STATE["latest_url"] = release_url
                _STATE["message"] = f"發現 DPort 新版 v{version}，等待使用者確認更新。"
            _save_state()
'''
    if old in text:
        text = text.replace(old, new, 1)
    elif '等待使用者確認更新' not in text:
        raise RuntimeError('check_now auto-update block not found')

    marker = 'def get_status() -> dict[str, Any]:\n'
    if 'def dismiss_update(' not in text:
        insert = '''def dismiss_update() -> dict[str, Any]:
    with _LOCK:
        _STATE["state"] = "dismissed"
        _STATE["message"] = "已暫不更新，仍可繼續使用目前版本。"
        _STATE["restart_required"] = False
    _save_state()
    return get_status()

def install_update() -> dict[str, Any]:
    with _LOCK:
        if str(_STATE.get("state") or "") == "updating":
            return dict(_STATE)
        known_latest = str(_STATE.get("latest_version") or "").strip()

    current = _bundled_version()
    candidate = _get_update_candidate(current)
    if candidate is None:
        with _LOCK:
            _STATE["current_version"] = current
            _STATE["state"] = "latest"
            _STATE["latest_version"] = current
            _STATE["message"] = f"DPort v{current} 已是最新正式版"
            _STATE["restart_required"] = False
        _save_state()
        return get_status()

    version, exe_url, sha_url, release_url = candidate
    if known_latest and _version_key(version) != _version_key(known_latest):
        raise RuntimeError("更新版本資訊已變更，請重新檢查。")

    _launch_update(version, exe_url, sha_url, release_url)
    return get_status()


'''
        text = replace_once(text, marker, insert + marker, 'status function insertion')

    path.write_text(text, encoding='utf-8')

def patch_main(path: Path) -> None:
    text = path.read_text(encoding='utf-8')
    anchor = "@app.route('/pymobiledevice3/status')\n"
    if '/dport/update/install' not in text:
        routes = '''@app.route('/dport/update/install', methods=['POST'])
def dport_update_install():
    from dport_release_updater import install_update, get_status
    try:
        return jsonify(install_update())
    except Exception as exc:
        logging.getLogger('DPort').exception('DPort update install failed')
        status = get_status()
        return jsonify({
            'state': 'update_failed',
            'message': f'更新失敗：{exc}',
            'current_version': status.get('current_version'),
            'latest_version': status.get('latest_version'),
        }), 500


@app.route('/dport/update/dismiss', methods=['POST'])
def dport_update_dismiss():
    from dport_release_updater import dismiss_update
    return jsonify(dismiss_update())


'''
        text = replace_once(text, anchor, routes + anchor, 'DPort update routes insertion')
    path.write_text(text, encoding='utf-8')

def patch_map(path: Path) -> None:
    text = path.read_text(encoding='utf-8')
    old_modal = '''    <div class="dport-pm3-progress"><div class="dport-pm3-progress-bar"></div></div>
    <div id="dport-pm3-update-note" class="dport-pm3-update-note">請稍候</div>
'''
    new_modal = '''    <div class="dport-pm3-progress"><div class="dport-pm3-progress-bar"></div></div>
    <div id="dport-pm3-update-note" class="dport-pm3-update-note">請稍候</div>
    <div id="dport-pm3-update-actions" class="dport-pm3-update-actions">
      <button type="button" id="dport-pm3-update-confirm" class="dport-pm3-update-btn primary" onclick="dportPm3ConfirmUpdate()">立即更新</button>
      <button type="button" id="dport-pm3-update-cancel" class="dport-pm3-update-btn secondary" onclick="dportPm3CancelUpdate()">稍後再說</button>
    </div>
'''
    if 'id="dport-pm3-update-actions"' not in text:
        if old_modal not in text:
            raise RuntimeError('update modal markup not found')
        text = text.replace(old_modal, new_modal, 1)

    css_anchor = ".dport-pm3-update-note{margin-top:12px!important;color:#ffdfaa!important;font-size:14px!important;font-weight:900!important}\n"
    css_add = css_anchor + ".dport-pm3-update-actions{display:flex!important;justify-content:center!important;gap:10px!important;margin-top:18px!important}\n" + ".dport-pm3-update-btn{min-width:124px!important;height:42px!important;padding:6px 14px!important;border-radius:10px!important;border:1px solid #56657f!important;font-size:14px!important;font-weight:850!important;cursor:pointer!important}\n" + ".dport-pm3-update-btn.primary{background:#4f72d8!important;color:#fff!important;border-color:#6786df!important}\n" + ".dport-pm3-update-btn.secondary{background:#2a3240!important;color:#e6edf7!important}\n" + ".dport-pm3-update-btn:disabled{opacity:.55!important;cursor:not-allowed!important}\n"
    if '.dport-pm3-update-actions{' not in text:
        if css_anchor not in text:
            raise RuntimeError('update modal CSS anchor not found')
        text = text.replace(css_anchor, css_add, 1)

    js_anchor = 'function dportPm3HideUpdateModal(){\n'
    if 'function dportPm3ConfirmUpdate()' not in text:
        js_add = '''async function dportPm3ConfirmUpdate(){
    const confirmBtn=document.getElementById('dport-pm3-update-confirm');
    const cancelBtn=document.getElementById('dport-pm3-update-cancel');
    if(confirmBtn)confirmBtn.disabled=true;
    if(cancelBtn)cancelBtn.disabled=true;
    try{
        const r=await fetch('/dport/update/install',{method:'POST'});
        const s=await r.json();
        dportPm3RefreshStateFromObject(s);
        dportRefreshPm3Status();
    }catch(e){
        if(confirmBtn)confirmBtn.disabled=false;
        if(cancelBtn)cancelBtn.disabled=false;
    }
}

async function dportPm3CancelUpdate(){
    try{
        const r=await fetch('/dport/update/dismiss',{method:'POST'});
        const s=await r.json();
        dportPm3RefreshStateFromObject(s);
        dportPm3HideUpdateModal();
    }catch(e){
        dportPm3HideUpdateModal();
    }
}

function dportPm3RefreshStateFromObject(s){
    const el=document.getElementById('dport-pm3-status');
    const current=s.current_version?'v'+String(s.current_version).replace(/^v/,''):'?';
    const latest=s.latest_version?'v'+String(s.latest_version).replace(/^v/,''):'';
    if(el && s.state==='update_available'){
        el.className='dport-pm3-status update';
        el.textContent='DPort：'+current+' → '+latest+'（可更新）';
    }
    if(s.state==='update_available') dportPm3ShowUpdateModal('update_available',current,latest,s.message||'');
    else if(s.state==='updating') dportPm3ShowUpdateModal('updating',current,latest,s.message||'');
}

'''
        text = replace_once(text, js_anchor, js_add + js_anchor, 'update button JS insertion')

    replacements = [
        ("text.textContent=`${cur} → ${lat}，準備自動更新…`;", "text.textContent=`${cur} → ${lat}，是否要更新？`;"),
        ("note.textContent='請勿關閉 DPort';", "note.textContent='選擇「立即更新」才會開始下載；選擇「稍後再說」則維持目前版本。';"),
        ("el.textContent='DPort：'+current+' → '+latest+'（準備自動更新）';", "el.textContent='DPort：'+current+' → '+latest+'（可更新）';"),
        ("window.setInterval(dportRefreshPm3Status,800);", "window.setInterval(dportRefreshPm3Status,1500);"),
    ]
    for old, new in replacements:
        if old in text:
            text = text.replace(old, new, 1)

    show_anchor = '''    modal.classList.add('show');
    modal.classList.remove('done','error');
    modal.setAttribute('aria-hidden','false');
'''
    show_new = '''    modal.classList.add('show');
    modal.classList.remove('done','error');
    modal.setAttribute('aria-hidden','false');
    const actions=document.getElementById('dport-pm3-update-actions');
    const confirmBtn=document.getElementById('dport-pm3-update-confirm');
    const cancelBtn=document.getElementById('dport-pm3-update-cancel');
    if(actions) actions.style.display = state==='update_available' ? 'flex' : 'none';
    if(confirmBtn) confirmBtn.disabled = state!=='update_available';
    if(cancelBtn) cancelBtn.disabled = state!=='update_available';
'''
    if show_anchor in text and 'const actions=document.getElementById(\'dport-pm3-update-actions\')' not in text:
        text = text.replace(show_anchor, show_new, 1)

    path.write_text(text, encoding='utf-8')

def main() -> int:
    root = Path('src')
    updater = root / 'dport_release_updater.py'
    main_py = root / 'main.py'
    map_html = root / 'templates' / 'map.html'
    for p in (updater, main_py, map_html):
        if not p.exists():
            raise SystemExit(f'Missing required source file: {p}')
    patch_updater(updater)
    patch_main(main_py)
    patch_map(map_html)
    print('DPort update prompt patch applied.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())