from pathlib import Path
import re

path = Path("src/templates/map.html")
if not path.exists():
    raise SystemExit(f"UI template not found: {path}")

text = path.read_text(encoding="utf-8")
original = text

# Keep the intended rule inside dportRefreshDeviceList:
# connected => the refresh action itself is not allowed.
# The bug was that separate background code kept re-disabling the button
# after USB had actually been unplugged.
old_finally = "button.disabled = (typeof isDeviceConnected !== 'undefined' && isDeviceConnected);"
text = text.replace(old_finally, "button.disabled = false;")

# Remove the stale 500ms background synchronizer which blindly disabled the
# button whenever isDeviceConnected remained true.
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

# When the physical USB cable is detected as removed, explicitly enable Refresh.
disconnect_anchor = "    if (spinnerElement) spinnerElement.style.display = 'none';"
disconnect_insert = """    if (spinnerElement) spinnerElement.style.display = 'none';

    var refreshButton = document.getElementById('refresh-device');
    if (refreshButton) {
        refreshButton.disabled = false;
        refreshButton.removeAttribute('aria-disabled');
    }
"""
if disconnect_anchor in text and "refreshButton.disabled = false;" not in text:
    text = text.replace(disconnect_anchor, disconnect_insert, 1)

# A successful connection should explicitly disable Refresh.
connect_anchor = """        if (connectButton) {
            connectButton.disabled = true;  // Disable the button
        }
"""
connect_insert = """        if (connectButton) {
            connectButton.disabled = true;  // Disable the button
        }
        var refreshButtonConnected = document.getElementById('refresh-device');
        if (refreshButtonConnected) {
            refreshButtonConnected.disabled = true;
            refreshButtonConnected.removeAttribute('aria-disabled');
        }
"""
if connect_anchor in text and "refreshButtonConnected.disabled = true;" not in text:
    text = text.replace(connect_anchor, connect_insert, 1)

# Manual/programmatic disconnect should also re-enable Refresh.
manual_disc_anchor = """        if (connectButton) {
            connectButton.disabled = false;
        }
    }
"""
manual_disc_insert = """        if (connectButton) {
            connectButton.disabled = false;
        }
        var refreshButtonDisconnected = document.getElementById('refresh-device');
        if (refreshButtonDisconnected) {
            refreshButtonDisconnected.disabled = false;
            refreshButtonDisconnected.removeAttribute('aria-disabled');
        }
    }
"""
if manual_disc_anchor in text and "refreshButtonDisconnected.disabled = false;" not in text:
    text = text.replace(manual_disc_anchor, manual_disc_insert, 1)

path.write_text(text, encoding="utf-8")

print(f"legacy background sync removed: {legacy_removed}")
print(f"changed: {text != original}")
if legacy_removed == 0 and old_finally not in original:
    raise SystemExit("Expected stale refresh logic was not found.")
