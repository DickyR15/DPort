from pathlib import Path
import re

path = Path("src/templates/map.html")
if not path.exists():
    raise SystemExit(f"UI template not found: {path}")

text = path.read_text(encoding="utf-8")
original = text

# Remove the old connected-state guard from the manual refresh function.
text, guard_hits = re.subn(
    r'(?s)(async function dportRefreshDeviceList\(\)\s*\{\s*)'
    r'if\s*\(typeof isDeviceConnected\s*!==\s*[\'"]undefined[\'"]\s*&&\s*isDeviceConnected\)\s*\{.*?\}\s*',
    r'\1',
    text,
    count=0,
)

# Normalize every historical refresh-button synchronizer.
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
sync_replacement = """const refreshing=(typeof deviceListManualRefreshInFlight!=='undefined' && deviceListManualRefreshInFlight===true);
        button.disabled=refreshing;
        if(!refreshing && button.textContent!=='↻ 重新整理' && button.textContent!=='↻ 讀取中…'){
            button.textContent='↻ 重新整理';
        }"""
text, sync_hits = sync_pattern.subn(sync_replacement, text)

# Never leave the button disabled in the manual-refresh finally block.
text, final_hits = re.subn(
    r'button\.disabled\s*=\s*\(\s*typeof\s+isDeviceConnected[^;]+;',
    'button.disabled = false;',
    text,
)

text = text.replace(
    'title="重新讀取 USB 裝置清單"',
    'title="重新讀取 USB / Wi-Fi 裝置清單"',
)

# Authoritative final synchronizer: physical USB presence is the source of truth.
# This defeats stale isDeviceConnected state after a cable removal.
guard = r'''
<script id="dport-refresh-authoritative-state">
(function(){
    var refreshStateBusy = false;

    async function syncRefreshFromPhysicalUsb(){
        var button = document.getElementById('refresh-device');
        if (!button || refreshStateBusy) return;

        var manualBusy = (
            typeof deviceListManualRefreshInFlight !== 'undefined' &&
            deviceListManualRefreshInFlight === true
        );
        if (manualBusy) {
            button.disabled = true;
            return;
        }

        refreshStateBusy = true;
        try {
            var response = await fetch('/usb_presence?_=' + Date.now(), {
                cache: 'no-store'
            });
            var payload = response && response.ok ? await response.json() : null;
            var devices = payload && Array.isArray(payload.devices) ? payload.devices : [];
            var usbPresent = devices.some(function(device){
                return String(device && device.ConnectionType || 'USB').toUpperCase() === 'USB';
            });

            // USB physically present + app connected => disable.
            // USB absent (including Wi-Fi-only) => enable.
            button.disabled = usbPresent &&
                (typeof isDeviceConnected !== 'undefined' &&
                 isDeviceConnected === true);
        } catch (e) {
            // A failed lightweight probe must never permanently lock Refresh.
            button.disabled = false;
        } finally {
            refreshStateBusy = false;
        }
    }

    document.addEventListener('DOMContentLoaded', function(){
        syncRefreshFromPhysicalUsb();
        setInterval(syncRefreshFromPhysicalUsb, 1200);
    });

    window.addEventListener('load', syncRefreshFromPhysicalUsb);
})();
</script>
'''

if 'id="dport-refresh-authoritative-state"' in text:
    text = re.sub(
        r'(?s)\s*<script id="dport-refresh-authoritative-state">.*?</script>\s*',
        '\n',
        text,
    )
text += '\n' + guard + '\n'

path.write_text(text, encoding='utf-8')

print(f"refresh guards removed: {guard_hits}")
print(f"refresh sync blocks normalized: {sync_hits}")
print(f"stale final-state assignments fixed: {final_hits}")
print(f"changed: {text != original}")
