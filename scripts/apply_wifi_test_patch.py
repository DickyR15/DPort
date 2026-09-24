from pathlib import Path
import re

main = Path("src/main.py")
text = main.read_text(encoding="utf-8")

old_wifi = """    # USB-ONLY: Wi-Fi / Network discovery intentionally disabled.
    logger.info("USB-ONLY mode: Wi-Fi/Bonjour/mDNS/RemotePairing discovery skipped")
"""
new_wifi = """    # Wi-Fi / Network discovery: Apple mobdev2 Bonjour over the local LAN.
    # A USB pairing is required first; pymobiledevice3 v11.18.x can match the
    # Bonjour advertisement to the host's existing pair records.
    try:
        async def collect_network_devices():
            found = []
            async for ip, device in get_mobdev2_lockdowns(
                udid=None,
                pair_records=get_home_folder(),
                only_paired=True,
                timeout=timeout,
            ):
                try:
                    info = dict(device.short_info)
                    device_udid = (
                        getattr(device, "udid", None)
                        or info.get("UniqueDeviceID")
                        or info.get("Identifier")
                    )
                    if not device_udid:
                        continue
                    info["Identifier"] = device_udid
                    info["ConnectionType"] = "Network"
                    info["wifiAddress"] = str(ip)
                    info["wifiPort"] = 62078
                    info["wifiState"] = True
                    try:
                        info["userLocale"] = get_user_country()
                    except Exception:
                        info["userLocale"] = None
                    found.append((device_udid, info))
                finally:
                    try:
                        await device.close()
                    except Exception:
                        pass
            return found

        network_devices = asyncio.run(collect_network_devices())
        for device_udid, info in network_devices:
            add_device(device_udid, "Network", info)
        logger.info(
            f"Wi-Fi/mobdev2 discovery: {len(network_devices)} paired network device(s) found"
        )
    except Exception as exc:
        logger.warning(f"Wi-Fi/mobdev2 discovery failed: {exc}")
"""
if old_wifi not in text:
    raise SystemExit("Wi-Fi discovery placeholder not found")
text = text.replace(old_wifi, new_wifi, 1)

old_reject = '''    if connection_type != "USB":
        logger.warning(f"USB-ONLY build: rejecting non-USB connection type: {connection_type}")
        return jsonify({"error": "USB-only mode: please connect the iPhone by USB."}), 400

'''
new_reject = '''    if connection_type not in ("USB", "Network", "Manual"):
        logger.warning(f"Unsupported connection type: {connection_type}")
        return jsonify({"error": f"Unsupported connection type: {connection_type}"}), 400

'''
if old_reject not in text:
    raise SystemExit("USB-only connect guard not found")
text = text.replace(old_reject, new_reject, 1)

old_network = '''    if connection_type == "Network":
        check_pair_record(udid)
        if pair_record is None:
            logger.error("Network: No Remote Pair Record Found. Please connect once by USB first.")
            return jsonify({"Error": "No Pair Record Found"})
        return connect_wifi(data)
'''
new_network = '''    if connection_type == "Network":
        # Wi-Fi uses the host's normal lockdown pair record via mobdev2.
        # Do not require the separate RemotePairing record.
        return connect_wifi(data)
'''
if old_network not in text:
    raise SystemExit("Network connection block not found")
text = text.replace(old_network, new_network, 1)

# When a USB device is listed, turn on Apple's normal Wi-Fi lockdown transport.
old_state = '''                            try:
                                info["wifiState"] = await client.get_enable_wifi_connections()
                            except Exception:
                                info["wifiState"] = False
'''
new_state = '''                            try:
                                info["wifiState"] = await client.get_enable_wifi_connections()
                                if not info["wifiState"]:
                                    logger.info(
                                        f"Wi-Fi lockdown disabled for {device.serial}; enabling it via USB."
                                    )
                                    await client.set_enable_wifi_connections(True)
                                    await asyncio.sleep(1.0)
                                    info["wifiState"] = await client.get_enable_wifi_connections()
                            except Exception as exc:
                                logger.warning(
                                    f"Wi-Fi lockdown state/enable check failed for {device.serial}: {exc}"
                                )
                                info["wifiState"] = False
'''
if old_state not in text:
    raise SystemExit("Wi-Fi state block not found")
text = text.replace(old_state, new_state, 1)

main.write_text(text, encoding="utf-8")

# Keep the patch idempotent.
print("Applied Wi-Fi test patch:")
print("- Enables Wi-Fi lockdown transport while USB-connected")
print("- Enumerates paired Wi-Fi devices via mobdev2 Bonjour")
print("- Allows Network connections without a RemotePairing record")
print("- Reuses the existing Wi-Fi tunnel implementation")
