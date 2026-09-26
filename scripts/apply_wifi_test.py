from pathlib import Path
import re

MAIN = Path("src/main.py")
MAP = Path("src/templates/map.html")
src = MAIN.read_text(encoding="utf-8")
ui = MAP.read_text(encoding="utf-8")

# Remove DPort same-version updater from the Wi-Fi test build.
lines = []
for line in src.splitlines():
    if "dport_release_updater" in line or "bootstrap_dport_updater()" in line:
        continue
    lines.append(line)
src = "\n".join(lines) + "\n"

# Remove any updater status route line, regardless of formatting in the bundled
# DPort-source-6.9.0.zip snapshot. Do not depend on one exact decorator shape.
route_lines_removed = 0
filtered = []
for line in src.splitlines():
    if "/pymobiledevice3/status" in line:
        route_lines_removed += 1
        continue
    filtered.append(line)
src = "\n".join(filtered) + "\n"
route_count = route_lines_removed


# Add Wi-Fi discovery to the existing /list_devices endpoint.
disabled = '''            # USB-ONLY: Wi-Fi / Network discovery intentionally disabled.
            logger.info("USB-ONLY mode: Wi-Fi/Bonjour/mDNS/RemotePairing discovery skipped")
'''
discovery = '''            # Wi-Fi discovery through _apple-mobdev2._tcp.
            try:
                wifi_count = 0
                async for ip, network_device in get_mobdev2_lockdowns(
                    only_paired=True,
                    timeout=timeout,
                ):
                    try:
                        info = dict(network_device.short_info)
                        network_udid = (
                            getattr(network_device, "udid", None)
                            or info.get("UniqueDeviceID")
                            or info.get("Identifier")
                        )
                        if not network_udid:
                            continue
                        info["ConnectionType"] = "Network"
                        info["Identifier"] = network_udid
                        info["wifiAddress"] = str(ip)
                        info["wifiPort"] = 62078
                        info["wifiState"] = True
                        info["wifiTransport"] = "mobdev2"
                        add_device(network_udid, "Network", info)
                        wifi_count += 1
                    except Exception as exc:
                        logger.warning(f"Wi-Fi metadata failed for {ip}: {exc}")
                    finally:
                        try:
                            await network_device.close()
                        except Exception:
                            pass
                logger.info(f"Wi-Fi device-list count: {wifi_count}")
            except Exception as exc:
                logger.warning(f"Wi-Fi discovery failed: {exc}")
'''
if disabled not in src:
    raise SystemExit("Wi-Fi discovery insertion point not found.")
src = src.replace(disabled, discovery, 1)

# Use the selected Wi-Fi address directly. For iOS 17.4+ the official tunnel
# is Lockdown -> CoreDeviceProxy -> TCP, including over Wi-Fi.
start = src.find("async def start_wifi_tcp_tunnel() -> None:")
end = src.find("\n\nasync def start_wifi_quic_tunnel", start)
if start < 0 or end < 0:
    raise SystemExit("Wi-Fi TCP tunnel function not found.")

tcp = '''async def start_wifi_tcp_tunnel() -> None:
    global terminate_tunnel_thread, rsd_port, rsd_host, wifi_address, wifi_tunnel_error

    lockdown = None
    service = None
    try:
        wifi_tunnel_error = None

        host = str(wifi_address or "").strip()
        port = int(wifi_port or 62078)

        if not host:
            raise RuntimeError("Wi-Fi 裝置沒有有效的 IP 位址。")
        if not udid:
            raise RuntimeError("Wi-Fi 裝置缺少 UDID。")

        home = get_home_folder()
        pair = get_preferred_pair_record(udid, home)
        if pair is None:
            raise RuntimeError("找不到 iPhone 配對紀錄，請先用 USB 連接一次。")

        logger.info(f"Wi-Fi Lockdown connect: {host}:{port}, udid={udid}")

        lockdown = await create_using_tcp(
            hostname=host,
            identifier=udid,
            autopair=False,
            pair_record=pair,
            pairing_records_cache_folder=home,
            port=port,
            keep_alive=True,
        )

        logger.info(
            f"Wi-Fi Lockdown connected: udid={lockdown.udid}, "
            f"iOS={lockdown.product_version}"
        )

        service = await CoreDeviceTunnelProxy.create(lockdown)

        async with service.start_tcp_tunnel() as tunnel_result:
            rsd_host = tunnel_result.address
            rsd_port = str(tunnel_result.port)
            wifi_tunnel_error = None

            logger.info(
                f"Wi-Fi CoreDeviceProxy tunnel ready: "
                f"{rsd_host}:{rsd_port}"
            )

            while not terminate_tunnel_thread:
                await asyncio.sleep(0.5)

    except Exception as exc:
        wifi_tunnel_error = str(exc)
        logger.exception(f"Wi-Fi TCP tunnel failed: {exc}")
        raise
    finally:
        if service is not None:
            try:
                await service.close()
            except Exception:
                pass
        if lockdown is not None:
            try:
                await lockdown.close()
            except Exception:
                pass
'''
src = src[:start] + tcp + src[end:]

# Fail fast instead of waiting a full 60 seconds when the tunnel thread fails.
start = src.find("def check_rsd_data():")
end = src.find("\n\ndef connect_usb(data):", start)
if start < 0 or end < 0:
    raise SystemExit("check_rsd_data function not found.")

src = src[:start] + '''def check_rsd_data():
    for _ in range(120):
        if wifi_tunnel_error:
            logger.error(f"Wi-Fi tunnel error: {wifi_tunnel_error}")
            return False
        if rsd_host is not None and rsd_port is not None:
            return True
        time.sleep(0.25)
    return False
''' + src[end:]

# Background tunnel must use TCP/CoreDeviceProxy for iOS 17.4+.
start = src.find("def run_wifi_tunnel():")
end = src.find("\n\nasync def _mount_developer_image_async", start)
if start < 0 or end < 0:
    raise SystemExit("run_wifi_tunnel function not found.")
src = src[:start] + '''def run_wifi_tunnel():
    global wifi_tunnel_error
    try:
        wifi_tunnel_error = None
        if is_major_version_17_or_greater(ios_version):
            asyncio.run(start_wifi_tcp_tunnel())
        else:
            asyncio.run(start_wifi_quic_tunnel())
    except Exception as exc:
        wifi_tunnel_error = str(exc)
        logger.exception(f"Error in run_wifi_tunnel: {exc}")
''' + src[end:]

# Reset error for every attempt.
src = src.replace(
    "def start_wifi_tunnel_thread():\n    global terminate_tunnel_thread\n    terminate_tunnel_thread = False",
    "def start_wifi_tunnel_thread():\n    global terminate_tunnel_thread, wifi_tunnel_error\n    terminate_tunnel_thread = False\n    wifi_tunnel_error = None",
    1,
)

# Use the supplied Wi-Fi address; don't run a second discovery that can select
# another interface/device or race the UI.
old_wifi_discovery = '''            try:
                devices = get_wifi_with_retry()
                logger.info(f"Connect Wifi Devices: {devices}")
                logger.info(f"Wifi Address:  {wifi_address}")
            except RuntimeError as e:
                error_message = str(e)
                logger.error(f"Error: {error_message}")
                return jsonify({'error': 'No Devices Found', 'details': error_message}), 404
'''
if old_wifi_discovery in src:
    src = src.replace(old_wifi_discovery, '''            if not wifi_address:
                return jsonify({
                    'error': 'Wi-Fi 裝置沒有有效的 IP 位址',
                    'connection_retryable': True
                }), 400

            logger.info(
                f"Using selected Wi-Fi endpoint directly: "
                f"{wifi_address}:{wifi_port}"
            )
''', 1)

# Stabilize UI refresh selection.
ui = ui.replace(
'''        const displayedIds = Array.from(deviceDropdown.options)
            .map(function(option){
                try {
                    const info = JSON.parse(option.value || '{}');
                    return String(info.Identifier || '');
                } catch (e) {
                    return '';
                }
            })
            .filter(Boolean)
            .sort();
''',
'''        const displayedIds = Array.from(deviceDropdown.options)
            .map(function(option){
                try {
                    const info = JSON.parse(option.value || '{}');
                    if (String(info.ConnectionType || '').toUpperCase() !== 'USB') return '';
                    return String(info.Identifier || '');
                } catch (e) {
                    return '';
                }
            })
            .filter(Boolean)
            .sort();
''',
1)

ui = ui.replace(
'''        if (rawIds.length === 0) {
            // Only a successful, error-free empty snapshot may clear stale
            // device entries.
            deviceReinsertRetryCount = 0;
            deviceReinsertRetryUntil = 0;
            deviceAutoRefreshSignature = '';
            deviceAutoRefreshScheduled = false;

            if (deviceDropdown.options.length > 0) {
                deviceDropdown.innerHTML = '';
                deviceDropdown.value = '';
            }

            var connectionDropdown = document.getElementById('connection');
            if (connectionDropdown) {
                connectionDropdown.innerHTML = '';
                connectionDropdown.value = '';
            }
            return;
        }
''',
'''        if (rawIds.length === 0) {
            // USB presence is empty; keep Network/Wi-Fi entries visible.
            deviceReinsertRetryCount = 0;
            deviceReinsertRetryUntil = 0;
            deviceAutoRefreshSignature = '';
            deviceAutoRefreshScheduled = false;
            return;
        }
''',
1)

ui = ui.replace(
'''        deviceDropdown.innerHTML = '';
        connectionDropdown.innerHTML = '';

        const seenDeviceOptions = new Set();
''',
'''        const previousOption = deviceDropdown.options[deviceDropdown.selectedIndex];
        const previousKey = previousOption
            ? String(previousOption.dataset.dportKey || '')
            : '';

        deviceDropdown.innerHTML = '';
        connectionDropdown.innerHTML = '';

        const seenDeviceOptions = new Set();
''',
1)

ui = ui.replace(
'''                    option.value = JSON.stringify(deviceInfo);

                    devicesInfo[udid] = devicesInfo[udid] || {};
''',
'''                    option.value = JSON.stringify(deviceInfo);
                    option.dataset.dportKey =
                        String(udid) + '|' +
                        String(connectionType) + '|' +
                        String(deviceInfo.Identifier || '') + '|' +
                        String(deviceInfo.wifiAddress || '');

                    devicesInfo[udid] = devicesInfo[udid] || {};
''',
1)

ui = ui.replace(
'''        if (requestSerial !== deviceListRequestSerial) return false;
        deviceDropdown.devicesInfo = devicesInfo;
''',
'''        if (requestSerial !== deviceListRequestSerial) return false;

        if (previousKey) {
            const restoreIndex = Array.from(deviceDropdown.options).findIndex(
                function(option){
                    return option.dataset &&
                        option.dataset.dportKey === previousKey;
                }
            );
            if (restoreIndex >= 0) {
                deviceDropdown.selectedIndex = restoreIndex;
            }
        }

        deviceDropdown.devicesInfo = devicesInfo;
''',
1)

# Refresh follows DPort connection state only.
const_old = '''    function enableManualRefresh(){
        var btn=document.getElementById('refresh-device');
        if(!btn) return;
        // The user controls Refresh. Never leave it disabled merely because
        // a previous USB device was disconnected.
        btn.disabled=false;
        btn.removeAttribute('aria-disabled');
    }'''
const_new = '''    function enableManualRefresh(){
        var btn=document.getElementById('refresh-device');
        if(!btn) return;

        var connected = false;
        try {
            connected = (typeof isDeviceConnected !== 'undefined' &&
                         isDeviceConnected === true);
        } catch(e) {}

        btn.disabled = connected;
        if (connected) {
            btn.setAttribute('aria-disabled','true');
        } else {
            btn.removeAttribute('aria-disabled');
        }
    }'''
if const_old in ui:
    ui = ui.replace(const_old, const_new, 1)

# Explicit refresh lock on successful connection.
ui = ui.replace(
'''        if (connectButton) {
            connectButton.disabled = true;  // Disable the button
        }
        if (selectedDeviceConnType === 'USB') {
''',
'''        if (connectButton) {
            connectButton.disabled = true;  // Disable the button
        }

        var refreshButtonConnected = document.getElementById('refresh-device');
        if (refreshButtonConnected) {
            refreshButtonConnected.disabled = true;
            refreshButtonConnected.setAttribute('aria-disabled','true');
        }

        if (selectedDeviceConnType === 'USB') {
''',
1
)

# Hard remove the updater UI/polling from the test build.
ui = re.sub(
    r'<style id="dport-69-pm3-update-modal-fix9">.*?</style>\s*',
    '',
    ui,
    count=1,
    flags=re.S,
)
ui = re.sub(
    r'<div id="dport-pm3-update-modal"[^>]*>.*?</div>\s*</div>\s*',
    '',
    ui,
    count=1,
    flags=re.S,
)
ui = re.sub(
    r'<script id="dport-pm3-update-modal-start-fix9">.*?</script>\s*',
    '',
    ui,
    count=1,
    flags=re.S,
)
# IMPORTANT: Do not use a broad regex here. The updater modal function and
# setDPortLayout() live in the same JavaScript region in some 6.9.0 source
# snapshots. Removing everything between them can delete production header
# initialization (GPX / device / refresh controls). Keep setDPortLayout and
# the surrounding production UI intact.
# The updater modal DOM/polling is removed by the targeted ID-based regexes
# below; the function itself may remain as dead code.
ui = re.sub(r'^\s*dportStartPm3StatusPolling\(\);\s*\n?', '', ui, flags=re.M)
ui = re.sub(r'\s*<div id="dport-pm3-status"[^>]*>.*?</div>', '', ui, count=1, flags=re.S)


# Stabilize device-list transitions without changing the existing production UI
# structure beyond the specific USB/Wi-Fi race fixes.

# USB auto-detect compares only USB options. Network/Wi-Fi must never make the
# USB watcher think that the device set changed.
ui = re.sub(
    r"const displayedIds = Array\.from\(deviceDropdown\.options\)\s*"
    r"\.map\(function\(option\)\{\s*"
    r"try \{\s*"
    r"const info = JSON\.parse\(option\.value \|\| '\{\}'\);\s*"
    r"return String\(info\.Identifier \|\| ''\);\s*"
    r"\}\s*catch \(e\) \{\s*return '';\s*\}\s*"
    r"\}\)\s*\.filter\(Boolean\)\s*\.sort\(\);",
    """const displayedIds = Array.from(deviceDropdown.options)
            .map(function(option){
                try {
                    const info = JSON.parse(option.value || '{}');
                    if (String(info.ConnectionType || '').toUpperCase() !== 'USB') return '';
                    return String(info.Identifier || '');
                } catch (e) {
                    return '';
                }
            })
            .filter(Boolean)
            .sort();""",
    ui,
    count=1,
)

# An empty USB presence snapshot must never clear a visible Network/Wi-Fi entry.
ui = re.sub(
    r"if \(rawIds\.length === 0\) \{.*?"
    r"var connectionDropdown = document\.getElementById\('connection'\);.*?"
    r"return;\s*\}",
    """if (rawIds.length === 0) {
            deviceReinsertRetryCount = 0;
            deviceReinsertRetryUntil = 0;
            deviceAutoRefreshSignature = '';
            deviceAutoRefreshScheduled = false;

            if (deviceDropdown && deviceDropdown.options.length > 0) {
                const hasNetwork = Array.from(deviceDropdown.options).some(function(option){
                    try {
                        const info = JSON.parse(option.value || '{}');
                        return String(info.ConnectionType || '').toUpperCase() === 'NETWORK';
                    } catch (e) {
                        return false;
                    }
                });
                if (hasNetwork) {
                    return;
                }
            }
            return;
        }""",
    ui,
    count=1,
    flags=re.S,
)

# Save and restore the selected USB/Wi-Fi entry around any list rebuild.
ui = ui.replace(
"""        deviceDropdown.innerHTML = '';
        connectionDropdown.innerHTML = '';

        const seenDeviceOptions = new Set();""",
"""        const previousOption = deviceDropdown.options[deviceDropdown.selectedIndex];
        const previousKey = previousOption
            ? String(previousOption.dataset.dportKey || '')
            : '';

        deviceDropdown.innerHTML = '';
        connectionDropdown.innerHTML = '';

        const seenDeviceOptions = new Set();""",
1,
)

ui = ui.replace(
"""                    option.value = JSON.stringify(deviceInfo);

                    devicesInfo[udid] = devicesInfo[udid] || {};""",
"""                    option.value = JSON.stringify(deviceInfo);
                    option.dataset.dportKey =
                        String(udid) + '|' +
                        String(connectionType) + '|' +
                        String(deviceInfo.Identifier || '') + '|' +
                        String(deviceInfo.wifiAddress || '');

                    devicesInfo[udid] = devicesInfo[udid] || {};""",
1,
)

ui = ui.replace(
"""        if (requestSerial !== deviceListRequestSerial) return false;
        deviceDropdown.devicesInfo = devicesInfo;""",
"""        if (requestSerial !== deviceListRequestSerial) return false;

        if (previousKey) {
            const restoreIndex = Array.from(deviceDropdown.options).findIndex(function(option){
                return option.dataset &&
                    option.dataset.dportKey === previousKey;
            });
            if (restoreIndex >= 0) {
                deviceDropdown.selectedIndex = restoreIndex;
            }
        }

        deviceDropdown.devicesInfo = devicesInfo;""",
1,
)

# Refresh is disabled only while DPort itself is connected.
ui = re.sub(
    r"function enableManualRefresh\(\)\{.*?\n\s*\}",
    """function enableManualRefresh(){
        var btn=document.getElementById('refresh-device');
        if(!btn) return;

        var connected = false;
        try {
            connected = (typeof isDeviceConnected !== 'undefined' &&
                         isDeviceConnected === true);
        } catch(e) {}

        btn.disabled = connected;
        if (connected) {
            btn.setAttribute('aria-disabled','true');
        } else {
            btn.removeAttribute('aria-disabled');
        }
    }""",
    ui,
    count=1,
    flags=re.S,
)

# Successful connection explicitly locks Refresh.
ui = ui.replace(
    """        if (connectButton) {
            connectButton.disabled = true;  // Disable the button
        }
        if (selectedDeviceConnType === 'USB') {""",
    """        if (connectButton) {
            connectButton.disabled = true;  // Disable the button
        }

        var refreshButtonConnected = document.getElementById('refresh-device');
        if (refreshButtonConnected) {
            refreshButtonConnected.disabled = true;
            refreshButtonConnected.setAttribute('aria-disabled','true');
        }

        if (selectedDeviceConnType === 'USB') {""",
    1,
)

# Replace only the USB cleanup portion inside handleUsbCableRemoved().
# Keep the existing production handler structure; do not replace the whole
# function because source formatting can differ between v6.9.0 snapshots.
handler_start = ui.find("function handleUsbCableRemoved()")
handler_end = ui.find("var appVersionNum", handler_start)

if handler_start >= 0 and handler_end > handler_start:
    handler = ui[handler_start:handler_end]

    clear_pattern = re.compile(
        r"if\s*\(\s*deviceDropdown\s*\)\s*\{\s*"
        r"deviceDropdown\.innerHTML\s*=\s*'';\s*"
        r"deviceDropdown\.value\s*=\s*'';\s*"
        r"\}",
        re.S,
    )

    keep_usb_network = """if (deviceDropdown) {
        // Remove only stale USB entries. Network/Wi-Fi entries must remain.
        Array.from(deviceDropdown.options).forEach(function(option){
            try {
                var info = JSON.parse(option.value || '{}');
                if (String(info.ConnectionType || '').toUpperCase() === 'USB') {
                    option.remove();
                }
            } catch (e) {}
        });
    }"""

    handler, clear_count = clear_pattern.subn(
        keep_usb_network,
        handler,
        count=1,
    )

    if clear_count == 1:
        ui = ui[:handler_start] + handler + ui[handler_end:]
        print("USB disconnect cleanup updated: USB-only removal; Wi-Fi preserved.")
    else:
        # If the source snapshot already differs, keep the existing handler
        # rather than failing the complete Wi-Fi build.
        print("USB disconnect cleanup block not found; existing handler preserved.")
else:
    print("USB disconnect handler not found; existing UI preserved.")

# Ensure the Refresh button state after physical USB removal is correct.
handler_start = ui.find("function handleUsbCableRemoved()")
handler_end = ui.find("var appVersionNum", handler_start)
if handler_start >= 0 and handler_end > handler_start:
    handler = ui[handler_start:handler_end]

    refresh_pattern = re.compile(
        r"var\s+refreshButtonAfterUsbRemoval\s*=\s*document\.getElementById\('refresh-device'\);\s*"
        r"if\s*\(\s*refreshButtonAfterUsbRemoval\s*\)\s*\{\s*"
        r"refreshButtonAfterUsbRemoval\.disabled\s*=\s*(?:false|true)\s*;\s*"
        r"(?:refreshButtonAfterUsbRemoval\.removeAttribute\('aria-disabled'\);\s*)?"
        r"\}",
        re.S,
    )

    refresh_replacement = """var refreshButtonAfterUsbRemoval = document.getElementById('refresh-device');
    if (refreshButtonAfterUsbRemoval) {
        refreshButtonAfterUsbRemoval.disabled = false;
        refreshButtonAfterUsbRemoval.removeAttribute('aria-disabled');
    }"""

    handler, refresh_count = refresh_pattern.subn(
        refresh_replacement,
        handler,
        count=1,
    )
    if refresh_count == 1:
        ui = ui[:handler_start] + handler + ui[handler_end:]
        print("USB disconnect Refresh state normalized.")

# Remove the retired updater modal function without touching surrounding
# production layout functions (notably setDPortLayout).
def _remove_js_function(text, function_name):
    needle = "function " + function_name
    start = text.find(needle)
    if start < 0:
        return text
    brace = text.find("{", start)
    if brace < 0:
        return text
    depth = 0
    i = brace
    quote = None
    escaped = False
    line_comment = False
    block_comment = False
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if line_comment:
            if ch == "\n":
                line_comment = False
            i += 1
            continue
        if block_comment:
            if ch == "*" and nxt == "/":
                block_comment = False
                i += 2
                continue
            i += 1
            continue
        if quote:
            if escaped:
                escaped = False
            elif ch == "\\\\":
                escaped = True
            elif ch == quote:
                quote = None
            i += 1
            continue
        if ch == "/" and nxt == "/":
            line_comment = True
            i += 2
            continue
        if ch == "/" and nxt == "*":
            block_comment = True
            i += 2
            continue
        if ch in ("'", '"', "`"):
            quote = ch
            i += 1
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                while end < len(text) and text[end] in " \\t":
                    end += 1
                if end < len(text) and text[end] == ";":
                    end += 1
                if end < len(text) and text[end] == "\n":
                    end += 1
                return text[:start] + text[end:]
        i += 1
    return text

ui = _remove_js_function(ui, "dportPm3ShowUpdateModal")
ui = _remove_js_function(ui, "dportPm3ShowUpdateModalFix9")
ui = ui.replace("dport-pm3-update-modal", "dport-retired-update-modal")

# Final targeted updater residue cleanup. Remove only lines containing the
# retired updater endpoint/polling identifiers; do not touch the production
# DPort layout or connection code.
def _strip_updater_lines(text):
    kept = []
    for line in text.splitlines():
        if any(token in line for token in (
            "/pymobiledevice3/status",
            "dportStartPm3StatusPolling();",
        )):
            continue
        kept.append(line)
    return "\n".join(kept) + "\n"

src = _strip_updater_lines(src)
ui = _strip_updater_lines(ui)

# Don't build if an updater residue is present.
for forbidden in (
    "dport_release_updater",
    "bootstrap_dport_updater",
    "/pymobiledevice3/status",
    "dport-pm3-update-modal",
    "dportStartPm3StatusPolling();",
):
    if forbidden in src or forbidden in ui:
        raise SystemExit(f"Updater residue remains: {forbidden}")

MAIN.write_text(src, encoding="utf-8")
MAP.write_text(ui, encoding="utf-8")
print(f"Wi-Fi patch applied; updater route removed={route_count}.")
