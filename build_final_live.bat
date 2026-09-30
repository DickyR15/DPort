@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

title DPort-6.9.0 Builder

echo ==========================================================
echo DPort-6.9.0 Builder
echo ==========================================================
echo.

if not exist "src\main.py" goto fail

REM ==========================================================
REM Python runtime management
REM - Build with CPython 3.14.x (current stable via WinGet).
REM - Older CPython 3.x versions are removed first.
REM - Do NOT depend on the legacy "py" launcher.
REM ==========================================================
echo [1/6] Checking WinGet...
where winget >nul 2>&1
if errorlevel 1 (
    echo WinGet was not found.
    echo Please install Microsoft App Installer, then run this builder again.
    goto fail
)

echo.
echo [2/6] Removing older CPython 3.x versions if present...
for %%V in (3.7 3.8 3.9 3.10 3.11 3.12 3.13) do (
    winget uninstall --id Python.Python.%%V --exact --silent --disable-interactivity >nul 2>&1
)

echo Installing/updating the latest stable Python 3.14...
winget install --id Python.Python.3.14 --exact --source winget --accept-source-agreements --accept-package-agreements --silent
if errorlevel 1 (
    echo.
    echo Python 3.14 installation failed.
    goto fail
)

winget upgrade --id Python.Python.3.14 --exact --source winget --accept-source-agreements --accept-package-agreements --silent >nul 2>&1

REM Refresh common Python/WindowsApps locations in this CMD.
set "PATH=%LocalAppData%\Programs\Python\Python314;%LocalAppData%\Programs\Python\Python314\Scripts;%LocalAppData%\Python\bin;%LocalAppData%\Microsoft\WindowsApps;%PATH%"

echo.
echo Locating installed Python 3.14 executable...

set "PYTHON_EXE="

REM 1) Common per-user/per-machine classic installer locations.
for %%P in (
    "%LocalAppData%\Programs\Python\Python314\python.exe"
    "%LocalAppData%\Programs\Python\Python314-64\python.exe"
    "%ProgramFiles%\Python314\python.exe"
    "%ProgramFiles%\Python314-64\python.exe"
    "%ProgramFiles(x86)%\Python314\python.exe"
) do (
    if not defined PYTHON_EXE if exist "%%~P" set "PYTHON_EXE=%%~P"
)

REM 2) Python registry InstallPath entries.
if not defined PYTHON_EXE (
    for /f "tokens=2,*" %%A in ('reg query "HKCU\Software\Python\PythonCore\3.14\InstallPath" /ve 2^>nul') do (
        if /i "%%A"=="REG_SZ" if exist "%%Bpython.exe" set "PYTHON_EXE=%%Bpython.exe"
    )
)
if not defined PYTHON_EXE (
    for /f "tokens=2,*" %%A in ('reg query "HKLM\Software\Python\PythonCore\3.14\InstallPath" /ve 2^>nul') do (
        if /i "%%A"=="REG_SZ" if exist "%%Bpython.exe" set "PYTHON_EXE=%%Bpython.exe"
    )
)
if not defined PYTHON_EXE (
    for /f "tokens=2,*" %%A in ('reg query "HKLM\Software\WOW6432Node\Python\PythonCore\3.14\InstallPath" /ve 2^>nul') do (
        if /i "%%A"=="REG_SZ" if exist "%%Bpython.exe" set "PYTHON_EXE=%%Bpython.exe"
    )
)

REM 3) Try the global python command after PATH refresh.
if not defined PYTHON_EXE (
    where python >nul 2>&1
    if not errorlevel 1 (
        for /f "delims=" %%P in ('where python 2^>nul') do (
            if not defined PYTHON_EXE set "PYTHON_EXE=%%P"
        )
    )
)

if not defined PYTHON_EXE (
    echo.
    echo Python 3.14 was installed, but python.exe could not be located.
    echo Please close this window and run build_final_live.bat again.
    goto fail
)

echo Python executable: !PYTHON_EXE!
"!PYTHON_EXE!" --version
if errorlevel 1 goto fail

for /f "tokens=2" %%V in ('"!PYTHON_EXE!" --version 2^>^&1') do set "PY_VERSION=%%V"
echo Detected Python: !PY_VERSION!

echo.
echo Checking Python 3.14...
echo !PY_VERSION! | findstr /r /b /c:"3.14." >nul
if errorlevel 1 (
    echo.
    echo ERROR: Python 3.14.x is required.
    echo Detected: !PY_VERSION!
    goto fail
)

echo.
echo Creating clean Python 3.14 build environment...
if exist ".venv" rmdir /s /q ".venv"
"!PYTHON_EXE!" -m venv .venv
if errorlevel 1 goto fail

call ".venv\Scripts\activate.bat"
if errorlevel 1 goto fail

python --version
if errorlevel 1 goto fail

REM ==========================================================
REM Native compiler needed by lzfse on CPython 3.14.
REM ==========================================================
echo.
echo Installing/verifying Microsoft C++ Build Tools...
winget install --id Microsoft.VisualStudio.2022.BuildTools --exact --source winget --accept-source-agreements --accept-package-agreements --silent --override "--wait --quiet --norestart --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"
if errorlevel 1 (
    echo.
    echo WARNING: Visual C++ Build Tools installation returned an error.
    echo lzfse may not build until the C++ toolchain is installed.
)

REM Load the VS developer environment when Build Tools is present.
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if exist "!VSWHERE!" (
    for /f "delims=" %%V in ('"!VSWHERE!" -latest -products * -requires Microsoft.VisualStudio.Workload.VCTools -property installationPath 2^>nul') do (
        if exist "%%V\Common7\Tools\VsDevCmd.bat" (
            call "%%V\Common7\Tools\VsDevCmd.bat" -arch=x64 -host_arch=x64 >nul 2>&1
            goto vs_env_ready
        )
    )
)
:vs_env_ready

echo.
echo [3/6] Installing build dependencies...
python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" > python_runtime.txt
python -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto fail

REM lzfse has no CPython 3.14 Windows wheel at present, so compile it
REM locally with the Visual C++ toolchain instead of failing mid-install.
python -m pip install --upgrade "lzfse==0.4.2"
if errorlevel 1 goto fail

python -m pip install -r requirements-build.txt
if errorlevel 1 goto fail

echo.
echo [4/6] Checking source...
python -m py_compile "src\main.py"
if errorlevel 1 goto fail

if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

echo.
echo [5/6] Checking DPort icon...
if not exist "DPort-6.9.0.ico" (
    echo ERROR: DPort-6.9.0.ico was not found.
    goto fail
)

echo.
echo [5/6] Building embedded DPort updater helper...
if not exist "src\dport_updater_helper.py" (
    echo ERROR: src\dport_updater_helper.py was not found.
    goto fail
)

if exist "dist\DPortUpdater.exe" del /q "dist\DPortUpdater.exe"
if exist "build\updater" rmdir /s /q "build\updater"

python -m PyInstaller --noconfirm --clean --onefile --name "DPortUpdater" --collect-all certifi --hidden-import "importlib.metadata" "src\dport_updater_helper.py"
if errorlevel 1 goto fail

if not exist "dist\DPortUpdater.exe" (
    echo ERROR: DPortUpdater.exe was not created.
    goto fail
)

mkdir "build\updater"
copy /y "dist\DPortUpdater.exe" "build\updater\DPortUpdater.exe" >nul
if errorlevel 1 goto fail

echo Embedded updater helper ready.

echo.
echo [5/6] Building DPort-6.9.0.exe...
python -m PyInstaller --noconfirm --clean --onefile --name "DPort-6.9.0" --icon "DPort-6.9.0.ico" --collect-all pymobiledevice3 --collect-all pytun_pmd3 --collect-all pyimg4 --collect-all inquirer3 --copy-metadata pymobiledevice3 --copy-metadata pyimg4 --copy-metadata readchar --hidden-import "pymobiledevice3.remote.userspace_tunnel" --hidden-import "dport_version" --hidden-import "dport_release_updater" --hidden-import "pymobiledevice3.services.dvt.instruments.dvt_provider" --hidden-import "pymobiledevice3.services.dvt.instruments.location_simulation" --hidden-import "pymobiledevice3.usbmux" --add-data "src\templates;templates" --add-data "moenv_api_key.txt;." --add-data "python_runtime.txt;." --add-binary "build\updater\DPortUpdater.exe;dport_updater" --version-file "version_info.txt" "src\main.py"
if errorlevel 1 goto fail

echo.
echo [6/6] BUILD SUCCESSFUL
echo EXE: %CD%\dist\DPort-6.9.0.exe
echo API KEY: embedded in DPort-6.9.0.exe
echo Updater: embedded in DPort-6.9.0.exe
if exist "dist\DPortUpdater.exe" del /q "dist\DPortUpdater.exe"
if exist "build\updater" rmdir /s /q "build\updater"
echo Python: !PY_VERSION!
echo.
timeout /t 3 /nobreak >nul
exit /b 0

:fail
echo.
echo BUILD FAILED
echo Check the messages above.
echo.
timeout /t 15 /nobreak >nul
exit /b 1
