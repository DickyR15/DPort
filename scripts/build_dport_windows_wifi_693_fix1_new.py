#!/usr/bin/env python3
from __future__ import annotations
import hashlib, os, shutil, subprocess, sys, tarfile, tempfile
from pathlib import Path

TAG = "v6.9.3"
VERSION = "6.9.3"
FINAL_EXE_NAME = "DPort-WiFi-Test-6.9.3-FIX1"
ROOT = Path.cwd()
WORK = Path(tempfile.gettempdir()) / "DPort-WiFi-693-FIX1"
SOURCE = WORK / "source"
BUILD = WORK / "build"
ARCHIVE = WORK / "source.tar"
OUT = ROOT / "DPort-WiFi-Test-6.9.3"

MAIN = BUILD / "src" / "main.py"
MAP = BUILD / "src" / "templates" / "map.html"
VERSION_FILE = BUILD / "src" / "dport_version.py"
ICON = next((p for p in SOURCE.glob("DPort-*.ico")), None)

def run(cmd, cwd=None):
    print("+", " ".join(map(str, cmd)))
    p = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    if p.stdout: print(p.stdout)
    if p.stderr: print(p.stderr, file=sys.stderr)
    if p.returncode:
        raise RuntimeError(f"Command failed ({p.returncode}): {' '.join(map(str, cmd))}")
    return p.stdout

def build_source():
    if WORK.exists(): shutil.rmtree(WORK)
    if OUT.exists(): shutil.rmtree(OUT)
    SOURCE.mkdir(parents=True); BUILD.mkdir(parents=True); OUT.mkdir(parents=True)

    run(["git","fetch","--tags","--force"])
    run(["git","archive","--format=tar",f"--output={ARCHIVE}",TAG])
    with tarfile.open(ARCHIVE,"r") as tf: tf.extractall(SOURCE)
    shutil.copytree(SOURCE,BUILD,dirs_exist_ok=True)

    if not VERSION_FILE.exists() or "6.9.3" not in VERSION_FILE.read_text(encoding="utf-8"):
        raise RuntimeError("Not DPort 6.9.3")
    if not MAIN.exists() or not MAP.exists(): raise RuntimeError("Missing required source")
    main = MAIN.read_text(encoding="utf-8-sig")
    page = MAP.read_text(encoding="utf-8-sig")

    # Enable the existing 6.9.3 Network/Wi-Fi connect path.
    gate = '''    if connection_type != "USB":
        logger.warning(f"USB-ONLY build: rejecting non-USB connection type: {connection_type}")
        return jsonify({"error": "USB-only mode: please connect the Apple device by USB."}), 400
'''
    if gate not in main: raise RuntimeError("6.9.3 USB-only gate not found")
    main = main.replace(gate, "", 1)

    # WiFi tunnel service switch used by CoreDeviceProxy on Windows.
    tunnel_import_anchor = "from pymobiledevice3.remote.userspace_tunnel import UserspaceRsdTunnel"
    if "import pymobiledevice3.remote.tunnel_service as tunnel_service" not in main:
        if tunnel_import_anchor not in main:
            raise RuntimeError("WiFi tunnel_service import anchor not found")
        main = main.replace(
            tunnel_import_anchor,
            tunnel_import_anchor + "\nimport pymobiledevice3.remote.tunnel_service as tunnel_service",
            1,
        )

    # Force CoreDeviceProxy to use the TCP tunnel path on Windows.
    main = main.replace(
        "        service = await CoreDeviceTunnelProxy.create(lockdown)\n        async with service.start_tcp_tunnel() as tunnel_result:",
        "        service = await CoreDeviceTunnelProxy.create(lockdown)\n        tunnel_service.USE_USERSPACE_TUNNEL = False\n        async with service.start_tcp_tunnel() as tunnel_result:",
        1,
    )

    # 6.9.3 Wi-Fi discovery: replace only the nested collect_devices()
    # function with a concurrent USB + mobdev2 implementation. This avoids the
    # slow sequential Wi-Fi scan while preserving the clean 6.9.3 source.
    collect_start = main.find("        async def collect_devices():")
    collect_end = main.find("        asyncio.run(collect_devices())", collect_start)
    if collect_start < 0 or collect_end < 0:
        raise RuntimeError("6.9.3 collect_devices markers not found")
    collect_end += len("        asyncio.run(collect_devices())")
    collect_function = '''        async def collect_devices():
            async def collect_usb_devices():
                try:
                    usb_devices = []
                    attempts = 6 if force_refresh else 1
                    for attempt in range(attempts):
                        try:
                            usb_devices = await list_devices()
                        except Exception as exc:
                            logger.warning(f"USB enumeration attempt {attempt + 1}/{attempts} failed: {exc}")
                            usb_devices = []
                        if usb_devices:
                            break
                        if attempt + 1 < attempts:
                            await asyncio.sleep(0.35)

                    for device in usb_devices:
                        try:
                            client = await create_using_usbmux(
                                serial=device.serial,
                                connection_type=device.connection_type,
                                autopair=True,
                            )
                            try:
                                info = dict(client.short_info)
                                info["ConnectionType"] = device.connection_type
                                info["Identifier"] = info.get("Identifier") or device.serial
                                info["wifiAddress"] = None
                                info["wifiPort"] = None
                                try:
                                    info["wifiState"] = await client.get_enable_wifi_connections()
                                except Exception:
                                    info["wifiState"] = False
                                try:
                                    info["userLocale"] = get_user_country()
                                except Exception:
                                    info["userLocale"] = None
                                add_device(device.serial, device.connection_type, info)
                            finally:
                                await client.close()
                        except Exception as exc:
                            logger.warning(f"USB device info failed: {exc}")
                            identifier = getattr(device, "serial", None)
                            if identifier:
                                add_device(
                                    identifier,
                                    getattr(device, "connection_type", "USB") or "USB",
                                    {
                                        "Identifier": identifier,
                                        "ConnectionType": "USB",
                                        "DeviceName": "Apple 裝置",
                                        "DeviceClass": "Apple 裝置",
                                        "ProductVersion": "?",
                                        "wifiAddress": None,
                                        "wifiPort": None,
                                        "wifiState": False,
                                        "userLocale": None,
                                    },
                                )
                except Exception as exc:
                    logger.warning(f"USB enumeration failed: {exc}")

            async def collect_wifi_devices():
                try:
                    wifi_count = 0
                    async for ip, network_device in get_mobdev2_lockdowns(
                        udid=None,
                        pair_records=get_home_folder(),
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
                        finally:
                            try:
                                await network_device.close()
                            except Exception:
                                pass
                    logger.info(f"WiFi device-list count: {wifi_count}")
                except Exception as exc:
                    logger.exception(f"WiFi discovery failed: {exc}")

            await asyncio.gather(
                collect_usb_devices(),
                collect_wifi_devices(),
            )
'''
    main = main[:collect_start] + collect_function + main[collect_end:]
    
    # Fix the 6.9.3 get_wifi_with_retry scope bug: the paired flag is captured
    # inside discover(), then read from the returned short-info dictionary.
    main = main.replace(
        'short["_DeviceUDID"] = device.udid or short.get("UniqueDeviceID")',
        'short["_DeviceUDID"] = getattr(device, "udid", None) or short.get("UniqueDeviceID")\n                        short["_Paired"] = bool(getattr(device, "paired", False))',
        1,
    )
    main = main.replace(
        'paired={getattr(device, \'paired\', None)}',
        'paired={short.get("_Paired")}',
        1,
    )
    
    # Frontend: USB and WiFi coexistence.
    ad_start = page.find("async function checkDeviceAutoDetect() {")
    ad_end = page.find("function startDeviceAutoDetect()", ad_start)
    if ad_start < 0 or ad_end < 0:
        raise RuntimeError("6.9.3 could not locate checkDeviceAutoDetect()")

    auto_fix = r'''var dportLastUsbPresent = false;

async function checkDeviceAutoDetect() {
    if (isDeviceConnected || deviceAutoDetectBusy || deviceListManualRefreshInFlight) return;

    var deviceDropdown = document.getElementById('device');
    if (!deviceDropdown) return;

    deviceAutoDetectBusy = true;
    try {
        const presence = await fetchJsonWithTimeout('/usb_presence?_=' + Date.now(), 1500);
        const usbDevices = presence && Array.isArray(presence.devices) ? presence.devices : [];

        const rawIds = usbDevices
            .map(function(device){ return String(device.Identifier || ''); })
            .filter(Boolean)
            .sort();

        const usbJustInserted = !dportLastUsbPresent && rawIds.length > 0;
        dportLastUsbPresent = rawIds.length > 0;

        const displayedUsbIds = Array.from(deviceDropdown.options)
            .map(function(option){
                try {
                    const info = JSON.parse(option.value || '{}');
                    const type = String(info.ConnectionType || info.connectionType || '').toUpperCase();
                    if (type !== 'USB') return '';
                    return String(info.Identifier || info.UniqueDeviceID || '');
                } catch (e) {
                    return '';
                }
            })
            .filter(Boolean)
            .sort();

        if (rawIds.length > 0) {
            const sameUsb =
                rawIds.length === displayedUsbIds.length &&
                rawIds.every(function(id,index){ return id === displayedUsbIds[index]; });

            if (!sameUsb && Date.now() >= deviceFallbackFullScanNext) {
                deviceFallbackFullScanNext = Date.now() + 700;
                await populateDeviceList({
                    silent: true,
                    autoDetect: true,
                    forceFresh: true
                });
            }

            // Select USB only on the physical insertion edge. Later polling
            // never overrides a user's manual WiFi selection.
            if (usbJustInserted && !isDeviceConnected) {
                const usbOption = Array.from(deviceDropdown.options).find(function(option) {
                    try {
                        const info = JSON.parse(option.value || '{}');
                        return String(info.ConnectionType || info.connectionType || '').toUpperCase() === 'USB';
                    } catch (e) {
                        return false;
                    }
                });
                if (usbOption) {
                    deviceDropdown.value = usbOption.value;
                    deviceDropdown.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }
            return;
        }

        // USB absent: never clear Network/WiFi options. Refresh only if none
        // are currently visible.
        const hasNetworkOption = Array.from(deviceDropdown.options).some(function(option) {
            try {
                const info = JSON.parse(option.value || '{}');
                const type = String(info.ConnectionType || info.connectionType || '').toUpperCase();
                return type === 'NETWORK' || type === 'WIFI' ||
                       !!info.wifiAddress || !!info.wifiPort || !!info.wifiTransport;
            } catch (e) {
                return false;
            }
        });

        if (!hasNetworkOption && Date.now() >= deviceFallbackFullScanNext) {
            deviceFallbackFullScanNext = Date.now() + 1800;
            await populateDeviceList({
                silent: true,
                autoDetect: true,
                forceFresh: true
            });
        }
    } catch (e) {
        if (!e || e.name !== 'AbortError') {
            console.debug('自動偵測 USB/WiFi 裝置略過一次:', e);
        }
    } finally {
        deviceAutoDetectBusy = false;
    }
}

'''
page = page[:ad_start] + auto_fix + page[ad_end:]

    # Timeout modal is left unchanged in this build; WiFi discovery/selection is the focus.

    MAIN.write_text(main,encoding="utf-8")
    MAP.write_text(page,encoding="utf-8")

    run([sys.executable,"-m","py_compile",str(MAIN)])

def build_exe():
    run([sys.executable,"-m","pip","install","-r",str(BUILD/"requirements-build.txt")])
    run([sys.executable,"-m","pip","install","pefile","lzfse==0.4.2"])
    icon = next(BUILD.glob("DPort-*.ico"))
    run([sys.executable,"-m","PyInstaller","--noconfirm","--clean","--onefile","--windowed",
         "--name",FINAL_EXE_NAME,"--icon",str(icon),
         "--collect-all","pymobiledevice3","--collect-all","pytun_pmd3","--collect-all","pyimg4","--collect-all","inquirer3",
         "--copy-metadata","pymobiledevice3","--copy-metadata","pyimg4","--copy-metadata","readchar",
         "--hidden-import","pymobiledevice3.remote.userspace_tunnel",
         "--hidden-import","pymobiledevice3.services.dvt.instruments.dvt_provider",
         "--hidden-import","pymobiledevice3.services.dvt.instruments.location_simulation",
         "--hidden-import","pymobiledevice3.usbmux",
         "--hidden-import","dport_release_updater","--hidden-import","dport_version",
         "--add-data",f"src/templates{os.pathsep}templates",
         "--version-file",str(BUILD/"version_info.generated.txt"),str(MAIN)])
    exe = ROOT / "dist" / f"{FINAL_EXE_NAME}.exe"
    if not exe.exists():
        raise RuntimeError(f"Expected built EXE not found: {exe}")
    target = OUT / exe.name
    shutil.copy2(exe, target)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (OUT / f"{exe.name}.sha256").write_text(digest + "  " + exe.name + "\n", encoding="ascii")

def write_version_info():
    p = BUILD/"version_info.generated.txt"
    p.write_text("""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(6,9,3,0),
    prodvers=(6,9,3,0),
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0,0)
  ),
  kids=[StringFileInfo([StringTable('040404B0',[
    StringStruct('CompanyName','Dicky'),
    StringStruct('FileDescription','DPort WiFi Test'),
    StringStruct('FileVersion','6.9.3'),
    StringStruct('InternalName','DPort-WiFi-Test-6.9.3-FIX1'),
    StringStruct('LegalCopyright','Dicky'),
    StringStruct('OriginalFilename','DPort-WiFi-Test-6.9.3-FIX1.exe'),
    StringStruct('ProductName','DPort'),
    StringStruct('ProductVersion','6.9.3'),
    StringStruct('Comments','WiFi Test')
  ])]),
  VarFileInfo([VarStruct('Translation',[0x0404,1200])])]
)
""",encoding="utf-8")

def main():
    build_source()
    write_version_info()
    build_exe()

if __name__ == "__main__":
    main()
