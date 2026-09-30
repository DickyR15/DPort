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

        if (hasNetworkEntry) {
            return;
        }
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

if ($CheckMap -notlike '*hasNetworkEntry*') {
    throw 'WiFi persistence frontend patch is missing.'
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
    '--name',"DPort-WiFi-Test-$Version",
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

$Built = Get-ChildItem -Path $Build -Filter "DPort-WiFi-Test-$Version.exe" -File -Recurse |
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
DPort Windows WiFi Test 6.9.1

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
