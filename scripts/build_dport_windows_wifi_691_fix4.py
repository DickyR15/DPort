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
FINAL_EXE_NAME = "DPort-WiFi-Test-6.9.1-USBWiFi-FIX4"

ROOT = Path.cwd()
WORK = Path(tempfile.gettempdir()) / "DPort-WiFi-691-CLEAN-FIX4"
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


    # ========================================================================
    # FIX3 FINAL PASS
    # - WiFi auto-appears immediately after USB removal
    # - USB insertion never changes the selected WiFi connection while WiFi
    #   connection is in progress/active
    # - WiFi connect cannot report success unless a real RSD tunnel exists
    # - WiFi location is tied to the active Network RSD
    # - WiFi tunnel follows pymobiledevice3's official WiFi RemotePairing path
    # - test dependency uses pymobiledevice3 11.20.0
    # ========================================================================

    # Use the current pymobiledevice3 release for this research build.
    build_requirements = BUILD / "requirements-build.txt"
    req_text = build_requirements.read_text(encoding="utf-8")
    req_text = re.sub(
        r"(?m)^pymobiledevice3==[0-9.]+$",
        "pymobiledevice3==11.20.0",
        req_text,
        count=1,
    )
    build_requirements.write_text(req_text, encoding="utf-8")

    # --- Backend: USB disconnect must not destroy an active WiFi session -----
    route_start = main.find("@app.route('/device_disconnected', methods=['POST'])")
    route_end = main.find("@app.route('/connect_device', methods=['POST'])", route_start)
    if route_start < 0 or route_end < 0:
        raise RuntimeError("FIX3 could not locate /device_disconnected")

    main = main[:route_start] + r'''@app.route('/device_disconnected', methods=['POST'])
def device_disconnected():
    """Reset stale USB state without destroying an active WiFi session."""
    global rsd_data, rsd_host, rsd_port, lockdown
    global userspace_location_tunnel, connection_type, terminate_tunnel_thread

    logger.info(
        f"Physical USB disconnect detected; current connection_type={connection_type}"
    )

    # A USB cable removal should clear USB state only. If DPort is currently
    # connected through WiFi/Network, that connection must remain untouched.
    if str(connection_type or '').upper() == 'NETWORK':
        logger.info(
            "USB disconnect ignored for active WiFi/Network session; "
            "preserving WiFi RSD state."
        )
        return jsonify({"success": True, "preserved": "Network"})

    try:
        stop_set_location_thread()
    except Exception as exc:
        logger.warning(f"USB disconnect location cleanup failed: {exc}")

    terminate_tunnel_thread = True
    rsd_data = None
    rsd_host = None
    rsd_port = None
    userspace_location_tunnel = None
    lockdown = None
    connection_type = None

    return jsonify({"success": True, "preserved": None})


''' + main[route_end:]

    # --- Backend: WiFi connect must fail when tunnel never became ready ------
    cw_start = main.find("def connect_wifi(data):")
    cw_end = main.find("\n\n\nasync def start_wifi_tcp_tunnel()", cw_start)
    if cw_start < 0 or cw_end < 0:
        raise RuntimeError("FIX3 could not locate connect_wifi()")

    main = main[:cw_start] + r'''def connect_wifi(data):
    try:
        global udid, wifi_address, connection_type, wifi_port
        global ios_version, rsd_data, rsd_host, rsd_port
        global terminate_tunnel_thread

        logger.info(f"Wifi data: {data}")

        udid = data.get('udid', None)
        ios_version = data.get('ios_version')
        connection_type = data.get('connType')

        if data.get('wifiAddress'):
            wifi_address = data.get('wifiAddress')
        if data.get('wifiPort'):
            try:
                wifi_port = int(data.get('wifiPort'))
            except (TypeError, ValueError):
                pass

        if ios_version is None:
            return jsonify({'error': 'No iOS version present'}), 400

        if not is_major_version_17_or_greater(ios_version):
            rsd_data = ios_version, udid
            return jsonify({
                'message': 'iOS version less than 17',
                'rsd_data': rsd_data
            })

        logger.info("iOS 17+ WiFi detected")

        try:
            devices = get_wifi_with_retry()
            logger.info(f"Connect Wifi Devices: {devices}")
        except RuntimeError as exc:
            logger.exception(f"WiFi discovery failed: {exc}")
            return jsonify({
                'error': 'No Devices Found',
                'details': str(exc)
            }), 404

        # A new WiFi connection owns its own tunnel lifecycle.
        terminate_tunnel_thread = False
        rsd_host = None
        rsd_port = None
        rsd_data = None

        start_wifi_tunnel_thread()

        # Never report "connected" with (None, None). Wait for the tunnel
        # thread to publish a real RSD endpoint.
        if not check_rsd_data():
            terminate_tunnel_thread = True
            logger.error(
                "WiFi tunnel did not become ready within the timeout; "
                "returning a real connection error."
            )
            rsd_data_map.setdefault(udid, {}).pop("Network", None)
            return jsonify({
                'error': 'WiFi Tunnel 建立失敗',
                'details': (
                    'WiFi 裝置已找到，但 RSD Tunnel 尚未建立成功。'
                    '請確認 iPhone 與電腦在同一個區域網路後再試。'
                ),
                'connection_retryable': True
            }), 504

        rsd_data = rsd_host, rsd_port
        logger.info(f"WiFi RSD Data: {rsd_data}")

        if not rsd_host or not rsd_port:
            terminate_tunnel_thread = True
            return jsonify({
                'error': 'WiFi RSD Tunnel 無效',
                'connection_retryable': True
            }), 502

        rsd_data_map.setdefault(udid, {})[connection_type] = {
            'host': rsd_host,
            'port': rsd_port
        }

        logger.info(f"WiFi Device Connection Map: {rsd_data_map}")

        return jsonify({
            'rsd_data': rsd_data,
            'connection_type': 'Network',
            'wifi_connected': True
        })

    except Exception as exc:
        logger.exception(f"WiFi connection failed: {type(exc).__name__}: {exc}")
        return jsonify({
            'error': str(exc),
            'connection_retryable': True
        }), 500
    finally:
        logger.warning("Connect WiFi function completed")


''' + main[cw_end:]

    # --- Frontend: persistent connection state --------------------------------
    if "var dportConnectionInProgress = false;" not in page:
        global_anchor = "var marker;"
        if global_anchor not in page:
            raise RuntimeError("FIX3 map global anchor missing")
        page = page.replace(
            global_anchor,
            "var dportConnectionInProgress = false;\n" + global_anchor,
            1,
        )

    # --- Frontend: auto detection must discover WiFi when USB disappears ------
    ad_start = page.find("async function checkDeviceAutoDetect() {")
    ad_end = page.find("function startDeviceAutoDetect()", ad_start)
    if ad_start < 0 or ad_end < 0:
        raise RuntimeError("FIX3 could not locate checkDeviceAutoDetect()")

    auto_fix = r'''async function checkDeviceAutoDetect() {
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

            // USB becomes the default only when DPort is NOT in a WiFi
            // connection transaction. This prevents plugging USB during WiFi
            // connection from switching the user's selected WiFi row.
            if (!dportConnectionInProgress && !isDeviceConnected) {
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

            deviceAutoRefreshSignature = rawIds.join('|');
            return;
        }

        // USB is absent. Keep Network/WiFi rows, and actively refresh the
        // complete device list so WiFi appears without requiring a manual
        // "重新整理" click.
        var hasNetworkOption = Array.from(deviceDropdown.options).some(function(option) {
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

        if (
            (!hasNetworkOption || deviceDropdown.options.length === 0) &&
            Date.now() >= deviceFallbackFullScanNext
        ) {
            deviceFallbackFullScanNext = Date.now() + 1800;

            try {
                await populateDeviceList({
                    silent: true,
                    autoDetect: true,
                    forceFresh: true
                });
            } catch (e) {
                if (!e || e.name !== 'AbortError') {
                    console.debug('WiFi 自動發現略過一次:', e);
                }
            }
        }

    } catch (e) {
        if (!e || e.name !== 'AbortError') {
            console.debug('自動偵測裝置略過一次:', e);
        }
    } finally {
        deviceAutoDetectBusy = false;
    }
}


'''
    page = page[:ad_start] + auto_fix + page[ad_end:]

    # --- Frontend: cable removal triggers immediate WiFi discovery ------------
    rm_start = page.find("function handleUsbCableRemoved() {")
    rm_end = page.find("var appVersionNum =", rm_start)
    if rm_start < 0 or rm_end < 0:
        raise RuntimeError("FIX3 could not locate handleUsbCableRemoved()")

    remove_fix = r'''function handleUsbCableRemoved() {
    stopUsbPresenceMonitor();
    activeUsbUDID = null;
    isDeviceConnected = false;
    dportConnectionInProgress = false;

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
                    ''
                ).toUpperCase();

                if (type === 'USB') {
                    option.remove();
                }
            } catch (e) {}
        });

        if (deviceDropdown.options.length === 0) {
            // WiFi may not have been discovered while USB was present.
            // populateDeviceList() below will add it.
            deviceDropdown.value = '';
        } else {
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

    var refreshButtonAfterUsbRemoval = document.getElementById('refresh-device');
    if (refreshButtonAfterUsbRemoval) {
        refreshButtonAfterUsbRemoval.disabled = false;
        refreshButtonAfterUsbRemoval.removeAttribute('aria-disabled');
    }

    // Immediate full scan: this discovers WiFi without requiring the user
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

    displayToast(
        "USB 已拔除，正在自動搜尋 WiFi 裝置。"
    );
}

    '''
    page = page[:rm_start] + remove_fix + page[rm_end:]

    # --- Frontend: prevent auto-selection changes during connection transaction
    connect_mark = "async function connectDevice() {"
    if connect_mark not in page:
        raise RuntimeError("FIX3 could not locate connectDevice()")
    connect_pos = page.find(connect_mark)
    # Set state after the initial isDeviceConnected guard and before any fetch.
    insert_after = page.find("    if (isDeviceConnected) return;", connect_pos)
    if insert_after < 0:
        raise RuntimeError("FIX3 connectDevice() guard missing")
    insert_after = page.find("\n", insert_after) + 1
    if "    dportConnectionInProgress = true;" not in page[insert_after:insert_after+500]:
        page = page[:insert_after] + "    dportConnectionInProgress = true;\n" + page[insert_after:]

    # Reset the flag on all terminal response branches.
    page = page.replace(
        "        if ('developer_mode_required' in data) {\n            // Display modal informing the user and providing options\n            showModalDeveloperModeRequired();\n            return;\n        }",
        "        if ('developer_mode_required' in data) {\n            dportConnectionInProgress = false;\n            showModalDeveloperModeRequired();\n            return;\n        }",
        1,
    )
    page = page.replace(
        "        if ('錯誤' in data && data.錯誤 === 'No Pair Record Found') {\n            showPairRecordModal();\n            return;\n        }",
        "        if ('錯誤' in data && data.錯誤 === 'No Pair Record Found') {\n            dportConnectionInProgress = false;\n            showPairRecordModal();\n            return;\n        }",
        1,
    )
    page = page.replace(
        "        if ('error' in data) {",
        "        if ('error' in data) {\n            dportConnectionInProgress = false;",
        1,
    )
    page = page.replace(
        "        isDeviceConnected = true;\n        stopDeviceAutoDetect();",
        "        isDeviceConnected = true;\n        dportConnectionInProgress = false;\n        stopDeviceAutoDetect();",
        1,
    )
    page = page.replace(
        "            if (connectButton) {\n                connectButton.disabled = false;  // 重新啟用連接按鈕\n            }\n});",
        "            if (connectButton) {\n                connectButton.disabled = false;  // 重新啟用連接按鈕\n            }\n            dportConnectionInProgress = false;\n});",
        1,
    )

    MAIN.write_text(main, encoding="utf-8")
    MAP.write_text(page, encoding="utf-8")
    MAIN.write_text(main, encoding="utf-8")
    MAP.write_text(page, encoding="utf-8")


    # ========================================================================
    # FIX4 FINAL PASS
    # ========================================================================
    # 1) Device selector remembers the user's explicit transport selection.
    #    USB remains the initial default, but WiFi is never overwritten just
    #    because USB is present.
    populate_anchor = "        deviceDropdown.innerHTML = '';\\n        connectionDropdown.innerHTML = '';"
    selection_capture = """        var __dportSelectedConnectionType = '';
        var __dportSelectedIdentifier = '';
        var __dportSelectedOption = deviceDropdown.options[deviceDropdown.selectedIndex];
        if (__dportSelectedOption) {
            try {
                var __dportSelectedInfo = JSON.parse(__dportSelectedOption.value || '{}');
                __dportSelectedConnectionType = String(
                    __dportSelectedInfo.ConnectionType ||
                    __dportSelectedInfo.connectionType ||
                    __dportSelectedInfo.wifiTransport ||
                    ''
                ).toUpperCase();
                __dportSelectedIdentifier = String(
                    __dportSelectedInfo.Identifier ||
                    __dportSelectedInfo.UniqueDeviceID ||
                    ''
                );
            } catch (e) {}
        }

"""
    if populate_anchor not in page:
        raise RuntimeError("FIX4 cannot locate device list clear point")
    page = page.replace(populate_anchor, selection_capture + populate_anchor, 1)

    selection_restore_anchor = """        // USB is the default when present.
        if (!isDeviceConnected) {
            var usbDefault = Array.from(deviceDropdown.options).find(function(option) {"""
    selection_restore = """        // Restore the transport the user had selected before the scan.
        // This is the key rule: USB is the startup default only; it must not
        // overwrite an explicit WiFi selection.
        var __dportRestoredSelection = false;
        if (__dportSelectedConnectionType && __dportSelectedIdentifier) {
            var __dportSelectedAfterRefresh = Array.from(deviceDropdown.options).find(function(option) {
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
                    return type === __dportSelectedConnectionType &&
                        identifier === __dportSelectedIdentifier;
                } catch (e) {
                    return false;
                }
            });

            if (__dportSelectedAfterRefresh) {
                deviceDropdown.value = __dportSelectedAfterRefresh.value;
                __dportRestoredSelection = true;
            }
        }

        // USB is the default only when there was no valid user selection to restore.
        if (!__dportRestoredSelection && !isDeviceConnected) {
            var usbDefault = Array.from(deviceDropdown.options).find(function(option) {"""
    if selection_restore_anchor not in page:
        raise RuntimeError("FIX4 cannot locate USB default block")
    page=page.replace(selection_restore_anchor,selection_restore,1)

    usb_default_guard = """            if (usbDefault) {
                deviceDropdown.value = usbDefault.value;
            }

            deviceAutoRefreshSignature = rawIds.join('|');"""
    usb_default_guard_new = """            if (
                usbDefault &&
                !__dportSelectedConnectionType ||
                (
                    usbDefault &&
                    __dportSelectedConnectionType === 'USB' &&
                    __dportSelectedIdentifier
                )
            ) {
                deviceDropdown.value = usbDefault.value;
            }

            deviceAutoRefreshSignature = rawIds.join('|');"""
    if usb_default_guard in page:
        page=page.replace(usb_default_guard,usb_default_guard_new,1)

    # 2) Auto detection may refresh while a WiFi selection is visible, but it
    #    cannot force-select USB over that explicit choice.
    ad_start=page.find("async function checkDeviceAutoDetect() {")
    ad_end=page.find("function startDeviceAutoDetect()",ad_start)
    if ad_start<0 or ad_end<0:
        raise RuntimeError("FIX4 cannot locate checkDeviceAutoDetect()")
    auto_fix=page[ad_start:ad_end]
    old_default="""            // USB becomes the default only when DPort is NOT in a WiFi
            // connection transaction. This prevents plugging USB during WiFi
            // connection from switching the user's selected WiFi row.
            if (!dportConnectionInProgress && !isDeviceConnected) {
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
            }"""
    new_default="""            // USB is the startup default only. If the user has explicitly
            // selected WiFi, keep WiFi selected even while USB is plugged in.
            var currentSelectionIsNetwork = false;
            var currentSelection = deviceDropdown.options[deviceDropdown.selectedIndex];
            if (currentSelection) {
                try {
                    var currentInfo = JSON.parse(currentSelection.value || '{}');
                    var currentType = String(
                        currentInfo.ConnectionType ||
                        currentInfo.connectionType ||
                        currentInfo.wifiTransport ||
                        ''
                    ).toUpperCase();
                    currentSelectionIsNetwork =
                        currentType === 'NETWORK' ||
                        currentType === 'WIFI' ||
                        !!currentInfo.wifiAddress ||
                        !!currentInfo.wifiPort ||
                        !!currentInfo.wifiTransport;
                } catch (e) {}
            }

            if (!currentSelectionIsNetwork && !dportConnectionInProgress && !isDeviceConnected) {
                // Only select USB when there is no explicit WiFi selection.
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
            }"""
    if old_default in auto_fix:
        auto_fix=auto_fix.replace(old_default,new_default,1)
        page=page[:ad_start]+auto_fix+page[ad_end:]
    else:
        raise RuntimeError("FIX4 auto USB-default block not found")

    # 3) WiFi connection: use the same RemotePairing WiFi tunnel path as
    #    upstream pymobiledevice3 v11.20.0 instead of CoreDeviceProxy over
    #    mobdev2 lockdown. CoreDeviceTunnelProxy is not the WiFi service path.
    tunnel_start=main.find("async def start_wifi_tcp_tunnel() -> None:")
    tunnel_end=main.find("async def start_wifi_quic_tunnel()",tunnel_start)
    if tunnel_start<0 or tunnel_end<0:
        raise RuntimeError("FIX4 cannot locate start_wifi_tcp_tunnel()")

    official_wifi_tunnel=r'''async def start_wifi_tcp_tunnel() -> None:
    """Start the official pymobiledevice3 WiFi RemotePairing TCP tunnel."""
    global terminate_tunnel_thread, rsd_port, rsd_host, wifi_address

    logger.warning(
        "Start Wi-Fi TCP tunnel via RemotePairing Bonjour "
        "(pymobiledevice3 official WiFi path)"
    )

    # The classic TCP tunnel on Windows uses the kernel TUN device.
    tunnel_service.USE_USERSPACE_TUNNEL = False
    stop_remoted_if_required()

    services = []
    last_error = None

    for discovery_attempt in range(1, 4):
        try:
            services = await get_remote_pairing_tunnel_services(
                udid=udid,
            )

            logger.info(
                f"RemotePairing WiFi tunnel services discovered: "
                f"{len(services)} (attempt {discovery_attempt}/3)"
            )

            if services:
                break

        except Exception as exc:
            last_error = exc
            logger.exception(
                f"RemotePairing WiFi discovery attempt "
                f"{discovery_attempt}/3 failed: {type(exc).__name__}: {exc}"
            )

        if discovery_attempt < 3:
            await asyncio.sleep(1.0)

    if not services:
        raise RuntimeError(
            "RemotePairing WiFi tunnel service not found. "
            f"Last error: {last_error}"
        )

    for index, service in enumerate(services, start=1):
        try:
            logger.info(
                f"Starting RemotePairing WiFi TCP tunnel "
                f"{index}/{len(services)}: {service}"
            )

            async with service.start_tcp_tunnel() as tunnel_result:
                resume_remoted_if_required()

                wifi_address = str(tunnel_result.address)
                rsd_host = str(tunnel_result.address)
                rsd_port = str(tunnel_result.port)

                logger.info(
                    f"WiFi RemotePairing TCP tunnel established: "
                    f"RSD={rsd_host}:{rsd_port}"
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


'''
    main=main[:tunnel_start]+official_wifi_tunnel+main[tunnel_end:]

    # 4) WiFi connect: fail only after the official tunnel path has had time
    #    to establish an RSD endpoint. Never return false-success.
    main=main.replace(
        "def check_rsd_data():\n    max_attempts = 30",
        "def check_rsd_data():\n    # WiFi tunnel discovery + TCP/RSD establishment can take several seconds.\n    max_attempts = 60",
        1,
    )

    # 5) WiFi location: preserve the Network RSD path; never fall back to USB.
    if "Location worker using active WiFi RSD" not in main:
        logger.warning("FIX4: expected WiFi-specific location worker text not found; leaving prior FIX3 worker intact")

    # 6) Add front-end logging so future WiFi failures can be diagnosed even if
    #    no browser console log is captured.
    log_anchor="    console.log('connType: ', selectedDeviceConnectionType);"
    log_patch="""    console.log('connType: ', selectedDeviceConnectionType);
    console.log('[DPort WiFi FIX4] selected transport:', selectedDeviceConnectionType);
    console.log('[DPort WiFi FIX4] selected UDID:', selectedDeviceIdentifier);
    console.log('[DPort WiFi FIX4] wifiAddress:', selectedDeviceWifiAddress);
    console.log('[DPort WiFi FIX4] wifiPort:', selectedDeviceWifiPort);"""
    if log_anchor in page:
        page=page.replace(log_anchor,log_patch,1)

    # 7) Ensure build metadata clearly identifies this test build.
    req_path=BUILD / "requirements-build.txt"
    req=req_path.read_text(encoding="utf-8")
    req=re.sub(r"(?m)^pymobiledevice3==[0-9.]+$","pymobiledevice3==11.20.0",req,count=1)
    req_path.write_text(req,encoding="utf-8")

    # Static guarantees specific to FIX4.
    if "RemotePairing Bonjour" not in main:
        raise RuntimeError("FIX4 official WiFi tunnel implementation missing")
    if "service.start_tcp_tunnel()" not in main:
        raise RuntimeError("FIX4 WiFi TCP tunnel call missing")
    if "currentSelectionIsNetwork" not in page:
        raise RuntimeError("FIX4 WiFi selection guard missing")

    # Static verification before build.
    if "getattr(device, 'paired', None)" in main:
        raise RuntimeError("Known WiFi parser error remains")
    if "pair_records=home" in main or "pair_records=get_home_folder()" in main:
        raise RuntimeError("WiFi connection still has a hard-coded pairing override")
    if "usbDefault" not in page:
        raise RuntimeError("USB default selection patch missing")
    if "USB 已拔除，正在自動搜尋 WiFi 裝置。" not in page:
        raise RuntimeError("USB/WiFi coexistence patch missing")
    if "dportConnectionInProgress" not in page:
        raise RuntimeError("WiFi connection transaction lock missing")
    if "WiFi tunnel did not become ready" not in main:
        raise RuntimeError("WiFi tunnel readiness guard missing")

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
