from pathlib import Path
import re

main = Path("src/main.py")
text = main.read_text(encoding="utf-8")

# Keep the existing Wi-Fi discovery/connection changes from the Wi-Fi test
# branch. These are applied only when the original USB-only guard is present.
old_wifi = """    # USB-ONLY: Wi-Fi / Network discovery intentionally disabled.
    logger.info("USB-ONLY mode: Wi-Fi/Bonjour/mDNS/RemotePairing discovery skipped")
"""
new_wifi = """    # Wi-Fi / Network discovery: Apple mobdev2 Bonjour over the local LAN.
    try:
        async def collect_network_devices():
            found = []
            async for ip, device in get_mobdev2_lockdowns(
                udid=None,
                pair_records=get_home_folder(),
                only_paired=True,
                timeout=timeout,
            ):
                try:
                    info = dict(device.short_info)
                    device_udid = (
                        getattr(device, "udid", None)
                        or info.get("UniqueDeviceID")
                        or info.get("Identifier")
                    )
                    if not device_udid:
                        continue
                    info["Identifier"] = device_udid
                    info["ConnectionType"] = "Network"
                    info["wifiAddress"] = str(ip)
                    info["wifiPort"] = 62078
                    info["wifiState"] = True
                    found.append((device_udid, info))
                finally:
                    try:
                        await device.close()
                    except Exception:
                        pass
            return found

        network_devices = asyncio.run(collect_network_devices())
        for device_udid, info in network_devices:
            add_device(device_udid, "Network", info)
        logger.info(
            f"Wi-Fi/mobdev2 discovery: {len(network_devices)} paired network device(s) found"
        )
    except Exception as exc:
        logger.warning(f"Wi-Fi/mobdev2 discovery failed: {exc}")
"""
if old_wifi in text:
    text = text.replace(old_wifi, new_wifi, 1)

old_reject = '''    if connection_type != "USB":
        logger.warning(f"USB-ONLY build: rejecting non-USB connection type: {connection_type}")
        return jsonify({"error": "USB-only mode: please connect the iPhone by USB."}), 400

'''
new_reject = '''    if connection_type not in ("USB", "Network", "Manual"):
        logger.warning(f"Unsupported connection type: {connection_type}")
        return jsonify({"error": f"Unsupported connection type: {connection_type}"}), 400

'''
if old_reject in text:
    text = text.replace(old_reject, new_reject, 1)

old_network = '''    if connection_type == "Network":
        check_pair_record(udid)
        if pair_record is None:
            logger.error("Network: No Remote Pair Record Found. Please connect once by USB first.")
            return jsonify({"Error": "No Pair Record Found"})
        return connect_wifi(data)
'''
new_network = '''    if connection_type == "Network":
        return connect_wifi(data)
'''
if old_network in text:
    text = text.replace(old_network, new_network, 1)

old_state = '''                            try:
                                info["wifiState"] = await client.get_enable_wifi_connections()
                            except Exception:
                                info["wifiState"] = False
'''
new_state = '''                            try:
                                info["wifiState"] = await client.get_enable_wifi_connections()
                                if not info["wifiState"]:
                                    await client.set_enable_wifi_connections(True)
                                    await asyncio.sleep(1.0)
                                    info["wifiState"] = await client.get_enable_wifi_connections()
                            except Exception:
                                info["wifiState"] = False
'''
if old_state in text:
    text = text.replace(old_state, new_state, 1)

main.write_text(text, encoding="utf-8")

map_file = Path("src/templates/map.html")
map_text = map_file.read_text(encoding="utf-8")

# Keep the Wi-Fi discovery UI, but make Refresh deterministic:
# connected => disabled; USB removed/disconnected => enabled.
old_finally = "button.disabled = (typeof isDeviceConnected !== 'undefined' && isDeviceConnected);"
map_text = map_text.replace(old_finally, "button.disabled = false;")

old_guard = """async function dportRefreshDeviceList() {
    if (typeof isDeviceConnected !== 'undefined' && isDeviceConnected) {
        displayToast("裝置已連接，無需重新整理裝置清單。");
        return;
    }

    if (deviceListManualRefreshInFlight) return;"""
new_guard = """async function dportRefreshDeviceList() {
    if (isDeviceConnected) {
        displayToast("裝置已連接，無需重新整理裝置清單。");
        return;
    }

    if (deviceListManualRefreshInFlight) return;"""
map_text = map_text.replace(old_guard, new_guard, 1)

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
map_text, legacy_removed = legacy_pattern.subn("\n", map_text)

disconnect_anchor = "    if (spinnerElement) spinnerElement.style.display = 'none';"
disconnect_insert = """    if (spinnerElement) spinnerElement.style.display = 'none';

    var refreshButton = document.getElementById('refresh-device');
    if (refreshButton) {
        refreshButton.disabled = false;
        refreshButton.removeAttribute('aria-disabled');
    }
"""
if disconnect_anchor in map_text and "refreshButton.disabled = false;" not in map_text:
    map_text = map_text.replace(disconnect_anchor, disconnect_insert, 1)

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
if connect_anchor in map_text and "refreshButtonConnected.disabled = true;" not in map_text:
    map_text = map_text.replace(connect_anchor, connect_insert, 1)

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
if manual_disc_anchor in map_text and "refreshButtonDisconnected.disabled = false;" not in map_text:
    map_text = map_text.replace(manual_disc_anchor, manual_disc_insert, 1)

# Remove any earlier authoritative script that can race with the explicit states.
map_text = re.sub(
    r'''\s*<script id="dport-refresh-authoritative-state">.*?</script>\s*''',
    "\n",
    map_text,
    flags=re.S,
)

# Explicit states are driven by the actual application state changes.
# Do not add another background timer.
map_file.write_text(map_text, encoding="utf-8")

print(f"legacy background refresh synchronizer removed: {legacy_removed}")
print("Wi-Fi discovery + deterministic USB refresh state patch applied.")
