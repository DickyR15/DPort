Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$version = '6.9.30'
$sourceZip = 'DPort-source-6.9.0.zip'
$tmp = Join-Path $env:RUNNER_TEMP 'dport-wifi-clean-source'
$stage = Join-Path $PWD "DPort-WiFi-Test-$version"
$exe = Join-Path $PWD "dist\DPort-WiFi-Test-$version.exe"
$zip = Join-Path $PWD "DPort-WiFi-Test-$version.zip"

if (-not (Test-Path $sourceZip)) { throw "$sourceZip is missing." }

if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
Expand-Archive -LiteralPath $sourceZip -DestinationPath $tmp -Force

$mainFiles = @(Get-ChildItem $tmp -Filter 'main.py' -File -Recurse)
if ($mainFiles.Count -eq 0) { throw 'main.py was not found in source ZIP.' }
$root = $mainFiles[0].Directory.Parent.FullName
if (-not (Test-Path (Join-Path $root 'src\main.py'))) { throw "Invalid source root: $root" }

Copy-Item (Join-Path $root '*') . -Recurse -Force

if (Test-Path src) { Remove-Item src -Recurse -Force }
New-Item -ItemType Directory -Force -Path src | Out-Null
Copy-Item (Join-Path $root 'src\*') src -Recurse -Force

python scripts\apply_wifi_test.py
if ($LASTEXITCODE -ne 0) { throw 'Wi-Fi patch failed.' }

foreach ($file in @('src\dport_release_updater.py','src\dport_updater_helper.py')) {
    if (Test-Path $file) { Remove-Item $file -Force }
}

python -m py_compile src\main.py
if ($LASTEXITCODE -ne 0) { throw 'Python syntax validation failed.' }

$main = Get-Content 'src\main.py' -Raw
$ui = Get-Content 'src\templates\map.html' -Raw

foreach ($feature in @(
    'get_mobdev2_lockdowns',
    'create_using_tcp(',
    'CoreDeviceTunnelProxy',
    'wifi_tunnel_error'
)) {
    if ($main -notlike "*$feature*") { throw "Missing Wi-Fi feature: $feature" }
}

foreach ($forbidden in @(
    'dport_release_updater',
    'bootstrap_dport_updater',
    '/pymobiledevice3/status'
)) {
    if ($main -like "*$forbidden*") { throw "UPDATER BACKEND RESIDUE FOUND: $forbidden" }
}

foreach ($forbiddenUi in @(
    'id="dport-pm3-update-modal"',
    'id="dport-69-pm3-update-modal-fix9"',
    'dportStartPm3StatusPolling();'
)) {
    if ($ui -like "*$forbiddenUi*") { throw "UPDATER UI RESIDUE FOUND: $forbiddenUi" }
}

# Verify production UI using ASCII-safe identifiers only.
# This avoids Windows PowerShell 5.1 encoding/parser issues while still
# checking the actual production controls are present.
foreach ($requiredUi in @(
    'GPX',
    'deviceDropdown',
    'refresh-device',
    'connection',
    'connectButton'
)) {
    if ($ui -notlike "*$requiredUi*") { throw "PRODUCTION UI MISSING: $requiredUi" }
}

Set-Content 'src\dport_version.py' 'DPORT_VERSION="6.9.16"' -Encoding utf8

$req = Get-Content 'requirements-build.txt' -Raw
$req = $req -replace 'pymobiledevice3\s*=\s*[=<>!~]{1,2}\s*[^\r\n#]+', 'pymobiledevice3==11.19.1'
Set-Content 'requirements-build.txt' $req -Encoding utf8

python -m pip install --upgrade pip setuptools wheel
if ($LASTEXITCODE -ne 0) { throw 'pip bootstrap failed.' }

python -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'requirements installation failed.' }

python -m pip install lzfse==0.4.2 pyinstaller
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller installation failed.' }

$pm3 = (python -c "from importlib.metadata import version; print(version('pymobiledevice3'))").Trim()
if ($pm3 -ne '11.19.1') { throw "Expected pymobiledevice3 11.19.1, got [$pm3]" }

if (Test-Path dist) { Remove-Item dist -Recurse -Force }
if (Test-Path build) { Remove-Item build -Recurse -Force }

$args = @(
    '--noconfirm',
    '--clean',
    '--onefile',
    '--name',"DPort-WiFi-Test-$version",
    '--icon','DPort-6.9.0.ico',
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
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }

if (-not (Test-Path $exe)) { throw "EXE not found: $exe" }

if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Force -Path $stage | Out-Null

Copy-Item $exe (Join-Path $stage (Split-Path $exe -Leaf)) -Force
Set-Content (Join-Path $stage 'README-WiFi-Test.txt') @"
DPort Wi-Fi Test $version

Base: DPort v6.9.0
Wi-Fi discovery: mobdev2
Wi-Fi tunnel: TCP Lockdown + CoreDeviceProxy for iOS 17.4+
pymobiledevice3: $pm3

Same-version DPort auto-update: DISABLED
DPort updater UI/API: REMOVED

Production UI layout: PRESERVED FROM DPort 6.9.0
Test build only.
"@ -Encoding utf8

if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zip -Force

$zipSize = (Get-Item $zip).Length
if ($zipSize -lt 1000000) { throw "ZIP unexpectedly small: $zipSize" }

# Validate the actual ZIP content itself.
$check = Join-Path $env:RUNNER_TEMP 'dport-wifi-package-check'
if (Test-Path $check) { Remove-Item $check -Recurse -Force }
New-Item -ItemType Directory -Force -Path $check | Out-Null
Expand-Archive -LiteralPath $zip -DestinationPath $check -Force

$files = @(Get-ChildItem $check -File)
if (@($files | Where-Object {$_.Extension -eq '.zip'}).Count -ne 0) { throw 'Nested ZIP detected inside the release ZIP.' }
if (@($files | Where-Object {$_.Extension -eq '.exe'}).Count -ne 1) { throw 'Expected exactly one EXE in release ZIP.' }

Write-Host "DPort Wi-Fi $version DIRECT PACKAGE CREATED: $zip ($zipSize bytes)"
