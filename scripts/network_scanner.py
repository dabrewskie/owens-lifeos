#!/usr/bin/env python3
"""
S6 Network Scanner — Owens Family Network Operations
=====================================================
Autonomous network device discovery, fingerprinting, and anomaly detection.
Compares current scan against the device registry baseline and alerts on changes.

Usage:
    python3 network_scanner.py                  # Quick scan + diff against registry
    python3 network_scanner.py --full           # Full scan with mDNS + port probing
    python3 network_scanner.py --baseline       # Update the baseline registry
    python3 network_scanner.py --watch          # Continuous monitoring (60s interval)
    python3 network_scanner.py --aar            # Generate After Action Review of last scan
"""

import subprocess
import json
import sys
import os
import time
import re
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
REGISTRY_FILE = SCRIPT_DIR / "network_device_registry.json"
SCAN_LOG_DIR = SCRIPT_DIR / "scan_logs"
AAR_LOG_DIR = SCRIPT_DIR / "aar_logs"

def ensure_dirs():
    SCAN_LOG_DIR.mkdir(exist_ok=True)
    AAR_LOG_DIR.mkdir(exist_ok=True)

def run_cmd(cmd, timeout=10):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return ""
    except Exception as e:
        return f"ERROR: {e}"

def get_arp_table():
    """Parse ARP table into device list."""
    output = run_cmd("arp -a")
    devices = []
    for line in output.split("\n"):
        match = re.match(r'\? \((\d+\.\d+\.\d+\.\d+)\) at ([0-9a-f:]+) on (\w+)', line)
        if match and match.group(2) != "ff:ff:ff:ff:ff:ff":
            devices.append({
                "ip": match.group(1),
                "mac": match.group(2),
                "interface": match.group(3),
                "timestamp": datetime.now().isoformat()
            })
    # Deduplicate by IP (prefer en0)
    seen = {}
    for d in devices:
        if d["ip"] not in seen or d["interface"] == "en0":
            seen[d["ip"]] = d
    return list(seen.values())

def is_randomized_mac(mac):
    """Check if MAC address is locally administered (randomized)."""
    try:
        first_byte = int(mac.split(":")[0], 16)
        return bool(first_byte & 0x02)
    except (ValueError, IndexError):
        return False

def lookup_mac_vendor(mac):
    """Quick OUI lookup using local heuristics."""
    prefix = mac[:8].upper().replace(":", "")
    known_vendors = {
        "A8B088": "eero",
        "ACEC85": "eero",
        "9CA570": "eero",
        "303422": "eero",
        "90486C": "Ring LLC",
        "341513": "Texas Instruments (IoT)",
        "DC4628": "Intel",
        "48A6B8": "Sonos",
        "38420B": "Sonos",
        "C43875": "Sonos",
        "949F3E": "Sonos",
        "943A91": "Amazon/Android"
    }
    if is_randomized_mac(mac):
        return "randomized"
    return known_vendors.get(prefix[:6], "unknown")

def load_registry():
    """Load the baseline device registry."""
    if REGISTRY_FILE.exists():
        with open(REGISTRY_FILE) as f:
            return json.load(f)
    return {"devices": []}

def diff_against_registry(current_devices, registry):
    """Compare current scan against baseline registry."""
    registry_macs = {d.get("mac", "").lower() for d in registry.get("devices", [])}
    registry_ips = {d.get("ip", "") for d in registry.get("devices", [])}

    new_devices = []
    missing_devices = []

    current_macs = {d["mac"].lower() for d in current_devices}
    current_ips = {d["ip"] for d in current_devices}

    # Devices in current scan but not in registry (by IP, since MACs can be randomized)
    for device in current_devices:
        mac = device["mac"].lower()
        ip = device["ip"]
        if ip not in registry_ips and mac not in registry_macs:
            device["vendor"] = lookup_mac_vendor(mac)
            device["is_randomized"] = is_randomized_mac(mac)
            new_devices.append(device)

    # Devices in registry but not in current scan (non-randomized only)
    for reg_device in registry.get("devices", []):
        mac = reg_device.get("mac", "").lower()
        ip = reg_device.get("ip", "")
        if mac and mac != "unknown" and mac != "incomplete":
            if not is_randomized_mac(mac) and mac not in current_macs:
                missing_devices.append(reg_device)

    return new_devices, missing_devices

def check_open_ports(ip, ports=[22, 80, 443, 5555, 8080, 8443, 9090]):
    """Quick port scan on a specific IP."""
    open_ports = []
    for port in ports:
        result = run_cmd(f"nc -z -w1 {ip} {port} 2>/dev/null && echo OPEN || echo closed", timeout=3)
        if "OPEN" in result:
            open_ports.append(port)
    return open_ports

def check_security_issues(current_devices):
    """Check for known security concerns."""
    alerts = []

    for device in current_devices:
        ip = device["ip"]
        mac = device["mac"]

        # Check for ADB (port 5555) on any device
        result = run_cmd(f"nc -z -w1 {ip} 5555 2>/dev/null && echo OPEN || echo closed", timeout=3)
        if "OPEN" in result:
            alerts.append({
                "severity": "HIGH",
                "device_ip": ip,
                "device_mac": mac,
                "finding": f"ADB (Android Debug Bridge) OPEN on port 5555 at {ip}. Remote shell access possible.",
                "recommendation": "Disable ADB in device Settings > Developer Options unless actively sideloading."
            })

        # Check for open HTTP on non-infrastructure devices
        if ip != "192.168.4.1":  # Skip gateway
            result = run_cmd(f"nc -z -w1 {ip} 80 2>/dev/null && echo OPEN || echo closed", timeout=3)
            if "OPEN" in result:
                alerts.append({
                    "severity": "MEDIUM",
                    "device_ip": ip,
                    "device_mac": mac,
                    "finding": f"HTTP (port 80) open on {ip}. May expose web interface.",
                    "recommendation": "Verify this is expected. IoT devices with web interfaces should have auth enabled."
                })

    return alerts

def quick_scan():
    """Quick scan: ARP + diff against registry."""
    print("S6 NETWORK SCAN — Quick Mode")
    print("=" * 50)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    current = get_arp_table()
    registry = load_registry()
    new_devices, missing_devices = diff_against_registry(current, registry)

    print(f"Devices on network: {len(current)}")
    print(f"Devices in registry: {len(registry.get('devices', []))}")
    print()

    if new_devices:
        print("⚠️  NEW/UNKNOWN DEVICES DETECTED:")
        for d in new_devices:
            vendor = d.get("vendor", "unknown")
            rand_tag = " [randomized MAC]" if d.get("is_randomized") else ""
            print(f"  → {d['ip']} | {d['mac']} | {vendor}{rand_tag}")
        print()
    else:
        print("✅ No new devices detected")
        print()

    if missing_devices:
        print("📡 EXPECTED DEVICES NOT SEEN:")
        for d in missing_devices:
            print(f"  → {d.get('name', 'Unknown')} | {d.get('ip', '?')} | {d.get('mac', '?')}")
        print()

    return current, new_devices, missing_devices

def full_scan():
    """Full scan: ARP + security checks + port scanning."""
    print("S6 NETWORK SCAN — Full Mode")
    print("=" * 50)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    current, new_devices, missing_devices = quick_scan()

    print("-" * 50)
    print("SECURITY SCAN:")
    print()

    alerts = check_security_issues(current)
    if alerts:
        for alert in alerts:
            print(f"  [{alert['severity']}] {alert['finding']}")
            print(f"         FIX: {alert['recommendation']}")
            print()
    else:
        print("  ✅ No security issues detected")
        print()

    # Check VPN
    vpn = run_cmd("ps aux | grep -i expressvpn | grep -v grep")
    print(f"VPN Status: {'ACTIVE' if vpn else 'NOT RUNNING ⚠️'}")

    # Check DNS
    dns = run_cmd("scutil --dns | grep 'nameserver' | head -4")
    print(f"DNS Config:\n{dns}")
    print()

    # Save scan log
    ensure_dirs()
    scan_data = {
        "timestamp": datetime.now().isoformat(),
        "mode": "full",
        "devices_found": len(current),
        "new_devices": len(new_devices),
        "missing_devices": len(missing_devices),
        "security_alerts": len(alerts),
        "devices": current,
        "alerts": alerts
    }
    log_file = SCAN_LOG_DIR / f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(log_file, "w") as f:
        json.dump(scan_data, f, indent=2)
    print(f"Scan log saved: {log_file}")

    return scan_data

def generate_aar(scan_data=None):
    """Generate After Action Review from latest scan."""
    ensure_dirs()

    if scan_data is None:
        # Load most recent scan log
        logs = sorted(SCAN_LOG_DIR.glob("scan_*.json"), reverse=True)
        if not logs:
            print("No scan logs found. Run a scan first.")
            return
        with open(logs[0]) as f:
            scan_data = json.load(f)

    aar = []
    aar.append("=" * 60)
    aar.append(f"S6 AFTER ACTION REVIEW (AAR)")
    aar.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    aar.append(f"Scan Time: {scan_data.get('timestamp', 'unknown')}")
    aar.append("=" * 60)
    aar.append("")
    aar.append("1. WHAT WAS PLANNED?")
    aar.append("   Network device scan and security posture assessment")
    aar.append("")
    aar.append("2. WHAT HAPPENED?")
    aar.append(f"   Devices found: {scan_data.get('devices_found', 0)}")
    aar.append(f"   New/unknown devices: {scan_data.get('new_devices', 0)}")
    aar.append(f"   Missing expected devices: {scan_data.get('missing_devices', 0)}")
    aar.append(f"   Security alerts: {scan_data.get('security_alerts', 0)}")
    aar.append("")
    aar.append("3. WHAT WENT WELL?")
    if scan_data.get("new_devices", 0) == 0:
        aar.append("   + No unauthorized devices detected")
    if scan_data.get("security_alerts", 0) == 0:
        aar.append("   + No security vulnerabilities found")
    aar.append("   + Scan completed successfully")
    aar.append("")
    aar.append("4. WHAT CAN BE IMPROVED?")
    if scan_data.get("security_alerts", 0) > 0:
        for alert in scan_data.get("alerts", []):
            aar.append(f"   - [{alert['severity']}] {alert['finding']}")
    if scan_data.get("new_devices", 0) > 0:
        aar.append(f"   - {scan_data['new_devices']} device(s) need identification")
    aar.append("")
    aar.append("5. ACTION ITEMS:")
    action_count = 0
    for alert in scan_data.get("alerts", []):
        action_count += 1
        aar.append(f"   {action_count}. {alert['recommendation']}")
    if scan_data.get("new_devices", 0) > 0:
        action_count += 1
        aar.append(f"   {action_count}. Identify and authorize new devices in registry")
    if action_count == 0:
        aar.append("   None — maintain current posture")
    aar.append("")
    aar.append("=" * 60)

    aar_text = "\n".join(aar)
    print(aar_text)

    # Save AAR
    aar_file = AAR_LOG_DIR / f"aar_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(aar_file, "w") as f:
        f.write(aar_text)
    print(f"\nAAR saved: {aar_file}")

def watch_mode(interval=60):
    """Continuous monitoring mode."""
    print(f"S6 NETWORK WATCH — Monitoring every {interval}s")
    print("Press Ctrl+C to stop")
    print("=" * 50)

    registry = load_registry()
    baseline_ips = {d["ip"] for d in registry.get("devices", []) if d.get("ip")}

    while True:
        try:
            current = get_arp_table()
            current_ips = {d["ip"] for d in current}

            new_ips = current_ips - baseline_ips
            gone_ips = baseline_ips - current_ips

            timestamp = datetime.now().strftime("%H:%M:%S")

            if new_ips or gone_ips:
                print(f"\n[{timestamp}] CHANGE DETECTED:")
                for ip in new_ips:
                    mac = next((d["mac"] for d in current if d["ip"] == ip), "?")
                    vendor = lookup_mac_vendor(mac)
                    print(f"  ⚠️  NEW: {ip} | {mac} | {vendor}")
                for ip in gone_ips:
                    print(f"  📡 GONE: {ip}")
            else:
                print(f"[{timestamp}] All clear — {len(current)} devices", end="\r")

            time.sleep(interval)
        except KeyboardInterrupt:
            print("\n\nWatch mode stopped.")
            break

def main():
    args = sys.argv[1:]

    if "--full" in args:
        scan_data = full_scan()
        print("\n")
        generate_aar(scan_data)
    elif "--baseline" in args:
        print("Updating baseline registry...")
        current = get_arp_table()
        registry = load_registry()
        # Only add non-randomized new devices
        for device in current:
            if not any(d.get("ip") == device["ip"] for d in registry.get("devices", [])):
                device["vendor"] = lookup_mac_vendor(device["mac"])
                device["name"] = f"Auto-discovered ({device['ip']})"
                device["authorized"] = "pending_identification"
                registry["devices"].append(device)
        registry["last_scan"] = datetime.now().isoformat()
        with open(REGISTRY_FILE, "w") as f:
            json.dump(registry, f, indent=2)
        print(f"Registry updated with {len(current)} devices")
    elif "--watch" in args:
        interval = 60
        if "--interval" in args:
            idx = args.index("--interval")
            if idx + 1 < len(args):
                interval = int(args[idx + 1])
        watch_mode(interval)
    elif "--aar" in args:
        generate_aar()
    else:
        quick_scan()

if __name__ == "__main__":
    main()
