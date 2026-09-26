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

# --- Wi-Fi 6.9.3 build trigger / backend transport patch ---
# --- Backend: enable Wi-Fi transport when USB is available ---
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
if wifi_state_old in src:
    src = src.replace(wifi_state_old, wifi_state_new, 1)

# Let the common route accept USB, Network and Manual.
usb_guard_old = """    if connection_type != "USB":
        logger.warning(f"USB-ONLY build: rejecting non-USB connection type: {connection_type}")
        return jsonify({"error": "USB-only mode: please connect the iPhone by USB."}), 400

"""
usb_guard_new = """    if connection_type not in ("USB", "Network", "Manual"):
        logger.warning(f"Unsupported connection type: {connection_type}")
        return jsonify({"error": f"Unsupported connection type: {connection_type}"}), 400

"""
if usb_guard_old in src:
    src = src.replace(usb_guard_old, usb_guard_new, 1)

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
if network_old in src:
    src = src.replace(network_old, network_new, 1)

manual_old = """    if connection_type == "Manual":
        check_pair_record(udid)
        if pair_record is None:
            return jsonify({"Error": "No Pair Record Found"})
        return connect_wifi(data)
"""
manual_new = """    if connection_type == "Manual":
        return connect_wifi(data)
"""
if manual_old in src:
    src = src.replace(manual_old, manual_new, 1)

# pymobiledevice3 11.18.0 should resolve the host pairing records automatically.
src = src.replace("            pair_records=get_home_folder(),\n", "")
src = src.replace("        pair_records=get_home_folder(),\n", "")
src = src.replace("                    pair_records=get_home_folder(),\n", "")

# Remove the stale/out-of-scope device variable from the old Wi-Fi diagnostic.
src = src.replace(
    "                        f\"mobdev2 device: ip={ip}, udid={device_udid}, iOS={product}, paired={getattr(device, 'paired', None)}\"",
    "                        f\"mobdev2 device: ip={ip}, udid={device_udid}, iOS={product}\"",
)

# Do not require a preliminary get_wifi_with_retry() call. The selected IP is
# already known from mobdev2 discovery; the authenticated tunnel reconnect is
# handled in start_wifi_tcp_tunnel().
wifi_probe_old = """            try:
                devices = get_wifi_with_retry()
                logger.info(f"Connect Wifi Devices: {devices}")
                logger.info(f"Wifi Address:  {wifi_address}")
            except RuntimeError as e:
                error_message = str(e)
                logger.error(f"Error: {error_message}")
                return jsonify({'error': 'No Devices Found', 'details': error_message}), 404


"""
wifi_probe_new = """            logger.info(f"Selected Wi-Fi address: {wifi_address}")
            logger.info(f"Selected Wi-Fi port: {wifi_port}")
            if not wifi_address:
                return jsonify({
                    'error': 'Wi-Fi 裝置沒有有效的 IP 位址，請重新整理裝置清單。'
                }), 400

"""
if wifi_probe_old in src:
    src = src.replace(wifi_probe_old, wifi_probe_new, 1)

# Do not report success unless the RSD tunnel is actually established.
rsd_old = """            if not check_rsd_data():
                logger.error("RSD Data is None, Perhaps the tunnel isn't established")
            else:
                rsd_data = rsd_host, rsd_port
                logger.info(f"RSD Data: {rsd_data}")

            rsd_data_map.setdefault(udid, {})[connection_type] = {"host": rsd_host, "port": rsd_port}
            logger.info(f"Device Connection Map: {rsd_data_map}")
            return jsonify({'rsd_data': rsd_data})
"""
rsd_new = """            if not check_rsd_data() or rsd_host is None or rsd_port is None:
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
"""
if rsd_old in src:
    src = src.replace(rsd_old, rsd_new, 1)

# In the Wi-Fi tunnel, match the selected IP when possible. The new
# pymobiledevice3 API discovers the correct pair record automatically.
tunnel_old = """        async for ip, candidate in get_mobdev2_lockdowns(
            udid=udid,
            pair_records=get_home_folder(),
            only_paired=True,
            timeout=timeout,
        ):
            logger.info(f"mobdev2 tunnel candidate: {ip}, udid={candidate.udid}")
            wifi_address = str(ip)
            lockdown = candidate
            break
"""
tunnel_new = """        fallback = None
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
"""
if tunnel_old in src:
    src = src.replace(tunnel_old, tunnel_new, 1)

# --- UI: make the selected transport sticky across background list refreshes ---
clear_old = """        deviceDropdown.innerHTML = '';
        connectionDropdown.innerHTML = '';
"""
clear_new = """        const previousOption = deviceDropdown.options[deviceDropdown.selectedIndex];
        const previousKey = deviceDropdown.dataset.dportPreferredKey ||
            (previousOption ? (previousOption.dataset.dportKey || '') : '');

        deviceDropdown.innerHTML = '';
        connectionDropdown.innerHTML = '';
"""
if clear_old in ui and "const previousKey = deviceDropdown.dataset.dportPreferredKey" not in ui:
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
if option_old in ui and "option.dataset.dportKey = optionKey" not in ui:
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
if restore_old in ui and "const restoredIndex = Array.from(deviceDropdown.options)" not in ui:
    ui = ui.replace(restore_old, restore_new, 1)

listener_old = """            deviceDropdown.addEventListener('change', function() {
                var connectTextElement = document.getElementById('connectText');
                var connectButton = document.getElementById('connect');
"""
listener_new = """            deviceDropdown.addEventListener('change', function() {
                var selected = deviceDropdown.options[deviceDropdown.selectedIndex];
                if (selected && selected.dataset && selected.dataset.dportKey) {
                    deviceDropdown.dataset.dportPreferredKey = selected.dataset.dportKey;
                }
                var connectTextElement = document.getElementById('connectText');
                var connectButton = document.getElementById('connect');
"""
if listener_old in ui and "dportPreferredKey = selected.dataset.dportKey" not in ui:
    ui = ui.replace(listener_old, listener_new, 1)

# Ensure manual refresh can always be clicked; only an active refresh disables it.
ui = ui.replace(
    "button.disabled = (typeof isDeviceConnected !== 'undefined' && isDeviceConnected);",
    "button.disabled = false;"
)

# Remove known stale 500ms synchronizer if still present.
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
ui, legacy_removed = legacy_sync.subn("\\n", ui)

main.write_text(src, encoding="utf-8")
map_file.write_text(ui, encoding="utf-8")

print(f"Legacy refresh timers removed: {legacy_removed}")
print(f"Wi-Fi probe block present after patch: {'Selected Wi-Fi address:' in src}")
print(f"Wi-Fi tunnel matching present: {'fallback = None' in src}")
print("USB/Wi-Fi selection is sticky across list refresh.")



# --- Final backend Wi-Fi connection fix ---
# CI build trigger checkpoint 3
src = src.replace(
    """                        f"mobdev2 device: ip={ip}, udid={device_udid}, iOS={product}, paired={getattr(device, 'paired', None)}" """.rstrip(),
    """                        f"mobdev2 device: ip={ip}, udid={device_udid}, iOS={product}" """.rstrip(),
)

wifi_probe_old = """            try:
                devices = get_wifi_with_retry()
                logger.info(f"Connect Wifi Devices: {devices}")
                logger.info(f"Wifi Address:  {wifi_address}")
            except RuntimeError as e:
                error_message = str(e)
                logger.error(f"Error: {error_message}")
                return jsonify({'error': 'No Devices Found', 'details': error_message}), 404


"""
wifi_probe_new = """            logger.info(f"Selected Wi-Fi address: {wifi_address}")
            logger.info(f"Selected Wi-Fi port: {wifi_port}")
            if not wifi_address:
                return jsonify({
                    'error': 'Wi-Fi 裝置沒有有效的 IP 位址，請重新整理裝置清單。'
                }), 400

"""
src = src.replace(wifi_probe_old, wifi_probe_new, 1)

rsd_old = """            if not check_rsd_data():
                logger.error("RSD Data is None, Perhaps the tunnel isn't established")
            else:
                rsd_data = rsd_host, rsd_port
                logger.info(f"RSD Data: {rsd_data}")

            rsd_data_map.setdefault(udid, {})[connection_type] = {"host": rsd_host, "port": rsd_port}
            logger.info(f"Device Connection Map: {rsd_data_map}")
            return jsonify({'rsd_data': rsd_data})
"""
rsd_new = """            if not check_rsd_data() or rsd_host is None or rsd_port is None:
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
"""
src = src.replace(rsd_old, rsd_new, 1)

tunnel_old = """        async for ip, candidate in get_mobdev2_lockdowns(
            udid=udid,
            pair_records=get_home_folder(),
            only_paired=True,
            timeout=timeout,
        ):
            logger.info(f"mobdev2 tunnel candidate: {ip}, udid={candidate.udid}")
            wifi_address = str(ip)
            lockdown = candidate
            break
"""
tunnel_old2 = """        async for ip, candidate in get_mobdev2_lockdowns(
            udid=udid,
            only_paired=True,
            timeout=timeout,
        ):
            logger.info(f"mobdev2 tunnel candidate: {ip}, udid={candidate.udid}")
            wifi_address = str(ip)
            lockdown = candidate
            break
"""
tunnel_new = """        fallback = None
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
"""
if tunnel_old in src:
    src = src.replace(tunnel_old, tunnel_new, 1)
elif tunnel_old2 in src:
    src = src.replace(tunnel_old2, tunnel_new, 1)
else:
    raise SystemExit("Expected Wi-Fi tunnel block not found")

main.write_text(src, encoding="utf-8")
print("Final backend Wi-Fi connection fix applied.")
