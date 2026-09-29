Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = $PWD
$tag = 'v6.9.1'
$version = '6.9.1'
$srcRoot = Join-Path $env:RUNNER_TEMP 'dport-windows-wifi-test-source'
$archive = Join-Path $env:RUNNER_TEMP 'dport-6.9.1.tar'
$buildRoot = Join-Path $env:RUNNER_TEMP 'dport-windows-wifi-build'
$outDir = Join-Path $root 'dist'
$buildOutDir = Join-Path $buildRoot 'dist'
$builtExe = Join-Path $buildOutDir "DPort-WiFi-Test-$version.exe"
$exe = Join-Path $outDir "DPort-WiFi-Test-$version.exe"
$sha = "$exe.sha256"
$stage = Join-Path $root "DPort-WiFi-Test-$version"
$zip = Join-Path $root "DPort-WiFi-Test-$version.zip"

Write-Host "=== DPort Windows WiFi Test ==="
Write-Host "Base: DPort $version"

if ([string]::IsNullOrWhiteSpace($env:MOENV_API_KEY)) {
    throw 'Missing MOENV_API_KEY secret.'
}

git fetch --tags --force
if ($LASTEXITCODE -ne 0) { throw 'Failed to fetch Git tags.' }

git rev-parse --verify $tag
if ($LASTEXITCODE -ne 0) { throw "$tag was not found." }

foreach ($path in @($srcRoot, $buildRoot)) {
    if (Test-Path $path) { Remove-Item $path -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $path | Out-Null
}

if (Test-Path $archive) { Remove-Item $archive -Force }
if (Test-Path $outDir) { Remove-Item $outDir -Recurse -Force }
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
if (Test-Path $zip) { Remove-Item $zip -Force }

git archive --format=tar --output="$archive" $tag
if ($LASTEXITCODE -ne 0) { throw 'Failed to archive DPort 6.9.1.' }

tar -xf "$archive" -C "$srcRoot"
if ($LASTEXITCODE -ne 0) { throw 'Failed to extract DPort 6.9.1 source.' }

if (-not (Test-Path (Join-Path $srcRoot 'src\main.py'))) {
    throw 'DPort 6.9.1 source root is invalid.'
}

Copy-Item (Join-Path $srcRoot '*') $buildRoot -Recurse -Force
Set-Location $buildRoot

$rawVersion = Get-Content -LiteralPath 'src\dport_version.py' -Raw
if ($rawVersion -notmatch 'DPORT_VERSION\s*=\s*["'']6\.9\.1["'']') {
    throw 'Tagged source version is not 6.9.1.'
}

[IO.File]::WriteAllText(
    (Join-Path $buildRoot 'moenv_api_key.txt'),
    $env:MOENV_API_KEY.Trim(),
    (New-Object Text.UTF8Encoding($false))
)

$mainPath = Join-Path $buildRoot 'src\main.py'
$main = Get-Content -LiteralPath $mainPath -Raw
$mapPath = Join-Path $buildRoot 'src\templates\map.html'
if (-not (Test-Path $mapPath)) { throw 'map.html is missing from v6.9.1 source.' }
$map = Get-Content -LiteralPath $mapPath -Raw

# ---------------------------------------------------------------------------
# Enable WiFi device discovery in the v6.9.1 test build.
# The production v6.9.1 source intentionally leaves /list_devices in USB-only
# mode. The WiFi test build enables Apple's paired mobdev2 Bonjour discovery.
# ---------------------------------------------------------------------------
$disabledWifiDiscovery = @'
            # USB-ONLY: Wi-Fi / Network discovery intentionally disabled.
            logger.info("USB-ONLY mode: Wi-Fi/Bonjour/mDNS/RemotePairing discovery skipped")
'@

$enabledWifiDiscovery = @'
            # Wi-Fi discovery through Apple's mobdev2 Bonjour service.
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
'@

if ($main.Contains($disabledWifiDiscovery)) {
    $main = $main.Replace($disabledWifiDiscovery, $enabledWifiDiscovery)
} else {
    throw 'WiFi discovery insertion point was not found in v6.9.1 main.py.'
}

# ---------------------------------------------------------------------------
# Keep WiFi entries visible while the USB-only presence watcher runs.
# The /usb_presence endpoint intentionally reports USB devices only.
# ---------------------------------------------------------------------------
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

                    if (type !== 'USB') return '';
                    return String(info.Identifier || '');
                } catch (e) {
                    return '';
                }
            })
            .filter(Boolean)
            .sort();
'@

if ($map.Contains($oldDisplayedIds)) {
    $map = $map.Replace($oldDisplayedIds, $newDisplayedIds)
} else {
    throw 'USB displayedIds block was not found in v6.9.1 map.html.'
}

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
            // /usb_presence only sees USB. Never clear a currently visible
            // WiFi/Network option just because no USB cable is attached.
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

if ($map.Contains($oldEmptySnapshot)) {
    $map = $map.Replace($oldEmptySnapshot, $newEmptySnapshot)
} else {
    throw 'USB empty-snapshot block was not found in v6.9.1 map.html.'
}

Set-Content -LiteralPath $mapPath -Value $map -Encoding utf8
Set-Content -LiteralPath $mainPath -Value $main -Encoding utf8


# Keep the updater module itself available for compatibility, but disable
# automatic update bootstrap/background checks in this test build.
$main = [regex]::Replace(
    $main,
    '(?m)^bootstrap_dport_updater\(\)\s*\r?\n',
    ''
)

$main = [regex]::Replace(
    $main,
    '(?ms)^try:\s*\r?\n\s+from dport_release_updater import start_background_update_check\s*\r?\n\s+start_background_update_check\(\)\s*\r?\nexcept Exception as exc:\s*\r?\n\s+logging\.getLogger\("DPort"\)\.debug\("pymobiledevice3 updater startup skipped: %s", exc\)\s*\r?\n',
    ''
)

Set-Content -LiteralPath $mainPath -Value $main -Encoding utf8

foreach ($file in @(
    'src\main.py',
    'src\dport_version.py',
    'src\dport_release_updater.py',
    'src\dport_updater_helper.py'
)) {
    if (-not (Test-Path $file)) {
        throw "Required source file is missing: $file"
    }
}

python -m py_compile src\main.py
python -m py_compile src\dport_version.py
python -m py_compile src\dport_release_updater.py
python -m py_compile src\dport_updater_helper.py

python -m pip install --upgrade pip setuptools wheel
if ($LASTEXITCODE -ne 0) { throw 'pip bootstrap failed.' }

python -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Build requirements installation failed.' }

python -m pip install lzfse==0.4.2 pefile
if ($LASTEXITCODE -ne 0) { throw 'Extra dependency installation failed.' }

$pm3 = (python -c "from importlib.metadata import version; print(version('pymobiledevice3'))").Trim()
if ($pm3 -ne '11.19.4') {
    throw "Expected pymobiledevice3 11.19.4, got [$pm3]"
}

$mainCheck = Get-Content -LiteralPath $mainPath -Raw
foreach ($feature in @(
    'get_wifi_with_retry',
    'get_mobdev2_lockdowns',
    'create_using_tcp',
    'CoreDeviceTunnelProxy',
    'wifihost'
)) {
    if ($mainCheck -notlike "*$feature*") {
        throw "Missing WiFi feature: $feature"
    }
}

if ($mainCheck -like '*bootstrap_dport_updater()*' -or
    $mainCheck -like '*start_background_update_check()*') {
    throw 'Automatic updater startup code is still present.'
}

if (Test-Path dist) { Remove-Item dist -Recurse -Force }
if (Test-Path build) { Remove-Item build -Recurse -Force }

New-Item -ItemType Directory -Force -Path $outDir | Out-Null

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
    '--add-data','src/templates;templates',
    '--add-data','moenv_api_key.txt;.',
    'src/main.py'
)

python -m PyInstaller @args
if ($LASTEXITCODE -ne 0) {
    throw 'PyInstaller WiFi test build failed.'
}

# PyInstaller may use a different output directory when the build script
# changes the working directory. Locate the generated EXE explicitly.
$foundExe = Get-ChildItem -Path $buildRoot -Filter "DPort-WiFi-Test-$version.exe" -File -Recurse |
    Select-Object -First 1

if (-not $foundExe) {
    throw "PyInstaller completed but DPort-WiFi-Test-$version.exe could not be located under $buildRoot"
}

New-Item -ItemType Directory -Force -Path $outDir | Out-Null
Copy-Item $foundExe.FullName $exe -Force

if (-not (Test-Path $exe)) {
    throw "Failed to copy built EXE to workspace output: $exe"
}

python -c "import pefile,sys; p=pefile.PE(sys.argv[1]); sys.exit(0 if p.OPTIONAL_HEADER.Subsystem==2 else 1)" $exe
if ($LASTEXITCODE -ne 0) {
    throw 'WiFi test executable is not a Windows GUI executable.'
}

(Get-FileHash $exe -Algorithm SHA256).Hash.ToLower() |
    Set-Content $sha -Encoding ascii

New-Item -ItemType Directory -Force -Path $stage | Out-Null
Copy-Item $exe $stage -Force
Copy-Item $sha $stage -Force

@"
DPort Windows WiFi Test $version

Base source: DPort v$version
pymobiledevice3: $pm3
WiFi discovery: Apple mobdev2 / Bonjour
Production updater: disabled for this test build
This is a test build, not a production release.
"@ | Set-Content (Join-Path $stage 'README-WiFi-Test.txt') -Encoding utf8

Compress-Archive -Path "$stage\*" -DestinationPath $zip -Force

if (-not (Test-Path $zip)) {
    throw 'WiFi test ZIP was not produced.'
}

Write-Host "=== BUILD SUCCESS ==="
Write-Host $exe
Write-Host $zip
