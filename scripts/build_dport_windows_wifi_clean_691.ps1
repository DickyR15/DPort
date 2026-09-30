Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# DPort 6.9.1 clean WiFi research build.
# Source baseline is always Release v6.9.1.
# No previous WiFi test source is used.

$Root = $PWD
$Tag = 'v6.9.1'
$Version = '6.9.1'

$Work = Join-Path $env:RUNNER_TEMP 'DPort-WiFi-v691-clean-final'
$Source = Join-Path $Work 'source'
$Build = Join-Path $Work 'build'
$Tar = Join-Path $Work 'source.tar'

$Out = Join-Path $Root "DPort-WiFi-Test-$Version"
$Exe = Join-Path $Out "DPort-WiFi-Test-$Version.exe"
$Sha = "$Exe.sha256"
$Readme = Join-Path $Out 'README-WiFi-Test.txt'

Write-Host '=== DPort 6.9.1 CLEAN WiFi BUILD ==='
Write-Host "BASE RELEASE: $Tag"

if (Test-Path $Work) { Remove-Item $Work -Recurse -Force }
if (Test-Path $Out) { Remove-Item $Out -Recurse -Force }
New-Item -ItemType Directory -Force -Path $Source,$Build,$Out | Out-Null

git fetch --tags --force
if ($LASTEXITCODE -ne 0) { throw 'git fetch tags failed.' }

git rev-parse --verify $Tag
if ($LASTEXITCODE -ne 0) { throw "Git tag $Tag was not found." }

$ReleaseCommit = (git rev-list -n 1 $Tag).Trim()
Write-Host "Release commit: $ReleaseCommit"

git archive --format=tar --output="$Tar" $Tag
if ($LASTEXITCODE -ne 0) { throw 'Unable to export Release v6.9.1.' }

tar -xf "$Tar" -C "$Source"
if ($LASTEXITCODE -ne 0) { throw 'Unable to extract Release v6.9.1.' }

Copy-Item (Join-Path $Source '*') $Build -Recurse -Force
Set-Location $Build

$MainPath = Join-Path $Build 'src\main.py'
$MapPath = Join-Path $Build 'src\templates\map.html'
$VersionPath = Join-Path $Build 'src\dport_version.py'

foreach ($p in @($MainPath,$MapPath,$VersionPath)) {
    if (-not (Test-Path $p)) { throw "Missing v6.9.1 file: $p" }
}

$VersionSource = Get-Content $VersionPath -Raw
if ($VersionSource -notmatch 'DPORT_VERSION\s*=\s*["'']6\.9\.1["'']') {
    throw 'Extracted source is not DPort 6.9.1.'
}

$Main = Get-Content $MainPath -Raw
$Map = Get-Content $MapPath -Raw

# ---------------------------------------------------------------------------
# 1. Server cache for WiFi endpoint
# ---------------------------------------------------------------------------
if (-not $Main.Contains('wifi_device_cache = {}')) {
    $Main = $Main.Replace(
@'
wifi_address = None
wifihost = args.wifihost
'@,
@'
wifi_address = None
wifihost = args.wifihost
wifi_device_cache = {}
'@,
1
    )
}

# ---------------------------------------------------------------------------
# 2. Remove the old USB-only connection gate
# ---------------------------------------------------------------------------
$UsbGate = @'
    if connection_type != "USB":
        logger.warning(f"USB-ONLY build: rejecting non-USB connection type: {connection_type}")
        return jsonify({"error": "USB-only mode: please connect the Apple device by USB."}), 400

'@

if ($Main.Contains($UsbGate)) {
    $Main = $Main.Replace($UsbGate,'')
} else {
    Write-Host 'USB-only connection gate was not present; continuing.'
}

# ---------------------------------------------------------------------------
# 3. Replace the old WiFi-disabled /list_devices section
# ---------------------------------------------------------------------------
$DisabledWifi = @'
            # USB-ONLY: Wi-Fi / Network discovery intentionally disabled.
            logger.info("USB-ONLY mode: Wi-Fi/Bonjour/mDNS/RemotePairing discovery skipped")
'@

$WifiBlock = @'
            # WiFi discovery enabled for the clean v6.9.1 research build.
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
                            logger.warning(f"WiFi device at {ip} has no UDID")
                            continue

                        info["ConnectionType"] = "Network"
                        info["Identifier"] = network_udid
                        info["wifiAddress"] = str(ip)
                        info["wifiPort"] = 62078
                        info["wifiState"] = True
                        info["wifiTransport"] = "mobdev2"

                        add_device(network_udid, "Network", info)

                        wifi_device_cache[network_udid] = {
                            "info": dict(info),
                            "last_seen": time.time(),
                        }

                        wifi_count += 1
                        logger.info(
                            f"WiFi device added: udid={network_udid}, "
                            f"host={ip}, port=62078"
                        )
                    except Exception as exc:
                        logger.warning(
                            f"WiFi device metadata failed for {ip}: {exc}"
                        )
                    finally:
                        try:
                            await network_device.close()
                        except Exception:
                            pass

                logger.info(f"WiFi device-list live count: {wifi_count}")

                # When USB is active, mobdev2 can be temporarily quiet.
                # Keep the most recently confirmed Network endpoint visible.
                now = time.time()
                for cached_udid, cached in list(wifi_device_cache.items()):
                    try:
                        if now - float(cached.get("last_seen", 0)) <= 1800:
                            if not (
                                cached_udid in connected_devices
                                and "Network" in connected_devices[cached_udid]
                            ):
                                cached_info = dict(cached.get("info") or {})
                                cached_info["ConnectionType"] = "Network"
                                add_device(cached_udid, "Network", cached_info)
                                logger.info(
                                    f"WiFi device restored from cache: "
                                    f"udid={cached_udid}, "
                                    f"host={cached_info.get('wifiAddress')}"
                                )
                        else:
                            wifi_device_cache.pop(cached_udid, None)
                    except Exception as cache_exc:
                        logger.warning(
                            f"WiFi cache restore failed for {cached_udid}: {cache_exc}"
                        )

            except Exception as exc:
                logger.exception(f"WiFi discovery failed: {exc}")
'@

if (-not $Main.Contains($DisabledWifi)) {
    throw 'The clean v6.9.1 WiFi-disabled list_devices block was not found.'
}
$Main = $Main.Replace($DisabledWifi,$WifiBlock)

# ---------------------------------------------------------------------------
# 4. Fix the actual v6.9.1 WiFi reconnect parser error from the user's log
# ---------------------------------------------------------------------------
$Main = $Main.Replace(
    "paired={getattr(device, 'paired', None)}",
    "paired={short.get('_Paired')}"
)

$Main = $Main.Replace(
    'short["_DeviceUDID"] = device.udid or short.get("UniqueDeviceID")',
    'short["_DeviceUDID"] = device.udid or short.get("UniqueDeviceID")' + [Environment]::NewLine + '                        short["_Paired"] = bool(getattr(device, "paired", False))'
)

# ---------------------------------------------------------------------------
# 5. Remove all explicit home-only pairing overrides
# ---------------------------------------------------------------------------
$Main = [regex]::Replace(
    $Main,
    '(?m)^\s*pair_records\s*=\s*(?:get_home_folder\(\)|home),\s*$',
    ''
)

# ---------------------------------------------------------------------------
# 6. Diagnostic error state for WiFi tunnel
# ---------------------------------------------------------------------------
if (-not $Main.Contains('wifi_tunnel_error = None')) {
    $Main = $Main.Replace(
@'
rsd_port = None
connection_type = None
'@,
@'
rsd_port = None
wifi_tunnel_error = None
connection_type = None
'@,
1
    )
}

$Main = $Main.Replace(
'    except Exception as e:
        logger.error(f"Error in run_wifi_tunnel: {e}")',
'    except Exception as e:
        wifi_tunnel_error = f"run_wifi_tunnel: {type(e).__name__}: {e}"
        logger.exception(f"Error in run_wifi_tunnel: {wifi_tunnel_error}")'
)

# ---------------------------------------------------------------------------
# 7. Frontend: USB remains default, WiFi remains visible
# ---------------------------------------------------------------------------
$AutoDetectAnchor = @'
    deviceAutoDetectBusy = true;
    try {
'@

$AutoDetectGuard = @'
    deviceAutoDetectBusy = true;
    try {
        const hasNetworkEntry = Array.from(deviceDropdown.options).some(function(option){
            try {
                const info = JSON.parse(option.value || '{}');
                const type = String(
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

'@

if (-not $Map.Contains('hasNetworkEntry')) {
    if (-not $Map.Contains($AutoDetectAnchor)) {
        throw 'v6.9.1 USB auto-detect anchor was not found.'
    }
    $Map = $Map.Replace($AutoDetectAnchor,$AutoDetectGuard,1)
}

$DefaultAnchor = @'
        if (requestSerial !== deviceListRequestSerial) return false;
        deviceDropdown.devicesInfo = devicesInfo;
'@

$DefaultPatch = @'
        if (requestSerial !== deviceListRequestSerial) return false;
        deviceDropdown.devicesInfo = devicesInfo;

        if (!isDeviceConnected && deviceDropdown.options.length > 0) {
            const usbDefault = Array.from(deviceDropdown.options).find(function(option){
                try {
                    const info = JSON.parse(option.value || '{}');
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
'@

if (-not $Map.Contains('usbDefault')) {
    if (-not $Map.Contains($DefaultAnchor)) {
        throw 'v6.9.1 device-list default selector anchor was not found.'
    }
    $Map = $Map.Replace($DefaultAnchor,$DefaultPatch,1)
}

$Map = $Map.Replace(
@'
        if (rawIds.length === 0) {
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
'@,
@'
        if (rawIds.length === 0) {
            // USB presence is independent from Network/WiFi presence.
            // Keep WiFi visible while continuing to poll for a later USB replug.
            deviceReinsertRetryCount = 0;
            deviceReinsertRetryUntil = 0;
            deviceAutoRefreshSignature = '';
            deviceAutoRefreshScheduled = false;

            const hasNetworkEntryNow = Array.from(deviceDropdown.options).some(function(option){
                try {
                    const info = JSON.parse(option.value || '{}');
                    const type = String(
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

            if (hasNetworkEntryNow) {
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
        }
'@,
1
)

# ---------------------------------------------------------------------------
# 8. Timeout modal close must not reload the page
# ---------------------------------------------------------------------------
$TimeoutOld = '<button type="button" class="btn btn-secondary" data-bs-dismiss="modal" onclick="window.location.href = ''/''">關閉</button>'
$TimeoutNew = '<button type="button" class="btn btn-secondary" data-bs-dismiss="modal">關閉</button>'
$Map = $Map.Replace($TimeoutOld,$TimeoutNew)

# ---------------------------------------------------------------------------
# 9. Add runtime diagnostic log
# ---------------------------------------------------------------------------
$LogAnchor = "app_directory = os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, 'frozen', False) else base_directory"
if (-not $Main.Contains('DPort WiFi diagnostic logging initialized.')) {
    $LogBlock = @'
app_directory = os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, 'frozen', False) else base_directory

try:
    _dport_wifi_log_path = os.path.join(app_directory, "DPort-WiFi-Test-6.9.1.log")
    _dport_wifi_handler = logging.FileHandler(_dport_wifi_log_path, encoding="utf-8")
    _dport_wifi_handler.setLevel(logging.DEBUG)
    _dport_wifi_handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s"
    ))
    logger.addHandler(_dport_wifi_handler)
    logger.info("DPort WiFi diagnostic logging initialized.")
except Exception as _log_exc:
    logger.warning("WiFi diagnostic log initialization failed: %s", _log_exc)
'@
    if (-not $Main.Contains($LogAnchor)) {
        throw 'app_directory anchor was not found.'
    }
    $Main = $Main.Replace($LogAnchor,$LogBlock,1)
}

# ---------------------------------------------------------------------------
# FINAL UI FIX: USB + WiFi coexistence across unplug/replug
# ---------------------------------------------------------------------------

# Preserve Network/WiFi entries when populateDeviceList replaces the selector.
$Map = [regex]::Replace(
    $Map,
    '(?s)        deviceDropdown\.innerHTML = '''';\s*        connectionDropdown\.innerHTML = '''';\s*        const seenDeviceOptions = new Set\(\);',
@'
        const __dportPreservedNetwork = [];
        Array.from(deviceDropdown.options).forEach(function(option){
            try {
                const info = JSON.parse(option.value || '{}');
                const type = String(
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
                    __dportPreservedNetwork.push(info);
                }
            } catch (e) {}
        });

        deviceDropdown.innerHTML = '';
        connectionDropdown.innerHTML = '';
        const seenDeviceOptions = new Set();
'@,
    1
)

# Re-add preserved Network/WiFi options after a fresh USB scan.
$Map = [regex]::Replace(
    $Map,
    '(?s)        if \(requestSerial !== deviceListRequestSerial\) return false;\s*        deviceDropdown\.devicesInfo = devicesInfo;',
@'
        __dportPreservedNetwork.forEach(function(info){
            try {
                const networkUdid = String(
                    info.Identifier ||
                    info.UniqueDeviceID ||
                    ''
                );
                if (!networkUdid) return;

                const alreadyShown = Array.from(deviceDropdown.options).some(function(option){
                    try {
                        const current = JSON.parse(option.value || '{}');
                        const type = String(
                            current.ConnectionType ||
                            current.connectionType ||
                            current.wifiTransport ||
                            ''
                        ).toUpperCase();

                        return (
                            (
                                type === 'NETWORK' ||
                                type === 'WIFI' ||
                                !!current.wifiAddress ||
                                !!current.wifiPort ||
                                !!current.wifiTransport
                            ) &&
                            String(
                                current.Identifier ||
                                current.UniqueDeviceID ||
                                ''
                            ) === networkUdid
                        );
                    } catch (e) {
                        return false;
                    }
                });

                if (alreadyShown) return;

                const option = document.createElement('option');
                option.text =
                    'Wi-Fi: ' + (info.DeviceName || 'Apple 裝置') +
                    ' - (' + (info.DeviceClass || 'Apple 裝置') +
                    ' - iOS: ' + (info.ProductVersion || '?') + ')';
                option.value = JSON.stringify(info);
                deviceDropdown.add(option);

                devicesInfo[networkUdid] = devicesInfo[networkUdid] || {};
                devicesInfo[networkUdid].Network = info;
            } catch (e) {
                console.debug('保留 WiFi 項目略過:', e);
            }
        });

        if (requestSerial !== deviceListRequestSerial) return false;
        deviceDropdown.devicesInfo = devicesInfo;
'@,
    1
)

# USB presence comparison must only compare USB entries.
$Map = [regex]::Replace(
    $Map,
    '(?s)        const displayedIds = Array\.from\(deviceDropdown\.options\).*?\.sort\(\);',
@'
        const displayedIds = Array.from(deviceDropdown.options)
            .map(function(option){
                try {
                    const info = JSON.parse(option.value || '{}');
                    const type = String(
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
'@,
    1
)

# USB replug fallback: /usb_presence itself can immediately restore the USB
# option even when the full /list_devices request is still racing usbmuxd.
$Map = [regex]::Replace(
    $Map,
    '(?s)        const sameSet =',
@'
        if (rawIds.length > 0) {
            rawIds.forEach(function(id){
                const alreadyHasUsb = Array.from(deviceDropdown.options).some(function(option){
                    try {
                        const info = JSON.parse(option.value || '{}');
                        return (
                            String(
                                info.ConnectionType ||
                                info.connectionType ||
                                ''
                            ).toUpperCase() === 'USB' &&
                            String(
                                info.Identifier ||
                                info.UniqueDeviceID ||
                                ''
                            ) === id
                        );
                    } catch (e) {
                        return false;
                    }
                });

                if (alreadyHasUsb) return;

                const presenceDevice = usbDevices.find(function(device){
                    return String(device.Identifier || '') === id;
                });

                if (!presenceDevice) return;

                const info = Object.assign({}, presenceDevice, {
                    Identifier: id,
                    ConnectionType: 'USB'
                });

                const option = document.createElement('option');
                option.text =
                    'USB: ' + (info.DeviceName || 'Apple 裝置') +
                    ' - (' + (info.DeviceClass || 'Apple 裝置') +
                    ' - iOS: ' + (info.ProductVersion || '?') + ')';
                option.value = JSON.stringify(info);
                deviceDropdown.add(option);
            });

            if (!isDeviceConnected) {
                const usbDefault = Array.from(deviceDropdown.options).find(function(option){
                    try {
                        const info = JSON.parse(option.value || '{}');
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
        }

        const sameSet =
'@,
    1
)

# When USB disappears, keep WiFi but do not stop future USB polling.
$Map = [regex]::Replace(
    $Map,
    '(?s)        if \(rawIds\.length === 0\) \{.*?^\s*return;\s*\n\s*\}',
@'
        if (rawIds.length === 0) {
            deviceReinsertRetryCount = 0;
            deviceReinsertRetryUntil = 0;
            deviceAutoRefreshSignature = '';
            deviceAutoRefreshScheduled = false;

            const hasNetworkEntryNow = Array.from(deviceDropdown.options).some(function(option){
                try {
                    const info = JSON.parse(option.value || '{}');
                    const type = String(
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

            if (hasNetworkEntryNow) {
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
        }
'@,
    1
)

# ---------------------------------------------------------------------------
# FINAL TEST EXE NAME / ICON
# ---------------------------------------------------------------------------
$FinalExeName = 'DPort-WiFi-Test-6.9.1-USBWiFi'
$BuildIcon = Join-Path $Build 'DPort-6.9.0.ico'
$FinalIcon = Join-Path $Build 'DPort-WiFi-Test.ico'
if (-not (Test-Path $BuildIcon)) {
    throw 'DPort icon source DPort-6.9.0.ico is missing.'
}
Copy-Item $BuildIcon $FinalIcon -Force

$Exe = Join-Path $Out ($FinalExeName + '.exe')
$Sha = $Exe + '.sha256'

# ---------------------------------------------------------------------------

# ===========================================================================
# FINAL VERIFIED TRANSPORT/UI PATCHES
# These replacements are applied to the freshly extracted v6.9.1 source
# immediately before verification and PyInstaller.
# ===========================================================================

# --- Frontend: replace populateDeviceList ---------------------------------
$PopulateStart = $Map.IndexOf('async function populateDeviceList(options) {')
$PopulateEnd = $Map.IndexOf('/* Manual device-list refresh:', $PopulateStart)
if ($PopulateStart -lt 0 -or $PopulateEnd -lt 0) {
    throw 'Unable to locate v6.9.1 populateDeviceList().'
}

$PopulateFunction = @'
async function populateDeviceList(options) {
    options = options || {};
    var silent = !!options.silent;
    var requestSerial = ++deviceListRequestSerial;

    var deviceDropdown = document.getElementById('device');
    var connectionDropdown = document.getElementById('connection');
    if (!deviceDropdown || !connectionDropdown) return false;

    // Preserve a known Network/Wi-Fi option during USB re-enumeration.
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
        const listUrl = options.forceFresh
            ? '/list_devices?force=1&_=' + Date.now()
            : '/list_devices?_=' + Date.now();

        const data = await fetchJsonWithTimeout(
            listUrl,
            options.forceFresh ? 9000 : 7000
        );

        if (!data || requestSerial !== deviceListRequestSerial) {
            return false;
        }

        deviceDropdown.innerHTML = '';
        connectionDropdown.innerHTML = '';

        const seenDeviceOptions = new Set();

        Object.keys(data).forEach(function(udid) {
            var connections = data[udid];
            if (!connections || typeof connections !== 'object') return;

            Object.keys(connections).forEach(function(connectionType) {
                var deviceInfoArray = connections[connectionType];
                if (!Array.isArray(deviceInfoArray)) return;

                deviceInfoArray.forEach(function(deviceInfo) {
                    if (!deviceInfo || typeof deviceInfo !== 'object') return;

                    var key =
                        String(udid) + '|' +
                        String(connectionType) + '|' +
                        String(deviceInfo.Identifier || '') + '|' +
                        String(deviceInfo.wifiAddress || '');

                    if (seenDeviceOptions.has(key)) return;
                    seenDeviceOptions.add(key);

                    var option = document.createElement('option');
                    var displayType =
                        connectionType === 'Network' ? 'Wi-Fi' : connectionType;

                    option.text =
                        displayType + ': ' +
                        (deviceInfo.DeviceName || 'Apple 裝置') +
                        ' - (' +
                        (deviceInfo.DeviceClass || 'Apple 裝置') +
                        ' - iOS: ' +
                        (deviceInfo.ProductVersion || '?') +
                        ')';

                    option.value = JSON.stringify(deviceInfo);
                    devicesInfo[udid] = devicesInfo[udid] || {};
                    devicesInfo[udid][connectionType] = deviceInfo;
                    deviceDropdown.add(option);
                });
            });
        });

        // If this refresh returned only USB, restore the last known Wi-Fi row.
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
                        var current = JSON.parse(option.value || '{}');
                        var currentType = String(
                            current.ConnectionType ||
                            current.connectionType ||
                            current.wifiTransport ||
                            ''
                        ).toUpperCase();

                        return (
                            (
                                currentType === 'NETWORK' ||
                                currentType === 'WIFI' ||
                                !!current.wifiAddress ||
                                !!current.wifiPort ||
                                !!current.wifiTransport
                            ) &&
                            String(
                                current.Identifier ||
                                current.UniqueDeviceID ||
                                ''
                            ) === networkUdid
                        );
                    } catch (e) {
                        return false;
                    }
                });

                if (alreadyThere) return;

                var networkOption = document.createElement('option');
                networkOption.text =
                    'Wi-Fi: ' +
                    (info.DeviceName || 'Apple 裝置') +
                    ' - (' +
                    (info.DeviceClass || 'Apple 裝置') +
                    ' - iOS: ' +
                    (info.ProductVersion || '?') +
                    ')';

                networkOption.value = JSON.stringify(info);
                deviceDropdown.add(networkOption);

                devicesInfo[networkUdid] = devicesInfo[networkUdid] || {};
                devicesInfo[networkUdid].Network = info;
            } catch (e) {
                console.debug('保留 WiFi 裝置略過:', e);
            }
        });

        if (requestSerial !== deviceListRequestSerial) return false;
        deviceDropdown.devicesInfo = devicesInfo;

        // USB is always the default selection when available.
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
                var selectedOption = deviceDropdown.options[deviceDropdown.selectedIndex];
                if (!selectedOption) return;

                try {
                    var info = JSON.parse(selectedOption.value || '{}');
                    selectedOption.value = JSON.stringify(info);
                } catch (e) {
                    console.debug('裝置選項資料解析失敗:', e);
                }
            });

            deviceDropdown.addEventListener('change', function() {
                var connectTextElement = document.getElementById('connectText');
                var connectButton = document.getElementById('connect');

                if (connectButton && connectTextElement) {
                    if (
                        connectTextElement.innerText === "Connected" ||
                        connectTextElement.innerText === "Connect" ||
                        connectTextElement.innerText === "連接裝置"
                    ) {
                        connectButton.disabled = false;
                    }
                }
            });

            deviceDropdown.dataset.geoportHandlersBound = '1';
        }

        if (!isDeviceConnected) {
            if (!deviceAutoDetectTimer) {
                startDeviceAutoDetect();
            }
        } else {
            stopDeviceAutoDetect();
        }

        if (sudo_message && !silent) {
            displayToast(sudo_message);
        }

        return deviceDropdown.options.length > 0;
    } catch (error) {
        if (!silent) {
            console.error('錯誤 fetching device list:', error);
        } else if (!error || error.name !== 'AbortError') {
            console.debug('自動偵測裝置清單暫時無法取得:', error);
        }
        return false;
    }
}
'@;
$Map = $Map.Substring(0,$PopulateStart) + $PopulateFunction + $Map.Substring($PopulateEnd)

# --- Frontend: replace USB auto detector -----------------------------------
$AutoStart = $Map.IndexOf('async function checkDeviceAutoDetect() {')
$AutoEnd = $Map.IndexOf('function startDeviceAutoDetect()', $AutoStart)
if ($AutoStart -lt 0 -or $AutoEnd -lt 0) {
    throw 'Unable to locate v6.9.1 checkDeviceAutoDetect().'
}

$AutoFunction = @'
async function checkDeviceAutoDetect() {
    if (isDeviceConnected || deviceAutoDetectBusy || deviceListManualRefreshInFlight) {
        return;
    }

    var deviceDropdown = document.getElementById('device');
    if (!deviceDropdown) return;

    deviceAutoDetectBusy = true;

    try {
        const presence = await fetchJsonWithTimeout(
            '/usb_presence?_=' + Date.now(),
            1500
        );

        if (!presence || presence.error) {
            if (Date.now() >= deviceFallbackFullScanNext) {
                deviceFallbackFullScanNext = Date.now() + 1200;
                await populateDeviceList({
                    silent: true,
                    autoDetect: true,
                    forceFresh: true
                });
            }
            return;
        }

        const usbDevices = Array.isArray(presence.devices)
            ? presence.devices
            : [];

        const rawIds = usbDevices
            .map(function(device) {
                return String(device.Identifier || '');
            })
            .filter(Boolean)
            .sort();

        const displayedUsbIds = Array.from(deviceDropdown.options)
            .map(function(option) {
                try {
                    const info = JSON.parse(option.value || '{}');
                    const type = String(
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
            var usbMatches =
                rawIds.length === displayedUsbIds.length &&
                rawIds.every(function(id, index) {
                    return id === displayedUsbIds[index];
                });

            // Do NOT build a fake "iOS: ?" option from /usb_presence.
            // Always use the full /list_devices result for complete USB metadata.
            if (!usbMatches && Date.now() >= deviceFallbackFullScanNext) {
                deviceFallbackFullScanNext = Date.now() + 700;

                for (let attempt = 0; attempt < 2; attempt++) {
                    const found = await populateDeviceList({
                        silent: true,
                        autoDetect: true,
                        usbRetry: attempt + 1,
                        forceFresh: true
                    });

                    if (found) {
                        const nowDisplayedUsb = Array.from(deviceDropdown.options)
                            .map(function(option) {
                                try {
                                    const info = JSON.parse(option.value || '{}');
                                    const type = String(
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
                            .filter(Boolean);

                        if (rawIds.every(function(id) {
                            return nowDisplayedUsb.indexOf(id) !== -1;
                        })) {
                            break;
                        }
                    }

                    if (attempt === 0) {
                        await new Promise(function(resolve) {
                            setTimeout(resolve, 250);
                        });
                    }
                }
            }

            // Whenever USB is present, make USB the default. WiFi remains a
            // separate selectable option and is never counted in USB presence.
            var usbDefault = Array.from(deviceDropdown.options).find(function(option) {
                try {
                    const info = JSON.parse(option.value || '{}');
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

        // No USB: remove only USB options. Keep Network/WiFi visible.
        Array.from(deviceDropdown.options).forEach(function(option) {
            try {
                const info = JSON.parse(option.value || '{}');
                const type = String(
                    info.ConnectionType ||
                    info.connectionType ||
                    ''
                ).toUpperCase();

                if (type === 'USB') {
                    option.remove();
                }
            } catch (e) {}
        });

        // If no Network option remains, the list really is empty.
        if (deviceDropdown.options.length === 0) {
            connectionDropdown = document.getElementById('connection');
            if (connectionDropdown) {
                connectionDropdown.innerHTML = '';
                connectionDropdown.value = '';
            }
        }

        deviceAutoRefreshSignature = '';
    } catch (e) {
        if (!e || e.name !== 'AbortError') {
            console.debug('自動偵測 USB 裝置略過一次檢查:', e);
        }
    } finally {
        deviceAutoDetectBusy = false;
    }
}



'@;

$Map = $Map.Substring(0,$AutoStart) + $AutoFunction + $Map.Substring($AutoEnd)

# --- Frontend: replace USB cable removal handler ----------------------------
$RemoveStart = $Map.IndexOf('function handleUsbCableRemoved() {')
$RemoveEnd = $Map.IndexOf('var appVersionNum = "{{ app_version_num }}";', $RemoveStart)
if ($RemoveStart -lt 0 -or $RemoveEnd -lt 0) {
    throw 'Unable to locate v6.9.1 handleUsbCableRemoved().'
}

$RemoveFunction = @'
function handleUsbCableRemoved() {
    stopUsbPresenceMonitor();
    activeUsbUDID = null;
    isDeviceConnected = false;

    if (typeof stopGPXPlaybackForReason === 'function') {
        stopGPXPlaybackForReason("裝置已中斷連接，GPX 軌跡播放已停止。");
    }

    var connectButton = document.getElementById('connect');
    var connectTextElement = document.getElementById('connectText');
    var disconnectButton = document.getElementById('disconnect');
    var deviceDropdown = document.getElementById('device');
    var connectionDropdown = document.getElementById('connection');
    var spinnerElement = document.getElementById('spinner');

    // Remove only USB entries. WiFi remains valid and selectable.
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

    // WiFi remains in the selector. Restart USB polling so a later cable
    // replug causes a complete /list_devices scan and restores USB metadata.
    startDeviceAutoDetect();

    fetch('/device_disconnected', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({})
    }).catch(function(error) {
        console.debug('USB disconnect cleanup skipped:', error);
    });

    displayToast("裝置已中斷連接，WiFi 仍可使用；重新插入 USB 後會自動恢復 USB。");
}

    '@;

$Map = $Map.Substring(0,$RemoveStart) + $RemoveFunction + $Map.Substring($RemoveEnd)

# --- Backend: robust WiFi discovery parser ---------------------------------
$WifiFuncStart = $Main.IndexOf('def get_wifi_with_retry(max_attempts=10):')
$WifiFuncEnd = $Main.IndexOf("@app.route('/stop_tunnel'", $WifiFuncStart)
if ($WifiFuncStart -lt 0 -or $WifiFuncEnd -lt 0) {
    throw 'Unable to locate v6.9.1 get_wifi_with_retry().'
}

$WifiFunction = @'
def get_wifi_with_retry(max_attempts=10):
    """Discover a paired iOS device over Apple mobdev2 Bonjour."""
    global udid, wifi_address, wifi_port, ios_version

    logger.info(
        "Wi-Fi discovery: using Apple mobdev2 Bonjour "
        "(_apple-mobdev2._tcp)"
    )

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
                        short["_Paired"] = bool(
                            getattr(device, "paired", False)
                        )
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

                logger.info(
                    f"Wi-Fi device selected via mobdev2: "
                    f"udid={udid}, host={wifi_address}, port={wifi_port}"
                )

                return {
                    "udid": udid,
                    "hostname": wifi_address,
                    "port": wifi_port,
                }

        except Exception as e:
            logger.warning(
                f"Attempt {attempt}: mobdev2 Wi-Fi discovery error - {e}"
            )

        if not found:
            logger.warning(
                f"Attempt {attempt}: no paired mobdev2 Wi-Fi device found."
            )

        time.sleep(0.5)

    raise RuntimeError(
        "No Wi-Fi device found. Verify Apple Mobile Device Service, "
        "Wi-Fi sync, pairing, same LAN, and Windows Firewall/mDNS."
    )


'@;

$Main = $Main.Substring(0,$WifiFuncStart) + $WifiFunction + $Main.Substring($WifiFuncEnd)

# --- Backend: CoreDeviceProxy WiFi tunnel + RemotePairing fallback ----------
$TunnelStart = $Main.IndexOf('async def start_wifi_tcp_tunnel() -> None:')
$TunnelEnd = $Main.IndexOf('async def start_wifi_quic_tunnel()', $TunnelStart)
if ($TunnelStart -lt 0 -or $TunnelEnd -lt 0) {
    throw 'Unable to locate v6.9.1 start_wifi_tcp_tunnel().'
}

$TunnelFunction = @'
async def start_wifi_tcp_tunnel() -> None:
    """Establish the iOS 17.4+ WiFi RSD tunnel.

    Primary path:
        mobdev2 WiFi lockdown -> CoreDeviceProxy TCP tunnel

    Fallback:
        RemotePairing Bonjour -> TCP tunnel
    """
    global terminate_tunnel_thread, rsd_port, rsd_host, wifi_address

    logger.warning("Start Wi-Fi TCP tunnel via mobdev2 + CoreDeviceProxy")

    # Use the normal CoreDeviceProxy TCP tunnel on Windows. This keeps the
    # resulting TUN interface kernel-routable so the location worker can open
    # a second RSD connection over the active WiFi tunnel.
    import pymobiledevice3.remote.tunnel_service as tunnel_service
    tunnel_service.USE_USERSPACE_TUNNEL = False

    stop_remoted_if_required()

    primary_error = None

    # Primary: normal paired lockdown over mobdev2.
    for attempt in range(1, 3):
        lockdown = None
        service = None

        try:
            async for ip, candidate in get_mobdev2_lockdowns(
                udid=udid,
                only_paired=True,
                timeout=timeout,
            ):
                logger.info(
                    f"mobdev2 tunnel candidate: {ip}, udid={candidate.udid}"
                )
                wifi_address = str(ip)
                lockdown = candidate
                break

            if lockdown is None:
                raise RuntimeError(
                    f"mobdev2 could not find paired device {udid}"
                )

            logger.info(
                f"WiFi CoreDeviceProxy attempt {attempt}/2: creating service"
            )

            service = await CoreDeviceTunnelProxy.create(lockdown)

            async with service.start_tcp_tunnel() as tunnel_result:
                resume_remoted_if_required()

                logger.info(
                    f"WiFi CoreDeviceProxy TCP tunnel established: "
                    f"RSD={tunnel_result.address}:{tunnel_result.port}"
                )

                rsd_host = tunnel_result.address
                rsd_port = str(tunnel_result.port)

                while not terminate_tunnel_thread:
                    await asyncio.sleep(0.5)

                return

        except Exception as e:
            primary_error = e
            logger.exception(
                f"WiFi CoreDeviceProxy attempt {attempt}/2 failed: {type(e).__name__}: {e}"
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

    # Fallback: RemotePairing over Bonjour.
    logger.warning(
        "CoreDeviceProxy WiFi tunnel failed; trying RemotePairing fallback."
    )

    services = []
    try:
        services = await get_remote_pairing_tunnel_services(udid=udid)

        if not services:
            raise RuntimeError(
                "RemotePairing Bonjour found no matching WiFi tunnel service."
            )

        for index, service in enumerate(services, start=1):
            try:
                logger.info(
                    f"RemotePairing WiFi tunnel attempt {index}/{len(services)}"
                )

                async with service.start_tcp_tunnel() as tunnel_result:
                    resume_remoted_if_required()

                    logger.info(
                        f"RemotePairing WiFi TCP tunnel established: "
                        f"RSD={tunnel_result.address}:{tunnel_result.port}"
                    )

                    rsd_host = tunnel_result.address
                    rsd_port = str(tunnel_result.port)

                    while not terminate_tunnel_thread:
                        await asyncio.sleep(0.5)

                    return

            except Exception as fallback_error:
                logger.exception(
                    f"RemotePairing WiFi tunnel attempt failed: "
                    f"{type(fallback_error).__name__}: {fallback_error}"
                )
            finally:
                try:
                    await service.close()
                except Exception:
                    pass

    except Exception as e:
        logger.exception(
            f"RemotePairing WiFi fallback discovery failed: "
            f"{type(e).__name__}: {e}"
        )

    raise RuntimeError(
        "WiFi tunnel could not be established. "
        f"CoreDeviceProxy error: {type(primary_error).__name__ if primary_error else 'unknown'}: "
        f"{primary_error}"
    )


'@;

$Main = $Main.Substring(0,$TunnelStart) + $TunnelFunction + $Main.Substring($TunnelEnd)

# --- Backend: use the already-established WiFi RSD for location ------------
$LocStart = $Main.IndexOf('async def _geoport_location_worker():')
$LocEnd = $Main.IndexOf('def _geoport_location_worker_entry():', $LocStart)
if ($LocStart -lt 0 -or $LocEnd -lt 0) {
    throw 'Unable to locate v6.9.1 location worker.'
}

$LocationFunction = @'
async def _geoport_location_worker():
    global location_worker_stop, location_worker_ready, location_worker_error
    logger.warning("Location worker starting")

    try:
        # WiFi connection already owns the RSD tunnel. Do not fall back to
        # UserspaceRsdTunnel(serial=udid), because that implementation selects
        # usbmux and fails as soon as the USB cable is removed.
        if str(connection_type or '').upper() == 'NETWORK':
            if not rsd_host or not rsd_port:
                raise RuntimeError(
                    "WiFi RSD tunnel is not established; cannot start location simulation."
                )

            logger.info(
                f"Location worker using active WiFi RSD: {rsd_host}:{rsd_port}"
            )

            rsd = RemoteServiceDiscoveryService(
                (str(rsd_host), int(rsd_port)),
                name=f"DPort-WiFi-{udid or 'device'}"
            )
            await rsd.connect()

            try:
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
                                    float(longitude)
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
                                if is_device_locked_error(set_error):
                                    location_worker_error = PASSWORD_PROTECTED_LOCATION_MESSAGE
                                else:
                                    location_worker_error = str(set_error)

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
                            await asyncio.sleep(1.0)
                        except Exception as clear_error:
                            location_worker_error = (
                                PASSWORD_PROTECTED_LOCATION_MESSAGE
                                if is_device_locked_error(clear_error)
                                else str(clear_error)
                            )
                            logger.warning(
                                f"Location clear failed: {location_worker_error}"
                            )
            finally:
                await rsd.close()

        else:
            # Original USB path remains unchanged.
            async with UserspaceRsdTunnel(
                serial=udid,
                autopair=True
            ) as rsd:
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
                                    float(latitude),
                                    float(longitude)
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
                                if is_device_locked_error(set_error):
                                    location_worker_error = PASSWORD_PROTECTED_LOCATION_MESSAGE
                                else:
                                    location_worker_error = str(set_error)

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
                            await asyncio.sleep(1.0)
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
        logger.info("Location worker cancelled")
        if not location_worker_ready.is_set():
            location_worker_error = "Location worker cancelled during initialization"
            location_worker_ready.set()

    except Exception as e:
        error_text = str(e)

        if is_device_locked_error(e):
            location_worker_error = PASSWORD_PROTECTED_LOCATION_MESSAGE
        else:
            location_worker_error = error_text

        logger.exception(
            f"Location worker failed: {location_worker_error}"
        )

        if not location_worker_ready.is_set():
            location_worker_ready.set()

    finally:
        logger.warning("Location worker terminated")


'@;

$Main = $Main.Substring(0,$LocStart) + $LocationFunction + $Main.Substring($LocEnd)

# Finalize globals/imports required by the network tunnel path.
if (-not $Main.Contains('import pymobiledevice3.remote.tunnel_service as tunnel_service')) {
    $ImportAnchor = 'from pymobiledevice3.remote.userspace_tunnel import UserspaceRsdTunnel'
    if (-not $Main.Contains($ImportAnchor)) {
        throw 'UserspaceRsdTunnel import anchor not found.'
    }
    $Main = $Main.Replace(
        $ImportAnchor,
        $ImportAnchor + [Environment]::NewLine +
        'import pymobiledevice3.remote.tunnel_service as tunnel_service',
        1
    )
}

# New executable name prevents Windows from showing the previously cached
# generic icon. Explicitly embed the DPort icon from the v6.9.1 tag.
$FinalExeName = 'DPort-WiFi-Test-6.9.1-USBWiFi-FIX'
$BuildIcon = Join-Path $Build 'DPort-6.9.0.ico'
$FinalIcon = Join-Path $Build 'DPort-WiFi-Test-USBWiFi-FIX.ico'

if (-not (Test-Path $BuildIcon)) {
    throw 'DPort-6.9.0.ico is missing from Release v6.9.1.'
}

Copy-Item $BuildIcon $FinalIcon -Force

$Exe = Join-Path $Out ($FinalExeName + '.exe')
$Sha = $Exe + '.sha256'

# 10. Verify source AFTER every patch and BEFORE PyInstaller
# ---------------------------------------------------------------------------
Set-Content -LiteralPath $MainPath -Value $Main -Encoding utf8
Set-Content -LiteralPath $MapPath -Value $Map -Encoding utf8

$CheckMain = Get-Content $MainPath -Raw
$CheckMap = Get-Content $MapPath -Raw

foreach ($Needle in @(
    'get_mobdev2_lockdowns',
    'wifi_device_cache',
    'CoreDeviceTunnelProxy',
    'start_wifi_tcp_tunnel',
    'wifi_tunnel_error'
)) {
    if ($CheckMain -notlike "*$Needle*") {
        throw "WiFi verification failed: $Needle"
    }
}

if ($CheckMain -match "getattr\(device, 'paired', None\)") {
    throw 'Known WiFi parser bug is still present.'
}

if ($CheckMain -match 'get_wifi_with_retry[\s\S]{0,14000}pair_records\s*=') {
    throw 'get_wifi_with_retry still has a pair_records override.'
}

if ($CheckMain -match 'start_wifi_tcp_tunnel[\s\S]{0,9000}pair_records\s*=') {
    throw 'start_wifi_tcp_tunnel still has a pair_records override.'
}

if ($CheckMain -like '*USB-ONLY build: rejecting non-USB connection type*') {
    throw 'USB-only connection gate is still present.'
}

if ($CheckMain -like '*USB-ONLY: Wi-Fi / Network discovery intentionally disabled*') {
    throw 'USB-only WiFi discovery stub is still present.'
}

if ($CheckMap -notlike '*usbDefault*') {
    throw 'USB default selector patch is missing.'
}

if ($CheckMap -like '*if (hasNetworkEntry) { return; }*') {
    throw 'USB auto-detect is incorrectly stopped by a WiFi entry.'
}

if ($CheckMap -notlike '*hasNetworkEntryNow*') {
    throw 'USB/WiFi coexistence preservation patch is missing.'
}

if ($CheckMap -notlike '*hasNetworkEntry*') {
    throw 'WiFi persistence frontend patch is missing.'
}

if (-not (Test-Path (Join-Path $Build 'DPort-6.9.0.ico'))) {
    throw 'DPort icon file DPort-6.9.0.ico is missing from the v6.9.1 source.'
}

python -m py_compile src\main.py
if ($LASTEXITCODE -ne 0) {
    throw 'main.py syntax check failed.'
}

# ---------------------------------------------------------------------------
# 11. Build only after all source changes are complete
# ---------------------------------------------------------------------------
python -m pip install --upgrade pip setuptools wheel
if ($LASTEXITCODE -ne 0) { throw 'pip bootstrap failed.' }

python -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Build requirements installation failed.' }

python -m pip install lzfse==0.4.2 pefile
if ($LASTEXITCODE -ne 0) { throw 'Extra build dependencies installation failed.' }

$pm3 = (python -c "from importlib.metadata import version; print(version('pymobiledevice3'))").Trim()
Write-Host "pymobiledevice3: $pm3"

if (Test-Path dist) { Remove-Item dist -Recurse -Force }
if (Test-Path build) { Remove-Item build -Recurse -Force }

$PyInstallerArgs = @(
    '--noconfirm',
    '--clean',
    '--onefile',
    '--windowed',
    '--name',$FinalExeName,
    '--icon',$FinalIcon,
    '--collect-all','pymobiledevice3',
    '--collect-all','pytun_pmd3',
    '--collect-all','pyimg4',
    '--collect-all','inquirer3',
    '--copy-metadata','pymobiledevice3',
    '--copy-metadata','pyimg4',
    '--copy-metadata','readchar',
    '--hidden-import','pymobiledevice3.remote.userspace_tunnel',
    '--hidden-import','pymobiledevice3.services.dvt.instruments.dvt_provider',
    '--hidden-import','pymobiledevice3.services.dvt.instruments.location_simulation',
    '--hidden-import','pymobiledevice3.usbmux',
    '--add-data','src/templates;templates',
    'src/main.py'
)

python -m PyInstaller @PyInstallerArgs
if ($LASTEXITCODE -ne 0) {
    throw 'PyInstaller build failed.'
}

$Built = Get-ChildItem -Path $Build -Filter ($FinalExeName + '.exe') -File -Recurse |
    Select-Object -First 1

if (-not $Built) {
    throw 'Built EXE was not found.'
}

Copy-Item $Built.FullName $Exe -Force
if (-not (Test-Path $Exe)) {
    throw 'Final EXE copy failed.'
}

python -c "import pefile,sys; p=pefile.PE(sys.argv[1]); sys.exit(0 if p.OPTIONAL_HEADER.Subsystem==2 else 1)" $Exe
if ($LASTEXITCODE -ne 0) {
    throw 'Final EXE is not a Windows GUI executable.'
}

(Get-FileHash $Exe -Algorithm SHA256).Hash.ToLower() |
    Set-Content $Sha -Encoding ascii

@"
DPort Windows WiFi Test 6.9.1 - USB + WiFi

BASE RELEASE:
DPort v6.9.1
Git tag: $Tag
Git commit: $ReleaseCommit

USB:
USB is the default selection.

WIFI:
WiFi/Network remains visible alongside USB.
WiFi discovery uses mobdev2/Bonjour.
WiFi reconnect uses the v6.9.1 CoreDeviceProxy path.

FIXES:
- WiFi and USB can coexist in the device list.
- USB remains the default option.
- v6.9.1 WiFi parser error is fixed.
- Pairing-record override is removed from WiFi reconnect.
- Diagnostic log is written beside the EXE.

RESEARCH BUILD ONLY.
"@ | Set-Content $Readme -Encoding utf8

Write-Host '=== BUILD SUCCESS ==='
Write-Host "EXE: $Exe"
Write-Host "SHA: $Sha"
