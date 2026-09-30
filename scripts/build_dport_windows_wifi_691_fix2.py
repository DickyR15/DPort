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
FINAL_EXE_NAME = "DPort-WiFi-Test-6.9.1-USBWiFi-FIX3"

ROOT = Path.cwd()
WORK = Path(tempfile.gettempdir()) / "DPort-WiFi-691-CLEAN-FIX3"
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


def replace_function(text: str, start_marker: str, end_marker: str, replacement: str, label: str) -> str:
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError(f"Could not locate start of {label}")
    end = text.find(end_marker, start)
    if end < 0:
        raise RuntimeError(f"Could not locate end of {label}")
    return text[:start] + replacement + text[end:]


def build_source() -> None:
    if WORK.exists():
        shutil.rmtree(WORK)
    if OUT.exists():
        shutil.rmtree(OUT)
    SOURCE.mkdir(parents=True)
    BUILD.mkdir(parents=True)
    OUT.mkdir(parents=True)

    run(["git", "fetch", "--tags", "--force"])
    run(["git", "rev-parse", "--verify", TAG])
    commit = run(["git", "rev-list", "-n", "1", TAG]).strip()

    run(["git", "archive", "--format=tar", f"--output={ARCHIVE}", TAG])
    with tarfile.open(ARCHIVE, "r") as tf:
        tf.extractall(SOURCE)

    shutil.copytree(SOURCE, BUILD, dirs_exist_ok=True)

    if not VERSION_FILE.exists() or "6.9.1" not in VERSION_FILE.read_text(encoding="utf-8"):
        raise RuntimeError("Extracted source is not DPort v6.9.1")
    if not MAIN.exists() or not MAP.exists() or not ICON.exists():
        raise RuntimeError("Required v6.9.1 source files are missing")

    main = MAIN.read_text(encoding="utf-8-sig")
    page = MAP.read_text(encoding="utf-8-sig")

    # Imports needed by the WiFi tunnel.
    anchor = "from pymobiledevice3.remote.userspace_tunnel import UserspaceRsdTunnel"
    if "import pymobiledevice3.remote.tunnel_service as tunnel_service" not in main:
        if anchor not in main:
            raise RuntimeError("tunnel_service import anchor missing")
        main = main.replace(
            anchor,
            anchor + "\nimport pymobiledevice3.remote.tunnel_service as tunnel_service",
            1,
        )

    # Open Network/WiFi connection path from clean v6.9.1.
    usb_gate = '''    if connection_type != "USB":
        logger.warning(f"USB-ONLY build: rejecting non-USB connection type: {connection_type}")
        return jsonify({"error": "USB-only mode: please connect the Apple device by USB."}), 400

'''
    main = main.replace(usb_gate, "", 1)

    # Real WiFi discovery; preserves the original clean v6.9.1 USB path.
    disabled = '''            # USB-ONLY: Wi-Fi / Network discovery intentionally disabled.
            logger.info("USB-ONLY mode: Wi-Fi/Bonjour/mDNS/RemotePairing discovery skipped")
'''
    wifi_discovery = '''            try:
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
                        add_device(network_udid, "Network", info)
                    finally:
                        try:
                            await network_device.close()
                        except Exception:
                            pass
                logger.info(f"WiFi device-list count: {wifi_count}")
            except Exception as exc:
                logger.exception(f"WiFi discovery failed: {exc}")
'''
    if disabled not in main:
        # The exact disabled block is in v6.9.1; fail rather than patch the wrong source.
        raise RuntimeError("v6.9.1 WiFi-disabled discovery block not found")
    main = main.replace(disabled, wifi_discovery, 1)

    # Robust WiFi discovery parser.
    wifi_function = '''def get_wifi_with_retry(max_attempts=10):
    global udid, wifi_address, wifi_port, ios_version

    logger.info("Wi-Fi discovery: using Apple mobdev2 Bonjour (_apple-mobdev2._tcp)")

    for attempt in range(1, max_attempts + 1):
        found = False
        try:
            async def discover():
                results = []
                async for ip, device in get_mobdev2_lockdowns(
                    udid=udid,
                    only_paired=True,
                    timeout=timeout,
                ):
                    try:
                        short = dict(device.short_info)
                        short["_DeviceUDID"] = (
                            getattr(device, "udid", None)
                            or short.get("UniqueDeviceID")
                        )
                        short["_Paired"] = bool(getattr(device, "paired", False))
                        results.append((ip, short))
                    finally:
                        try:
                            await device.close()
                        except Exception:
                            pass
                return results

            devices = asyncio.run(discover())
            logger.info(f"mobdev2 Wi-Fi devices found: {len(devices)}")

            for ip, short in devices:
                device_udid = (
                    short.get("_DeviceUDID")
                    or short.get("UniqueDeviceID")
                    or udid
                )
                product = short.get("ProductVersion")

                logger.info(
                    f"mobdev2 device: ip={ip}, udid={device_udid}, "
                    f"iOS={product}, paired={short.get('_Paired')}"
                )

                if udid and device_udid and device_udid != udid:
                    continue

                udid = device_udid or udid
                ios_version = product or ios_version
                wifi_address = str(ip)
                wifi_port = 62078
                found = True
                return {
                    "udid": udid,
                    "hostname": wifi_address,
                    "port": wifi_port,
                }

        except Exception as exc:
            logger.exception(
                f"Attempt {attempt}: mobdev2 Wi-Fi discovery error: {exc}"
            )

        if not found:
            logger.warning(
                f"Attempt {attempt}: no paired mobdev2 Wi-Fi device found."
            )
        time.sleep(0.5)

    raise RuntimeError(
        "No Wi-Fi device found. Check Apple Mobile Device Service, "
        "Wi-Fi Sync, pairing, same LAN, and Windows Firewall/mDNS."
    )


'''
    main = replace_function(
        main,
        r"def get_wifi_with_retry(max_attempts=10):",
        r"@app.route('/stop_tunnel'",
        wifi_function,
        "get_wifi_with_retry()",
    )

    # CoreDeviceProxy first, RemotePairing fallback.
    tunnel_function = '''async def start_wifi_tcp_tunnel() -> None:
    global terminate_tunnel_thread, rsd_port, rsd_host, wifi_address

    logger.warning("Start Wi-Fi TCP tunnel via mobdev2 + CoreDeviceProxy")
    stop_remoted_if_required()

    primary_error = None

    for attempt in range(1, 3):
        lockdown = None
        service = None
        try:
            async for ip, candidate in get_mobdev2_lockdowns(
                udid=udid,
                only_paired=True,
                timeout=timeout,
            ):
                wifi_address = str(ip)
                lockdown = candidate
                logger.info(
                    f"mobdev2 tunnel candidate: {ip}, udid={candidate.udid}"
                )
                break

            if lockdown is None:
                raise RuntimeError(
                    f"mobdev2 could not reconnect to paired device {udid}"
                )

            service = await CoreDeviceTunnelProxy.create(lockdown)
            tunnel_service.USE_USERSPACE_TUNNEL = False

            async with service.start_tcp_tunnel() as tunnel_result:
                resume_remoted_if_required()
                rsd_host = tunnel_result.address
                rsd_port = str(tunnel_result.port)

                logger.info(
                    f"CoreDeviceProxy Wi-Fi TCP tunnel established: "
                    f"{rsd_host}:{rsd_port}"
                )

                while not terminate_tunnel_thread:
                    await asyncio.sleep(0.5)
                return

        except Exception as exc:
            primary_error = exc
            logger.exception(
                f"CoreDeviceProxy WiFi attempt {attempt}/2 failed: "
                f"{type(exc).__name__}: {exc}"
            )
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

        if attempt == 1:
            await asyncio.sleep(1.0)

    logger.warning("CoreDeviceProxy failed; trying RemotePairing WiFi fallback.")

    try:
        services = await get_remote_pairing_tunnel_services(udid=udid)
    except Exception as exc:
        raise RuntimeError(
            f"RemotePairing discovery failed after CoreDeviceProxy error: {exc}"
        ) from exc

    if not services:
        raise RuntimeError(
            "No RemotePairing WiFi service found after CoreDeviceProxy failure: "
            f"{primary_error}"
        )

    for service in services:
        try:
            tunnel_service.USE_USERSPACE_TUNNEL = False

            async with service.start_tcp_tunnel() as tunnel_result:
                resume_remoted_if_required()
                rsd_host = tunnel_result.address
                rsd_port = str(tunnel_result.port)

                logger.info(
                    f"RemotePairing WiFi TCP tunnel established: "
                    f"{rsd_host}:{rsd_port}"
                )

                while not terminate_tunnel_thread:
                    await asyncio.sleep(0.5)
                return

        except Exception as exc:
            logger.exception(
                f"RemotePairing WiFi tunnel failed: "
                f"{type(exc).__name__}: {exc}"
            )
        finally:
            try:
                await service.close()
            except Exception:
                pass

    raise RuntimeError(
        "WiFi tunnel failed. "
        f"CoreDeviceProxy error: {primary_error}"
    )


'''
    main = replace_function(
        main,
        r"async def start_wifi_tcp_tunnel() -> None:",
        r"async def start_wifi_quic_tunnel()",
        tunnel_function,
        "start_wifi_tcp_tunnel()",
    )

    # Detailed failure is kept in logs instead of being swallowed.
    main = main.replace(
        '''    except Exception as e:
        logger.error(f"Error in run_wifi_tunnel: {e}")
''',
        '''    except Exception as e:
        logger.exception(f"Error in run_wifi_tunnel: {type(e).__name__}: {e}")
''',
        1,
    )

    # WiFi location must not fall back to usbmux when USB is unplugged.
    location_function = '''async def _geoport_location_worker():
    global location_worker_stop, location_worker_ready, location_worker_error
    logger.warning("Location worker starting")

    try:
        if str(connection_type or "").upper() == "NETWORK":
            if not rsd_host or not rsd_port:
                raise RuntimeError(
                    "WiFi RSD tunnel is not established; LocationSimulation cannot start."
                )

            logger.info(
                f"Location worker using active WiFi RSD: {rsd_host}:{rsd_port}"
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
                                    f"Location set failed: {location_worker_error}"
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
                                f"Location clear failed: {location_worker_error}"
                            )
            return

        # USB path: keep the existing DPort v6.9.1 implementation.
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
                                f"Location set failed: {location_worker_error}"
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
                            f"Location clear failed: {location_worker_error}"
                        )

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
        logger.exception(f"Location worker failed: {location_worker_error}")
        if not location_worker_ready.is_set():
            location_worker_ready.set()
    finally:
        logger.warning("Location worker terminated")


'''
    main = replace_function(
        main,
        r"async def _geoport_location_worker():",
        r"def _geoport_location_worker_entry():",
        location_function,
        "_geoport_location_worker()",
    )

    # ------------------------------------------------------------------
    # map.html - deterministic USB/WiFi coexistence
    # ------------------------------------------------------------------
    populate_function = '''async function populateDeviceList(options) {
    options = options || {};
    var silent = !!options.silent;
    var requestSerial = ++deviceListRequestSerial;

    var deviceDropdown = document.getElementById('device');
    var connectionDropdown = document.getElementById('connection');
    if (!deviceDropdown || !connectionDropdown) return false;

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
            options.forceFresh ? 9000 : 7000
        );

        if (!data || requestSerial !== deviceListRequestSerial) {
            return false;
        }

        deviceDropdown.innerHTML = '';
        connectionDropdown.innerHTML = '';

        var seen = new Set();

        Object.keys(data).forEach(function(deviceUdid) {
            var connections = data[deviceUdid];
            if (!connections || typeof connections !== 'object') return;

            Object.keys(connections).forEach(function(connectionType) {
                var rows = connections[connectionType];
                if (!Array.isArray(rows)) return;

                rows.forEach(function(info) {
                    if (!info || typeof info !== 'object') return;

                    var key =
                        String(deviceUdid) + '|' +
                        String(connectionType) + '|' +
                        String(info.Identifier || '') + '|' +
                        String(info.wifiAddress || '');

                    if (seen.has(key)) return;
                    seen.add(key);

                    var option = document.createElement('option');
                    var displayType =
                        connectionType === 'Network' ? 'Wi-Fi' : connectionType;

                    option.text =
                        displayType + ': ' +
                        (info.DeviceName || 'Apple 裝置') +
                        ' - (' +
                        (info.DeviceClass || 'Apple 裝置') +
                        ' - iOS: ' +
                        (info.ProductVersion || '?') +
                        ')';

                    option.value = JSON.stringify(info);

                    devicesInfo[deviceUdid] = devicesInfo[deviceUdid] || {};
                    devicesInfo[deviceUdid][connectionType] = info;
                    deviceDropdown.add(option);
                });
            });
        });

        // Keep a previously visible WiFi option if the fresh scan temporarily
        // returns only USB.
        preservedNetwork.forEach(function(info) {
            try {
                var networkUdid = String(
                    info.Identifier ||
                    info.UniqueDeviceID ||
                    ''
                );
                if (!networkUdid) return;

                var alreadyThere = Array.from(deviceDropdown.options).some(function(option) {
                    try {
                        var cur = JSON.parse(option.value || '{}');
                        var type = String(
                            cur.ConnectionType ||
                            cur.connectionType ||
                            cur.wifiTransport ||
                            ''
                        ).toUpperCase();

                        return (
                            (
                                type === 'NETWORK' ||
                                type === 'WIFI' ||
                                !!cur.wifiAddress ||
                                !!cur.wifiPort ||
                                !!cur.wifiTransport
                            ) &&
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

                if (alreadyThere) return;

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

        // USB is the default when present.
        if (!isDeviceConnected) {
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
                var selected = deviceDropdown.options[deviceDropdown.selectedIndex];
                if (!selected) return;
                try {
                    selected.value = JSON.stringify(
                        JSON.parse(selected.value || '{}')
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
    page = replace_function(
        page,
        r"async function populateDeviceList(options)",
        r"/* Manual device-list refresh:",
        populate_function,
        "populateDeviceList()",
    )

    auto_function = '''async function checkDeviceAutoDetect() {
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

        if (!presence || presence.error) {
            if (Date.now() >= deviceFallbackFullScanNext) {
                deviceFallbackFullScanNext = Date.now() + 1000;
                await populateDeviceList({
                    silent: true,
                    autoDetect: true,
                    forceFresh: true
                });
            }
            return;
        }

        var usbDevices = Array.isArray(presence.devices)
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
                deviceFallbackFullScanNext = Date.now() + 600;

                // Never create an incomplete "iOS: ?" row from usb_presence.
                await populateDeviceList({
                    silent: true,
                    autoDetect: true,
                    usbRetry: 1,
                    forceFresh: true
                });
            }

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

            deviceAutoRefreshSignature = rawIds.join('|');
            return;
        }

        // USB is absent: remove only USB rows. WiFi stays.
        Array.from(deviceDropdown.options).forEach(function(option) {
            try {
                var info = JSON.parse(option.value || '{}');
                var type = String(
                    info.ConnectionType ||
                    info.connectionType ||
                    ''
                ).toUpperCase();

                if (type === 'USB') {
                    option.remove();
                }
            } catch (e) {}
        });

        deviceAutoRefreshSignature = '';

    } catch (e) {
        if (!e || e.name !== 'AbortError') {
            console.debug('自動偵測 USB 裝置略過一次檢查:', e);
        }
    } finally {
        deviceAutoDetectBusy = false;
    }
}



'''
    page = replace_function(
        page,
        r"async function checkDeviceAutoDetect()",
        r"function startDeviceAutoDetect()",
        auto_function,
        "checkDeviceAutoDetect()",
    )

    remove_function = '''function handleUsbCableRemoved() {
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

    // Remove only USB. WiFi remains visible.
    if (deviceDropdown) {
        Array.from(deviceDropdown.options).forEach(function(option) {
            try {
                var info = JSON.parse(option.value || '{}');
                var type = String(
                    info.ConnectionType ||
                    info.connectionType ||
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
        connectTextElement.innerText = '連接裝置';
        connectTextElement.style.display = 'inline-block';
    }

    if (connectButton) connectButton.disabled = false;

    if (disconnectButton) {
        disconnectButton.style.display = 'none';
        disconnectButton.disabled = false;
        disconnectButton.innerText = '中斷連接';
    }

    if (deviceDropdown) deviceDropdown.disabled = false;
    if (spinnerElement) spinnerElement.style.display = 'none';

    var refreshButton = document.getElementById('refresh-device');
    if (refreshButton) {
        refreshButton.disabled = false;
        refreshButton.removeAttribute('aria-disabled');
    }

    startDeviceAutoDetect();

    fetch('/device_disconnected', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({})
    }).catch(function(error) {
        console.debug('USB disconnect cleanup skipped:', error);
    });

    displayToast(
        '裝置已中斷連接，WiFi 仍可使用；重新插入 USB 後會自動恢復 USB。'
    );
}

    '''
    page = replace_function(
        page,
        r"function handleUsbCableRemoved()",
        "var appVersionNum =",
        remove_function,
        "handleUsbCableRemoved()",
    )

    # ------------------------------------------------------------------
    # FINAL RACE FIXES
    # ------------------------------------------------------------------

    # Frontend connection-attempt state. USB hotplug may update the list,
    # but it must not steal the current WiFi selection while connectDevice()
    # is awaiting /connect_device.
    page = page.replace(
        "var deviceAutoDetectTimer = null;\nvar deviceAutoDetectBusy = false;",
        "var deviceAutoDetectTimer = null;\n"
        "var deviceAutoDetectBusy = false;\n"
        "var deviceConnectionAttemptInProgress = false;\n"
        "var deviceConnectionAttemptTransport = '';\n"
        "var deviceConnectionAttemptUdid = '';",
        1,
    )

    page = page.replace(
        "        // USB is the default when present.\n"
        "        if (!isDeviceConnected) {",
        "        // USB is the default when present, except during an active "
        "WiFi connection request.\n"
        "        if (!isDeviceConnected && !deviceConnectionAttemptInProgress) {",
        1,
    )

    # The auto-detector's USB-default assignment is a second path that can
    # steal the selection during WiFi connection.
    page = page.replace(
        "            if (usbDefault) {\n"
        "                deviceDropdown.value = usbDefault.value;\n"
        "            }\n\n"
        "            deviceAutoRefreshSignature = rawIds.join('|');",
        "            if (usbDefault && !deviceConnectionAttemptInProgress) {\n"
        "                deviceDropdown.value = usbDefault.value;\n"
        "            }\n\n"
        "            deviceAutoRefreshSignature = rawIds.join('|');",
        1,
    )

    # When a USB hotplug refresh completes, restore the in-flight WiFi option.
    page = page.replace(
        "        deviceDropdown.devicesInfo = devicesInfo;\n\n"
        "        // USB is the default when present, except during an active "
        "WiFi connection request.",
        "        deviceDropdown.devicesInfo = devicesInfo;\n\n"
        "        if (deviceConnectionAttemptInProgress &&\n"
        "            deviceConnectionAttemptTransport === 'NETWORK') {\n"
        "            var wifiInFlight = Array.from(deviceDropdown.options).find(function(option) {\n"
        "                try {\n"
        "                    var info = JSON.parse(option.value || '{}');\n"
        "                    var type = String(info.ConnectionType || info.connectionType || info.wifiTransport || '').toUpperCase();\n"
        "                    return (type === 'NETWORK' || type === 'WIFI') &&\n"
        "                        String(info.Identifier || info.UniqueDeviceID || '') === String(deviceConnectionAttemptUdid || '');\n"
        "                } catch (e) {\n"
        "                    return false;\n"
        "                }\n"
        "            });\n"
        "            if (wifiInFlight) deviceDropdown.value = wifiInFlight.value;\n"
        "        }\n\n"
        "        // USB is the default when present, except during an active "
        "WiFi connection request.",
        1,
    )

    # USB removal: rediscover WiFi immediately so manual Refresh is no longer
    # required.
    page = page.replace(
        "    startDeviceAutoDetect();\n\n    fetch('/device_disconnected', {",
        "    startDeviceAutoDetect();\n\n"
        "    setTimeout(function() {\n"
        "        if (!isDeviceConnected && !deviceConnectionAttemptInProgress) {\n"
        "            populateDeviceList({silent:true, autoDetect:true, forceFresh:true})\n"
        "                .catch(function(e) {\n"
        "                    console.debug('USB 拔除後自動恢復 WiFi 清單略過一次:', e);\n"
        "                });\n"
        "        }\n"
        "    }, 120);\n\n"
        "    fetch('/device_disconnected', {",
        1,
    )

    # Freeze the chosen transport as soon as connectDevice() has resolved the
    # selected option.
    page = page.replace(
        "    var selectedDeviceConnType = selectedDeviceConnectionType;\n"
        "    var selectedDeviceCountry = selectedOptionValue.userLocale;",
        "    var selectedDeviceConnType = selectedDeviceConnectionType;\n"
        "    var selectedDeviceCountry = selectedOptionValue.userLocale;\n\n"
        "    deviceConnectionAttemptInProgress = true;\n"
        "    deviceConnectionAttemptTransport = String(selectedDeviceConnType || '').toUpperCase();\n"
        "    deviceConnectionAttemptUdid = String(selectedDeviceIdentifier || '');",
        1,
    )

    # Always clear the attempt lock when the asynchronous connection request
    # finishes, regardless of success, retryable failure, or modal path.
    page = page.replace(
        "            if (connectButton) {\n"
        "                connectButton.disabled = false;  // 重新啟用連接按鈕\n"
        "            }\n"
        "});\n}",
        "            if (connectButton) {\n"
        "                connectButton.disabled = false;  // 重新啟用連接按鈕\n"
        "            }\n"
        "        })\n"
        "        .finally(function() {\n"
        "            deviceConnectionAttemptInProgress = false;\n"
        "            deviceConnectionAttemptTransport = '';\n"
        "            deviceConnectionAttemptUdid = '';\n"
        "        });\n"
        "}",
        1,
    )

    # Backend: never report a successful WiFi connection until the actual RSD
    # endpoint exists. This prevents "已連接" followed by immediate location
    # failure while the background tunnel is still negotiating.
    main = main.replace(
        "            start_wifi_tunnel_thread()\n\n"
        "            if not check_rsd_data():\n"
        "                logger.error("RSD Data is None, Perhaps the tunnel isn't established")\n"
        "            else:\n"
        "                rsd_data = rsd_host, rsd_port\n"
        "                logger.info(f"RSD Data: {rsd_data}")\n\n"
        "            rsd_data_map.setdefault(udid, {})[connection_type] = {"host": rsd_host, "port": rsd_port}\n"
        "            logger.info(f"Device Connection Map: {rsd_data_map}")\n"
        "            return jsonify({'rsd_data': rsd_data})",
        "            rsd_data = None\n"
        "            rsd_host = None\n"
        "            rsd_port = None\n"
        "            start_wifi_tunnel_thread()\n\n"
        "            if not check_rsd_data():\n"
        "                logger.error("WiFi RSD tunnel did not become ready.")\n"
        "                terminate_tunnel_thread = True\n"
        "                return jsonify({\n"
        "                    'error': 'WiFi Tunnel 建立失敗，尚未建立 RSD。請重新嘗試連線。',\n"
        "                    'connection_retryable': True,\n"
        "                    'connection_type': 'Network'\n"
        "                }), 504\n\n"
        "            rsd_data = rsd_host, rsd_port\n"
        "            logger.info(f"WiFi RSD Data ready: {rsd_data}")\n\n"
        "            rsd_data_map.setdefault(udid, {})[connection_type] = {\n"
        "                "host": rsd_host,\n"
        "                "port": rsd_port\n"
        "            }\n"
        "            logger.info(f"Device Connection Map: {rsd_data_map}")\n"
        "            return jsonify({\n"
        "                'rsd_data': rsd_data,\n"
        "                'connection_type': 'Network'\n"
        "            })",
        1,
    )

    main = main.replace(
        "def check_rsd_data():\n    max_attempts = 30",
        "def check_rsd_data():\n    # Wait for the real tunnel endpoint, not just the background thread start.\n    max_attempts = 45",
        1,
    )

    MAIN.write_text(main, encoding="utf-8")
    MAP.write_text(page, encoding="utf-8")

    # Static verification before build.
    if "getattr(device, 'paired', None)" in main:
        raise RuntimeError("Known WiFi parser error remains")
    if "pair_records=home" in main or "pair_records=get_home_folder()" in main:
        raise RuntimeError("WiFi connection still has a hard-coded pairing override")
    if "usbDefault" not in page:
        raise RuntimeError("USB default selection patch missing")
    if "Remove only USB. WiFi remains visible." not in page:
        raise RuntimeError("USB/WiFi coexistence patch missing")

    run([sys.executable, "-m", "py_compile", str(MAIN)])


def build_exe() -> None:
    run([
        sys.executable, "-m", "pip", "install",
        "-r", str(BUILD / "requirements-build.txt")
    ])
    run([sys.executable, "-m", "pip", "install", "pefile"])

    run([
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name", FINAL_EXE_NAME,
        "--icon", str(ICON),
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
        raise RuntimeError("Expected EXE was not produced")

    final = OUT / built.name
    shutil.copy2(built, final)

    digest = hashlib.sha256(final.read_bytes()).hexdigest()
    (OUT / f"{final.name}.sha256").write_text(digest + "\n", encoding="ascii")

    (OUT / "README-WiFi-Test.txt").write_text(
        f"""DPort Windows WiFi Test 6.9.1
Base: Release v6.9.1
Executable: {final.name}

USB:
- USB is the default selection.
- WiFi remains visible while USB is connected.
- USB is re-detected after a cable replug.
- No incomplete "iOS: ?" entry is created from USB presence alone.

WiFi:
- mobdev2 Bonjour discovery
- CoreDeviceProxy TCP primary path
- RemotePairing fallback
- WiFi location uses the active WiFi RSD path instead of usbmux

Icon:
- DPort-6.9.0.ico embedded explicitly.

Research/test build only.
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    # Define after functions are declared so StrictMode is irrelevant here.
    VERSION_FILE = BUILD / "src" / "dport_version.py"
    MAIN = BUILD / "src" / "main.py"
    MAP = BUILD / "src" / "templates" / "map.html"
    ICON = BUILD / "DPort-6.9.0.ico"

    build_source()
    build_exe()
    print(f"BUILD SUCCESS: {OUT / (FINAL_EXE_NAME + '.exe')}")
