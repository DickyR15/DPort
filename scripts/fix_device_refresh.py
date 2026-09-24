from pathlib import Path
import re

path = Path("src/templates/map.html")
if not path.exists():
    raise SystemExit(f"UI template not found: {path}")

text = path.read_text(encoding="utf-8")
original = text

# Remove every historical sync script that blindly disables Refresh whenever
# isDeviceConnected is stale.
legacy_script_pattern = re.compile(
    r'''\s*<script>\s*\(function\(\)\{\s*
        function\s+syncDeviceRefreshButton\(\)\s*\{.*?
        document\.addEventListener\(['"]DOMContentLoaded['"],function\(\)\{\s*
        syncDeviceRefreshButton\(\);\s*
        setInterval\(syncDeviceRefreshButton,500\);\s*
        \}\);\s*
        \}\)\(\);\s*</script>''',
    re.S | re.X,
)
text, legacy_count = legacy_script_pattern.subn("\n", text)

# Remove stale connection-state guards from every manual refresh function.
guard_pattern = re.compile(
    r'''(?s)(async function dportRefreshDeviceList\(\)\s*\{\s*)'''
    r'''if\s*\(typeof\s+isDeviceConnected\s*!==\s*['"]undefined['"]\s*&&\s*isDeviceConnected\)\s*\{.*?\}\s*'''
)
text, guard_count = guard_pattern.subn(r'\1', text)

# Never set Refresh.disabled from isDeviceConnected inside refresh cleanup.
text, final_count = re.subn(
    r'''button\.disabled\s*=\s*\(\s*typeof\s+isDeviceConnected.*?;''',
    'button.disabled = false;',
    text,
)

# Add one authoritative synchronizer.
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

            // Connected through USB: disabled.
            // USB removed or Wi-Fi-only: enabled, even if the old JS connection
            // flag is stale.
            button.disabled = usbPresent && connected;
            button.removeAttribute('aria-disabled');
        } catch (e) {
            // A failed presence probe must never trap the button in a disabled
            // state after USB has been removed.
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

# Make the tooltip accurately describe the scope.
text = text.replace(
    'title="重新讀取 USB 裝置清單"',
    'title="重新讀取 USB / Wi-Fi 裝置清單"',
)

path.write_text(text, encoding="utf-8")

print(f"legacy refresh sync scripts removed: {legacy_count}")
print(f"stale refresh guards removed: {guard_count}")
print(f"stale cleanup assignments fixed: {final_count}")
print(f"changed: {text != original}")

if legacy_count == 0 and guard_count == 0 and final_count == 0:
    raise SystemExit("No known stale refresh logic was found; inspect source layout.")
