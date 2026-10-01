import dport_release_updater
import locale
import os
import re
import sys
import time
import pyuac
import psutil
import signal
import socket
import random
import asyncio
import argparse
import requests
import threading
import queue
import webbrowser
import subprocess
import pycountry
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from urllib3.exceptions import InsecureRequestWarning, ConnectionError
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# DPort pymobiledevice3 updater MUST bootstrap before the first pymobiledevice3 import.
from dport_release_updater import bootstrap_dport_updater
bootstrap_dport_updater()

from pymobiledevice3.usbmux import list_devices
from pymobiledevice3.cli.mounter import auto_mount
from pymobiledevice3.lockdown import create_using_usbmux, get_mobdev2_lockdowns
from pymobiledevice3.services.amfi import AmfiService
from pymobiledevice3.exceptions import DeviceHasPasscodeSetError, PasscodeRequiredError, PasswordRequiredError
from pymobiledevice3.services.dvt.instruments.dvt_provider import DvtProvider
from pymobiledevice3.services.dvt.instruments.location_simulation import LocationSimulation
from pymobiledevice3.remote.remote_service_discovery import RemoteServiceDiscoveryService
from pymobiledevice3.remote.utils import resume_remoted_if_required
from pymobiledevice3.remote.tunnel_service import create_core_device_tunnel_service_using_rsd, get_remote_pairing_tunnel_services, create_core_device_tunnel_service_using_remotepairing, CoreDeviceTunnelProxy
from pymobiledevice3.remote.userspace_tunnel import UserspaceRsdTunnel
from pymobiledevice3.osu.os_utils import get_os_utils
from pymobiledevice3.bonjour import DEFAULT_BONJOUR_TIMEOUT
from pymobiledevice3.pair_records import get_local_pairing_record, get_remote_pairing_record_filename, get_preferred_pair_record
from pymobiledevice3.common import get_home_folder
def cli_install_wetest_drivers(*args, **kwargs):
    logger.warning("WeTest driver installer is unavailable in this pymobiledevice3 build; skipping it.")

from pymobiledevice3.cli.remote import tunnel_task

from pymobiledevice3.lockdown_service_provider import LockdownServiceProvider
from pymobiledevice3.remote.common import TunnelProtocol

#========= Arg Parser ========
# Parse command-line arguments
parser = argparse.ArgumentParser()
parser.add_argument('--no-browser', action='store_true', help='Skip auto opening the browser')
parser.add_argument('--port', type=int, help='Specify port number to listen on for web browser requests')
parser.add_argument('--wifihost', type=str, help='Specify the wifi IP address to connect to')
parser.add_argument('--udid', type=str, help='Specify the device udid to target')
args = parser.parse_args()
#========= Arg Parser ========

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
OSUTILS = get_os_utils()


import logging
def is_device_locked_error(error: BaseException | str) -> bool:
    """Return True only when the location operation is blocked by a locked/password-protected device."""
    if isinstance(error, (PasscodeRequiredError, PasswordRequiredError)):
        return True

    text = str(error).lower()
    locked_markers = (
        "passwordprotected",
        "password protected",
        "password-required",
        "password required",
        "passcode required",
        "passcoderequired",
        "device is locked",
        "device locked",
        "device currently locked",
        "locked device",
    )
    return any(marker in text for marker in locked_markers)
timeout = DEFAULT_BONJOUR_TIMEOUT

# Get the current platform using sys.platform
current_platform = sys.platform

# Map the platform names to standard values
platform = {
    'win32': 'Windows',
    'linux': 'Linux',
    'darwin': 'MacOS',
}.get(current_platform, 'Unknown')

# Check if running as sudo
if current_platform == "darwin":
    if os.geteuid() != 0:
        logger.error("*********************** WARNING ***********************")
        logger.error("Not running as Sudo, this probably isn't going to work")
        logger.error("*********************** WARNING ***********************")
        sudo_message = "Not running as Sudo, this probably isn't going to work"
    else:
        logger.info("Running as Sudo")
        sudo_message = ""



def fetch_api_data(api_url):
    global api_data
    try:
        api_data = requests.get(api_url, verify=False).json()
        return api_data
    except requests.exceptions.RequestException as e:
        logger.error(f"Error: {e}")
        logger.error(f"API is unreachable or there was an error during the request")
        logger.error("Sorry - Fuel data is not available")
        return None
    except ConnectionError as e:
        logger.error("Error: Name resolution failed.")
        logger.error("Please check your internet connection or the correctness of the API URL.")
        logger.error("Sorry - Fuel data is not available")
        logger.error(f"Details: {e}")
        return None

def create_geoport_folder():
    # Define the path to the GeoPort folder
    geoport_folder = os.path.join(home_dir, 'GeoPort')

    # Check if the GeoPort folder exists, create it if not
    if not os.path.exists(geoport_folder):
        os.makedirs(geoport_folder)
        logger.info(f"GeoPort Home: {geoport_folder}")
        logger.info("GeoPort folder created successfully")

    # Set permissions for the GeoPort folder
    if current_platform == 'win32':
        # Windows permissions (read/write for everyone)
        os.system(f"icacls {geoport_folder} /grant Everyone:(OI)(CI)F")
        logger.info("Permissions set for GeoPort folder on Windows")
    else:  # Linux and MacOS
        # POSIX permissions (read/write for everyone)
        os.chmod(geoport_folder, 0o777)
        logger.info("Permissions set for GeoPort folder on MacOS")



# Define the function to be executed in the thread
def run_tunnel(service_provider):

    try:
        asyncio.run(start_quic_tunnel(service_provider))

        logger.info("run_tun completed")
        sys.exit(0)

    except Exception as e:
        error_message = str(e)

        # Handle the exception, such as logging it or returning an error response
        with app.app_context():
            return jsonify({'error': error_message})

    #return

# Define a function to start the tunnel thread
async def start_quic_tunnel(service_provider: RemoteServiceDiscoveryService) -> None:

    logger.warning("Start USB QUIC tunnel")

    global terminate_tunnel_thread
    
    # if sys.platform == 'win32':
                
    service = await create_core_device_tunnel_service_using_rsd(service_provider, autopair=True)

    async with service.start_quic_tunnel() as tunnel_result:
        resume_remoted_if_required()

        logger.info(f"QUIC Address: {tunnel_result.address}")
        logger.info(f"QUIC Port: {tunnel_result.port}")
        global rsd_port
        global rsd_host
        rsd_host = tunnel_result.address

        rsd_port = str(tunnel_result.port)


        while True:
            if terminate_tunnel_thread is True:
                return
            # wait user input while the asyncio tasks execute
            await asyncio.sleep(.5)


# Define the function to be executed in the thread
def run_tcp_tunnel(service_provider):

    try:
        asyncio.run(start_tcp_tunnel(service_provider))

        logger.info("run_tun completed")
        sys.exit(0)

    except Exception as e:
        error_message = str(e)

        # Handle the exception, such as logging it or returning an error response
        with app.app_context():
            return jsonify({'error': error_message})

    #return

# Define a function to start the tunnel thread
async def start_tcp_tunnel(service_provider: CoreDeviceTunnelProxy) -> None:

    logger.warning("Start USB TCP tunnel")

    global terminate_tunnel_thread
    
    
    lockdown = await create_using_usbmux(udid, autopair=True)
        service = await CoreDeviceTunnelProxy.create(lockdown)
        async with service.start_tcp_tunnel() as tunnel_result:
        logger.info(f"TCP Address: {tunnel_result.address}")
        logger.info(f"TCP Port: {tunnel_result.port}")
        global rsd_port
        global rsd_host
        rsd_host = tunnel_result.address

        rsd_port = str(tunnel_result.port)

        while True:
            if terminate_tunnel_thread is True:
                return
            # wait user input while the asyncio tasks execute
            await asyncio.sleep(.5)





def is_major_version_17_or_greater(version_string):
    # Check if the major version in the given version string is 17 or greater.
    try:
        major_version = int(version_string.split('.')[0])
        return major_version >= 17
    except (ValueError, IndexError):
        # Handle invalid version string or missing major version
        return False

def version_check(version_string):
    try:
        # Split the version string into major and minor version parts
        version_parts = version_string.split('.')

        # Extract the major and minor version parts
        major_version = int(version_parts[0])
        minor_version = int(version_parts[1]) if len(version_parts) > 1 else 0

        # Check if the version string satisfies the condition
        if major_version == 17 and 0 <= minor_version <= 3:
            if sys.platform == 'win32':
                logger.info("Checking Windows Driver requirement")
                logger.info("Driver is required")
            return True
        else:
            if sys.platform == 'win32':
                logger.info("Driver is not required")
                return False
            logger.info("MacOS - pass")
            return False



    except (ValueError, IndexError) as e:
        logger.error(f"Driver check error: {e}")
        # Handle invalid version string or missing major/minor version
        return False

def get_user_country():
    global user_locale
    try:
        # Attempt to get the user's country using locale and pycountry
        user_locale, _ = locale.getlocale()

        if user_locale is None:
            logger.warning("User locale is None. Defaulting to IP geolocation service.")
            return get_country_from_ip()

        country_code = user_locale.split('_')[-1]
        country = pycountry.countries.get(alpha_2=country_code)
        country_name = country.name if country else None

        # If country_name is None, try IP geolocation service as a fallback
        if country_name is None:
            logger.warning("Failed to retrieve country name using locale. Using IP geolocation service.")
            return get_country_from_ip()
        else:
            return country_name

    except Exception as e:
        logger.error(f"Error getting user country: {e}")
        return None


def get_country_from_ip():
    try:
        response = requests.get("http://ip-api.com/json/")
        if response.status_code == 200:
            data = response.json()
            country_name = data.get("country")
            if country_name:
                return country_name
            else:
                logger.warning("Failed to retrieve country name from IP geolocation service.")
        else:
            logger.error(f"Error: Unable to retrieve data. Status code: {response.status_code}")
            logger.warning("Setting to default country")
            country_name = "Spain"
        return country_name
    except Exception as e:
        logger.error(f"Error getting country from IP geolocation service: {e}")
        country_name = "Spain"
        return country_name
def get_wifi_with_retry(max_attempts=10):
    """Discover normal iTunes/Apple Wi-Fi devices through mobdev2 Bonjour.

    iTunes Wi-Fi Sync advertises _apple-mobdev2._tcp.  This is a different
    discovery path from RemotePairing (_remotepairing._tcp), which FIX4 used.
    Normal Apple devices on iOS 17.4+ should use mobdev2 + CoreDeviceProxy for the
    Wi-Fi lockdown tunnel.
    """
    global udid, wifi_address, wifi_port, ios_version
    home = get_home_folder()
    logger.info("Wi-Fi discovery: using Apple mobdev2 Bonjour (_apple-mobdev2._tcp)")

    for attempt in range(1, max_attempts + 1):
        found = False
        try:
            async def discover():
                results = []
                async for ip, device in get_mobdev2_lockdowns(
                    udid=udid,
                    pair_records=home,
                    only_paired=True,
                    timeout=timeout,
                ):
                    try:
                        # TcpLockdownClient.short_info.Identifier is the TCP hostname/IP,
                        # not the iPhone UDID. The authoritative UDID is device.udid /
                        # UniqueDeviceID. Keep both so selection never confuses IP with UDID.
                        short = dict(device.short_info)
                        short["_DeviceUDID"] = device.udid or short.get("UniqueDeviceID")
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
                try:
                    device_udid = short.get("_DeviceUDID") or short.get("UniqueDeviceID") or udid
                    product = short.get("ProductVersion")
                    logger.info(
                        f"mobdev2 device: ip={ip}, udid={device_udid}, iOS={product}, paired={getattr(device, 'paired', None)}"
                    )
                    if udid and device_udid and device_udid != udid:
                        logger.warning(f"Skipping mobdev2 device with different UDID: {device_udid}")
                        continue

                    udid = device_udid or udid
                    wifi_address = str(ip)
                    wifi_port = 62078
                    found = True
                    logger.info(
                        f"Wi-Fi device selected via mobdev2: udid={udid}, host={wifi_address}, port={wifi_port}"
                    )
                    return {"udid": udid, "hostname": wifi_address, "port": wifi_port}
                except Exception as e:
                    logger.warning(f"mobdev2 device parsing failed: {e}")
        except Exception as e:
            logger.warning(f"Attempt {attempt}: mobdev2 Wi-Fi discovery error - {e}")

        if not found:
            logger.warning(
                f"Attempt {attempt}: no paired mobdev2 Wi-Fi device found. "
                "Check iTunes Wi-Fi management, Apple Mobile Device/Bonjour services, "
                "same LAN, and Windows Firewall/mDNS (UDP 5353)."
            )
        time.sleep(1)

    # Keep RemotePairing as a fallback for devices/environments that expose it.
    logger.info("mobdev2 discovery failed; trying RemotePairing as a fallback")
    try:
        for attempt in range(1, 3):
            devices = []
            try:
                devices = asyncio.run(get_remote_pairing_tunnel_services(timeout, udid=udid or None))
                for device in devices:
                    device_id = getattr(device, "remote_identifier", None)
                    if udid and device_id and device_id != udid:
                        continue
                    hostname = getattr(device, "hostname", None)
                    port = getattr(device, "port", None)
                    if device_id:
                        udid = device_id
                    wifi_address = hostname or wifi_address
                    wifi_port = int(port or 62078)
                    logger.info(
                        f"Wi-Fi device selected via RemotePairing fallback: udid={udid}, host={wifi_address}, port={wifi_port}"
                    )
                    return {"udid": udid, "hostname": wifi_address, "port": wifi_port}
            finally:
                if devices:
                    try:
                        asyncio.run(_close_remote_pairing_services(devices))
                    except Exception:
                        pass
    except Exception as e:
        logger.warning(f"RemotePairing fallback failed: {e}")

    raise RuntimeError(
        "No Wi-Fi device found. iTunes Wi-Fi Sync uses mobdev2 (_apple-mobdev2._tcp), "
        "not RemotePairing. Verify the Apple device was paired by USB, Wi-Fi management is enabled, "
        "the PC and iPhone are on the same LAN, and Windows Firewall allows mDNS/Bonjour."
    )

@app.route('/stop_tunnel', methods=['POST'])
def stop_tunnel_thread():
    global terminate_tunnel_thread
    logger.info("stop tunnel thread")
    # Set the terminate flag to True to stop the thread
    terminate_tunnel_thread = True
    return jsonify("Tunnel stopped")

@app.route('/api/data/<fuel_type>')
def get_fuel_type_data(fuel_type):
    selected_fuel_region = request.args.get('region', 'All')

    if api_data is None:
        logger.error("API Data is none, Fuel data is not available")
        return jsonify({}), 500  # Return an empty response with status code 500 (Internal Server Error)

    all_region_data = next(
        (region['prices'] for region in api_data['regions'] if region['region'] == selected_fuel_region), [])

    selected_data = next((entry for entry in all_region_data if entry['type'] == fuel_type), None)

    return jsonify(selected_data)


@app.route('/api/fuel_types')
def get_fuel_types():
    selected_fuel_region = request.args.get('region', 'All')

    if api_data is None:
        logger.error("API Data is none, sorry - Fuel data is not available")
        return jsonify({}), 500  # Return an empty response with status code 500 (Internal Server Error)

    all_region_data = next(
        (region['prices'] for region in api_data['regions'] if region['region'] == selected_fuel_region), [])

    fuel_types = set(entry['type'] for entry in all_region_data)

    return jsonify(list(fuel_types))


@app.route('/update_location', methods=['POST'])
def update_location():
    # Use 'request' to get the JSON data from the client
    data = request.get_json()

    # Convert latitude and longitude to float values
    lat = float(data['lat'])
    lng = float(data['lng'])

    global location
    location = f"{lat} {lng}"
    return 'Location updated successfully'

def check_pair_record(udid):
    global pair_record
    logger.info(f"Connection Type: {connection_type}")
    logger.info("Enable Developer Mode")

    home = get_home_folder()
    logger.info(f"Pair Record Home: {home}")

    filename = get_remote_pairing_record_filename(udid)
    logger.info(f"Pair Record File: {filename}")

        pair_record = get_preferred_pair_record(udid, home)
        return pair_record

def wait_for_usb_device_stable(udid, attempts=8, interval=0.5, consecutive=2):
    """Wait for a USB device to remain visible in usbmux before opening Lockdown.

    A cable replug can briefly produce Raw USB Devices: [] even though the phone
    is already visible again shortly afterward. Requiring consecutive sightings
    prevents Developer Mode/Lockdown from racing that re-enumeration window.
    """
    if not udid:
        return False, "沒有可用的裝置識別碼"

    last_error = None
    stable_hits = 0

    for attempt in range(1, attempts + 1):
        try:
            async def _list():
                return await list_devices()

            devices = asyncio.run(_list())
            present = any(
                getattr(device, "serial", None) == udid
                for device in devices
            )

            if present:
                stable_hits += 1
                logger.info(
                    f"USB stability check {attempt}/{attempts}: "
                    f"UDID {udid} present ({stable_hits}/{consecutive})"
                )
                if stable_hits >= consecutive:
                    return True, None
            else:
                stable_hits = 0
                last_error = (
                    f"usbmux 尚未穩定看到裝置 {udid}"
                )
                logger.info(
                    f"USB stability check {attempt}/{attempts}: device not ready"
                )

        except Exception as exc:
            stable_hits = 0
            last_error = str(exc)
            logger.warning(
                f"USB stability check {attempt}/{attempts} failed: {last_error}"
            )

        if attempt < attempts:
            time.sleep(interval)

    return False, last_error or "USB 裝置未穩定出現"

def check_developer_mode(udid, connection_type):
    """Check Developer Mode after USB enumeration has stabilized."""
    if connection_type == "Network":
        logger.info("Network device: skipping usbmux Developer Mode pre-check")
        return True

    stable, stable_error = wait_for_usb_device_stable(udid)
    if not stable:
        logger.error(f"USB device not stable: {stable_error}")
        return None

    async def _check():
        lockdown = None
        try:
            lockdown = await create_using_usbmux(
                serial=udid,
                connection_type=connection_type,
                autopair=True,
            )
            result = await lockdown.get_developer_mode_status()
            logger.info(f"Developer Mode Check result: {result}")
            return bool(result), None
        except Exception as exc:
            return None, str(exc)
        finally:
            if lockdown is not None:
                try:
                    await lockdown.close()
                except Exception:
                    pass

    last_error = None
    for attempt in range(1, 4):
        try:
            result, error_text = asyncio.run(_check())
        except Exception as exc:
            result, error_text = None, str(exc)

        if result is True:
            return True
        if result is False:
            return False

        last_error = error_text or "未知 USB/Lockdown 錯誤"
        logger.warning(
            f"Developer Mode check {attempt}/3 failed: {last_error}"
        )
        if attempt < 3:
            time.sleep(0.75)
            stable, stable_error = wait_for_usb_device_stable(udid)
            if not stable:
                last_error = stable_error

    logger.error(f"Developer Mode check could not be completed: {last_error}")
    return None



def enable_developer_mode(udid, connection_type):
    """Enable Developer Mode using the async pymobiledevice3 API."""
    check_pair_record(udid)

    logger.info(f"Connection Type: {connection_type}")
    logger.info("Enable Developer Mode")
    home = get_home_folder()
    logger.info(f"Pair Record Home: {home}")

    if connection_type == "Network":
        if pair_record is None:
            logger.error("Network: No Pair Record Found. Please use a USB cable first to create a pair record")
            return False, "No Pair Record Found. Please use a USB cable first to create a pair record"
        return False, "Developer Mode must be enabled once over USB"

    async def _enable():
        lockdown = await create_using_usbmux(
            serial=udid,
            connection_type=connection_type,
            autopair=True,
            pairing_records_cache_folder=home,
        )
        try:
            await AmfiService(lockdown).enable_developer_mode()
            logger.info("Enable complete, mount developer image...")
        except DeviceHasPasscodeSetError:
            raise
        finally:
            try:
                await lockdown.close()
            except Exception:
                pass

        # Developer Mode changes may reboot the phone. Open a fresh connection
        # for DDI mounting after the reboot.
        await _mount_developer_image_async()

    try:
        asyncio.run(_enable())
        return True, None
    except DeviceHasPasscodeSetError:
        error_message = (
            'Error: Device has a passcode set\n\n'
            'Please temporarily remove the passcode and run GeoPort again to enable Developer Mode\n\n'
            'Go to "Settings - Face ID & Passcode"\n'
        )
        logger.error(error_message)
        return False, error_message
    except Exception as e:
        logger.exception(f"Developer Mode enable failed: {e}")
        return False, str(e)


@app.route('/enable_developer_mode', methods=['POST'])
def enable_developer_mode_route():
    try:
        global udid
        data = request.get_json()

        # Extract the udid from the request
        udid = data.get('udid', None)

        if connection_type == "Network":
            return jsonify({
                'error': 'Developer Mode must be enabled once over USB. Reconnect the Apple device by USB, enable Developer Mode, then use Wi-Fi.'
            })
        success, error_message = enable_developer_mode(udid, connection_type)

        if success:
            # Return a success response with any additional data needed
            return jsonify({'success': True, 'udid': udid})
        else:
            return jsonify({'error': error_message})

    except Exception as e:
        error_message = str(e)
        if "PasswordProtected" in error_message:
            return jsonify({
                'error': PASSWORD_PROTECTED_LOCATION_MESSAGE,
                'error_type': 'PasswordProtected'
            }), 423
        return jsonify({'error': error_message})




@app.route('/device_disconnected', methods=['POST'])
def device_disconnected():
    """Reset stale state after the physical USB cable is removed."""
    global rsd_data, rsd_host, rsd_port, lockdown
    global userspace_location_tunnel, connection_type

    logger.info("Physical USB disconnect detected; clearing stale state")

    try:
        stop_set_location_thread()
    except Exception as exc:
        logger.warning(f"USB disconnect location cleanup failed: {exc}")

    rsd_data = None
    rsd_host = None
    rsd_port = None
    userspace_location_tunnel = None
    lockdown = None
    connection_type = None
    return jsonify({"success": True})

@app.route('/connect_device', methods=['POST'])
def connect_device():
    global udid, connection_type, ios_version, rsd_data, rsd_host, rsd_port, wifi_address
    data = request.get_json()
    logger.info(f"Connect Device Data: {data}")

    udid = data.get('udid', None)
    connection_type = data.get('connType')

    if connection_type != "USB":
        logger.warning(f"USB-ONLY build: rejecting non-USB connection type: {connection_type}")
        return jsonify({"error": "USB-only mode: please connect the Apple device by USB."}), 400

    # Reuse an already-established connection when valid.
    if connection_type != "USB" and udid in rsd_data_map:
        if connection_type in rsd_data_map[udid]:
            cached = rsd_data_map[udid][connection_type]
            if isinstance(cached, dict) and cached.get('host') and cached.get('port'):
                rsd_data = cached
                rsd_host = cached['host']
                rsd_port = cached['port']
                logger.info(f"RSD in udid mapping is: {rsd_data}")
                logger.info("RSD already created. Reusing valid connection")
                return jsonify({'rsd_data': rsd_data})
            rsd_data_map[udid].pop(connection_type, None)

    # IMPORTANT: Network devices must not be sent through the old usbmux
    # Developer Mode check. The selected Network identifier is a Remote Pairing
    # identifier, not a usbmux device serial.
    if connection_type == "Network":
        check_pair_record(udid)
        if pair_record is None:
            logger.error("Network: No Remote Pair Record Found. Please connect once by USB first.")
            return jsonify({"Error": "No Pair Record Found"})
        return connect_wifi(data)

    developer_mode_state = check_developer_mode(udid, connection_type)

    if developer_mode_state is None:
        return jsonify({
            'error': 'USB 裝置正在重新連線，請稍候再試。',
            'connection_retryable': True
        }), 503

    if developer_mode_state is False:
        return jsonify({'developer_mode_required': 'True'})

    if connection_type == "USB":
        return connect_usb(data)

    if connection_type == "Manual":
        check_pair_record(udid)
        if pair_record is None:
            return jsonify({"Error": "No Pair Record Found"})
        return connect_wifi(data)

    return jsonify({"Error": "No matching connection type"})

def check_rsd_data():
    max_attempts = 30
    attempts = 0
    while attempts < max_attempts:
        if rsd_host is not None and rsd_port is not None:
            return True  # Data is available
        time.sleep(1)
        attempts += 1
    return False  # Data is still None after all attempts

def connect_usb(data):
    global udid, connection_type, ios_version, rsd_data, rsd_host, rsd_port
    try:
        logger.info(f"USB data: {data}")
        udid=data.get('udid',None)
        ios_version=data.get('ios_version')
        connection_type=data.get('connType')
        rsd_data=None; rsd_host=None; rsd_port=None
        if ios_version is None:
            return jsonify({'error':'No iOS version present'}),400
        if is_major_version_17_or_greater(ios_version):
            logger.warning("iOS 17+ USB: defer UserspaceRsdTunnel until Simulate Location")
            return jsonify({'connected':True,'userspace_tunnel':True})
        lockdown=asyncio.run(create_using_usbmux(serial=udid,autopair=True))
        rsd_data=(ios_version,udid)
        rsd_host,rsd_port=rsd_data
        rsd_data_map.setdefault(udid,{})[connection_type]={'host':rsd_host,'port':rsd_port}
        try:
            asyncio.run(lockdown.close())
        except Exception:
            pass
        return jsonify({'message':'iOS version less than 17','rsd_data':rsd_data})
    except Exception as e:
        logger.exception("USB connection failed")
        return jsonify({'error':str(e)}),500
    finally:
        logger.warning("Connect Device function completed")

def connect_wifi(data):
    try:
        global udid, wifi_address, connection_type, wifi_port
        global ios_version
        global rsd_data, rsd_host, rsd_port

        logger.info(f"Wifi data: {data}")

        # Extract the udid from the request
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

        if ios_version is not None and is_major_version_17_or_greater(ios_version):
            logger.info("iOS 17+ detected")

            # iOS 17.4+ uses the lockdown CoreDeviceProxy tunnel over Wi-Fi.
            # Do not gate discovery on the old 17.0-17.3 driver check.
            try:
                devices = get_wifi_with_retry()
                logger.info(f"Connect Wifi Devices: {devices}")
                logger.info(f"Wifi Address:  {wifi_address}")
            except RuntimeError as e:
                error_message = str(e)
                logger.error(f"Error: {error_message}")
                return jsonify({'error': 'No Devices Found', 'details': error_message}), 404


            rsd_host = None
            rsd_port = None

                                                            start_wifi_tunnel_thread()

            if not check_rsd_data():
                logger.error("RSD Data is None, Perhaps the tunnel isn't established")
            else:
                rsd_data = rsd_host, rsd_port
                logger.info(f"RSD Data: {rsd_data}")

            rsd_data_map.setdefault(udid, {})[connection_type] = {"host": rsd_host, "port": rsd_port}
            logger.info(f"Device Connection Map: {rsd_data_map}")
            return jsonify({'rsd_data': rsd_data})

        elif ios_version is not None and not is_major_version_17_or_greater(ios_version):
            rsd_data = ios_version, udid
            logger.info(f"RSD Data: {rsd_data}")

            # create LockdownServiceProvider
            global lockdown
            lockdown = asyncio.run(create_using_usbmux(serial=udid, connection_type=connection_type, autopair=True))
                        logger.info(f"Lockdown client = {lockdown}")

            rsd_data_map.setdefault(udid, {})[connection_type] = {"host": rsd_host, "port": rsd_port}

            return jsonify({'message': 'iOS version less than 17', 'rsd_data': rsd_data})

        else:
            # Invalid ios_version
            return jsonify({'error': 'No iOS version present'})
    finally:
        logger.warning("Connect Device function completed")




async def start_wifi_tcp_tunnel() -> None:
    """Start the official iOS 17.4+ CoreDeviceProxy TCP tunnel over mobdev2 Wi-Fi."""
    logger.warning("Start Wi-Fi TCP tunnel via mobdev2 + CoreDeviceProxy")
    global terminate_tunnel_thread, rsd_port, rsd_host, wifi_address

    lockdown = None
    service = None
    try:
        # Re-discover inside this event loop.  Lockdown/ServiceConnection objects
        # are loop-bound and must not be reused from the Flask request thread.
        async for ip, candidate in get_mobdev2_lockdowns(
            udid=udid,
            pair_records=get_home_folder(),
            only_paired=True,
            timeout=timeout,
        ):
            logger.info(f"mobdev2 tunnel candidate: {ip}, udid={candidate.udid}")
            wifi_address = str(ip)
            lockdown = candidate
            break

        if lockdown is None:
            raise RuntimeError(
                f"mobdev2 could not reconnect to the paired Apple device {udid} over Wi-Fi"
            )

        # iOS 17.4+ exposes CoreDeviceProxy through the normal lockdown service.
        # This is the correct Wi-Fi tunnel path for ordinary iPhones; RemotePairing
        # is not required for this path.
        service = await CoreDeviceTunnelProxy.create(lockdown)

        async with service.start_tcp_tunnel() as tunnel_result:
            resume_remoted_if_required()
            logger.info(f"Identifier: {service.remote_identifier}")
            logger.info(f"Interface: {tunnel_result.interface}")
            logger.info(f"RSD Address: {tunnel_result.address}")
            logger.info(f"RSD Port: {tunnel_result.port}")
            rsd_host = tunnel_result.address
            rsd_port = str(tunnel_result.port)

            while not terminate_tunnel_thread:
                await asyncio.sleep(.5)
    finally:
        resume_remoted_if_required()
        if service is not None:
            try:
                await service.close()
            except Exception:
                pass
        elif lockdown is not None:
            try:
                await lockdown.close()
            except Exception:
                pass


async def start_wifi_quic_tunnel() -> None:

    logger.warning(f"Start Wifi QUIC Tunnel")

    global terminate_tunnel_thread
    
    # if sys.platform == 'win32':
    #     if is_driver_required:
                service = await create_core_device_tunnel_service_using_remotepairing(udid, wifi_address, wifi_port)
        
    async with service.start_quic_tunnel() as tunnel_result:
        resume_remoted_if_required()

        logger.info(f'Identifier: {service.remote_identifier}')
        logger.info(f'Interface: {tunnel_result.interface}')
        logger.info(f'RSD Address: {tunnel_result.address}')
        logger.info(f'RSD Port: {tunnel_result.port}')
        global rsd_port
        global rsd_host
        rsd_host = tunnel_result.address

        rsd_port = str(tunnel_result.port)


        while True:
            if terminate_tunnel_thread is True:
                return
            # wait user input while the asyncio tasks execute
            await asyncio.sleep(.5)

# Define a function to start the tunnel thread
def start_wifi_tunnel_thread():
    global terminate_tunnel_thread
    terminate_tunnel_thread = False  # Set the value of the global variable
    thread = threading.Thread(target=run_wifi_tunnel)
    thread.start()
    return

# Entry point for running the tunnel async function
def run_wifi_tunnel():
    try:
        if is_major_version_17_or_greater(ios_version) and not version_check(ios_version):
            # iOS 17.4+ (including iOS 26.x): normal Wi-Fi lockdown + CoreDeviceProxy.
            asyncio.run(start_wifi_tcp_tunnel())
        elif version_check(ios_version):
            # Legacy iOS 17.0-17.3 Windows path.
            asyncio.run(start_wifi_quic_tunnel())
        else:
            asyncio.run(start_wifi_tcp_tunnel())
            except Exception as e:
        logger.error(f"Error in run_wifi_tunnel: {e}")


async def _mount_developer_image_async():
    global lockdown
    lockdown = await create_using_usbmux(serial=udid, autopair=True)
    try:
        logger.info(f"mount lockdown: {lockdown}")
        await auto_mount(lockdown)
    finally:
        try:
            await lockdown.close()
        except Exception:
            pass


@app.route('/mount_developer_image', methods=['POST'])
def mount_developer_image():
    try:
        asyncio.run(_mount_developer_image_async())
        return 'Developer image mounted successfully'
    except Exception as e:
        error_message = str(e)
        logger.exception(f"Developer image mount failed: {error_message}")
        return jsonify({'error': error_message})


async def _geoport_location_worker():
    global location_worker_stop, location_worker_ready, location_worker_error
    logger.warning("Location worker starting")
    try:
        async with UserspaceRsdTunnel(serial=udid, autopair=True) as rsd:
            logger.info("Userspace RSD tunnel established")
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

                        # Normal command: (latitude, longitude)
                        # Synchronized command: (latitude, longitude, done_event, result_box)
                        command_event = None
                        result_box = None
                        if isinstance(command, tuple) and len(command) == 4:
                            latitude, longitude, command_event, result_box = command
                        else:
                            latitude, longitude = command

                        try:
                            await location_service.set(float(latitude), float(longitude))
                            logger.warning(
                                f"Location Set Successfully: {latitude}, {longitude}"
                            )
                            if result_box is not None:
                                result_box["success"] = True
                            # Signal only after the device-side set() call has
                            # completed. This removes the first-click race.
                            if not location_worker_ready.is_set():
                                location_worker_ready.set()
                        except Exception as set_error:
                            if is_device_locked_error(set_error):
                                location_worker_error = PASSWORD_PROTECTED_LOCATION_MESSAGE
                                logger.warning(
                                    "Location set blocked because the Apple device is password-protected/locked."
                                )
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
                        # Give the device a short moment to receive the clear
                        # command before the DVT/tunnel session is closed.
                        await asyncio.sleep(1.0)
                    except Exception as clear_error:
                        location_worker_error = str(clear_error)
                        if is_device_locked_error(clear_error):
                            location_worker_error = PASSWORD_PROTECTED_LOCATION_MESSAGE
                            logger.warning(
                                "Location clear blocked because the iPhone is password-protected/locked."
                            )
                        else:
                            logger.warning(f"Location clear failed: {clear_error}")
    except asyncio.CancelledError:
        logger.info("Location worker cancelled")
        if not location_worker_ready.is_set():
            location_worker_error = "Location worker cancelled during initialization"
            location_worker_ready.set()
    except Exception as e:
        error_text = str(e)
        if is_device_locked_error(e):
            location_worker_error = PASSWORD_PROTECTED_LOCATION_MESSAGE
            logger.warning(
                "LocationSimulation blocked because the Apple device is password-protected/locked."
            )
        else:
            location_worker_error = error_text
            logger.exception(f"Location worker failed: {e}")
        if not location_worker_ready.is_set():
            location_worker_ready.set()
    finally:
        logger.warning("Location worker terminated")

def _geoport_location_worker_entry():
    asyncio.run(_geoport_location_worker())

async def set_location_thread(latitude, longitude):
    start_set_location_thread(latitude, longitude)
    while not location_worker_stop.is_set():
        await asyncio.sleep(0.1)


# Function to start the set_location_thread in a separate thread
def start_set_location_thread(latitude, longitude):
    global location_worker_thread, location_worker_stop
    global location_worker_ready, location_worker_error

    if location_worker_thread is None or not location_worker_thread.is_alive():
        location_worker_stop.clear()
        location_worker_ready.clear()
        location_worker_error = None

        while True:
            try:
                location_command_queue.get_nowait()
            except queue.Empty:
                break

        location_worker_thread = threading.Thread(
            target=_geoport_location_worker_entry,
            name="DPortLocationWorker",
            daemon=True,
        )
        location_worker_thread.start()

        # On the first request, wait until LocationSimulation.set() has actually
        # completed (or failed), rather than merely queueing the command.
        location_command_queue.put((latitude, longitude))

        if not location_worker_ready.wait(timeout=15):
            location_worker_error = "LocationSimulation 初始化逾時"
            logger.error(location_worker_error)
            return False

        if location_worker_error:
            logger.error(f"LocationSimulation 初始化/定位失敗: {location_worker_error}")
            return False

        return True

    # Reuse the active tunnel/session; wait until the device-side set() call
    # has actually completed before reporting success.
    location_worker_error = None
    command_done = threading.Event()
    result_box = {"success": False, "error": None}
    location_command_queue.put((latitude, longitude, command_done, result_box))

    if not command_done.wait(timeout=15):
        location_worker_error = "LocationSimulation 套用座標逾時"
        logger.error(location_worker_error)
        return False

    if not result_box.get("success"):
        location_worker_error = result_box.get("error") or "LocationSimulation 套用座標失敗"
        logger.error(location_worker_error)
        return False

    return True


# Function to stop the location thread
def stop_set_location_thread():
    global location_worker_thread, location_worker_stop, location_worker_error

    # Clear any previous command error. A stop request should report only the
    # result of the clear() operation being performed now.
    location_worker_error = None
    location_worker_stop.set()
    try:
        location_command_queue.put_nowait("STOP")
    except Exception:
        pass

    thread = location_worker_thread
    if thread is not None and thread.is_alive() and thread is not threading.current_thread():
        thread.join(timeout=10)
    location_worker_thread = None




@app.route('/set_location', methods=['POST'])
def set_location():
    try:
        global rsd_data, rsd_host, rsd_port
        global location
        global udid, connection_type
        global ios_version

        # Accept coordinates directly from the button request so a manually
        # typed coordinate can never be lost between the browser and backend.
        payload = request.get_json(silent=True) or {}
        if payload.get('lat') is not None and payload.get('lng') is not None:
            try:
                lat_value = float(payload['lat'])
                lng_value = float(payload['lng'])
            except (TypeError, ValueError):
                return jsonify({'error': '座標格式不正確，請使用「緯度 經度」。'}), 400
            if not (-90 <= lat_value <= 90) or not (-180 <= lng_value <= 180):
                return jsonify({'error': '座標超出有效範圍。'}), 400
            location = f"{lat_value} {lng_value}"

        if ios_version is not None and is_major_version_17_or_greater(ios_version):
            if not location:
                return jsonify({'error': '請先輸入或選擇座標，再進行模擬定位。'}), 400
            # Split the location string into latitude and longitude
            try:
                latitude, longitude = location.split()
            except (AttributeError, ValueError):
                return jsonify({'error': '座標格式不正確，請使用「緯度 經度」。'}), 400

                        success = start_set_location_thread(latitude, longitude)
            if success:
                return 'Location set successfully'
            if location_worker_error == PASSWORD_PROTECTED_LOCATION_MESSAGE:
                return PASSWORD_PROTECTED_LOCATION_MESSAGE, 423
            return jsonify({'error': location_worker_error or 'Location set failed'}), 500

        elif ios_version is not None and not is_major_version_17_or_greater(ios_version):
            global lockdown
            if not location:
                return jsonify({'error': '請先輸入或選擇座標，再進行模擬定位。'}), 400
            # Split the location string into latitude and longitude
            try:
                latitude, longitude = location.split()
            except (AttributeError, ValueError):
                return jsonify({'error': '座標格式不正確，請使用「緯度 經度」。'}), 400

            mount_developer_image()
                        success = start_set_location_thread(latitude, longitude)
            if success:
                return 'Location set successfully'
            if location_worker_error == PASSWORD_PROTECTED_LOCATION_MESSAGE:
                return PASSWORD_PROTECTED_LOCATION_MESSAGE, 423
            return jsonify({'error': location_worker_error or 'Location set failed'}), 500

        else:
            # Invalid ios_version
            return jsonify({'error': 'No iOS version present'})

    except Exception as e:
        if is_device_locked_error(e):
            return jsonify({
                'error': PASSWORD_PROTECTED_LOCATION_MESSAGE,
                'error_type': 'PasswordProtected'
            }), 423
        logger.exception("Set location failed: %s", e)
        return jsonify({'error': str(e)}), 500


@app.route('/stop_location', methods=['POST'])
async def stop_location():
    try:
        stop_set_location_thread()
        if location_worker_error:
            if location_worker_error == PASSWORD_PROTECTED_LOCATION_MESSAGE:
                return jsonify({
                    'error': PASSWORD_PROTECTED_LOCATION_MESSAGE,
                    'error_type': 'PasswordProtected'
                }), 423
            return jsonify({'error': location_worker_error}), 500
        return 'Location cleared successfully'
    except Exception as e:
        logger.exception("Error stopping location: %s",e)
        if "PasswordProtected" in str(e):
            return jsonify({
                'error': PASSWORD_PROTECTED_LOCATION_MESSAGE,
                'error_type': 'PasswordProtected'
            }), 423
        return jsonify({'error':str(e)})


@app.route('/usb_presence')
def usb_presence():
    """Lightweight USB presence check for automatic re-enumeration.

    This intentionally avoids opening a Lockdown/usbmux client. After a cable
    replug, Windows/usbmux may expose the raw USB device before the higher-level
    device information service is ready.
    """
    try:
        devices = asyncio.run(list_devices())
        result = []
        for device in devices:
            serial = getattr(device, 'serial', None)
            if serial:
                result.append({
                    'Identifier': serial,
                    'ConnectionType': getattr(device, 'connection_type', 'USB') or 'USB'
                })
        return jsonify({'devices': result})
    except Exception as exc:
        logger.warning(f"USB presence check failed: {exc}")
        return jsonify({'devices': [], 'error': str(exc)}), 200


@app.route('/list_devices')
def py_list_devices():
    force_refresh = request.args.get('force', '') == '1'
    """List both USB and Wi-Fi/Network devices.

    USB devices are returned from usbmuxd.  Wi-Fi devices are discovered
    through Apple's mobdev2 Bonjour service.  This is the missing piece that
    prevents a previously paired iPhone from appearing after the USB cable
    is removed.
    """
    try:
        connected_devices = {}

        def add_device(serial, conn_type, info):
            if not serial:
                return
            connected_devices.setdefault(serial, {}).setdefault(conn_type, []).append(info)

        async def collect_devices():
            # USB devices
            try:
                usb_devices = []
                attempts = 6 if force_refresh else 1

                for attempt in range(attempts):
                    try:
                        usb_devices = await list_devices()
                        logger.info(
                            f"Raw USB Devices (attempt {attempt + 1}/{attempts}): {usb_devices}"
                        )
                    except Exception as exc:
                        logger.warning(
                            f"USB enumeration attempt {attempt + 1}/{attempts} failed: {exc}"
                        )
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
                        # The raw usbmux device is already present. Do not hide it
                        # from the selector just because Lockdown metadata is still
                        # temporarily unavailable after a USB replug.
                        fallback_info = {
                            "Identifier": getattr(device, "serial", None),
                            "ConnectionType": getattr(device, "connection_type", "USB") or "USB",
                            "DeviceName": "Apple 裝置",
                            "DeviceClass": "Apple 裝置",
                            "ProductVersion": "?",
                            "wifiAddress": None,
                            "wifiPort": None,
                            "wifiState": False,
                            "userLocale": None,
                        }
                        if fallback_info["Identifier"]:
                            add_device(device.serial, device.connection_type, fallback_info)
            except Exception as exc:
                logger.warning(f"USB enumeration failed: {exc}")

            # USB-ONLY: Wi-Fi / Network discovery intentionally disabled.
            logger.info("USB-ONLY mode: Wi-Fi/Bonjour/mDNS/RemotePairing discovery skipped")

        asyncio.run(collect_devices())
        logger.info(f"Connected Devices: {connected_devices}")
        return jsonify(connected_devices)

    except Exception as e:
        logger.exception(f"Error listing devices: {e}")
        return jsonify({"error": str(e)}), 500



def clear_geoport():
    logger.info("clear any DPort instances")
    substring = "DPort"

    for process in psutil.process_iter(['pid', 'name']):
        if substring in process.info['name']:
            logger.info(f"Found process: {process.info['pid']} - {process.info['name']}")

            # Terminate the process
            process.terminate()
    else:
        logger.warning("No GeoPort found")


def shutdown_server(preserve_updater=False):
    logger.warning("shutdown server")
    try:
        asyncio.run(stop_location())
    except Exception as exc:
        logger.warning(f"Unable to stop location during shutdown: {exc}")

    stop_set_location_thread()

    # Do not call the Flask route function directly here; it uses jsonify(),
    # which requires an application/request context. Set the underlying flag.
    global terminate_tunnel_thread
    terminate_tunnel_thread = True

    cancel_async_tasks()
    terminate_threads()


    # During an update, the standalone updater must survive this shutdown.
    if not preserve_updater:
        clear_geoport()

    logger.error("OS Kill")
    os.kill(os.getpid(), signal.SIGINT)
    list_threads()
    terminate_threads()
    logger.error("sys exit")
    os._exit(0)


def terminate_threads():
    """
    Terminate all threads.
    """
    for thread in threading.enumerate():
        if thread != threading.main_thread():
            logger.info(f"thread: {thread}")
            terminate_flag = threading.Event()
            terminate_flag.set()
            
def list_threads():
    """
    Terminate all threads.
    """
    for thread in threading.enumerate():
        logger.info(f"thread: {thread}")
def cancel_async_tasks():
    try:
                tasks = asyncio.all_tasks()
        for task in tasks:
            logger.info(f"task: {task}")
            task.cancel()
    except RuntimeError as e:
        if "no running event loop" in str(e):
            logger.error("No running event loop found.")
        else:
            raise e  # Re-raise the error if it's not related to the event loop



@app.route('/exit', methods=['POST'])
def exit_app():
    logger.warning("Exit DPort")
    # Let the browser receive the response/beacon before the process exits.
    def delayed_shutdown():
        time.sleep(0.10)
        shutdown_server()

    threading.Thread(target=delayed_shutdown, daemon=True).start()
    return jsonify({"success": True, "message": "DPort is shutting down..."})


@app.route('/pymobiledevice3/status')
def pymobiledevice3_status():
    try:
        from dport_release_updater import get_status
        return jsonify(get_status())
    except Exception as exc:
        return jsonify({
            "state": "error",
            "message": str(exc),
            "current_version": None,
            "latest_version": None,
        })

@app.route('/')
def index():
    fetch_api_data(api_url)
    user_locale = get_user_country()
    logger.info(f"Country: {user_locale}")
    logger.info(f"Current platform: {platform}")
    logger.info(f"App Version = {APP_VERSION_NUMBER}")
    logger.info(f"base dir =  {base_directory}")

    return render_template(
        'map.html',
        user_locale=user_locale,
        app_version_num=DISPLAY_VERSION,
        app_version_type=APP_VERSION_TYPE,
        error_message=error_message,
        current_platform=platform,
        sudo_message=sudo_message,
    )

def open_browser():
    time.sleep(2)  # Wait for the Flask app to start
        browser = webbrowser.get()
    browser.open(f'http://localhost:{chosen_port}')


def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0
    # with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    #     try:
            #     except OSError:
    

# Define try_bind_listener_on_free_port function
def try_bind_listener_on_free_port():
    global chosen_port
    min_port = 49215
    max_port = 65535

    # Check if --port argument is provided
    if args.port:
        chosen_port = args.port
    else:
        chosen_port = flask_port

    if is_port_in_use(chosen_port):
        chosen_port = random.randint(min_port, max_port)
    logger.info(f'Serving: http://localhost:{chosen_port}')
    return chosen_port


# DPort user-confirmed updater endpoint: never called automatically.
@app.get("/dport/update")
def _dport_user_confirmed_update():
    try:
        try:
            os.environ["DPORT_PORT"] = str(chosen_port)
        except Exception:
            os.environ["DPORT_PORT"] = "54321"

        result = dport_release_updater.request_update()
        if isinstance(result, tuple):
            payload = result[0]
            status = result[1] if len(result) > 1 else 200
        else:
            payload = result
            status = 200

        if isinstance(payload, dict) and payload.get("ok"):
            def delayed_update_shutdown():
                time.sleep(0.8)
                shutdown_server(preserve_updater=True)
            threading.Thread(
                target=delayed_update_shutdown,
                name="DPort-update-shutdown",
                daemon=True,
            ).start()

        return (jsonify(payload) if isinstance(payload, dict) else payload), status
    except Exception as exc:
        return {"ok": False, "state": "update_failed", "message": str(exc)}, 500



if __name__ == '__main__':
        if is_windows:
        try:
            import pyi_splash

            pyi_splash.update_text('UI Loaded ...')
            logger.info("clear splash")
            pyi_splash.close()
        except:
            pass
        if not pyuac.isUserAdmin():
            import ctypes
            executable = str(Path(sys.executable).resolve())
            params = subprocess.list2cmdline(sys.argv[1:])
            result = ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                executable,
                params,
                str(Path(executable).parent),
                0,
            )
            if result <= 32:
                raise RuntimeError(f"Hidden elevation failed: {result}")
            raise SystemExit(0)

    chosen_port = try_bind_listener_on_free_port()

    # Check if --no-browser flag is provided
    if not args.no_browser:
        open_browser()
    else:
        logger.info("--no-browser flag passed")
        logger.info("Running without auto-browser popup")



    
    app.run(debug=True, use_reloader=False, port=chosen_port, host='0.0.0.0')




