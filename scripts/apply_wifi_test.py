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

MAIN.write_text(src, encoding="utf-8")
MAP.write_text(ui, encoding="utf-8")
print("Wi-Fi patch applied. Production UI layout preserved; updater UI removed safely.")
