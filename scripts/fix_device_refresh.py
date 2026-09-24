from pathlib import Path
import re

path = Path("src/templates/map.html")
if not path.exists():
    raise SystemExit(f"UI template not found: {path}")

text = path.read_text(encoding="utf-8")
original = text

# Allow manual refresh even while the app still reports a stale connected flag.
text, guard_hits = re.subn(
    r'(?s)(async function dportRefreshDeviceList\(\)\s*\{\s*)'
    r'if\s*\(typeof isDeviceConnected\s*!==\s*[\'"]undefined[\'"]\s*&&\s*isDeviceConnected\)\s*\{.*?\}\s*',
    r'\1',
    text,
    count=1,
)

# Normalize every historical copy of the refresh-button state helper.
sync_pattern = re.compile(
    r"""const\s+connected\s*=\s*\(typeof\s+isDeviceConnected\s*!==\s*'undefined'\s*&&\s*isDeviceConnected\s*===\s*true\)\s*;\s*
if\s*\(\s*connected\s*\)\s*\{\s*
button\.disabled\s*=\s*true\s*;\s*
if\s*\(\s*button\.textContent\s*!==\s*'↻ 重新整理'\s*&&\s*button\.textContent\s*!==\s*'↻ 讀取中…'\s*\)\s*\{\s*
button\.textContent\s*=\s*'↻ 重新整理'\s*;\s*
\}\s*
\}""",
    re.S,
)
replacement = """const refreshing=(typeof deviceListManualRefreshInFlight!=='undefined' && deviceListManualRefreshInFlight===true);
        button.disabled=refreshing;
        if(!refreshing && button.textContent!=='↻ 重新整理' && button.textContent!=='↻ 讀取中…'){
            button.textContent='↻ 重新整理';
        }"""
text, sync_hits = sync_pattern.subn(replacement, text)

# Never re-disable the button in the refresh routine based on connection state.
text, final_hits = re.subn(
    r'button\.disabled\s*=\s*\(\s*typeof\s+isDeviceConnected[^;]+;',
    'button.disabled = false;',
    text,
)

# Make the tooltip accurately describe the operation.
text = text.replace(
    'title="重新讀取 USB 裝置清單"',
    'title="重新讀取 USB / Wi-Fi 裝置清單"',
)

path.write_text(text, encoding="utf-8")

print(f"refresh guard removed: {guard_hits}")
print(f"refresh sync blocks normalized: {sync_hits}")
print(f"stale final-state assignments fixed: {final_hits}")
print(f"changed: {text != original}")

if sync_hits == 0 and final_hits == 0 and guard_hits == 0:
    raise SystemExit("No refresh-state fix points were found; source layout may have changed.")
