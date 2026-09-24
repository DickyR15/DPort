from pathlib import Path
import re

path = Path("src/templates/map.html")
if not path.exists():
    raise SystemExit(f"UI template not found: {path}")

text = path.read_text(encoding="utf-8")
original = text

# 1) Remove the connected-state guard from manual refresh. The physical USB
# presence monitor is responsible for disabling the button while a connected
# USB device is actually present.
old_guard = '''async function dportRefreshDeviceList() {
    if (typeof isDeviceConnected !== 'undefined' && isDeviceConnected) {
        displayToast("裝置已連接，無需重新整理裝置清單。");
        return;
    }

    if (deviceListManualRefreshInFlight) return;'''
new_guard = '''async function dportRefreshDeviceList() {
    if (deviceListManualRefreshInFlight) return;'''
if old_guard in text:
    text = text.replace(old_guard, new_guard, 1)

# 2) Never re-disable Refresh from the refresh routine based on stale
# isDeviceConnected.
text = text.replace(
    "button.disabled = (typeof isDeviceConnected !== 'undefined' && isDeviceConnected);",
    "button.disabled = false;",
)

# 3) Remove the historical 500ms sync script which blindly disables the button
# whenever isDeviceConnected is true, even after the cable has been removed.
legacy = re.compile(
    r'''\s*<script>\s*\(function\(\)\{\s*
    function\s+syncDeviceRefreshButton\(\)\{.*?
    document\.addEventListener\('DOMContentLoaded',function\(\)\{\s*
    syncDeviceRefreshButton\(\);\s*
    setInterval\(syncDeviceRefreshButton,500\);\s*
    \}\);\s*
    \}\)\(\);\s*</script>''',
    re.S | re.X,
)
text, legacy_removed = legacy.subn("\n", text)

# 4) Replace any prior authoritative synchronizer with one final synchronizer
# that uses the actual /usb_presence endpoint. This makes the physical cable
# the source of truth for the disabled state.
text = re.sub(
    r'''\s*<script id="dport-refresh-authoritative-state">.*?</script>\s*''',
    "\n",
    text,
    flags=re.S,
)

authoritative = r'''
<script id="dport-refresh-authoritative-state">
(function(){
    var refreshStateBusy = false;

    async function syncRefreshButton(){
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
                return String((device && device.ConnectionType) || 'USB').toUpperCase() === 'USB';
            });
            var connected = (
                typeof isDeviceConnected !== 'undefined' &&
                isDeviceConnected === true
            );

            button.disabled = usbPresent && connected;
            button.removeAttribute('aria-disabled');
        } catch (e) {
            // Do not lock Refresh when the physical presence probe fails.
            button.disabled = false;
        } finally {
            refreshStateBusy = false;
        }
    }

    document.addEventListener('DOMContentLoaded', function(){
        syncRefreshButton();
        setInterval(syncRefreshButton, 800);
    });
    window.addEventListener('focus', syncRefreshButton);
})();
</script>
'''
text += "
" + authoritative + "
"

text = text.replace(
    'title="重新讀取 USB 裝置清單"',
    'title="重新讀取 USB / Wi-Fi 裝置清單"',
)

path.write_text(text, encoding="utf-8")

print(f"legacy sync scripts removed: {legacy_removed}")
print(f"changed: {text != original}")
