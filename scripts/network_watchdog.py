#!/usr/bin/env python3
"""
S6 Network Watchdog — Continuous network monitoring daemon.
Monitors: new devices, ADB exposure, Dragonslayer activity, security ports.
Alerts Commander via iMessage/notification on security events.

Usage:
    python3 network_watchdog.py              # Run once (quick check)
    python3 network_watchdog.py --daemon     # Run continuously (every 5 min)
    python3 network_watchdog.py --dragonslayer  # Focus on Dragonslayer monitoring
"""

import subprocess
import sys
import os
import json
import time
import re
from datetime import datetime

# Add scripts dir to path for imports
SCRIPTS_DIR = os.path.expanduser("~/Documents/S6_COMMS_TECH/scripts")
sys.path.insert(0, SCRIPTS_DIR)

from s6_alert import alert, CRITICAL, HIGH, MEDIUM, LOW, INFO

# Configuration
SCAN_INTERVAL = 300  # 5 minutes between scans in daemon mode
REGISTRY_FILE = os.path.join(SCRIPTS_DIR, "network_device_registry.json")
WATCHDOG_LOG = os.path.join(SCRIPTS_DIR, "watchdog_logs")

# Known critical devices — set via env vars or .env file
DRAGONSLAYER_IP = os.environ.get("DRAGONSLAYER_IP", "192.168.7.148")
DRAGONSLAYER_MAC = os.environ.get("DRAGONSLAYER_MAC", "dc:46:28:34:f5:e9")
ADB_DEVICE_IP = os.environ.get("ADB_DEVICE_IP", "192.168.4.64")

# Dangerous ports to check
SECURITY_PORTS = {
    22: "SSH", 23: "Telnet", 445: "SMB", 3389: "RDP",
    5555: "ADB", 5900: "VNC", 8080: "HTTP-Proxy", 8443: "HTTPS-Alt"
}

def ensure_dirs():
    os.makedirs(WATCHDOG_LOG, exist_ok=True)

def run_cmd(cmd, timeout=10):
    """Run a shell command and return stdout."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, Exception):
        return ""

def get_arp_devices():
    """Get current devices from ARP table."""
    output = run_cmd("arp -a")
    devices = {}
    for line in output.split("\n"):
        match = re.search(r'\((\d+\.\d+\.\d+\.\d+)\)\s+at\s+([0-9a-f:]+)', line)
        if match:
            ip, mac = match.group(1), match.group(2)
            if mac != "(incomplete)" and ip not in devices:
                devices[ip] = mac
    return devices

def normalize_mac(mac):
    """Normalize MAC for comparison — ARP table doesn't zero-pad hex bytes."""
    if not mac or mac in ["(incomplete)", "incomplete", "unknown", "randomized"]:
        return mac.lower() if mac else ""
    parts = mac.lower().split(":")
    return ":".join(p.lstrip("0") or "0" for p in parts)

def load_registry():
    """Load known device registry."""
    try:
        with open(REGISTRY_FILE, "r") as f:
            data = json.load(f)
        known_macs = set()
        known_ips = set()
        for dev in data.get("devices", []):
            if dev.get("mac"):
                known_macs.add(normalize_mac(dev["mac"]))
            if dev.get("ip"):
                known_ips.add(dev["ip"])
        return known_macs, known_ips, data.get("devices", [])
    except Exception:
        return set(), set(), []

def check_port(ip, port, timeout=1):
    """Check if a specific port is open."""
    result = run_cmd(f"nc -z -w{timeout} {ip} {port} 2>/dev/null && echo OPEN || echo CLOSED", timeout=timeout+2)
    return "OPEN" in result

def check_new_devices(current_devices, known_macs):
    """Check for unknown devices on the network."""
    alerts = []
    for ip, mac in current_devices.items():
        # Skip multicast/broadcast addresses
        if ip.startswith("224.") or ip.startswith("239.") or ip.endswith(".255"):
            continue
        normalized = normalize_mac(mac)
        if normalized not in known_macs:
            # Check if it's a randomized MAC (locally administered bit)
            try:
                first_byte = int(mac.split(":")[0], 16)
                is_random = bool(first_byte & 0x02)
            except ValueError:
                is_random = True
            if not is_random:
                # Non-randomized unknown MAC = potentially concerning
                alerts.append({
                    "severity": MEDIUM,
                    "subject": f"Unknown device: {ip}",
                    "body": f"New non-randomized MAC device detected. IP: {ip}, MAC: {mac}. Not in device registry. Investigate."
                })
    return alerts

def check_adb_exposure():
    """Check if ADB is still exposed on known device."""
    if check_port(ADB_DEVICE_IP, 5555):
        return {
            "severity": HIGH,
            "subject": "ADB Still Exposed",
            "body": f"Android Debug Bridge (port 5555) is STILL OPEN on {ADB_DEVICE_IP}. This allows full remote control of the device. Disable ADB in Developer Options immediately."
        }
    return None

def check_dragonslayer():
    """Monitor Dragonslayer for security concerns."""
    findings = []

    # Check if online (responds to ARP)
    arp_output = run_cmd(f"arp -a | grep {DRAGONSLAYER_IP}")
    is_online = DRAGONSLAYER_MAC in arp_output.lower() if arp_output else False

    if not is_online:
        return [{"severity": INFO, "subject": "Dragonslayer Offline",
                 "body": f"Dragonslayer ({DRAGONSLAYER_IP}) is not responding. May be powered off."}]

    # Check dangerous ports
    for port, service in SECURITY_PORTS.items():
        if check_port(DRAGONSLAYER_IP, port, timeout=1):
            findings.append({
                "severity": HIGH if port in [23, 5555, 445] else MEDIUM,
                "subject": f"Dragonslayer: {service} port {port} OPEN",
                "body": f"Rylan's PC (Dragonslayer) has {service} (port {port}) open. This could indicate unauthorized services or configuration changes."
            })

    # Check gaming-specific ports
    gaming_ports = {25565: "Minecraft Server", 27015: "Steam Server", 7777: "Game Server",
                    19132: "Minecraft Bedrock", 3074: "Xbox Live"}
    for port, service in gaming_ports.items():
        if check_port(DRAGONSLAYER_IP, port, timeout=1):
            findings.append({
                "severity": LOW,
                "subject": f"Dragonslayer: {service} (port {port})",
                "body": f"Gaming service detected on Dragonslayer: {service}. Port {port} is open. This is expected for gaming but verify it's authorized."
            })

    return findings

def check_all_devices_security(current_devices):
    """Quick security scan of all active devices."""
    findings = []
    critical_ports = [23, 5555, 445, 3389]  # Only check most dangerous

    for ip, mac in current_devices.items():
        # Skip EERO nodes and this MacBook
        if ip.startswith("192.168.4.1") or ip == "192.168.7.85":
            continue
        for port in critical_ports:
            if check_port(ip, port, timeout=1):
                findings.append({
                    "severity": HIGH if port == 5555 else MEDIUM,
                    "subject": f"Open port {port} on {ip}",
                    "body": f"Security-sensitive port {port} ({SECURITY_PORTS.get(port, 'Unknown')}) detected open on {ip} (MAC: {mac}). Investigate immediately."
                })
    return findings

def check_vpn_status():
    """Verify ExpressVPN is running."""
    output = run_cmd("ps aux | grep -i expressvpn | grep -v grep | wc -l")
    try:
        count = int(output.strip())
        if count == 0:
            return {"severity": HIGH, "subject": "VPN Down", "body": "ExpressVPN is not running. Network traffic is unprotected."}
    except ValueError:
        pass
    return None

def check_dns_integrity():
    """Verify DNS is still set to Cloudflare on the Wi-Fi interface."""
    # Use networksetup (interface-level) not scutil (which includes Tailscale/VPN resolvers)
    output = run_cmd("networksetup -getdnsservers Wi-Fi")
    if "1.1.1.1" not in output and "1.0.0.1" not in output:
        return {"severity": HIGH, "subject": "DNS Changed",
                "body": f"Wi-Fi DNS is no longer Cloudflare (1.1.1.1). Current: {output[:200]}"}
    return None

def run_watchdog_cycle():
    """Execute one full monitoring cycle."""
    ensure_dirs()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    all_findings = []

    print(f"\n[{timestamp}] S6 Watchdog — Starting scan cycle...")

    # 1. Get current network state
    current_devices = get_arp_devices()
    known_macs, known_ips, registry = load_registry()
    print(f"  Devices on network: {len(current_devices)}")

    # 2. Check for new/unknown devices
    new_device_alerts = check_new_devices(current_devices, known_macs)
    all_findings.extend(new_device_alerts)

    # 3. ADB exposure check
    adb_finding = check_adb_exposure()
    if adb_finding:
        all_findings.append(adb_finding)

    # 4. Dragonslayer monitoring
    dragon_findings = check_dragonslayer()
    all_findings.extend(dragon_findings)

    # 5. VPN status
    vpn_finding = check_vpn_status()
    if vpn_finding:
        all_findings.append(vpn_finding)

    # 6. DNS integrity
    dns_finding = check_dns_integrity()
    if dns_finding:
        all_findings.append(dns_finding)

    # Report findings
    critical_count = sum(1 for f in all_findings if f["severity"] == CRITICAL)
    high_count = sum(1 for f in all_findings if f["severity"] == HIGH)
    medium_count = sum(1 for f in all_findings if f["severity"] == MEDIUM)

    if critical_count > 0 or high_count > 0:
        for finding in all_findings:
            if finding["severity"] in [CRITICAL, HIGH]:
                alert(finding["severity"], finding["subject"], finding["body"])
    elif medium_count > 0:
        for finding in all_findings:
            if finding["severity"] == MEDIUM:
                alert(finding["severity"], finding["subject"], finding["body"], send_text=False)

    # Log cycle results
    log_entry = {
        "timestamp": timestamp,
        "devices_online": len(current_devices),
        "findings": len(all_findings),
        "critical": critical_count,
        "high": high_count,
        "medium": medium_count,
        "details": all_findings
    }
    log_file = os.path.join(WATCHDOG_LOG, f"watchdog_{datetime.now().strftime('%Y-%m-%d')}.jsonl")
    with open(log_file, "a") as f:
        f.write(json.dumps(log_entry) + "\n")

    # Summary
    if critical_count + high_count + medium_count == 0:
        print(f"  Status: GREEN — No security concerns detected")
    else:
        print(f"  Status: {'RED' if critical_count > 0 else 'AMBER'}")
        print(f"  Findings: {critical_count} CRITICAL, {high_count} HIGH, {medium_count} MEDIUM")
        for f in all_findings:
            if f["severity"] not in [INFO]:
                print(f"    [{f['severity']}] {f['subject']}")

    return all_findings

def daemon_mode():
    """Run continuously, scanning every SCAN_INTERVAL seconds."""
    print(f"S6 Network Watchdog — DAEMON MODE")
    print(f"Scan interval: {SCAN_INTERVAL}s ({SCAN_INTERVAL//60}min)")
    print(f"Monitoring: {DRAGONSLAYER_IP} (Dragonslayer), {ADB_DEVICE_IP} (ADB device)")
    print(f"Alerts to: Commander (iMessage + notification)")
    print(f"Press Ctrl+C to stop\n")

    cycle = 0
    while True:
        try:
            cycle += 1
            print(f"{'='*50}")
            print(f"Cycle #{cycle}")
            run_watchdog_cycle()
            print(f"Next scan in {SCAN_INTERVAL//60} minutes...")
            time.sleep(SCAN_INTERVAL)
        except KeyboardInterrupt:
            print("\nWatchdog stopped by user.")
            break

def dragonslayer_focus():
    """Focused monitoring on Dragonslayer only."""
    print("S6 Watchdog — DRAGONSLAYER FOCUS MODE")
    print(f"Target: {DRAGONSLAYER_IP} ({DRAGONSLAYER_MAC})")

    findings = check_dragonslayer()
    for f in findings:
        print(f"  [{f['severity']}] {f['subject']}: {f['body']}")
        if f["severity"] in [CRITICAL, HIGH]:
            alert(f["severity"], f["subject"], f["body"])

    if not findings or all(f["severity"] == INFO for f in findings):
        print("  Dragonslayer: No security concerns (may be offline)")

if __name__ == "__main__":
    if "--daemon" in sys.argv:
        daemon_mode()
    elif "--dragonslayer" in sys.argv:
        dragonslayer_focus()
    else:
        run_watchdog_cycle()
