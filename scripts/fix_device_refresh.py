from pathlib import Path
import re

path = Path("src/templates/map.html")
if not path.exists():
    raise SystemExit(f"UI template not found: {path}")

text = path.read_text(encoding="utf-8")
original = text

# The refresh button must only be disabled while the application is actively
# connected. Remove the historical background timer that re-disabled it from
# stale isDeviceConnected state after the USB cable was removed.
legacy_pattern = re.compile(
    r'''\s*<script>\s*\(function\(\)\{\s*
        function\s+syncDeviceRefreshButton\(\)\s*\{.*?
        document\.addEventListener\(\s*['"]DOMContentLoaded['"]\s*,\s*function\(\)\{\s*
        syncDeviceRefreshButton\(\);\s*
        setInterval\(syncDeviceRefreshButton\s*,\s*500\);\s*
        \}\);\s*
        \}\)\(\);\s*</script>\s*''',
    re.S | re.X,
)
text, legacy_removed = legacy_pattern.subn("\n", text)

# Manual refresh is intentionally blocked while an active connection exists.
# After refresh finishes, the button must not be left disabled based on stale
# state.
text = text.replace(
    "button.disabled = (typeof isDeviceConnected !== 'undefined' && isDeviceConnected);",
    "button.disabled = false;",
)

# Make the physical USB removal handler the authoritative place that restores
# Refresh.
handler_pattern = re.compile(
    r'''(function\s+handleUsbCableRemoved\(\)\s*\{.*?
        if\s*\(spinnerElement\)\s*spinnerElement\.style\.display\s*=\s*'none';)''',
    re.S | re.X,
)
if "refreshButtonAfterUsbRemoval.disabled = false;" not in text:
    def handler_repl(m):
        return m.group(1) + """
    var refreshButtonAfterUsbRemoval = document.getElementById('refresh-device');
    if (refreshButtonAfterUsbRemoval) {
        refreshButtonAfterUsbRemoval.disabled = false;
        refreshButtonAfterUsbRemoval.removeAttribute('aria-disabled');
    }"""
    text, handler_hits = handler_pattern.subn(handler_repl, text, count=1)
else:
    handler_hits = 0

text = text.replace(
    'title="重新讀取 USB 裝置清單"',
    'title="重新讀取 USB / Wi-Fi 裝置清單"',
)

path.write_text(text, encoding="utf-8")

print(f"legacy refresh timer removed: {legacy_removed}")
print(f"USB removal handler patched: {handler_hits}")
print(f"changed: {text != original}")

if legacy_removed == 0 and handler_hits == 0 and "button.disabled = false;" not in text:
    raise SystemExit("Refresh state patch did not find expected source patterns.")
