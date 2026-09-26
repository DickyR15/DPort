from pathlib import Path
import ast
import re

MAIN = Path("src/main.py")
MAP = Path("src/templates/map.html")

src = MAIN.read_text(encoding="utf-8")
ui = MAP.read_text(encoding="utf-8")

# ---------------------------------------------------------------------------
# Backend-only Wi-Fi patch.
# The 6.9.0 production HTML is intentionally preserved. Only the retired
# updater DOM elements are removed by exact element-id matching; no layout,
# header, device-list rendering, or refresh code is rewritten.
# ---------------------------------------------------------------------------

# Remove DPort same-version updater imports/bootstrapping.
src_lines = [
    line for line in src.splitlines()
    if "dport_release_updater" not in line
    and "bootstrap_dport_updater()" not in line
]
src = "\n".join(src_lines) + "\n"

# Remove the retired updater status endpoint using Python's AST so only the
# named function and its decorators are removed; neighboring routes are kept.
try:
    tree = ast.parse(src)
    removals = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            decorators = list(getattr(node, "decorator_list", []))
            names = [getattr(d, "name", None) for d in decorators]
            if node.name == "pymobiledevice3_status" or "/pymobiledevice3/status" in ast.get_source_segment(src, node):
                start_line = min([d.lineno for d in decorators] + [node.lineno])
                end_line = node.end_lineno or node.lineno
                removals.append((start_line, end_line))
    for start_line, end_line in reversed(removals):
        lines = src.splitlines(True)
        del lines[start_line - 1:end_line]
        src = "".join(lines)
except SyntaxError:
    # The build script performs the final py_compile check.
    raise

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

# iOS 17.4+ Wi-Fi tunnel: Lockdown over TCP -> CoreDeviceProxy -> TCP tunnel.
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

# Fail fast when the Wi-Fi tunnel worker reports an error.
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

# Background tunnel uses TCP/CoreDeviceProxy for iOS 17.4+.
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

src = src.replace(
    "def start_wifi_tunnel_thread():\n    global terminate_tunnel_thread\n    terminate_tunnel_thread = False",
    "def start_wifi_tunnel_thread():\n    global terminate_tunnel_thread, wifi_tunnel_error\n    terminate_tunnel_thread = False\n    wifi_tunnel_error = None",
    1,
)

# Use the selected Wi-Fi endpoint directly. Do not perform a second discovery
# during connect, which can race the UI selection.
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


# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# UI state fixes. Patch the production functions directly.
# No high-frequency polling, no document-wide MutationObserver, and no layout
# rewriting. All selectors below use the actual DPort 6.9.0 IDs (#device and
# #refresh-device).
# ---------------------------------------------------------------------------

def patch_inside_function(text, function_name, patcher):
    start_i = text.find(function_name)
    if start_i < 0:
        return text, False
    next_i = text.find("\nfunction ", start_i + len(function_name))
    next_async_i = text.find("\nasync function ", start_i + len(function_name))
    candidates = [i for i in (next_i, next_async_i) if i >= 0]
    end_i = min(candidates) if candidates else len(text)
    block = text[start_i:end_i]
    new_block, changed = patcher(block)
    return text[:start_i] + new_block + text[end_i:], changed

# 1) Lock Refresh immediately after a successful device connection.
success_marker = """        isDeviceConnected = true;
        stopDeviceAutoDetect();
"""
success_insert = """        isDeviceConnected = true;
        stopDeviceAutoDetect();

        var refreshButtonConnected = document.getElementById('refresh-device');
        if (refreshButtonConnected) {
            refreshButtonConnected.disabled = true;
            refreshButtonConnected.setAttribute('aria-disabled', 'true');
            refreshButtonConnected.setAttribute('data-dport-connected-lock', '1');
        }
"""
if success_marker in ui and "data-dport-connected-lock" not in ui[ui.find(success_marker):ui.find(success_marker)+800]:
    ui = ui.replace(success_marker, success_insert, 1)

# 2) Manual Refresh: visual + functional guard.
manual_marker = """async function dportRefreshDeviceList() {
    if (typeof isDeviceConnected !== 'undefined' && isDeviceConnected) {
"""
manual_insert = """async function dportRefreshDeviceList() {
    if (typeof isDeviceConnected !== 'undefined' && isDeviceConnected) {
        var refreshWhileConnected = document.getElementById('refresh-device');
        if (refreshWhileConnected) {
            refreshWhileConnected.disabled = true;
            refreshWhileConnected.setAttribute('aria-disabled', 'true');
        }
"""
if manual_marker in ui and "refreshWhileConnected" not in ui[ui.find(manual_marker):ui.find(manual_marker)+900]:
    ui = ui.replace(manual_marker, manual_insert, 1)

# 3) Connect failure unlocks Refresh.
def patch_connect_function(block):
    marker = """            if (connectButton) {
                connectButton.disabled = false;
            }
"""
    if marker not in block or "refreshButtonConnectError" in block:
        return block, False
    repl = marker + """
            var refreshButtonConnectError = document.getElementById('refresh-device');
            if (refreshButtonConnectError) {
                refreshButtonConnectError.disabled = false;
                refreshButtonConnectError.removeAttribute('aria-disabled');
                refreshButtonConnectError.removeAttribute('data-dport-connected-lock');
            }
"""
    return block.replace(marker, repl, 1), True

ui, _ = patch_inside_function(ui, "function connectDevice()", patch_connect_function)

# 4) Physical USB removal: unlock Refresh if the source has a refresh reset.
def patch_usb_remove(block):
    marker = "var refreshButtonAfterUsbRemoval = document.getElementById('refresh-device');"
    if marker in block and "removeAttribute('data-dport-connected-lock')" not in block:
        block = block.replace(
            """        refreshButtonAfterUsbRemoval.disabled = false;
        refreshButtonAfterUsbRemoval.removeAttribute('aria-disabled');""",
            """        refreshButtonAfterUsbRemoval.disabled = false;
        refreshButtonAfterUsbRemoval.removeAttribute('aria-disabled');
        refreshButtonAfterUsbRemoval.removeAttribute('data-dport-connected-lock');""",
            1,
        )
    return block, True

ui, _ = patch_inside_function(ui, "function handleUsbCableRemoved()", patch_usb_remove)

# 5) Explicit disconnect: unlock Refresh in the disconnect function itself.
def patch_disconnect(block):
    marker = """        if (connectButton) {
            connectButton.disabled = false;
        }
"""
    if marker not in block or "refreshButtonAfterDisconnect" in block:
        return block, False
    repl = marker + """
        var refreshButtonAfterDisconnect = document.getElementById('refresh-device');
        if (refreshButtonAfterDisconnect) {
            refreshButtonAfterDisconnect.disabled = false;
            refreshButtonAfterDisconnect.removeAttribute('aria-disabled');
            refreshButtonAfterDisconnect.removeAttribute('data-dport-connected-lock');
        }
"""
    return block.replace(marker, repl, 1), True

ui, _ = patch_inside_function(ui, "function disconnectDevice()", patch_disconnect)

# 6) Preserve Wi-Fi entries inside populateDeviceList(). This is the root UI
#    producer; keeping the cache here prevents Wi-Fi from disappearing during
#    USB re-enumeration instead of trying to repaint it later.
pop_start = ui.find("async function populateDeviceList(options)")
if pop_start >= 0:
    pop_end_candidates = [
        i for i in (
            ui.find("\nasync function ", pop_start + 20),
            ui.find("\nfunction ", pop_start + 20),
        ) if i >= 0
    ]
    pop_end = min(pop_end_candidates) if pop_end_candidates else len(ui)
    pop = ui[pop_start:pop_end]

    clear_i = pop.find("deviceDropdown.innerHTML = '';")
    if clear_i >= 0 and "cachedNetworkOptions" not in pop:
        cache_code = """        // Preserve Network/Wi-Fi options before rebuilding the USB list.
        const cachedNetworkOptions = [];
        Array.from(deviceDropdown.options).forEach(function(option){
            try {
                const oldInfo = JSON.parse(option.value || '{}');
                const oldType = String(
                    oldInfo.ConnectionType ||
                    oldInfo.connectionType ||
                    oldInfo.wifiTransport ||
                    ''
                ).toUpperCase();
                if (
                    oldType === 'NETWORK' ||
                    oldType === 'WIFI' ||
                    oldInfo.wifiAddress ||
                    oldInfo.wifiPort ||
                    oldInfo.wifiTransport
                ) {
                    cachedNetworkOptions.push({
                        value: option.value,
                        text: option.text,
                        title: option.title || ''
                    });
                }
            } catch (e) {}
        });

"""
        pop = pop[:clear_i] + cache_code + pop[clear_i:]

    devices_info_i = pop.find("deviceDropdown.devicesInfo = devicesInfo;")
    if devices_info_i >= 0 and "A /list_devices response can be USB-only" not in pop:
        merge_code = """        // A /list_devices response can be USB-only while Bonjour is between
        // advertisements. Keep the last known Wi-Fi entry visible.
        const hasNetworkOption = Array.from(deviceDropdown.options).some(function(option){
            try {
                const info = JSON.parse(option.value || '{}');
                const t = String(
                    info.ConnectionType ||
                    info.connectionType ||
                    info.wifiTransport ||
                    ''
                ).toUpperCase();
                return (
                    t === 'NETWORK' ||
                    t === 'WIFI' ||
                    !!info.wifiAddress ||
                    !!info.wifiPort ||
                    !!info.wifiTransport
                );
            } catch (e) {
                return false;
            }
        });

        if (!hasNetworkOption && cachedNetworkOptions.length > 0) {
            cachedNetworkOptions.forEach(function(cached){
                const option = document.createElement('option');
                option.value = cached.value;
                option.text = cached.text;
                if (cached.title) option.title = cached.title;
                deviceDropdown.add(option);
            });
        }

"""
        pop = pop[:devices_info_i] + merge_code + pop[devices_info_i:]

    ui = ui[:pop_start] + pop + ui[pop_end:]
else:
    raise SystemExit("populateDeviceList() not found.")

# 7) Do not let an empty USB presence snapshot clear a live Wi-Fi option.
auto_start = ui.find("async function checkDeviceAutoDetect()")
if auto_start >= 0:
    auto_end = ui.find("\nfunction startDeviceAutoDetect()", auto_start)
    auto = ui[auto_start:auto_end if auto_end >= 0 else len(ui)]
    empty_start = auto.find("if (rawIds.length === 0) {")
    if empty_start >= 0:
        empty_end = auto.find("\n        }", empty_start)
        # Locate the end of the whole if-block by brace counting.
        brace_pos = auto.find("{", empty_start)
        depth = 0
        pos = brace_pos
        while pos >= 0 and pos < len(auto):
            if auto[pos] == "{":
                depth += 1
            elif auto[pos] == "}":
                depth -= 1
                if depth == 0:
                    empty_end = pos + 1
                    break
            pos += 1
        if depth == 0 and empty_end > empty_start:
            old_block = auto[empty_start:empty_end]
            if "hasNetworkEntry" not in old_block:
                new_block = """if (rawIds.length === 0) {
            const hasNetworkEntry = Array.from(deviceDropdown.options).some(function(option){
                try {
                    const info = JSON.parse(option.value || '{}');
                    const t = String(
                        info.ConnectionType ||
                        info.connectionType ||
                        info.wifiTransport ||
                        ''
                    ).toUpperCase();
                    return (
                        t === 'NETWORK' ||
                        t === 'WIFI' ||
                        !!info.wifiAddress ||
                        !!info.wifiPort ||
                        !!info.wifiTransport
                    );
                } catch (e) {
                    return false;
                }
            });

            deviceReinsertRetryCount = 0;
            deviceReinsertRetryUntil = 0;
            deviceAutoRefreshSignature = '';
            deviceAutoRefreshScheduled = false;

            if (hasNetworkEntry) {
                return;
            }

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
        }"""
                auto = auto[:empty_start] + new_block + auto[empty_end:]
                ui = ui[:auto_start] + auto + ui[auto_end:]

# Build-time sanity checks use actual production identifiers, not localized
# text, to avoid PowerShell encoding issues.
for required_ui in (
    'id="device"',
    'id="refresh-device"',
    'dportRefreshDeviceList',
    'populateDeviceList',
):
    if required_ui not in ui:
        raise SystemExit("Production UI missing: " + required_ui)

# ---------------------------------------------------------------------------
# UI: remove only the retired updater elements by exact IDs.
# This scanner removes one complete HTML element while preserving every other
# element byte-for-byte, so the production header/layout cannot be swallowed.
# ---------------------------------------------------------------------------

def remove_html_element_by_id(text: str, element_id: str) -> tuple[str, int]:
    pattern = re.compile(
        r'<(?P<tag>[A-Za-z][A-Za-z0-9:-]*)\b[^>]*\bid=["\']'
        + re.escape(element_id)
        + r'["\'][^>]*>',
        re.I,
    )
    match = pattern.search(text)
    if not match:
        return text, 0

    tag = match.group("tag")
    if match.group(0).rstrip().endswith("/>"):
        return text[:match.start()] + text[match.end():], 1

    tag_re = re.compile(r'<(/?)' + re.escape(tag) + r'\b[^>]*>', re.I)
    depth = 0
    end_pos = None
    for m in tag_re.finditer(text, match.start()):
        raw = m.group(0)
        closing = bool(m.group(1))
        self_closing = raw.rstrip().endswith("/>")
        if not closing and not self_closing:
            depth += 1
        elif closing:
            depth -= 1
            if depth == 0:
                end_pos = m.end()
                break

    if end_pos is None:
        raise SystemExit(f"Could not safely remove HTML element id={element_id}")
    return text[:match.start()] + text[end_pos:], 1

for element_id in (
    "dport-69-pm3-update-modal-fix9",
    "dport-pm3-update-modal",
    "dport-pm3-update-modal-start-fix9",
    "dport-pm3-status",
):
    ui, _ = remove_html_element_by_id(ui, element_id)

ui = re.sub(r'^\s*dportStartPm3StatusPolling\(\);\s*\r?\n?', '', ui, flags=re.M)

# The UI modifications above are deliberately limited to exact updater nodes.
# Assert that production controls remain present before writing.
for required in (
    "GPX 軌跡播放",
    "裝置連線",
    "重新整理",
    "連接裝置",
    "離開",
    "deviceDropdown",
):
    if required not in ui:
        raise SystemExit(f"Production UI element missing after Wi-Fi patch: {required}")

# Final updater checks: backend route/imports gone; updater DOM/polling gone.
for forbidden in (
    "dport_release_updater",
    "bootstrap_dport_updater",
    "/pymobiledevice3/status",
):
    if forbidden in src:
        raise SystemExit(f"Updater backend residue remains: {forbidden}")

for forbidden_ui in (
    'id="dport-pm3-update-modal"',
    'id="dport-69-pm3-update-modal-fix9"',
    'dportStartPm3StatusPolling();',
):
    if forbidden_ui in ui:
        raise SystemExit(f"Updater UI residue remains: {forbidden_ui}")

# ---------------------------------------------------------------------------
# Runtime guardrails for the existing production UI.
# This is intentionally appended without changing any existing layout/CSS or
# rewriting the production device-list code.
# ---------------------------------------------------------------------------
body_pos = ui.lower().rfind("</body>")
if body_pos < 0:
    raise SystemExit("Could not find </body> in production map.html")
ui = ui[:body_pos] + wifi_ui_guard + ui[body_pos:]

MAIN.write_text(src, encoding="utf-8")
MAP.write_text(ui, encoding="utf-8")
print("Wi-Fi patch applied. Production UI layout preserved; updater UI removed safely.")
