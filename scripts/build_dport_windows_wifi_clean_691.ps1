Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Clean research build:
# DPort Release v6.9.1 -> enable WiFi discovery -> build test EXE.
$Root = $PWD
$Tag = 'v6.9.1'
$Version = '6.9.1'
$Work = Join-Path $env:RUNNER_TEMP 'DPort-WiFi-v691-clean'
$Source = Join-Path $Work 'source'
$Build = Join-Path $Work 'build'
$Tar = Join-Path $Work 'source.tar'

$Out = Join-Path $Root "DPort-WiFi-Test-$Version"
$Exe = Join-Path $Out "DPort-WiFi-Test-$Version.exe"
$Sha = "$Exe.sha256"
$Readme = Join-Path $Out 'README-WiFi-Test.txt'

Write-Host "=== DPort Windows WiFi Test ==="
Write-Host "Base release: $Tag"

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
    if (-not (Test-Path $p)) { throw "Required v6.9.1 file missing: $p" }
}

$VersionSource = Get-Content $VersionPath -Raw
if ($VersionSource -notmatch 'DPORT_VERSION\s*=\s*["'']6\.9\.1["'']') {
    throw 'Source version is not 6.9.1.'
}

$Main = Get-Content $MainPath -Raw
$Map = Get-Content $MapPath -Raw

# ---- Enable WiFi discovery in the clean v6.9.1 source ----
$UsbOnly = @'
            # USB-ONLY: Wi-Fi / Network discovery intentionally disabled.
            logger.info("USB-ONLY mode: Wi-Fi/Bonjour/mDNS/RemotePairing discovery skipped")
'@

$WifiDiscovery = @'
            # Wi-Fi discovery enabled for this research build.
            # Normal Apple Wi-Fi sync uses _apple-mobdev2._tcp (Bonjour/mDNS).
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
                            logger.warning(f"Wi-Fi device found at {ip} without a UDID")
                            continue

                        info["ConnectionType"] = "Network"
                        info["Identifier"] = network_udid
                        info["wifiAddress"] = str(ip)
                        info["wifiPort"] = 62078
                        info["wifiState"] = True
                        info["wifiTransport"] = "mobdev2"

                        add_device(network_udid, "Network", info)
                        wifi_count += 1

                        logger.info(
                            f"Wi-Fi device added: udid={network_udid}, host={ip}, port=62078"
                        )
                    except Exception as exc:
                        logger.warning(f"Wi-Fi metadata failed for {ip}: {exc}")
                    finally:
                        try:
                            await network_device.close()
                        except Exception:
                            pass

                logger.info(f"Wi-Fi device-list count: {wifi_count}")
            except Exception as exc:
                logger.exception(f"Wi-Fi discovery failed: {exc}")
'@

if (-not $Main.Contains($UsbOnly)) {
    throw 'Clean v6.9.1 USB-only discovery block was not found.'
}
$Main = $Main.Replace($UsbOnly,$WifiDiscovery)

# ---- Keep Network/WiFi entries alive when USB watcher sees no cable ----
$OldDisplayed = @'
        const displayedIds = Array.from(deviceDropdown.options)
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
'@

$NewDisplayed = @'
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
                    return String(info.Identifier || '');
                } catch (e) {
                    return '';
                }
            })
            .filter(Boolean)
            .sort();
'@

if (-not $Map.Contains($OldDisplayed)) {
    throw 'Clean v6.9.1 USB watcher block was not found.'
}
$Map = $Map.Replace($OldDisplayed,$NewDisplayed)

$OldEmpty = @'
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
'@

$NewEmpty = @'
        if (rawIds.length === 0) {
            // /usb_presence is USB-only. Do not erase a Network/WiFi option.
            deviceReinsertRetryCount = 0;
            deviceReinsertRetryUntil = 0;
            deviceAutoRefreshSignature = '';
            deviceAutoRefreshScheduled = false;

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
'@

if (-not $Map.Contains($OldEmpty)) {
    throw 'Clean v6.9.1 USB empty-snapshot block was not found.'
}
$Map = $Map.Replace($OldEmpty,$NewEmpty)

# ---- Fix timeout modal flash in the research build ----
$TimeoutOld = '<button type="button" class="btn btn-secondary" data-bs-dismiss="modal" onclick="window.location.href = ''/''">關閉</button>'
$TimeoutNew = '<button type="button" class="btn btn-secondary" data-bs-dismiss="modal">關閉</button>'
if ($Map.Contains($TimeoutOld)) {
    $Map = $Map.Replace($TimeoutOld,$TimeoutNew)
}

Set-Content -LiteralPath $MainPath -Value $Main -Encoding utf8
Set-Content -LiteralPath $MapPath -Value $Map -Encoding utf8

# ---- Verify the patch really exists before compiling ----
$CheckMain = Get-Content $MainPath -Raw
$CheckMap = Get-Content $MapPath -Raw

foreach ($Needle in @(
    'get_mobdev2_lockdowns',
    'ConnectionType"] = "Network"',
    'wifiTransport"] = "mobdev2"',
    'start_wifi_tcp_tunnel',
    'CoreDeviceTunnelProxy'
)) {
    if ($CheckMain -notlike "*$Needle*") {
        throw "WiFi verification failed: $Needle"
    }
}

if ($CheckMain -like '*USB-ONLY: Wi-Fi / Network discovery intentionally disabled*') {
    throw 'USB-only discovery block still exists.'
}

python -m py_compile src\main.py
if ($LASTEXITCODE -ne 0) { throw 'main.py syntax check failed.' }

# ---- Build ----
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
DPort Windows WiFi Research Test $Version

BASE RELEASE:
DPort v$Version
Git tag: $Tag
Git commit: $ReleaseCommit

WiFi:
- Apple mobdev2 / Bonjour discovery
- Network device entries enabled
- iOS 17.4+ CoreDeviceProxy TCP tunnel preserved

This is a research/test build, not a production release.
"@ | Set-Content $Readme -Encoding utf8

Write-Host '=== Build finished ==='
Write-Host "EXE: $Exe"
Write-Host "SHA: $Sha"
