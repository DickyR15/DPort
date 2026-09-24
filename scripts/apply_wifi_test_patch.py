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

# 1) Enable Apple's Wi-Fi lockdown transport after USB enumeration.
wifi_state_old = """                            try:
                                info["wifiState"] = await client.get_enable_wifi_connections()
                            except Exception:
                                info["wifiState"] = False"""
wifi_state_new = """                            try:
                                info["wifiState"] = await client.get_enable_wifi_connections()
                                if not info["wifiState"]:
                                    logger.info("Wi-Fi lockdown is off; enabling it over USB.")
                                    await client.set_enable_wifi_connections(True)
                                    await asyncio.sleep(1.0)
                                    info["wifiState"] = await client.get_enable_wifi_connections()
                            except Exception as exc:
                                logger.warning(f"Wi-Fi lockdown enable/check failed: {exc}")
                                info["wifiState"] = False"""
ui_count = src.count(wifi_state_old)
src = src.replace(wifi_state_old, wifi_state_new)

# 2) Common connect route must accept Network / Manual, not reject them as USB-only.
usb_guard_old = """    if connection_type != "USB":
        logger.warning(f"USB-ONLY build: rejecting non-USB connection type: {connection_type}")
        return jsonify({"error": "USB-only mode: please connect the iPhone by USB."}), 400

"""
usb_guard_new = """    if connection_type not in ("USB", "Network", "Manual"):
        logger.warning(f"Unsupported connection type: {connection_type}")
        return jsonify({"error": f"Unsupported connection type: {connection_type}"}), 400

"""
usb_guard_count = src.count(usb_guard_old)
src = src.replace(usb_guard_old, usb_guard_new)

# 3) Normal iOS 17.4+/26 Network should use mobdev2/CoreDeviceProxy, not legacy
# RemotePairing-record gating.
network_old = """    if connection_type == "Network":
        check_pair_record(udid)
        if pair_record is None:
            logger.error("Network: No Remote Pair Record Found. Please connect once by USB first.")
            return jsonify({"Error": "No Pair Record Found"})
        return connect_wifi(data)
"""
network_new = """    if connection_type == "Network":
        return connect_wifi(data)
"""
network_count = src.count(network_old)
src = src.replace(network_old, network_new)

# 4) Explicit Manual Wi-Fi path should use the same implementation.
manual_old = """    if connection_type == "Manual":
        check_pair_record(udid)
        if pair_record is None:
            return jsonify({"Error": "No Pair Record Found"})
        return connect_wifi(data)
"""
manual_new = """    if connection_type == "Manual":
        return connect_wifi(data)
"""
manual_count = src.count(manual_old)
src = src.replace(manual_old, manual_new)

# 5) Let pymobiledevice3 11.18.0 select the correct host pair records itself.
src = src.replace("pair_records=get_home_folder(),\n", "")

# 6) Preserve the user's exact USB/Wi-Fi selection when the background
# auto-refresh repopulates the list. The current selection is sticky by option key.
# auto-refresh repopulates the list. Without this, the same iPhone's Network
# option can become the selected option after a refresh.
clear_old = """        deviceDropdown.innerHTML = '';
        connectionDropdown.innerHTML = '';
"""
clear_new = """        const previousOption = deviceDropdown.options[deviceDropdown.selectedIndex];
        const previousKey = deviceDropdown.dataset.dportPreferredKey ||
            (previousOption ? (previousOption.dataset.dportKey || '') : '');

        deviceDropdown.innerHTML = '';
        connectionDropdown.innerHTML = '';
"""
clear_count = ui.count(clear_old)
if clear_count == 0:
    raise SystemExit("populateDeviceList clear marker not found")
ui = ui.replace(clear_old, clear_new, 1)

option_old = """                    option.value = JSON.stringify(deviceInfo);

                    devicesInfo[udid] = devicesInfo[udid] || {};
"""
option_new = """                    option.value = JSON.stringify(deviceInfo);
                    option.dataset.dportKey = optionKey;

                    if (!deviceDropdown.dataset.dportPreferredKey &&
                        connectionType === 'USB') {
                        deviceDropdown.dataset.dportPreferredKey = optionKey;
                    }

                    devicesInfo[udid] = devicesInfo[udid] || {};
"""
if option_old not in ui:
    raise SystemExit("device option marker not found")
ui = ui.replace(option_old, option_new, 1)

restore_old = """        if (requestSerial !== deviceListRequestSerial) return false;
        deviceDropdown.devicesInfo = devicesInfo;
"""
restore_new = """        if (requestSerial !== deviceListRequestSerial) return false;

        if (previousKey) {
            const restoredIndex = Array.from(deviceDropdown.options).findIndex(function(opt){
                return (opt.dataset && opt.dataset.dportKey) === previousKey;
            });
            if (restoredIndex >= 0) {
                deviceDropdown.selectedIndex = restoredIndex;
                deviceDropdown.dataset.dportPreferredKey = previousKey;
            }
        }

        deviceDropdown.devicesInfo = devicesInfo;
"""
if restore_old not in ui:
    raise SystemExit("device restore marker not found")
ui = ui.replace(restore_old, restore_new, 1)

# 7) Remove the old background script that can force the wrong state.
legacy_sync = re.compile(
    r"""\\s*<script>\\s*\\(function\\(\\)\\{\\s*
    function\\s+syncDeviceRefreshButton\\(\\)\\s*\\{.*?
    document\\.addEventListener\\(\\s*['"]DOMContentLoaded['"]\\s*,\\s*function\\(\\)\\{\\s*
    syncDeviceRefreshButton\\(\\);\\s*
    setInterval\\(syncDeviceRefreshButton\\s*,\\s*500\\);\\s*
    \\}\\);\\s*
    \\}\\)\\(\\);\\s*</script>\\s*""",
    re.S | re.X,
)
ui, legacy_count = legacy_sync.subn("\\n", ui)

# 8) After a successful connection, refresh is disabled; after USB removal or
# programmatic disconnect, it is explicitly enabled. No timer re-locks it.
success_anchor = """        if (connectButton) {
            connectButton.disabled = true;  // Disable the button
        }
"""
success_insert = """        if (connectButton) {
            connectButton.disabled = true;  // Disable the button
        }
        var refreshButtonConnected = document.getElementById('refresh-device');
        if (refreshButtonConnected) {
            refreshButtonConnected.disabled = true;
            refreshButtonConnected.removeAttribute('aria-disabled');
        }
"""
if success_anchor in ui and "refreshButtonConnected.disabled = true;" not in ui:
    ui = ui.replace(success_anchor, success_insert, 1)

remove_anchor = """    if (spinnerElement) spinnerElement.style.display = 'none';
"""
remove_insert = """    if (spinnerElement) spinnerElement.style.display = 'none';
    var refreshButtonAfterUsbRemoval = document.getElementById('refresh-device');
    if (refreshButtonAfterUsbRemoval) {
        refreshButtonAfterUsbRemoval.disabled = false;
        refreshButtonAfterUsbRemoval.removeAttribute('aria-disabled');
    }
"""
if remove_anchor in ui and "refreshButtonAfterUsbRemoval.disabled = false;" not in ui:
    ui = ui.replace(remove_anchor, remove_insert, 1)

main.write_text(src, encoding="utf-8")
map_file.write_text(ui, encoding="utf-8")

print(f"Wi-Fi state blocks updated: {ui_count}")
print(f"USB-only connect guards replaced: {usb_guard_count}")
print(f"Network legacy guards replaced: {network_count}")
print(f"Manual legacy guards replaced: {manual_count}")
print(f"Refresh background scripts removed: {legacy_count}")
print("Wi-Fi tunnel pair-record overrides removed.")
print("Wi-Fi parsing no longer references a closed/out-of-scope device object.")
print("USB/Wi-Fi selection preservation enabled.")


# ---------- Wi-Fi connection repair ----------
# The discovery UI is now working. Repair the actual iOS 17.4+/26 tunnel path:
# use the selected Wi-Fi address, let pymobiledevice3 resolve host pair records,
# and do not return "connected" until RSD data is really available.

c = src

c = re.sub(
    r'''(?s)            try:
                devices = get_wifi_with_retry\(\)
                logger\.info\(f"Connect Wifi Devices: \{devices\}"\)
                logger\.info\(f"Wifi Address:  \{wifi_address\}"\)
            except RuntimeError as e:
                error_message = str\(e\)
                logger\.error\(f"Error: \{error_message\}"\)
                return jsonify\(\{'error': 'No Devices Found', 'details': error_message\}, 404\)\s*''',
    '''            logger.info(f"Selected Wi-Fi address: {wifi_address}")
            logger.info(f"Selected Wi-Fi port: {wifi_port}")
            if not wifi_address:
                return jsonify({
                    'error': 'Wi-Fi 裝置沒有有效的 IP 位址，請重新整理裝置清單。'
                }), 400
''',
    c,
)

c = re.sub(
    r'''(?s)            if not check_rsd_data\(\):
                logger\.error\("RSD Data is None, Perhaps the tunnel isn't established"\)
            else:
                rsd_data = rsd_host, rsd_port
                logger\.info\(f"RSD Data: \{rsd_data\}"\)

            rsd_data_map\.setdefault\(udid, \{\}\)\[connection_type\] = \{"host": rsd_host, "port": rsd_port\}
            logger\.info\(f"Device Connection Map: \{rsd_data_map\}"\)
            return jsonify\(\{'rsd_data': rsd_data\}\)
''',
    '''            if not check_rsd_data() or rsd_host is None or rsd_port is None:
                logger.error("Wi-Fi RSD tunnel was not established.")
                return jsonify({
                    'error': 'Wi-Fi tunnel 建立失敗',
                    'details': f'mobdev2/CoreDeviceProxy did not provide RSD data for {udid}.'
                }), 502

            rsd_data = rsd_host, rsd_port
            logger.info(f"RSD Data: {rsd_data}")
            rsd_data_map.setdefault(udid, {})[connection_type] = {
                "host": rsd_host,
                "port": rsd_port
            }
            logger.info(f"Device Connection Map: {rsd_data_map}")
            return jsonify({'rsd_data': rsd_data})
''',
    c,
)

# The source currently has no explicit pair_records override after step 5.
# Match the selected Wi-Fi IP when possible; fall back to the first paired
# mobdev2 candidate if Windows reports a canonicalized address.
c = re.sub(
    r'''(?s)        async for ip, candidate in get_mobdev2_lockdowns\(
            udid=udid,
            only_paired=True,
            timeout=timeout,
        \):
            logger\.info\(f"mobdev2 tunnel candidate: \{ip\}, udid=\{candidate\.udid\}"\)
            wifi_address = str\(ip\)
            lockdown = candidate
            break
''',
    '''        fallback = None
        async for ip, candidate in get_mobdev2_lockdowns(
            udid=udid,
            only_paired=True,
            timeout=timeout,
        ):
            logger.info(
                f"mobdev2 tunnel candidate: {ip}, udid={candidate.udid}, "
                f"selected_wifi={wifi_address}"
            )
            if fallback is None:
                fallback = (str(ip), candidate)
            if wifi_address and str(ip) == str(wifi_address):
                lockdown = candidate
                break
            await candidate.close()

        if lockdown is None and fallback is not None:
            wifi_address, lockdown = fallback
''',
    c,
)

# Remove the known out-of-scope variable from the old diagnostic helper.
c = c.replace(
    "                        f\"mobdev2 device: ip={ip}, udid={device_udid}, iOS={product}, paired={getattr(device, 'paired', None)}\"",
    "                        f\"mobdev2 device: ip={ip}, udid={device_udid}, iOS={product}\"",
)

if "Selected Wi-Fi address:" not in c:
    raise SystemExit("Wi-Fi connect repair was not applied.")
if "fallback = None" not in c:
    raise SystemExit("Wi-Fi tunnel repair was not applied.")

src = c
