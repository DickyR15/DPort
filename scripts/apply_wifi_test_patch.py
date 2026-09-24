from pathlib import Path
import re

main = Path("src/main.py")
map_file = Path("src/templates/map.html")

if not main.exists():
    raise SystemExit("src/main.py is missing")
if not map_file.exists():
    raise SystemExit("src/templates/map.html is missing")

src = main.read_text(encoding="utf-8")
ui = map_file.read_text(encoding="utf-8")

# ---------- Python backend: enable Wi-Fi and list Wi-Fi devices ----------
state_pattern = re.compile(
    r'''(?m)^(\s*)try:\s*\n\1    info\["wifiState"\]\s*=\s*await client\.get_enable_wifi_connections\(\)\s*\n\1except Exception:\s*\n\1    info\["wifiState"\]\s*=\s*False\s*$'''
)
state_repl = r'''\1try:
\1    info["wifiState"] = await client.get_enable_wifi_connections()
\1    if not info["wifiState"]:
\1        logger.info("Wi-Fi lockdown is off; enabling it over USB.")
\1        await client.set_enable_wifi_connections(True)
\1        await asyncio.sleep(1.0)
\1        info["wifiState"] = await client.get_enable_wifi_connections()
\1except Exception as exc:
\1    logger.warning(f"Wi-Fi lockdown enable/check failed: {exc}")
\1    info["wifiState"] = False'''
src, state_hits = state_pattern.subn(state_repl, src, count=0)

disabled_pattern = re.compile(
    r'''(?m)^(\s*)# USB-ONLY: Wi-Fi / Network discovery intentionally disabled\.\s*\n\1logger\.info\("USB-ONLY mode: Wi-Fi/Bonjour/mDNS/RemotePairing discovery skipped"\)\s*$'''
)
network_repl = r'''\1# Diagnostic + paired discovery for Apple's normal mobdev2 Wi-Fi path.
\1# First browse raw Bonjour so we can distinguish "no mDNS advert" from
\1# "advertisement received but no matching Windows pairing record".
\1try:
\1    adverts = asyncio.run(browse_mobdev2(timeout=min(float(timeout), 4.0)))
\1    logger.info(f"RAW mobdev2 Bonjour adverts: {len(adverts)}")
\1    for advert in adverts:
\1        try:
\1            addresses = [getattr(a, "full_ip", str(a)) for a in getattr(advert, "addresses", [])]
\1            logger.info(
\1                "mobdev2 advert: "
\1                f"instance={getattr(advert, 'instance', None)!r}, "
\1                f"port={getattr(advert, 'port', None)}, "
\1                f"addresses={addresses}, "
\1                f"properties={getattr(advert, 'properties', {})}"
\1            )
\1        except Exception as exc:
\1            logger.warning(f"mobdev2 advert logging failed: {exc}")
\1except Exception as exc:
\1    logger.warning(f"RAW mobdev2 Bonjour browse failed: {exc}")
\1
\1try:
\1    network_count = 0
\1    async for ip, network_lockdown in get_mobdev2_lockdowns(
\1        udid=None,
\1        only_paired=True,
\1        timeout=min(float(timeout), 5.0),
\1    ):
\1        try:
\1            info = dict(network_lockdown.short_info)
\1            network_udid = (
\1                getattr(network_lockdown, "udid", None)
\1                or info.get("UniqueDeviceID")
\1                or info.get("Identifier")
\1            )
\1            if not network_udid:
\1                continue
\1            info["Identifier"] = network_udid
\1            info["ConnectionType"] = "Network"
\1            info["wifiAddress"] = str(ip)
\1            info["wifiPort"] = 62078
\1            info["wifiState"] = True
\1            add_device(network_udid, "Network", info)
\1            network_count += 1
\1            logger.info(
\1                f"Wi-Fi mobdev2 paired device found: udid={network_udid}, ip={ip}"
\1            )
\1        except Exception as exc:
\1            logger.warning(f"Wi-Fi device metadata failed: {exc}")
\1        finally:
\1            try:
\1                await network_lockdown.close()
\1            except Exception:
\1                pass
\1    logger.info(f"Wi-Fi mobdev2 paired discovery completed: {network_count} device(s)")
\1except Exception as exc:
\1    logger.warning(f"Wi-Fi mobdev2 paired discovery failed: {exc}")'''
src, network_hits = disabled_pattern.subn(network_repl, src, count=0)

if network_hits == 0:
    raise SystemExit("The /list_devices Wi-Fi disabled block was not found in src/main.py")

# Ensure all mobdev2 calls use pymobiledevice3's automatic host pair-record sources.
src = src.replace("pair_records=get_home_folder(),\n", "")

# Allow USB and Wi-Fi/Network connection types through the common connect route.
usb_guard = re.compile(
    r'''(?s)    if connection_type != "USB":\n        logger\.warning\(f"USB-ONLY build: rejecting non-USB connection type: \{connection_type\}"\)\n        return jsonify\(\{"error": "USB-only mode: please connect the iPhone by USB\."\}\), 400\n\n'''
)
src, usb_guard_hits = usb_guard.subn(
    '''    if connection_type not in ("USB", "Network", "Manual"):\n        logger.warning(f"Unsupported connection type: {connection_type}")\n        return jsonify({"error": f"Unsupported connection type: {connection_type}"}), 400\n\n''',
    src,
    count=0,
)

network_guard = re.compile(
    r'''(?s)    if connection_type == "Network":\n        check_pair_record\(udid\)\n        if pair_record is None:\n            logger\.error\("Network: No Remote Pair Record Found\. Please connect once by USB first\."\)\n            return jsonify\(\{"Error": "No Pair Record Found"\}\)\n        return connect_wifi\(data\)'''
)
src, network_guard_hits = network_guard.subn(
    '''    if connection_type == "Network":\n        return connect_wifi(data)''',
    src,
    count=0,
)

manual_guard = re.compile(
    r'''(?s)    if connection_type == "Manual":\n        check_pair_record\(udid\)\n        if pair_record is None:\n            return jsonify\(\{"Error": "No Pair Record Found"\}\)\n        return connect_wifi\(data\)'''
)
src, manual_guard_hits = manual_guard.subn(
    '''    if connection_type == "Manual":\n        return connect_wifi(data)''',
    src,
    count=0,
)

# Keep USB/Wi-Fi selection stable across background / force refreshes.
clear_marker = """        deviceDropdown.innerHTML = '';
        connectionDropdown.innerHTML = '';
"""
if clear_marker not in ui:
    raise SystemExit("populateDeviceList clear marker not found")
ui = ui.replace(clear_marker, """        const previousOption = deviceDropdown.options[deviceDropdown.selectedIndex];
        const previousKey = previousOption ? (previousOption.dataset.dportKey || '') : '';

        deviceDropdown.innerHTML = '';
        connectionDropdown.innerHTML = '';
""", 1)

option_marker = """                    option.value = JSON.stringify(deviceInfo);

                    devicesInfo[udid] = devicesInfo[udid] || {};
"""
if option_marker not in ui:
    raise SystemExit("device option marker not found")
ui = ui.replace(option_marker, """                    option.value = JSON.stringify(deviceInfo);
                    option.dataset.dportKey = optionKey;

                    devicesInfo[udid] = devicesInfo[udid] || {};
""", 1)

restore_marker = """        if (requestSerial !== deviceListRequestSerial) return false;
        deviceDropdown.devicesInfo = devicesInfo;
"""
if restore_marker not in ui:
    raise SystemExit("device restore marker not found")
ui = ui.replace(restore_marker, """        if (requestSerial !== deviceListRequestSerial) return false;

        if (previousKey) {
            const restoredIndex = Array.from(deviceDropdown.options).findIndex(function(opt){
                return (opt.dataset && opt.dataset.dportKey) === previousKey;
            });
            if (restoredIndex >= 0) {
                deviceDropdown.selectedIndex = restoredIndex;
            }
        }

        deviceDropdown.devicesInfo = devicesInfo;
""", 1)

# Ensure the Wi-Fi tunnel also uses pymobiledevice3 automatic host pair-record
# discovery rather than a hard-coded path.
src = src.replace('pair_records=get_home_folder(),
', '')

main.write_text(src, encoding="utf-8")
map_file.write_text(ui, encoding="utf-8")

print(f"Wi-Fi connect guard hits: {usb_guard_hits}")
print(f"Network legacy guard hits: {network_guard_hits}")
print(f"Manual legacy guard hits: {manual_guard_hits}")
print("Wi-Fi tunnel pair-record override removed.")
print("USB/Wi-Fi selection is preserved across list refresh.")

# ---------- UI ----------
# ---------- UI: explicit connection-state refresh behavior ----------
legacy_refresh = re.compile(
    r'''\s*<script>\s*\(function\(\)\{\s*
    function\s+syncDeviceRefreshButton\(\)\s*\{.*?
    document\.addEventListener\(\s*['"]DOMContentLoaded['"]\s*,\s*function\(\)\{\s*
    syncDeviceRefreshButton\(\);\s*
    setInterval\(syncDeviceRefreshButton\s*,\s*500\);\s*
    \}\);\s*
    \}\)\(\);\s*</script>\s*''',
    re.S | re.X,
)
ui, legacy_ui_removed = legacy_refresh.subn("\n", ui)

ui = ui.replace(
    "button.disabled = (typeof isDeviceConnected !== 'undefined' && isDeviceConnected);",
    "button.disabled = false;",
)

# The user-visible rule is:
# connected => Refresh disabled
# USB physically removed => Refresh enabled
# No timer may override the removal handler.
handler_pattern = re.compile(
    r'''(function\s+handleUsbCableRemoved\(\)\s*\{.*?
        if\s*\(spinnerElement\)\s*spinnerElement\.style\.display\s*=\s*'none';)''',
    re.S | re.X,
)
if "refreshButtonAfterUsbRemoval.disabled = false;" not in ui:
    def add_refresh_reenable(m):
        return m.group(1) + """
    var refreshButtonAfterUsbRemoval = document.getElementById('refresh-device');
    if (refreshButtonAfterUsbRemoval) {
        refreshButtonAfterUsbRemoval.disabled = false;
        refreshButtonAfterUsbRemoval.removeAttribute('aria-disabled');
    }"""
    ui, handler_hits = handler_pattern.subn(add_refresh_reenable, ui, count=1)
else:
    handler_hits = 0

ui = ui.replace(
    'title="重新讀取 USB 裝置清單"',
    'title="重新讀取 USB / Wi-Fi 裝置清單"',
)

main.write_text(src, encoding="utf-8")
map_file.write_text(ui, encoding="utf-8")

print(f"Wi-Fi state enable blocks updated: {state_hits}")
print(f"Wi-Fi /list_devices blocks replaced: {network_hits}")
print(f"Legacy refresh timers removed: {legacy_ui_removed}")
print(f"USB removal handler refresh re-enable added: {handler_hits}")
