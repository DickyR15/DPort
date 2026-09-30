Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ============================================================================
# DPort WiFi Research Build
# Build trigger: persistent WiFi device-list test
# Build trigger: reconnect pairing-record fix
# BASE = Release v6.9.1
# No previous WiFi test source is used.
# ============================================================================

$Root = $PWD
$Tag = 'v6.9.1'
$Version = '6.9.1'
$Work = Join-Path $env:RUNNER_TEMP 'DPort-WiFi-v691-diagnostic'
$Source = Join-Path $Work 'source'
$Build = Join-Path $Work 'build'
$Tar = Join-Path $Work 'source.tar'
$Out = Join-Path $Root "DPort-WiFi-Test-$Version"
$Exe = Join-Path $Out "DPort-WiFi-Test-$Version.exe"
$Sha = "$Exe.sha256"
$Readme = Join-Path $Out 'README-WiFi-Test.txt'

Write-Host '=== DPort 6.9.1 WiFi Diagnostic Test ==='
Write-Host "BASE: $Tag"

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
if ($LASTEXITCODE -ne 0) { throw 'Unable to export v6.9.1 source.' }

tar -xf "$Tar" -C "$Source"
if ($LASTEXITCODE -ne 0) { throw 'Unable to extract v6.9.1 source.' }

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
# Final combined USB-default + WiFi connection test build.
# Trigger build after repairing WiFi pairing/parser section.
# Preserve WiFi options from the v6.9.1 USB auto-detector.
# /usb_presence reports USB only; an empty USB snapshot must never erase a
# Network/WiFi option that was just discovered by /list_devices.
# ---------------------------------------------------------------------------
$WifiAutoDetectGuard = @'
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

$WifiAutoDetectTail = @'
    } finally {
        deviceAutoDetectBusy = false;
    }
}
'@

if (-not $Map.Contains('async function checkDeviceAutoDetect()')) {
    throw 'v6.9.1 checkDeviceAutoDetect() was not found.'
}

$guardAnchor = @'
    deviceAutoDetectBusy = true;
    try {
'@

if (-not $Map.Contains($guardAnchor)) {
    throw 'v6.9.1 checkDeviceAutoDetect() body anchor was not found.'
}

# Insert a WiFi-preservation guard once, before the USB-only presence call.
# This prevents WiFi entries from disappearing while USB polling is idle.
$Map = $Map.Replace($guardAnchor, $WifiAutoDetectGuard, 1)

# Default the device selector to USB when both USB and WiFi entries exist.
# WiFi remains available as a selectable Network option.
$DefaultUsbSelectionOld = @'
        if (requestSerial !== deviceListRequestSerial) return false;
        deviceDropdown.devicesInfo = devicesInfo;
'@

$DefaultUsbSelectionNew = @'
        if (requestSerial !== deviceListRequestSerial) return false;
        deviceDropdown.devicesInfo = devicesInfo;

        if (!isDeviceConnected && deviceDropdown.options.length > 0) {
            const defaultUsbOption = Array.from(deviceDropdown.options).find(function(option) {
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

            if (defaultUsbOption) {
                deviceDropdown.value = defaultUsbOption.value;
            }
        }
'@

if (-not $Map.Contains($DefaultUsbSelectionOld)) {
    throw 'v6.9.1 device list default-selection anchor was not found.'
}
$Map = $Map.Replace($DefaultUsbSelectionOld, $DefaultUsbSelectionNew, 1)


# ---------------------------------------------------------------------------
# 1. Open Network/WiFi connection path.
# ---------------------------------------------------------------------------
$UsbGate = @'
    if connection_type != "USB":
        logger.warning(f"USB-ONLY build: rejecting non-USB connection type: {connection_type}")
        return jsonify({"error": "USB-only mode: please connect the Apple device by USB."}), 400

'@

if (-not $Main.Contains($UsbGate)) {
    throw 'v6.9.1 USB-only connection gate not found.'
}
$Main = $Main.Replace($UsbGate,'')

# ---------------------------------------------------------------------------
# 2. Enable WiFi discovery in /list_devices.
# ---------------------------------------------------------------------------
$UsbOnlyDiscovery = @'
            # USB-ONLY: Wi-Fi / Network discovery intentionally disabled.
            logger.info("USB-ONLY mode: Wi-Fi/Bonjour/mDNS/RemotePairing discovery skipped")
'@

$WifiDiscovery = @'
            # WiFi discovery enabled for the research build.
            # Uses pymobiledevice3 mobdev2 Bonjour discovery.
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
                            logger.warning(f"WiFi device found at {ip} without UDID")
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
                            "last_seen": time.time()
                        }
                        wifi_count += 1
                        logger.info(
                            f"WiFi device added: udid={network_udid}, host={ip}, port=62078"
                        )
                    except Exception as exc:
                        logger.warning(f"WiFi device metadata failed for {ip}: {exc}")
                    finally:
                        try:
                            await network_device.close()
                        except Exception:
                            pass

                now = time.time()
                for cached_udid, cached in list(wifi_device_cache.items()):
                    try:
                        cached_age = now - float(cached.get("last_seen", 0))
                        if cached_age <= 300 and cached_udid not in connected_devices:
                            cached_info = dict(cached.get("info") or {})
                            cached_info["ConnectionType"] = "Network"
                            add_device(cached_udid, "Network", cached_info)
                            wifi_count += 1
                            logger.info(
                                f"WiFi device restored from cache: udid={cached_udid}, "
                                f"host={cached_info.get('wifiAddress')}"
                            )
                        elif cached_age > 300:
                            wifi_device_cache.pop(cached_udid, None)
                    except Exception as cache_exc:
                        logger.warning(
                            f"WiFi cache restore failed for {cached_udid}: {cache_exc}"
                        )

                logger.info(f"WiFi device-list count: {wifi_count}")
            except Exception as exc:
                logger.exception(f"WiFi discovery failed: {exc}")
'@

if (-not $Main.Contains($UsbOnlyDiscovery)) {
    throw 'v6.9.1 USB-only discovery block not found.'
}
$Main = $Main.Replace($UsbOnlyDiscovery,$WifiDiscovery)

# Ensure ALL extracted v6.9.1 mobdev2 calls use pymobiledevice3's
# default pairing-record search on Windows.
$Main = [regex]::Replace(
    $Main,
    '(?m)^\\s*pair_records\\s*=\\s*(?:get_home_folder\\(\\)|home),\\s*$',
    ''
)

# Fix v6.9.1 get_wifi_with_retry(): the outer loop no longer has
# the inner discovery variable "device" after discover() returns.
$Main = $Main.Replace(
    "paired={getattr(device, 'paired', None)}",
    "paired={short.get('_Paired')}"
)

$Main = $Main.Replace(
    'short["_DeviceUDID"] = device.udid or short.get("UniqueDeviceID")',
    'short["_DeviceUDID"] = device.udid or short.get("UniqueDeviceID")' + [Environment]::NewLine + '                        short["_Paired"] = bool(getattr(device, "paired", False))'
)

# ---------------------------------------------------------------------------
# 4. Add a concrete WiFi tunnel error state.
# ---------------------------------------------------------------------------
$Main = $Main.Replace(
'rsd_port = None
connection_type = None',
'rsd_port = None
wifi_tunnel_error = None
connection_type = None'
)

$Main = $Main.Replace(
@'
def check_rsd_data():
    max_attempts = 30
    attempts = 0
    while attempts < max_attempts:
        if rsd_host is not None and rsd_port is not None:
            return True  # Data is available
        time.sleep(1)
        attempts += 1
    return False  # Data is still None after all attempts
'@,
@'
def check_rsd_data():
    global wifi_tunnel_error
    max_attempts = 120
    attempts = 0
    while attempts < max_attempts:
        if rsd_host is not None and rsd_port is not None:
            return True
        if wifi_tunnel_error:
            return False
        time.sleep(0.25)
        attempts += 1
    return False
'@
)

# Reset the error when a new WiFi connection starts.
$Main = $Main.Replace(
@'
def start_wifi_tunnel_thread():
    global terminate_tunnel_thread
    terminate_tunnel_thread = False  # Set the value of the global variable
    thread = threading.Thread(target=run_wifi_tunnel)
'@,
@'
def start_wifi_tunnel_thread():
    global terminate_tunnel_thread, wifi_tunnel_error
    terminate_tunnel_thread = False
    wifi_tunnel_error = None
    thread = threading.Thread(target=run_wifi_tunnel, name="DPort-WiFi-Tunnel")
'@
)

# ---------------------------------------------------------------------------
# 5. Make connect_wifi return the actual tunnel failure.
# ---------------------------------------------------------------------------
$TimeoutCheckOld = @'
            if not check_rsd_data():
                logger.error("RSD Data is None, Perhaps the tunnel isn't established")
            else:
                rsd_data = rsd_host, rsd_port
                logger.info(f"RSD Data: {rsd_data}")
'@

$TimeoutCheckNew = @'
            if not check_rsd_data():
                detail = wifi_tunnel_error or "WiFi tunnel did not produce RSD host/port."
                logger.error(f"WiFi tunnel failed: {detail}")
                return jsonify({
                    'error': 'WiFi Tunnel Failed',
                    'details': detail,
                    'stage': 'WiFi lockdown / CoreDeviceProxy / TCP tunnel'
                }), 504

            rsd_data = rsd_host, rsd_port
            logger.info(f"RSD Data: {rsd_data}")
'@

if (-not $Main.Contains($TimeoutCheckOld)) {
    throw 'v6.9.1 WiFi connection result block not found.'
}
$Main = $Main.Replace($TimeoutCheckOld,$TimeoutCheckNew)

# ---------------------------------------------------------------------------
# 6. Track exact tunnel stage and preserve the real exception.
# ---------------------------------------------------------------------------
$TunnelHeaderOld = @'
async def start_wifi_tcp_tunnel() -> None:
    """Start the official iOS 17.4+ CoreDeviceProxy TCP tunnel over mobdev2 Wi-Fi."""
    logger.warning("Start Wi-Fi TCP tunnel via mobdev2 + CoreDeviceProxy")
    global terminate_tunnel_thread, rsd_port, rsd_host, wifi_address

    lockdown = None
    service = None
    try:
'@

$TunnelHeaderNew = @'
async def start_wifi_tcp_tunnel() -> None:
    """Start the iOS 17.4+ CoreDeviceProxy TCP tunnel over mobdev2 Wi-Fi."""
    logger.warning("Start Wi-Fi TCP tunnel via mobdev2 + CoreDeviceProxy")
    global terminate_tunnel_thread, rsd_port, rsd_host, wifi_address, wifi_tunnel_error

    lockdown = None
    service = None
    stage = "mobdev2 discovery"
    try:
'@

if (-not $Main.Contains($TunnelHeaderOld)) {
    throw 'v6.9.1 WiFi tunnel function header not found.'
}
$Main = $Main.Replace($TunnelHeaderOld,$TunnelHeaderNew)

$LockdownNoneOld = @'
        if lockdown is None:
            raise RuntimeError(
                f"mobdev2 could not reconnect to the paired Apple device {udid} over Wi-Fi"
            )
'@
$LockdownNoneNew = @'
        if lockdown is None:
            stage = "mobdev2 lockdown"
            raise RuntimeError(
                f"mobdev2 could not reconnect to the paired Apple device {udid} over Wi-Fi"
            )
'@
if (-not $Main.Contains($LockdownNoneOld)) { throw 'v6.9.1 lockdown failure block not found.' }
$Main = $Main.Replace($LockdownNoneOld,$LockdownNoneNew)

$ServiceOld = @'
        service = await CoreDeviceTunnelProxy.create(lockdown)

        async with service.start_tcp_tunnel() as tunnel_result:
'@
$ServiceNew = @'
        stage = "CoreDeviceProxy.create"
        service = await CoreDeviceTunnelProxy.create(lockdown)

        stage = "CoreDeviceProxy.start_tcp_tunnel"
        async with service.start_tcp_tunnel() as tunnel_result:
'@
if (-not $Main.Contains($ServiceOld)) { throw 'v6.9.1 CoreDeviceProxy block not found.' }
$Main = $Main.Replace($ServiceOld,$ServiceNew)

$FinallyOld = @'
    finally:
        resume_remoted_if_required()
'@
$FinallyNew = @'
    except Exception as exc:
        wifi_tunnel_error = f"{stage}: {type(exc).__name__}: {exc}"
        logger.exception(f"WiFi tunnel failed at {wifi_tunnel_error}")
        raise
    finally:
        resume_remoted_if_required()
'@
if (-not $Main.Contains($FinallyOld)) { throw 'v6.9.1 WiFi tunnel finally block not found.' }
$Main = $Main.Replace($FinallyOld,$FinallyNew,1)

$RunWifiOld = @'
def run_wifi_tunnel():
    try:
        if is_major_version_17_or_greater(ios_version) and not version_check(ios_version):
'@
$RunWifiNew = @'
def run_wifi_tunnel():
    global wifi_tunnel_error
    try:
        if is_major_version_17_or_greater(ios_version) and not version_check(ios_version):
'@
if (-not $Main.Contains($RunWifiOld)) { throw 'run_wifi_tunnel header not found.' }
$Main = $Main.Replace($RunWifiOld,$RunWifiNew)

$RunWifiCatchOld = @'
    except Exception as e:
        logger.error(f"Error in run_wifi_tunnel: {e}")
'@
$RunWifiCatchNew = @'
    except Exception as e:
        wifi_tunnel_error = f"run_wifi_tunnel: {type(e).__name__}: {e}"
        logger.exception(f"Error in run_wifi_tunnel: {wifi_tunnel_error}")
'@
if (-not $Main.Contains($RunWifiCatchOld)) { throw 'run_wifi_tunnel exception block not found.' }
$Main = $Main.Replace($RunWifiCatchOld,$RunWifiCatchNew,1)

# ---------------------------------------------------------------------------
# 7. Put a diagnostic log beside the EXE so Windows runtime errors are saved.
# ---------------------------------------------------------------------------
$AppDirAnchor = "app_directory = os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, 'frozen', False) else base_directory"
$LogSetup = @'
app_directory = os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, 'frozen', False) else base_directory

try:
    _dport_log_path = os.path.join(app_directory, "DPort-WiFi-Test-6.9.1.log")
    _dport_file_handler = logging.FileHandler(_dport_log_path, encoding="utf-8")
    _dport_file_handler.setLevel(logging.DEBUG)
    _dport_file_handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s"
    ))
    logger.addHandler(_dport_file_handler)
    logger.info("DPort WiFi diagnostic log initialized: %s", _dport_log_path)
except Exception as _log_exc:
    logger.warning("Unable to initialize WiFi diagnostic log: %s", _log_exc)
'@
if (-not $Main.Contains($AppDirAnchor)) { throw 'app_directory anchor not found.' }
$Main = $Main.Replace($AppDirAnchor,$LogSetup,1)

# ---------------------------------------------------------------------------
# 8. Clean timeout-close behaviour.
# ---------------------------------------------------------------------------
$TimeoutOld = '<button type="button" class="btn btn-secondary" data-bs-dismiss="modal" onclick="window.location.href = ''/''">關閉</button>'
$TimeoutNew = '<button type="button" class="btn btn-secondary" data-bs-dismiss="modal">關閉</button>'
if ($Map.Contains($TimeoutOld)) {
    $Map = $Map.Replace($TimeoutOld,$TimeoutNew)
}

Set-Content -LiteralPath $MainPath -Value $Main -Encoding utf8
Set-Content -LiteralPath $MapPath -Value $Map -Encoding utf8

# ---------------------------------------------------------------------------
# 9. Verify the clean release source plus WiFi changes before build.
# ---------------------------------------------------------------------------
$CheckMain = Get-Content $MainPath -Raw
$CheckMap = Get-Content $MapPath -Raw

foreach ($Needle in @(
    'get_mobdev2_lockdowns',
    'ConnectionType"] = "Network"',
    'wifiTransport"] = "mobdev2"',
    'CoreDeviceTunnelProxy',
    'start_wifi_tcp_tunnel',
    'if connection_type == "Network":',
    'wifi_tunnel_error'
)) {
    if ($CheckMain -notlike "*$Needle*") {
        throw "WiFi build verification failed: $Needle"
    }
}

if ($CheckMain -like '*USB-ONLY: Wi-Fi / Network discovery intentionally disabled*') {
    throw 'USB-only WiFi discovery block still remains.'
}

if ($CheckMain -like '*USB-ONLY build: rejecting non-USB connection type*') {
    throw 'USB-only Network connection gate still remains.'
}

if ($CheckMain -match 'get_wifi_with_retry[\\s\\S]{0,14000}pair_records\\s*=') {
    throw 'get_wifi_with_retry still contains an explicit pair_records override.'
}

if ($CheckMain -match 'start_wifi_tcp_tunnel[\\s\\S]{0,9000}pair_records\\s*=') {
    throw 'start_wifi_tcp_tunnel still contains an explicit pair_records override.'
}

python -m py_compile src\main.py
if ($LASTEXITCODE -ne 0) { throw 'main.py syntax check failed.' }

# ---------------------------------------------------------------------------
# 10. Build.
# ---------------------------------------------------------------------------
python -m pip install --upgrade pip setuptools wheel
if ($LASTEXITCODE -ne 0) { throw 'pip bootstrap failed.' }

python -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Build requirements installation failed.' }

python -m pip install lzfse==0.4.2 pefile
if ($LASTEXITCODE -ne 0) { throw 'Extra build dependencies installation failed.' }

$PyMobileDeviceVersion = (python -c "from importlib.metadata import version; print(version('pymobiledevice3'))").Trim()
Write-Host "pymobiledevice3: $PyMobileDeviceVersion"

if (Test-Path dist) { Remove-Item dist -Recurse -Force }
if (Test-Path build) { Remove-Item build -Recurse -Force }

$args = @(
    '--noconfirm',
    '--clean',
    '--onefile',
    '--windowed',
    '--name',"DPort-WiFi-Test-$Version",
    '--icon',(Join-Path $Build 'DPort-6.9.0.ico'),
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

python -m PyInstaller @args
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed.' }

$Built = Get-ChildItem -Path $Build -Filter "DPort-WiFi-Test-$Version.exe" -File -Recurse | Select-Object -First 1
if (-not $Built) { throw 'Built EXE could not be found.' }

Copy-Item $Built.FullName $Exe -Force
if (-not (Test-Path $Exe)) { throw 'Final EXE copy failed.' }

python -c "import pefile,sys; p=pefile.PE(sys.argv[1]); sys.exit(0 if p.OPTIONAL_HEADER.Subsystem==2 else 1)" $Exe
if ($LASTEXITCODE -ne 0) { throw 'Final EXE is not a Windows GUI executable.' }

(Get-FileHash $Exe -Algorithm SHA256).Hash.ToLower() | Set-Content $Sha -Encoding ascii

@"
DPort Windows WiFi Diagnostic Test 6.9.1

BASE RELEASE:
DPort v6.9.1
Git tag: $Tag
Git commit: $ReleaseCommit

WiFi path:
Apple mobdev2 Bonjour discovery
Network/WiFi connection path
CoreDeviceProxy TCP tunnel

Diagnostic log:
DPort-WiFi-Test-6.9.1.log

Research build only.
"@ | Set-Content $Readme -Encoding utf8

Write-Host '=== BUILD SUCCESS ==='
Write-Host "EXE: $Exe"
Write-Host "SHA: $Sha"

# ---------------------------------------------------------------------------
# 3. Use pymobiledevice3's normal pairing-record search for every WiFi path.
#    The actual v6.9.1 connect path has multiple mobdev2 calls. Remove the
#    hard-coded user-home pairing override so Windows system pairing records
#    can also be discovered.
# ---------------------------------------------------------------------------
$Main = $Main.Replace(
'                    pair_records=home,
',
''
)

$Main = $Main.Replace(
'            pair_records=get_home_folder(),
',
''
)

$Main = $Main.Replace(
'                    pair_records = home,
',
''
)

$Main = $Main.Replace(
'            pair_records = get_home_folder(),
',
''
)

# Fix v6.9.1 get_wifi_with_retry(): the outer loop no longer has
# the inner discovery variable "device" after discover() returns.
$Main = $Main.Replace(
    "paired={getattr(device, 'paired', None)}",
    "paired={short.get('_Paired')}"
)

$Main = $Main.Replace(
    'short["_DeviceUDID"] = device.udid or short.get("UniqueDeviceID")',
    'short["_DeviceUDID"] = device.udid or short.get("UniqueDeviceID")' + [Environment]::NewLine + '                        short["_Paired"] = bool(getattr(device, "paired", False))'
)

# ---------------------------------------------------------------------------
# 4. Add a concrete WiFi tunnel error state.
# ---------------------------------------------------------------------------
$Main = $Main.Replace(
'rsd_port = None
connection_type = None',
'rsd_port = None
wifi_tunnel_error = None
connection_type = None'
)

$Main = $Main.Replace(
@'
def check_rsd_data():
    max_attempts = 30
    attempts = 0
    while attempts < max_attempts:
        if rsd_host is not None and rsd_port is not None:
            return True  # Data is available
        time.sleep(1)
        attempts += 1
    return False  # Data is still None after all attempts
'@,
@'
def check_rsd_data():
    global wifi_tunnel_error
    max_attempts = 120
    attempts = 0
    while attempts < max_attempts:
        if rsd_host is not None and rsd_port is not None:
            return True
        if wifi_tunnel_error:
            return False
        time.sleep(0.25)
        attempts += 1
    return False
'@
)

# Reset the error when a new WiFi connection starts.
$Main = $Main.Replace(
@'
def start_wifi_tunnel_thread():
    global terminate_tunnel_thread
    terminate_tunnel_thread = False  # Set the value of the global variable
    thread = threading.Thread(target=run_wifi_tunnel)
'@,
@'
def start_wifi_tunnel_thread():
    global terminate_tunnel_thread, wifi_tunnel_error
    terminate_tunnel_thread = False
    wifi_tunnel_error = None
    thread = threading.Thread(target=run_wifi_tunnel, name="DPort-WiFi-Tunnel")
'@
)

# ---------------------------------------------------------------------------
# 5. Make connect_wifi return the actual tunnel failure.
# ---------------------------------------------------------------------------
$TimeoutCheckOld = @'
            if not check_rsd_data():
                logger.error("RSD Data is None, Perhaps the tunnel isn't established")
            else:
                rsd_data = rsd_host, rsd_port
                logger.info(f"RSD Data: {rsd_data}")
'@

$TimeoutCheckNew = @'
            if not check_rsd_data():
                detail = wifi_tunnel_error or "WiFi tunnel did not produce RSD host/port."
                logger.error(f"WiFi tunnel failed: {detail}")
                return jsonify({
                    'error': 'WiFi Tunnel Failed',
                    'details': detail,
                    'stage': 'WiFi lockdown / CoreDeviceProxy / TCP tunnel'
                }), 504

            rsd_data = rsd_host, rsd_port
            logger.info(f"RSD Data: {rsd_data}")
'@

if (-not $Main.Contains($TimeoutCheckOld)) {
    throw 'v6.9.1 WiFi connection result block not found.'
}
$Main = $Main.Replace($TimeoutCheckOld,$TimeoutCheckNew)

# ---------------------------------------------------------------------------
# 6. Track exact tunnel stage and preserve the real exception.
# ---------------------------------------------------------------------------
$TunnelHeaderOld = @'
async def start_wifi_tcp_tunnel() -> None:
    """Start the official iOS 17.4+ CoreDeviceProxy TCP tunnel over mobdev2 Wi-Fi."""
    logger.warning("Start Wi-Fi TCP tunnel via mobdev2 + CoreDeviceProxy")
    global terminate_tunnel_thread, rsd_port, rsd_host, wifi_address

    lockdown = None
    service = None
    try:
'@

$TunnelHeaderNew = @'
async def start_wifi_tcp_tunnel() -> None:
    """Start the iOS 17.4+ CoreDeviceProxy TCP tunnel over mobdev2 Wi-Fi."""
    logger.warning("Start Wi-Fi TCP tunnel via mobdev2 + CoreDeviceProxy")
    global terminate_tunnel_thread, rsd_port, rsd_host, wifi_address, wifi_tunnel_error

    lockdown = None
    service = None
    stage = "mobdev2 discovery"
    try:
'@

if (-not $Main.Contains($TunnelHeaderOld)) {
    throw 'v6.9.1 WiFi tunnel function header not found.'
}
$Main = $Main.Replace($TunnelHeaderOld,$TunnelHeaderNew)

$LockdownNoneOld = @'
        if lockdown is None:
            raise RuntimeError(
                f"mobdev2 could not reconnect to the paired Apple device {udid} over Wi-Fi"
            )
'@
$LockdownNoneNew = @'
        if lockdown is None:
            stage = "mobdev2 lockdown"
            raise RuntimeError(
                f"mobdev2 could not reconnect to the paired Apple device {udid} over Wi-Fi"
            )
'@
if (-not $Main.Contains($LockdownNoneOld)) { throw 'v6.9.1 lockdown failure block not found.' }
$Main = $Main.Replace($LockdownNoneOld,$LockdownNoneNew)

$ServiceOld = @'
        service = await CoreDeviceTunnelProxy.create(lockdown)

        async with service.start_tcp_tunnel() as tunnel_result:
'@
$ServiceNew = @'
        stage = "CoreDeviceProxy.create"
        service = await CoreDeviceTunnelProxy.create(lockdown)

        stage = "CoreDeviceProxy.start_tcp_tunnel"
        async with service.start_tcp_tunnel() as tunnel_result:
'@
if (-not $Main.Contains($ServiceOld)) { throw 'v6.9.1 CoreDeviceProxy block not found.' }
$Main = $Main.Replace($ServiceOld,$ServiceNew)

$FinallyOld = @'
    finally:
        resume_remoted_if_required()
'@
$FinallyNew = @'
    except Exception as exc:
        wifi_tunnel_error = f"{stage}: {type(exc).__name__}: {exc}"
        logger.exception(f"WiFi tunnel failed at {wifi_tunnel_error}")
        raise
    finally:
        resume_remoted_if_required()
'@
if (-not $Main.Contains($FinallyOld)) { throw 'v6.9.1 WiFi tunnel finally block not found.' }
$Main = $Main.Replace($FinallyOld,$FinallyNew,1)

$RunWifiOld = @'
def run_wifi_tunnel():
    try:
        if is_major_version_17_or_greater(ios_version) and not version_check(ios_version):
'@
$RunWifiNew = @'
def run_wifi_tunnel():
    global wifi_tunnel_error
    try:
        if is_major_version_17_or_greater(ios_version) and not version_check(ios_version):
'@
if (-not $Main.Contains($RunWifiOld)) { throw 'run_wifi_tunnel header not found.' }
$Main = $Main.Replace($RunWifiOld,$RunWifiNew)

$RunWifiCatchOld = @'
    except Exception as e:
        logger.error(f"Error in run_wifi_tunnel: {e}")
'@
$RunWifiCatchNew = @'
    except Exception as e:
        wifi_tunnel_error = f"run_wifi_tunnel: {type(e).__name__}: {e}"
        logger.exception(f"Error in run_wifi_tunnel: {wifi_tunnel_error}")
'@
if (-not $Main.Contains($RunWifiCatchOld)) { throw 'run_wifi_tunnel exception block not found.' }
$Main = $Main.Replace($RunWifiCatchOld,$RunWifiCatchNew,1)

# ---------------------------------------------------------------------------
# 7. Put a diagnostic log beside the EXE so Windows runtime errors are saved.
# ---------------------------------------------------------------------------
$AppDirAnchor = "app_directory = os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, 'frozen', False) else base_directory"
$LogSetup = @'
app_directory = os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, 'frozen', False) else base_directory

try:
    _dport_log_path = os.path.join(app_directory, "DPort-WiFi-Test-6.9.1.log")
    _dport_file_handler = logging.FileHandler(_dport_log_path, encoding="utf-8")
    _dport_file_handler.setLevel(logging.DEBUG)
    _dport_file_handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s"
    ))
    logger.addHandler(_dport_file_handler)
    logger.info("DPort WiFi diagnostic log initialized: %s", _dport_log_path)
except Exception as _log_exc:
    logger.warning("Unable to initialize WiFi diagnostic log: %s", _log_exc)
'@
if (-not $Main.Contains($AppDirAnchor)) { throw 'app_directory anchor not found.' }
$Main = $Main.Replace($AppDirAnchor,$LogSetup,1)

# ---------------------------------------------------------------------------
# 8. Clean timeout-close behaviour.
# ---------------------------------------------------------------------------
$TimeoutOld = '<button type="button" class="btn btn-secondary" data-bs-dismiss="modal" onclick="window.location.href = ''/''">關閉</button>'
$TimeoutNew = '<button type="button" class="btn btn-secondary" data-bs-dismiss="modal">關閉</button>'
if ($Map.Contains($TimeoutOld)) {
    $Map = $Map.Replace($TimeoutOld,$TimeoutNew)
}

Set-Content -LiteralPath $MainPath -Value $Main -Encoding utf8
Set-Content -LiteralPath $MapPath -Value $Map -Encoding utf8

# ---------------------------------------------------------------------------
# 9. Verify the clean release source plus WiFi changes before build.
# ---------------------------------------------------------------------------
$CheckMain = Get-Content $MainPath -Raw
$CheckMap = Get-Content $MapPath -Raw

foreach ($Needle in @(
    'get_mobdev2_lockdowns',
    'ConnectionType"] = "Network"',
    'wifiTransport"] = "mobdev2"',
    'CoreDeviceTunnelProxy',
    'start_wifi_tcp_tunnel',
    'if connection_type == "Network":',
    'wifi_tunnel_error'
)) {
    if ($CheckMain -notlike "*$Needle*") {
        throw "WiFi build verification failed: $Needle"
    }
}

if ($CheckMain -like '*USB-ONLY: Wi-Fi / Network discovery intentionally disabled*') {
    throw 'USB-only WiFi discovery block still remains.'
}

if ($CheckMain -like '*USB-ONLY build: rejecting non-USB connection type*') {
    throw 'USB-only Network connection gate still remains.'
}

if ($CheckMain -match 'get_wifi_with_retry[\\s\\S]{0,14000}pair_records\\s*=') {
    throw 'get_wifi_with_retry still contains an explicit pair_records override.'
}

if ($CheckMain -match 'start_wifi_tcp_tunnel[\\s\\S]{0,9000}pair_records\\s*=') {
    throw 'start_wifi_tcp_tunnel still contains an explicit pair_records override.'
}

python -m py_compile src\main.py
if ($LASTEXITCODE -ne 0) { throw 'main.py syntax check failed.' }

# ---------------------------------------------------------------------------
# 10. Build.
# ---------------------------------------------------------------------------
python -m pip install --upgrade pip setuptools wheel
if ($LASTEXITCODE -ne 0) { throw 'pip bootstrap failed.' }

python -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Build requirements installation failed.' }

python -m pip install lzfse==0.4.2 pefile
if ($LASTEXITCODE -ne 0) { throw 'Extra build dependencies installation failed.' }

$PyMobileDeviceVersion = (python -c "from importlib.metadata import version; print(version('pymobiledevice3'))").Trim()
Write-Host "pymobiledevice3: $PyMobileDeviceVersion"

if (Test-Path dist) { Remove-Item dist -Recurse -Force }
if (Test-Path build) { Remove-Item build -Recurse -Force }

$args = @(
    '--noconfirm',
    '--clean',
    '--onefile',
    '--windowed',
    '--name',"DPort-WiFi-Test-$Version",
    '--icon',(Join-Path $Build 'DPort-6.9.0.ico'),
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

python -m PyInstaller @args
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed.' }

$Built = Get-ChildItem -Path $Build -Filter "DPort-WiFi-Test-$Version.exe" -File -Recurse | Select-Object -First 1
if (-not $Built) { throw 'Built EXE could not be found.' }

Copy-Item $Built.FullName $Exe -Force
if (-not (Test-Path $Exe)) { throw 'Final EXE copy failed.' }

python -c "import pefile,sys; p=pefile.PE(sys.argv[1]); sys.exit(0 if p.OPTIONAL_HEADER.Subsystem==2 else 1)" $Exe
if ($LASTEXITCODE -ne 0) { throw 'Final EXE is not a Windows GUI executable.' }

(Get-FileHash $Exe -Algorithm SHA256).Hash.ToLower() | Set-Content $Sha -Encoding ascii

@"
DPort Windows WiFi Diagnostic Test 6.9.1

BASE RELEASE:
DPort v6.9.1
Git tag: $Tag
Git commit: $ReleaseCommit

WiFi path:
Apple mobdev2 Bonjour discovery
Network/WiFi connection path
CoreDeviceProxy TCP tunnel

Diagnostic log:
DPort-WiFi-Test-6.9.1.log

Research build only.
"@ | Set-Content $Readme -Encoding utf8

Write-Host '=== BUILD SUCCESS ==='
Write-Host "EXE: $Exe"
Write-Host "SHA: $Sha"
