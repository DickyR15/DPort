from pathlib import Path
import re

main = Path("src/main.py")
text = main.read_text(encoding="utf-8")

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
                    try:
                        info["userLocale"] = get_user_country()
                    except Exception:
                        info["userLocale"] = None
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
                                    logger.info(
                                        f"Wi-Fi lockdown disabled for {device.serial}; enabling it via USB."
                                    )
                                    await client.set_enable_wifi_connections(True)
                                    await asyncio.sleep(1.0)
                                    info["wifiState"] = await client.get_enable_wifi_connections()
                            except Exception as exc:
                                logger.warning(
                                    f"Wi-Fi lockdown state/enable check failed for {device.serial}: {exc}"
                                )
                                info["wifiState"] = False
'''
if old_state in text:
    text = text.replace(old_state, new_state, 1)

main.write_text(text, encoding="utf-8")

map_file = Path("src/templates/map.html")
if not map_file.exists():
    raise SystemExit("UI template not found: src/templates/map.html")
map_text = map_file.read_text(encoding="utf-8")

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
map_text, legacy_count = legacy_script_pattern.subn("\n", map_text)

guard_pattern = re.compile(
    r'''(?s)(async function dportRefreshDeviceList\(\)\s*\{\s*)'''
    r'''if\s*\(typeof\s+isDeviceConnected\s*!==\s*['"]undefined['"]\s*&&\s*isDeviceConnected\)\s*\{.*?\}\s*'''
)
map_text, guard_count = guard_pattern.subn(r'\1', map_text)

map_text, final_count = re.subn(
    r'''button\.disabled\s*=\s*\(\s*typeof\s+isDeviceConnected.*?;''',
    'button.disabled = false;',
    map_text,
)

map_text = re.sub(
    r'''\s*<script id="dport-refresh-authoritative-state">.*?</script>\s*''',
    "\n",
    map_text,
    flags=re.S,
)

map_text += r'''
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

map_text = map_text.replace(
    'title="重新讀取 USB 裝置清單"',
    'title="重新讀取 USB / Wi-Fi 裝置清單"',
)
map_file.write_text(map_text, encoding="utf-8")

print(f"legacy refresh sync scripts removed: {legacy_count}")
print(f"stale refresh guards removed: {guard_count}")
print(f"stale cleanup assignments fixed: {final_count}")
