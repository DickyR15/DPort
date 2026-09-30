Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ============================================================================
# DPort Windows WiFi Research Build
# BASE: DPort Release v6.9.1
#
# IMPORTANT:
#   This script is intentionally independent from the previous WiFi test
#   scripts. It extracts the current v6.9.1 release tag and enables only the
#   WiFi discovery/tunnel path inside that release source.
# ============================================================================

$root = $PWD
$tag = 'v6.9.1'
$version = '6.9.1'

$sourceRoot = Join-Path $env:RUNNER_TEMP 'dport-release-v691-source'
$buildRoot = Join-Path $env:RUNNER_TEMP 'dport-release-v691-wifi-build'
$archive = Join-Path $env:RUNNER_TEMP 'dport-v691.tar'

$outDir = Join-Path $root 'dist'
$stageDir = Join-Path $root "DPort-WiFi-Test-$version"
$zipPath = Join-Path $root "DPort-WiFi-Test-$version.zip"
$exePath = Join-Path $outDir "DPort-WiFi-Test-$version.exe"
$shaPath = "$exePath.sha256"

Write-Host '=== DPort Windows WiFi Research Build ==='
Write-Host "Release baseline: DPort $version"

git fetch --tags --force
if ($LASTEXITCODE -ne 0) {
    throw 'Unable to fetch Git tags.'
}

$tagCommit = (git rev-list -n 1 $tag).Trim()
if ([string]::IsNullOrWhiteSpace($tagCommit)) {
    throw "Release tag $tag was not found."
}

Write-Host "Using Git tag $tag at commit $tagCommit"
Write-Host 'No previous WiFi test source is used.'

foreach ($path in @($sourceRoot, $buildRoot)) {
    if (Test-Path $path) {
        Remove-Item $path -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $path | Out-Null
}

foreach ($path in @($archive, $zipPath, $stageDir, $outDir)) {
    if (Test-Path $path) {
        Remove-Item $path -Recurse -Force
    }
}

git archive --format=tar --output="$archive" $tag
if ($LASTEXITCODE -ne 0) {
    throw "Unable to export $tag."
}

tar -xf "$archive" -C "$sourceRoot"
if ($LASTEXITCODE -ne 0) {
    throw 'Unable to extract release source.'
}

Copy-Item (Join-Path $sourceRoot '*') $buildRoot -Recurse -Force
Set-Location $buildRoot

$mainPath = Join-Path $buildRoot 'src\main.py'
$mapPath = Join-Path $buildRoot 'src\templates\map.html'

if (-not (Test-Path $mainPath)) {
    throw 'v6.9.1 src/main.py is missing.'
}
if (-not (Test-Path $mapPath)) {
    throw 'v6.9.1 src/templates/map.html is missing.'
}

$versionSource = Get-Content -LiteralPath 'src\dport_version.py' -Raw
if ($versionSource -notmatch 'DPORT_VERSION\s*=\s*["'']6\.9\.1["'']') {
    throw 'The extracted source is not DPort 6.9.1.'
}

$main = Get-Content -LiteralPath $mainPath -Raw
$map = Get-Content -LiteralPath $mapPath -Raw

# ============================================================================
# 1) Enable WiFi device discovery directly in v6.9.1.
# ============================================================================
$usbOnlyBlock = @'
            # USB-ONLY: Wi-Fi / Network discovery intentionally disabled.
            logger.info("USB-ONLY mode: Wi-Fi/Bonjour/mDNS/RemotePairing discovery skipped")
'@

$wifiDiscoveryBlock = @'
            # Wi-Fi discovery for the research build.
            # Apple normal Wi-Fi sync advertises _apple-mobdev2._tcp.
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
                            logger.warning(
                                f"Wi-Fi device discovered at {ip} but no UDID was available"
                            )
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
                            f"Wi-Fi device added: udid={network_udid}, "
                            f"host={ip}, port=62078"
                        )

                    except Exception as exc:
                        logger.warning(
                            f"Wi-Fi device metadata failed for {ip}: {exc}"
                        )
                    finally:
                        try:
                            await network_device.close()
                        except Exception:
                            pass

                logger.info(f"Wi-Fi device-list count: {wifi_count}")

            except Exception as exc:
                logger.exception(f"Wi-Fi device discovery failed: {exc}")
'@

if (-not $main.Contains($usbOnlyBlock)) {
    throw 'The clean v6.9.1 USB-only discovery block was not found.'
}

$main = $main.Replace($usbOnlyBlock, $wifiDiscoveryBlock)

# ============================================================================
# 2) Keep WiFi devices visible in the existing USB presence watcher.
# ============================================================================
$oldDisplayedIds = @'
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

$newDisplayedIds = @'
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

                    // /usb_presence reports USB only.
                    if (type !== 'USB') return '';

                    return String(info.Identifier || '');
                } catch (e) {
                    return '';
                }
            })
            .filter(Boolean)
            .sort();
'@

if (-not $map.Contains($oldDisplayedIds)) {
    throw 'The clean v6.9.1 USB watcher block was not found.'
}

$map = $map.Replace($oldDisplayedIds, $newDisplayedIds)

# When USB disappears, do not clear a visible Network/WiFi entry.
$oldEmptySnapshot = @'
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

$newEmptySnapshot = @'
        if (rawIds.length === 0) {
            // USB presence is independent from WiFi discovery.
            // An empty USB snapshot must not erase a WiFi/Network device.
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

if (-not $map.Contains($oldEmptySnapshot)) {
    throw 'The clean v6.9.1 USB empty snapshot block was not found.'
}

$map = $map.Replace($oldEmptySnapshot, $newEmptySnapshot)

# ============================================================================
# 3) Fix the timeout modal without changing connection logic.
# ============================================================================
$timeoutOld = '<button type="button" class="btn btn-secondary" data-bs-dismiss="modal" onclick="window.location.href = ''/''">關閉</button>'
$timeoutNew = '<button type="button" class="btn btn-secondary" data-bs-dismiss="modal">關閉</button>'

if ($map.Contains($timeoutOld)) {
    $map = $map.Replace($timeoutOld, $timeoutNew)
}

Set-Content -LiteralPath $mainPath -Value $main -Encoding utf8
Set-Content -LiteralPath $mapPath -Value $map -Encoding utf8

# ============================================================================
# 4) Source-level verification.
# ============================================================================
$finalMain = Get-Content -LiteralPath $mainPath -Raw

foreach ($required in @(
    'get_wifi_with_retry',
    'get_mobdev2_lockdowns',
    'CoreDeviceTunnelProxy',
    'start_wifi_tcp_tunnel',
    'wifihost'
)) {
    if ($finalMain -notlike "*$required*") {
        throw "Required WiFi implementation missing: $required"
    }
}

if ($finalMain -like '*USB-ONLY: Wi-Fi / Network discovery intentionally disabled*') {
    throw 'USB-only WiFi block is still present.'
}

python -m py_compile src\main.py
if ($LASTEXITCODE -ne 0) {
    throw 'main.py syntax check failed.'
}

# ============================================================================
# 5) Build from this release-derived source.
# ============================================================================
python -m pip install --upgrade pip setuptools wheel
if ($LASTEXITCODE -ne 0) { throw 'pip bootstrap failed.' }

python -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Build requirements installation failed.' }

python -m pip install lzfse==0.4.2 pefile
if ($LASTEXITCODE -ne 0) { throw 'Extra dependency installation failed.' }

$pm3 = (python -c "from importlib.metadata import version; print(version('pymobiledevice3'))").Trim()
Write-Host "pymobiledevice3: $pm3"

if (Test-Path 'dist') { Remove-Item 'dist' -Recurse -Force }
if (Test-Path 'build') { Remove-Item 'build' -Recurse -Force }

$args = @(
    '--noconfirm',
    '--clean',
    '--onefile',
    '--windowed',
    '--name',"DPort-WiFi-Test-$version",
    '--icon',(Join-Path $buildRoot 'DPort-6.9.0.ico'),
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
if ($LASTEXITCODE -ne 0) {
    throw 'PyInstaller build failed.'
}

$foundExe = Get-ChildItem -Path $buildRoot -Filter "DPort-WiFi-Test-$version.exe" -File -Recurse |
    Select-Object -First 1

if (-not $foundExe) {
    throw "Unable to locate DPort-WiFi-Test-$version.exe under $buildRoot"
}

New-Item -ItemType Directory -Force -Path $outDir | Out-Null
Copy-Item $foundExe.FullName $exePath -Force

if (-not (Test-Path $exePath)) {
    throw 'Final EXE copy failed.'
}

python -c "import pefile,sys; p=pefile.PE(sys.argv[1]); sys.exit(0 if p.OPTIONAL_HEADER.Subsystem==2 else 1)" $exePath
if ($LASTEXITCODE -ne 0) {
    throw 'Final EXE is not a Windows GUI executable.'
}

(Get-FileHash $exePath -Algorithm SHA256).Hash.ToLower() |
    Set-Content $shaPath -Encoding ascii

New-Item -ItemType Directory -Force -Path $stageDir | Out-Null
Copy-Item $exePath $stageDir -Force
Copy-Item $shaPath $stageDir -Force

@"
DPort Windows WiFi Research Test $version

Base: Release v$version
Git tag commit: $tagCommit
pymobiledevice3: $pm3

WiFi discovery:
  Apple mobdev2 / Bonjour (_apple-mobdev2._tcp)

WiFi transport:
  iOS 17.4+ -> lockdown + CoreDeviceProxy TCP tunnel

This is a research/test build, not a production release.
"@ | Set-Content (Join-Path $stageDir 'README-WiFi-Test.txt') -Encoding utf8

Compress-Archive -Path "$stageDir\*" -DestinationPath $zipPath -Force

if (-not (Test-Path $zipPath)) {
    throw 'Final ZIP was not produced.'
}

Write-Host '=== BUILD SUCCESS ==='
Write-Host "EXE: $exePath"
Write-Host "ZIP: $zipPath"
