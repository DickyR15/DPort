#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

TAG = "v6.9.1"
VERSION = "6.9.1"
FINAL_EXE_NAME = "DPort-WiFi-Test-6.9.1-USBWiFi-FIX5"

ROOT = Path.cwd()
WORK = Path(tempfile.gettempdir()) / "DPort-WiFi-691-CLEAN-FIX5"
SOURCE = WORK / "source"
BUILD = WORK / "build"
ARCHIVE = WORK / "source.tar"
OUT = ROOT / "DPort-WiFi-Test-6.9.1"


def run(cmd: list[str], cwd: Path | None = None) -> str:
    print("+", " ".join(cmd))
    p = subprocess.run(cmd, cwd=cwd, check=False, text=True, capture_output=True)
    if p.stdout:
        print(p.stdout)
    if p.stderr:
        print(p.stderr, file=sys.stderr)
    if p.returncode:
        raise RuntimeError(f"Command failed ({p.returncode}): {' '.join(cmd)}")
    return p.stdout


def replace_between(text: str, start: str, end: str, replacement: str, label: str) -> str:
    a = text.find(start)
    if a < 0:
        raise RuntimeError(f"Cannot find start of {label}")
    b = text.find(end, a)
    if b < 0:
        raise RuntimeError(f"Cannot find end of {label}")
    return text[:a] + replacement + text[b:]


def build_source() -> None:
    if WORK.exists():
        shutil.rmtree(WORK)
    if OUT.exists():
        shutil.rmtree(OUT)

    SOURCE.mkdir(parents=True)
    BUILD.mkdir(parents=True)
    OUT.mkdir(parents=True)

    run(["git", "fetch", "--tags", "--force"])
    commit = run(["git", "rev-list", "-n", "1", TAG]).strip()
    run(["git", "archive", "--format=tar", f"--output={ARCHIVE}", TAG])

    with tarfile.open(ARCHIVE, "r") as tf:
        tf.extractall(SOURCE)
    shutil.copytree(SOURCE, BUILD, dirs_exist_ok=True)

    main_path = BUILD / "src" / "main.py"
    map_path = BUILD / "src" / "templates" / "map.html"
    req_path = BUILD / "requirements-build.txt"
    icon_path = BUILD / "DPort-6.9.0.ico"

    if not main_path.exists() or not map_path.exists() or not icon_path.exists():
        raise RuntimeError("Required v6.9.1 release files are missing")

    main = main_path.read_text(encoding="utf-8-sig")
    page = map_path.read_text(encoding="utf-8-sig")

    if "APP_VERSION_NUMBER" not in main:
        raise RuntimeError("Unexpected v6.9.1 main.py source")

    # ------------------------------------------------------------------
    # Dependency: current pymobiledevice3 release used for WiFi testing.
    # ------------------------------------------------------------------
    req = req_path.read_text(encoding="utf-8")
    req = re.sub(
        r"(?m)^pymobiledevice3==[0-9.]+$",
        "pymobiledevice3==11.20.0",
        req,
        count=1,
    )
    req_path.write_text(req, encoding="utf-8")

    # The module is already imported in v6.9.1; import the module itself so
    # the tunnel backend can explicitly choose the Windows kernel TUN.
    if "import pymobiledevice3.remote.tunnel_service as tunnel_service" not in main:
        anchor = "from pymobiledevice3.remote.tunnel_service import"
        pos = main.find(anchor)
        if pos < 0:
            raise RuntimeError("v6.9.1 tunnel_service import anchor missing")
        line_end = main.find("\n", pos)
        main = main[:line_end+1] + "import pymobiledevice3.remote.tunnel_service as tunnel_service\n" + main[line_end+1:]

    # ------------------------------------------------------------------
    # Backend: enable Network/WiFi in the combined device list.
    # ------------------------------------------------------------------
    wifi_disabled = """            # USB-ONLY: Wi-Fi / Network discovery intentionally disabled.
            logger.info("USB-ONLY mode: Wi-Fi/Bonjour/mDNS/RemotePairing discovery skipped")
"""
    wifi_enabled = """            # WiFi devices: use Apple's mobdev2 Bonjour discovery for the
            # device list. This is separate from the RemotePairing tunnel
            # service used to establish the actual WiFi tunnel.
            try:
                wifi_count = 0
                async for ip, network_device in get_mobdev2_lockdowns(
                    udid=None,
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
                        info["userLocale"] = get_user_country()
                        add_device(network_udid, "Network", info)
                        wifi_count += 1
                    finally:
                        try:
                            await network_device.close()
                        except Exception:
                            pass

                logger.info(f"WiFi devices added to list: {wifi_count}")
            except Exception as exc:
                logger.exception(f"WiFi device-list discovery failed: {exc}")
"""
    if wifi_disabled not in main:
        raise RuntimeError("v6.9.1 WiFi-disabled device-list block not found")
    main = main.replace(wifi_disabled, wifi_enabled, 1)

    # ------------------------------------------------------------------
    # Backend: WiFi discovery uses mobdev2 but actual tunnel follows the
    # official upstream WiFi RemotePairing path in pymobiledevice3 v11.20.0.
    # ------------------------------------------------------------------
    wifi_discovery = """def get_wifi_with_retry(max_attempts=10):
    global udid, wifi_address, wifi_port, ios_version

    logger.info("Wi-Fi discovery: Apple mobdev2 Bonjour (_apple-mobdev2._tcp)")

    for attempt in range(1, max_attempts + 1):
        try:
            async def discover():
                found = []
                async for ip, device in get_mobdev2_lockdowns(
                    udid=udid,
                    only_paired=True,
                    timeout=timeout,
                ):
                    try:
                        info = dict(device.short_info)
                        device_udid = (
                            getattr(device, "udid", None)
                            or info.get("UniqueDeviceID")
                            or udid
                        )
                        info["_DeviceUDID"] = device_udid
                        info["_Paired"] = bool(getattr(device, "paired", False))
                        found.append((ip, info))
                    finally:
                        try:
                            await device.close()
                        except Exception:
                            pass
                return found

            devices = asyncio.run(discover())
            logger.info(f"mobdev2 WiFi devices found: {len(devices)}")

            for ip, info in devices:
                device_udid = info.get("_DeviceUDID") or udid
                product = info.get("ProductVersion")

                if udid and device_udid and device_udid != udid:
                    continue

                udid = device_udid or udid
                ios_version = product or ios_version
                wifi_address = str(ip)
                wifi_port = 62078

                logger.info(
                    f"WiFi device selected: udid={udid}, "
                    f"host={wifi_address}, port={wifi_port}, iOS={ios_version}"
                )
                return {
                    "udid": udid,
                    "hostname": wifi_address,
                    "port": wifi_port,
                }

        except Exception as exc:
            logger.exception(
                f"WiFi mobdev2 discovery attempt {attempt}/{max_attempts} failed: "
                f"{type(exc).__name__}: {exc}"
            )

        if attempt < max_attempts:
            time.sleep(0.6)

    raise RuntimeError(
        "No paired WiFi device found via mobdev2. "
        "Check WiFi Sync/Bonjour, pairing and same LAN."
    )


"""
    # Replace only the first get_wifi_with_retry implementation.
    main = replace_between(
        main,
        "def get_wifi_with_retry(max_attempts=10):",
        "@app.route('/stop_tunnel', methods=['POST'])",
        wifi_discovery,
        "get_wifi_with_retry()",
    )

    # ------------------------------------------------------------------
    # Backend: official WiFi RemotePairing TCP tunnel.
    # ------------------------------------------------------------------
    official_tunnel = """async def start_wifi_tcp_tunnel() -> None:
    global terminate_tunnel_thread, rsd_port, rsd_host, wifi_address

    logger.warning(
        "Starting WiFi tunnel using pymobiledevice3 official "
        "RemotePairing path"
    )

    # Windows classic TCP tunnel uses the kernel TUN implementation.
    tunnel_service.USE_USERSPACE_TUNNEL = False
    stop_remoted_if_required()

    services = []
    last_error = None

    for attempt in range(1, 4):
        try:
            services = await get_remote_pairing_tunnel_services(
                udid=udid,
            )
            logger.info(
                f"RemotePairing WiFi services: {len(services)} "
                f"(attempt {attempt}/3)"
            )
            if services:
                break
        except Exception as exc:
            last_error = exc
            logger.exception(
                f"RemotePairing WiFi discovery {attempt}/3 failed: "
                f"{type(exc).__name__}: {exc}"
            )

        if attempt < 3:
            await asyncio.sleep(1.0)

    if not services:
        raise RuntimeError(
            "No paired RemotePairing WiFi tunnel service found. "
            f"Last error: {last_error}"
        )

    for index, service in enumerate(services, 1):
        try:
            logger.info(
                f"RemotePairing WiFi TCP tunnel {index}/{len(services)}: {service}"
            )

            async with service.start_tcp_tunnel() as tunnel_result:
                resume_remoted_if_required()

                rsd_host = str(tunnel_result.address)
                rsd_port = str(tunnel_result.port)
                wifi_address = rsd_host

                logger.info(
                    f"WiFi tunnel established: RSD={rsd_host}:{rsd_port}"
                )

                while not terminate_tunnel_thread:
                    await asyncio.sleep(0.5)

                return

        except Exception as exc:
            last_error = exc
            logger.exception(
                f"RemotePairing WiFi TCP tunnel {index}/{len(services)} failed: "
                f"{type(exc).__name__}: {exc}"
            )
        finally:
            try:
                await service.close()
            except Exception:
                pass

    raise RuntimeError(
        "All RemotePairing WiFi TCP tunnel attempts failed. "
        f"Last error: {last_error}"
    )


"""
    main = replace_between(
        main,
        "async def start_wifi_tcp_tunnel() -> None:",
        "async def start_wifi_quic_tunnel()",
        official_tunnel,
        "start_wifi_tcp_tunnel()",
    )

    # ------------------------------------------------------------------
    # Backend: WiFi connect waits for a real RSD endpoint before success.
    # ------------------------------------------------------------------
    connect_wifi = """def connect_wifi(data):
    try:
        global udid, wifi_address, connection_type, wifi_port
        global ios_version, rsd_data, rsd_host, rsd_port
        global terminate_tunnel_thread

        logger.info(f"Wifi data: {data}")

        udid = data.get("udid")
        ios_version = data.get("ios_version")
        connection_type = data.get("connType")

        if data.get("wifiAddress"):
            wifi_address = data.get("wifiAddress")
        if data.get("wifiPort"):
            try:
                wifi_port = int(data.get("wifiPort"))
            except (TypeError, ValueError):
                pass

        if not ios_version:
            return jsonify({"error": "No iOS version present"}), 400

        if not is_major_version_17_or_greater(ios_version):
            return jsonify({
                "message": "iOS version less than 17",
                "rsd_data": (ios_version, udid),
            })

        try:
            device = get_wifi_with_retry()
            logger.info(f"WiFi device selected for connection: {device}")
        except Exception as exc:
            logger.exception(f"WiFi discovery failed: {exc}")
            return jsonify({
                "error": "WiFi 裝置搜尋失敗",
                "details": str(exc),
                "connection_retryable": True,
            }), 404

        terminate_tunnel_thread = False
        rsd_host = None
        rsd_port = None
        rsd_data = None

        start_wifi_tunnel_thread()

        if not check_rsd_data():
            terminate_tunnel_thread = True
            logger.error("WiFi tunnel did not become ready.")
            return jsonify({
                "error": "WiFi Tunnel 建立失敗",
                "details": (
                    "WiFi 裝置已找到，但 RemotePairing TCP Tunnel "
                    "沒有建立 RSD。"
                ),
                "connection_retryable": True,
            }), 504

        rsd_data = (rsd_host, rsd_port)

        if not rsd_host or not rsd_port:
            terminate_tunnel_thread = True
            return jsonify({
                "error": "WiFi RSD Tunnel 無效",
                "connection_retryable": True,
            }), 502

        rsd_data_map.setdefault(udid, {})[connection_type] = {
            "host": rsd_host,
            "port": rsd_port,
        }

        logger.info(f"WiFi RSD ready: {rsd_data}")

        return jsonify({
            "rsd_data": rsd_data,
            "connection_type": "Network",
            "wifi_connected": True,
        })

    except Exception as exc:
        logger.exception(
            f"WiFi connection failed: {type(exc).__name__}: {exc}"
        )
        return jsonify({
            "error": str(exc),
            "connection_retryable": True,
        }), 500
    finally:
        logger.warning("Connect WiFi function completed")


"""
    main = replace_between(
        main,
        "def connect_wifi(data):",
        "async def start_wifi_tcp_tunnel() -> None:",
        connect_wifi,
        "connect_wifi()",
    )

    main = main.replace(
        "def check_rsd_data():\n    max_attempts = 30",
        "def check_rsd_data():\n    max_attempts = 60",
        1,
    )

    # ------------------------------------------------------------------
    # Backend: USB disconnect must preserve active Network/WiFi state.
    # ------------------------------------------------------------------
    disconnect = """@app.route('/device_disconnected', methods=['POST'])
def device_disconnected():
    global rsd_data, rsd_host, rsd_port, lockdown
    global userspace_location_tunnel, connection_type

    logger.info(
        f"Physical USB disconnect detected; connection_type={connection_type}"
    )

    # If WiFi is active, the physical USB cable is unrelated to the active
    # Network tunnel and must not tear it down.
    if str(connection_type or "").upper() == "NETWORK":
        logger.info(
            "USB disconnect while WiFi is active: preserving Network state"
        )
        return jsonify({"success": True, "preserved": "Network"})

    try:
        stop_set_location_thread()
    except Exception as exc:
        logger.warning(f"USB disconnect location cleanup failed: {exc}")

    rsd_data = None
    rsd_host = None
    rsd_port = None
    userspace_location_tunnel = None
    lockdown = None
    connection_type = None

    return jsonify({"success": True, "preserved": None})


"""
    main = replace_between(
        main,
        "@app.route('/device_disconnected', methods=['POST'])",
        "@app.route('/connect_device', methods=['POST'])",
        disconnect,
        "/device_disconnected route",
    )

    # ------------------------------------------------------------------
    # Backend: WiFi location uses the established WiFi RSD.
    # ------------------------------------------------------------------
    location = r'''async def _geoport_location_worker():
    global location_worker_stop, location_worker_ready, location_worker_error
    logger.warning("Location worker starting")

    try:
        if str(connection_type or "").upper() == "NETWORK":
            if not rsd_host or not rsd_port:
                raise RuntimeError(
                    "WiFi RSD tunnel is not established."
                )

            logger.info(
                f"Location worker using WiFi RSD {rsd_host}:{rsd_port}"
            )

            async with RemoteServiceDiscoveryService(
                (str(rsd_host), int(rsd_port)),
                name=f"DPort-WiFi-{udid or 'device'}",
            ) as rsd:
                async with DvtProvider(rsd) as dvt:
                    async with LocationSimulation(dvt) as location_service:
                        while not location_worker_stop.is_set():
                            try:
                                command = location_command_queue.get_nowait()
                            except queue.Empty:
                                await asyncio.sleep(0.05)
                                continue

                            if command == "STOP":
                                break

                            command_event = None
                            result_box = None

                            if isinstance(command, tuple) and len(command) == 4:
                                latitude, longitude, command_event, result_box = command
                            else:
                                latitude, longitude = command

                            try:
                                await location_service.set(
                                    float(latitude),
                                    float(longitude),
                                )
                                logger.warning(
                                    f"Location Set Successfully: "
                                    f"{latitude}, {longitude}"
                                )
                                if result_box is not None:
                                    result_box["success"] = True
                                if not location_worker_ready.is_set():
                                    location_worker_ready.set()
                            except Exception as set_error:
                                location_worker_error = (
                                    PASSWORD_PROTECTED_LOCATION_MESSAGE
                                    if is_device_locked_error(set_error)
                                    else str(set_error)
                                )
                                logger.exception(
                                    f"WiFi Location set failed: "
                                    f"{location_worker_error}"
                                )
                                if result_box is not None:
                                    result_box["success"] = False
                                    result_box["error"] = location_worker_error
                                if not location_worker_ready.is_set():
                                    location_worker_ready.set()
                            finally:
                                if command_event is not None:
                                    command_event.set()

                        try:
                            await location_service.clear()
                            logger.warning("Location Cleared Successfully")
                        except Exception as clear_error:
                            location_worker_error = (
                                PASSWORD_PROTECTED_LOCATION_MESSAGE
                                if is_device_locked_error(clear_error)
                                else str(clear_error)
                            )
                            logger.warning(
                                f"WiFi Location clear failed: {location_worker_error}"
                            )
            return

        # USB path remains the v6.9.1 working path.
        async with UserspaceRsdTunnel(serial=udid, autopair=True) as rsd:
            logger.info("Userspace RSD tunnel established (USB)")
            async with DvtProvider(rsd) as dvt:
                async with LocationSimulation(dvt) as location_service:
                    while not location_worker_stop.is_set():
                        try:
                            command = location_command_queue.get_nowait()
                        except queue.Empty:
                            await asyncio.sleep(0.05)
                            continue

                        if command == "STOP":
                            break

                        command_event = None
                        result_box = None
                        if isinstance(command, tuple) and len(command) == 4:
                            latitude, longitude, command_event, result_box = command
                        else:
                            latitude, longitude = command

                        try:
                            await location_service.set(
                                float(latitude), float(longitude)
                            )
                            logger.warning(
                                f"Location Set Successfully: {latitude}, {longitude}"
                            )
                            if result_box is not None:
                                result_box["success"] = True
                            if not location_worker_ready.is_set():
                                location_worker_ready.set()
                        except Exception as set_error:
                            location_worker_error = (
                                PASSWORD_PROTECTED_LOCATION_MESSAGE
                                if is_device_locked_error(set_error)
                                else str(set_error)
                            )
                            logger.exception(
                                f"USB Location set failed: {location_worker_error}"
                            )
                            if result_box is not None:
                                result_box["success"] = False
                                result_box["error"] = location_worker_error
                            if not location_worker_ready.is_set():
                                location_worker_ready.set()
                        finally:
                            if command_event is not None:
                                command_event.set()

                    try:
                        await location_service.clear()
                        logger.warning("Location Cleared Successfully")
                    except Exception as clear_error:
                        location_worker_error = str(clear_error)

    except asyncio.CancelledError:
        if not location_worker_ready.is_set():
            location_worker_error = "Location worker cancelled during initialization"
            location_worker_ready.set()
    except Exception as exc:
        location_worker_error = (
            PASSWORD_PROTECTED_LOCATION_MESSAGE
            if is_device_locked_error(exc)
            else str(exc)
        )
        logger.exception(
            f"Location worker failed: {location_worker_error}"
        )
        if not location_worker_ready.is_set():
            location_worker_ready.set()
    finally:
        logger.warning("Location worker terminated")


'''
    main = replace_between(
        main,
        "async def _geoport_location_worker():",
        "def _geoport_location_worker_entry():",
        location,
        "_geoport_location_worker()",
    )

    # ------------------------------------------------------------------
    # Frontend: complete deterministic device list with selection persistence.
    # ------------------------------------------------------------------
    populate = r'''async function populateDeviceList(options) {
    options = options || {};
    var silent = !!options.silent;
    var requestSerial = ++deviceListRequestSerial;

    var deviceDropdown = document.getElementById('device');
    var connectionDropdown = document.getElementById('connection');
    if (!deviceDropdown || !connectionDropdown) return false;

    // Preserve the user's explicit current transport before rebuilding.
    var selectedKey = null;
    var selected = deviceDropdown.options[deviceDropdown.selectedIndex];

    if (selected && selected.value) {
        try {
            var selectedInfo = JSON.parse(selected.value || '{}');
            selectedKey = {
                type: String(
                    selectedInfo.ConnectionType ||
                    selectedInfo.connectionType ||
                    selectedInfo.wifiTransport ||
                    ''
                ).toUpperCase(),
                identifier: String(
                    selectedInfo.Identifier ||
                    selectedInfo.UniqueDeviceID ||
                    ''
                )
            };
        } catch (e) {}
    }

    // If the currently selected option is WiFi, also remember its complete
    // record as a fallback when the new scan temporarily omits Network.
    var preservedNetwork = [];
    Array.from(deviceDropdown.options).forEach(function(option) {
        try {
            var info = JSON.parse(option.value || '{}');
            var type = String(
                info.ConnectionType ||
                info.connectionType ||
                info.wifiTransport ||
                ''
            ).toUpperCase();

            if (
                type === 'NETWORK' ||
                type === 'WIFI' ||
                !!info.wifiAddress ||
                !!info.wifiPort ||
                !!info.wifiTransport
            ) {
                preservedNetwork.push(info);
            }
        } catch (e) {}
    });

    var devicesInfo = {};
    var sudo_message = "{{ sudo_message }}";

    try {
        var url = options.forceFresh
            ? '/list_devices?force=1&_=' + Date.now()
            : '/list_devices?_=' + Date.now();

        var data = await fetchJsonWithTimeout(
            url,
            options.forceFresh ? 10000 : 7000
        );

        if (!data || requestSerial !== deviceListRequestSerial) {
            return false;
        }

        deviceDropdown.innerHTML = '';
        connectionDropdown.innerHTML = '';

        var seen = new Set();

        Object.keys(data).forEach(function(udid) {
            var connections = data[udid];
            if (!connections || typeof connections !== 'object') return;

            Object.keys(connections).forEach(function(connectionType) {
                var rows = connections[connectionType];
                if (!Array.isArray(rows)) return;

                rows.forEach(function(info) {
                    if (!info || typeof info !== 'object') return;

                    var key =
                        String(udid) + '|' +
                        String(connectionType) + '|' +
                        String(info.Identifier || '') + '|' +
                        String(info.wifiAddress || '');

                    if (seen.has(key)) return;
                    seen.add(key);

                    var option = document.createElement('option');
                    option.text =
                        (connectionType === 'Network' ? 'Wi-Fi' : connectionType) +
                        ': ' +
                        (info.DeviceName || 'Apple 裝置') +
                        ' - (' +
                        (info.DeviceClass || 'Apple 裝置') +
                        ' - iOS: ' +
                        (info.ProductVersion || '?') +
                        ')';

                    option.value = JSON.stringify(info);

                    devicesInfo[udid] = devicesInfo[udid] || {};
                    devicesInfo[udid][connectionType] = info;
                    deviceDropdown.add(option);
                });
            });
        });

        // Restore WiFi if a fresh backend scan temporarily returned USB only.
        preservedNetwork.forEach(function(info) {
            try {
                var networkUdid = String(
                    info.Identifier ||
                    info.UniqueDeviceID ||
                    ''
                );

                if (!networkUdid) return;

                var exists = Array.from(deviceDropdown.options).some(function(option) {
                    try {
                        var cur = JSON.parse(option.value || '{}');
                        var type = String(
                            cur.ConnectionType ||
                            cur.connectionType ||
                            cur.wifiTransport ||
                            ''
                        ).toUpperCase();

                        return (
                            (type === 'NETWORK' || type === 'WIFI' ||
                             !!cur.wifiAddress || !!cur.wifiPort ||
                             !!cur.wifiTransport) &&
                            String(
                                cur.Identifier ||
                                cur.UniqueDeviceID ||
                                ''
                            ) === networkUdid
                        );
                    } catch (e) {
                        return false;
                    }
                });

                if (exists) return;

                var option = document.createElement('option');
                option.text =
                    'Wi-Fi: ' +
                    (info.DeviceName || 'Apple 裝置') +
                    ' - (' +
                    (info.DeviceClass || 'Apple 裝置') +
                    ' - iOS: ' +
                    (info.ProductVersion || '?') +
                    ')';
                option.value = JSON.stringify(info);
                deviceDropdown.add(option);

                devicesInfo[networkUdid] = devicesInfo[networkUdid] || {};
                devicesInfo[networkUdid].Network = info;
            } catch (e) {}
        });

        deviceDropdown.devicesInfo = devicesInfo;

        // Restore the previous user selection when possible.
        var restored = false;

        if (selectedKey && selectedKey.identifier) {
            var restoredOption = Array.from(deviceDropdown.options).find(function(option) {
                try {
                    var info = JSON.parse(option.value || '{}');
                    var type = String(
                        info.ConnectionType ||
                        info.connectionType ||
                        info.wifiTransport ||
                        ''
                    ).toUpperCase();

                    var identifier = String(
                        info.Identifier ||
                        info.UniqueDeviceID ||
                        ''
                    );

                    return (
                        type === selectedKey.type &&
                        identifier === selectedKey.identifier
                    );
                } catch (e) {
                    return false;
                }
            });

            if (restoredOption) {
                deviceDropdown.value = restoredOption.value;
                restored = true;
            }
        }

        // USB is the startup default only when there is no current explicit
        // selection to restore.
        if (!restored && !selectedKey && !isDeviceConnected) {
            var usbDefault = Array.from(deviceDropdown.options).find(function(option) {
                try {
                    var info = JSON.parse(option.value || '{}');
                    return String(
                        info.ConnectionType ||
                        info.connectionType ||
                        ''
                    ).toUpperCase() === 'USB';
                } catch (e) {
                    return false;
                }
            });

            if (usbDefault) {
                deviceDropdown.value = usbDefault.value;
            }
        }

        if (!deviceDropdown.dataset.geoportHandlersBound) {
            deviceDropdown.addEventListener('change', function() {
                var option = deviceDropdown.options[deviceDropdown.selectedIndex];
                if (!option) return;

                try {
                    var info = JSON.parse(option.value || '{}');
                    console.log(
                        '[DPort FIX5] user selected',
                        String(
                            info.ConnectionType ||
                            info.connectionType ||
                            info.wifiTransport ||
                            ''
                        ),
                        String(
                            info.Identifier ||
                            info.UniqueDeviceID ||
                            ''
                        )
                    );
                } catch (e) {}
            });
            deviceDropdown.dataset.geoportHandlersBound = '1';
        }

        if (!isDeviceConnected && !deviceAutoDetectTimer) {
            startDeviceAutoDetect();
        }

        if (sudo_message && !silent) {
            displayToast(sudo_message);
        }

        return deviceDropdown.options.length > 0;

    } catch (error) {
        if (!silent) {
            console.error('錯誤 fetching device list:', error);
        }
        return false;
    }
}



'''
    page = replace_between(
        page,
        "async function populateDeviceList(options) {",
        "/* Manual device-list refresh:",
        populate,
        "populateDeviceList()",
    )

    # Auto detector: never assign USB automatically. Its only responsibilities
    # are presence detection and triggering a refresh. populateDeviceList()
    # handles the initial USB default and selection restoration.
    auto = r'''async function checkDeviceAutoDetect() {
    if (
        isDeviceConnected ||
        deviceAutoDetectBusy ||
        deviceListManualRefreshInFlight
    ) {
        return;
    }

    var deviceDropdown = document.getElementById('device');
    if (!deviceDropdown) return;

    deviceAutoDetectBusy = true;

    try {
        var presence = await fetchJsonWithTimeout(
            '/usb_presence?_=' + Date.now(),
            1500
        );

        var usbDevices = presence && Array.isArray(presence.devices)
            ? presence.devices
            : [];

        var rawIds = usbDevices
            .map(function(device) {
                return String(device.Identifier || '');
            })
            .filter(Boolean)
            .sort();

        var displayedUsbIds = Array.from(deviceDropdown.options)
            .map(function(option) {
                try {
                    var info = JSON.parse(option.value || '{}');
                    var type = String(
                        info.ConnectionType ||
                        info.connectionType ||
                        info.wifiTransport ||
                        ''
                    ).toUpperCase();

                    if (type !== 'USB') return '';

                    return String(
                        info.Identifier ||
                        info.UniqueDeviceID ||
                        ''
                    );
                } catch (e) {
                    return '';
                }
            })
            .filter(Boolean)
            .sort();

        if (rawIds.length > 0) {
            var sameUsb =
                rawIds.length === displayedUsbIds.length &&
                rawIds.every(function(id, index) {
                    return id === displayedUsbIds[index];
                });

            if (!sameUsb && Date.now() >= deviceFallbackFullScanNext) {
                deviceFallbackFullScanNext = Date.now() + 700;

                await populateDeviceList({
                    silent: true,
                    autoDetect: true,
                    forceFresh: true
                });
            }

            deviceAutoRefreshSignature = rawIds.join('|');
            return;
        }

        // USB absent: remove only USB rows and immediately rebuild the list
        // so Network/WiFi can appear without pressing Refresh.
        Array.from(deviceDropdown.options).forEach(function(option) {
            try {
                var info = JSON.parse(option.value || '{}');
                var type = String(
                    info.ConnectionType ||
                    info.connectionType ||
                    info.wifiTransport ||
                    ''
                ).toUpperCase();

                if (type === 'USB') {
                    option.remove();
                }
            } catch (e) {}
        });

        var hasNetwork = Array.from(deviceDropdown.options).some(function(option) {
            try {
                var info = JSON.parse(option.value || '{}');
                var type = String(
                    info.ConnectionType ||
                    info.connectionType ||
                    info.wifiTransport ||
                    ''
                ).toUpperCase();

                return (
                    type === 'NETWORK' ||
                    type === 'WIFI' ||
                    !!info.wifiAddress ||
                    !!info.wifiPort ||
                    !!info.wifiTransport
                );
            } catch (e) {
                return false;
            }
        });

        if (
            !hasNetwork &&
            Date.now() >= deviceFallbackFullScanNext
        ) {
            deviceFallbackFullScanNext = Date.now() + 1800;

            await populateDeviceList({
                silent: true,
                autoDetect: true,
                forceFresh: true
            });
        }

        deviceAutoRefreshSignature = '';

    } catch (e) {
        if (!e || e.name !== 'AbortError') {
            console.debug('自動偵測裝置略過一次:', e);
        }
    } finally {
        deviceAutoDetectBusy = false;
    }
}



'''
    page = replace_between(
        page,
        "async function checkDeviceAutoDetect() {",
        "function startDeviceAutoDetect()",
        auto,
        "checkDeviceAutoDetect()",
    )

    # USB cable removal: keep WiFi and trigger a full combined scan.
    remove = r'''function handleUsbCableRemoved() {
    stopUsbPresenceMonitor();
    activeUsbUDID = null;
    isDeviceConnected = false;

    if (typeof stopGPXPlaybackForReason === 'function') {
        stopGPXPlaybackForReason(
            "裝置已中斷連接，GPX 軌跡播放已停止。"
        );
    }

    var connectButton = document.getElementById('connect');
    var connectTextElement = document.getElementById('connectText');
    var disconnectButton = document.getElementById('disconnect');
    var deviceDropdown = document.getElementById('device');
    var connectionDropdown = document.getElementById('connection');
    var spinnerElement = document.getElementById('spinner');

    if (deviceDropdown) {
        Array.from(deviceDropdown.options).forEach(function(option) {
            try {
                var info = JSON.parse(option.value || '{}');
                var type = String(
                    info.ConnectionType ||
                    info.connectionType ||
                    info.wifiTransport ||
                    ''
                ).toUpperCase();

                if (type === 'USB') {
                    option.remove();
                }
            } catch (e) {}
        });

        if (deviceDropdown.options.length > 0) {
            deviceDropdown.selectedIndex = 0;
        }
    }

    if (connectionDropdown) {
        connectionDropdown.innerHTML = '';
        connectionDropdown.value = '';
    }

    if (connectTextElement) {
        connectTextElement.innerText = "連接裝置";
        connectTextElement.style.display = 'inline-block';
    }

    if (connectButton) connectButton.disabled = false;

    if (disconnectButton) {
        disconnectButton.style.display = 'none';
        disconnectButton.disabled = false;
        disconnectButton.innerText = "中斷連接";
    }

    if (deviceDropdown) deviceDropdown.disabled = false;
    if (spinnerElement) spinnerElement.style.display = 'none';

    var refreshButton = document.getElementById('refresh-device');
    if (refreshButton) {
        refreshButton.disabled = false;
        refreshButton.removeAttribute('aria-disabled');
    }

    // Immediate combined re-enumeration. WiFi no longer waits for the user
    // to click "重新整理".
    populateDeviceList({
        silent: true,
        autoDetect: true,
        forceFresh: true
    }).catch(function(e) {
        console.debug('USB 拔除後 WiFi 自動發現略過一次:', e);
    });

    startDeviceAutoDetect();

    fetch('/device_disconnected', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({})
    }).catch(function(error) {
        console.debug('USB disconnect cleanup skipped:', error);
    });

    displayToast("USB 已拔除，正在自動搜尋 WiFi 裝置。");
}

    '''
    page = replace_between(
        page,
        "function handleUsbCableRemoved()",
        "var appVersionNum =",
        remove,
        "handleUsbCableRemoved()",
    )

    # Frontend diagnostics and request state.
    global_marker = "var isDeviceConnected = false;"
    if "var dportConnectionInProgress = false;" not in page:
        if global_marker not in page:
            raise RuntimeError("FIX5 device state anchor missing")
        page = page.replace(
            global_marker,
            global_marker + "\nvar dportConnectionInProgress = false;",
            1,
        )

    # Do not let the transport list change during a WiFi request alter the
    # semantic request already being sent to Flask.
    connect_start = page.find("async function connectDevice() {")
    if connect_start < 0:
        raise RuntimeError("FIX5 connectDevice() missing")
    guard_pos = page.find("    if (isDeviceConnected) return;", connect_start)
    if guard_pos < 0:
        raise RuntimeError("FIX5 connectDevice() guard missing")
    line_end = page.find("\n", guard_pos) + 1
    if "dportConnectionInProgress = true;" not in page[line_end:line_end+200]:
        page = page[:line_end] + "    dportConnectionInProgress = true;\n" + page[line_end:]

    # Add a diagnostic in the response path, while preserving existing UI.
    page = page.replace(
        "        console.log('connect data: ', data);",
        "        console.log('[DPort FIX5] connect data:', data);",
        1,
    )

    page = page.replace(
        "        isDeviceConnected = true;\n        stopDeviceAutoDetect();",
        "        isDeviceConnected = true;\n        dportConnectionInProgress = false;\n        stopDeviceAutoDetect();",
        1,
    )

    page = page.replace(
        "        if ('error' in data) {\n",
        "        if ('error' in data) {\n            dportConnectionInProgress = false;\n",
        1,
    )

    # Catch network/transport errors and reset the request flag.
    page = page.replace(
        "            if (connectButton) {\n                connectButton.disabled = false;  // 重新啟用連接按鈕\n            }\n});",
        "            if (connectButton) {\n                connectButton.disabled = false;  // 重新啟用連接按鈕\n            }\n            dportConnectionInProgress = false;\n});",
        1,
    )

    # ------------------------------------------------------------------
    # Static checks before PyInstaller.
    # ------------------------------------------------------------------
    checks = [
        ("Network device list enabled", "WiFi devices added to list:"),
        ("Official WiFi RemotePairing tunnel", "get_remote_pairing_tunnel_services("),
        ("WiFi TCP tunnel call", "service.start_tcp_tunnel()"),
        ("WiFi RSD location", "Location worker using WiFi RSD"),
        ("WiFi selection persistence", "selectedKey = null"),
        ("No forced USB in auto detector", "USB is already the initial default"),
    ]
    for label, needle in checks:
        if needle not in (main + page):
            raise RuntimeError(f"FIX5 static check failed: {label}")

    main_path.write_text(main, encoding="utf-8")
    map_path.write_text(page, encoding="utf-8")

    # Verify Python syntax after all source transformations.
    run([sys.executable, "-m", "py_compile", str(main_path)])

    (OUT / "BUILD-BASE.txt").write_text(
        f"DPort v{VERSION} clean release source\n"
        f"Git tag: {TAG}\n"
        f"Git commit: {commit}\n"
        f"WiFi test builder: FIX5\n"
        f"pymobiledevice3: 11.20.0\n",
        encoding="utf-8",
    )


def build_exe() -> None:
    run([
        sys.executable, "-m", "pip", "install",
        "-r", str(BUILD / "requirements-build.txt")
    ])
    run([sys.executable, "-m", "pip", "install", "pefile"])

    icon = BUILD / "DPort-6.9.0.ico"
    if not icon.exists():
        raise RuntimeError("DPort icon missing")

    run([
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name", FINAL_EXE_NAME,
        "--icon", str(icon),
        "--add-data", f"src/templates{os.pathsep}templates",
        "--collect-all", "pymobiledevice3",
        "--collect-all", "pytun_pmd3",
        "--collect-all", "pyimg4",
        "--collect-all", "inquirer3",
        "--copy-metadata", "pymobiledevice3",
        "--copy-metadata", "pyimg4",
        "--copy-metadata", "readchar",
        "src/main.py",
    ], cwd=BUILD)

    built = BUILD / "dist" / f"{FINAL_EXE_NAME}.exe"
    if not built.exists():
        raise RuntimeError("PyInstaller output EXE is missing")

    final = OUT / built.name
    shutil.copy2(built, final)

    digest = hashlib.sha256(final.read_bytes()).hexdigest()
    (OUT / f"{final.name}.sha256").write_text(
        digest + "\n",
        encoding="ascii",
    )

    (OUT / "README-WiFi-Test.txt").write_text(
        f"""DPort Windows WiFi Test 6.9.1 - FIX5

Base source:
DPort Release v6.9.1
Git tag: {TAG}

WiFi:
- Apple mobdev2 discovery
- Official pymobiledevice3 RemotePairing TCP tunnel
- WiFi RSD used for LocationSimulation

USB/WiFi selector:
- USB is the startup default
- User-selected WiFi remains selected while USB is inserted
- USB is re-detected without hiding WiFi
- USB removal triggers automatic WiFi rediscovery

Research/test build only.
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    build_source()
    build_exe()
    print(f"BUILD SUCCESS: {OUT / (FINAL_EXE_NAME + '.exe')}")
