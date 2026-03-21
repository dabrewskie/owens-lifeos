#!/usr/bin/env python3
"""
security_audit.py — S6 IT Department Security Audit Tool
Runs a comprehensive security posture check on Tory's Mac.
Output is designed to be consumed by Claude for the S6 SITREP.

Usage: python3 ~/Documents/S6_COMMS_TECH/scripts/security_audit.py [--quick|--full|--network]
"""

import subprocess
import json
import sys
import os
from datetime import datetime, timedelta

def run(cmd, timeout=30):
    """Run a shell command and return stdout."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip()
    except Exception as e:
        return f"ERROR: {e}"

def check_filevault():
    out = run("fdesetup status")
    return {"name": "FileVault", "status": "ON" if "On" in out else "OFF", "detail": out}

def check_sip():
    out = run("csrutil status")
    enabled = "enabled" in out.lower()
    return {"name": "SIP", "status": "ENABLED" if enabled else "DISABLED", "detail": out}

def check_gatekeeper():
    out = run("spctl --status")
    enabled = "enabled" in out.lower()
    return {"name": "Gatekeeper", "status": "ENABLED" if enabled else "DISABLED", "detail": out}

def check_firewall():
    state = run("/usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate")
    stealth = run("/usr/libexec/ApplicationFirewall/socketfilterfw --getstealthmode")
    fw_on = ("enabled" in state.lower() or "state = 1" in state.lower()) if state else False
    stealth_on = ("enabled" in stealth.lower() or "stealth mode is on" in stealth.lower()) if stealth else False
    status = "GREEN" if (fw_on and stealth_on) else "RED" if not fw_on else "AMBER"
    return {
        "name": "Firewall",
        "status": status,
        "firewall_enabled": fw_on,
        "stealth_mode": stealth_on,
        "detail": f"Firewall: {state} | Stealth: {stealth}"
    }

def check_vpn():
    out = run("ps aux | grep -i expressvpn | grep -v grep")
    running = len(out.strip()) > 0
    return {"name": "VPN (ExpressVPN)", "status": "RUNNING" if running else "NOT RUNNING", "detail": out[:200]}

def check_xprotect():
    out = run("launchctl list | grep -i xprotect")
    running = "XProtect" in out or "Xprotect" in out
    return {"name": "XProtect", "status": "RUNNING" if running else "NOT FOUND", "detail": out}

def check_uptime():
    out = run("uptime")
    # Parse days
    days = 0
    if "day" in out:
        try:
            days = int(out.split("up")[1].split("day")[0].strip().split(",")[0])
        except:
            pass
    status = "GREEN" if days < 7 else "AMBER" if days < 14 else "RED"
    return {"name": "Uptime", "status": status, "days": days, "detail": out}

def check_disk():
    out = run("df -h /")
    lines = out.strip().split("\n")
    if len(lines) >= 2:
        parts = lines[1].split()
        avail = parts[3] if len(parts) > 3 else "unknown"
        capacity = parts[4] if len(parts) > 4 else "unknown"
        pct = int(capacity.replace("%","")) if "%" in capacity else 0
        status = "GREEN" if pct < 70 else "AMBER" if pct < 85 else "RED"
        return {"name": "Disk", "status": status, "available": avail, "used_pct": capacity, "detail": out}
    return {"name": "Disk", "status": "UNKNOWN", "detail": out}

def check_smb_sharing():
    out = run("sharing -l")
    guest = "guest access:	1" in out
    shared = "shared:	1" in out
    status = "RED" if (shared and guest) else "AMBER" if shared else "GREEN"
    return {"name": "SMB Sharing", "status": status, "guest_access": guest, "detail": out[:300]}

def check_open_ports():
    out = run("lsof -iTCP -sTCP:LISTEN -P 2>/dev/null | awk '{print $1, $9}' | sort -u")
    lines = [l for l in out.strip().split("\n") if l and l != "COMMAND NAME"]
    return {"name": "Open Ports", "count": len(lines), "ports": lines[:15], "detail": out[:500]}

def check_pending_updates():
    out = run("softwareupdate -l 2>&1", timeout=60)
    has_updates = "Software Update found" in out or "Label:" in out
    return {"name": "Pending Updates", "status": "UPDATES AVAILABLE" if has_updates else "UP TO DATE", "detail": out[:500]}

def check_time_machine():
    out = run("tmutil status")
    running = '"Running" = 1' in out
    # Check last backup
    last = run("tmutil latestbackup 2>/dev/null")
    return {
        "name": "Time Machine",
        "status": "RUNNING" if running else "NOT CONFIGURED" if "No Time Machine" in (last or "") else "IDLE",
        "last_backup": last if last else "No backup found",
        "detail": out[:300]
    }

def network_scan():
    """Scan local network for devices."""
    arp = run("arp -a")
    devices = []
    for line in arp.strip().split("\n"):
        if line and "(" in line:
            parts = line.split()
            ip = parts[1].strip("()")  if len(parts) > 1 else "unknown"
            mac = parts[3] if len(parts) > 3 else "unknown"
            iface = parts[-1] if len(parts) > 1 else "unknown"
            if mac != "(incomplete)":
                devices.append({"ip": ip, "mac": mac, "interface": iface})
    return {"name": "Network Devices", "count": len(devices), "devices": devices}

def check_bluetooth():
    out = run("system_profiler SPBluetoothDataType 2>/dev/null | grep -c 'Address:'")
    try:
        count = int(out.strip())
    except:
        count = 0
    return {"name": "Bluetooth Devices", "count": count, "status": "AMBER" if count > 8 else "GREEN"}

def check_launch_agents():
    user_agents = run("ls ~/Library/LaunchAgents/ 2>/dev/null").strip().split("\n")
    user_agents = [a for a in user_agents if a]
    system_agents = run("ls /Library/LaunchAgents/ 2>/dev/null | grep -v com.apple").strip().split("\n")
    system_agents = [a for a in system_agents if a]
    return {
        "name": "Launch Agents",
        "user_agents": user_agents,
        "third_party_system_agents": system_agents,
        "status": "AMBER" if len(user_agents) + len(system_agents) > 5 else "GREEN"
    }

def quick_audit():
    """Quick security sweep — ~30 seconds."""
    print(json.dumps({
        "audit_type": "quick",
        "timestamp": datetime.now().isoformat(),
        "checks": [
            check_filevault(),
            check_sip(),
            check_gatekeeper(),
            check_firewall(),
            check_vpn(),
            check_xprotect(),
            check_uptime(),
            check_disk(),
            check_pending_updates(),
        ]
    }, indent=2))

def full_audit():
    """Full security audit — ~60 seconds."""
    print(json.dumps({
        "audit_type": "full",
        "timestamp": datetime.now().isoformat(),
        "checks": [
            check_filevault(),
            check_sip(),
            check_gatekeeper(),
            check_firewall(),
            check_vpn(),
            check_xprotect(),
            check_uptime(),
            check_disk(),
            check_pending_updates(),
            check_smb_sharing(),
            check_open_ports(),
            check_time_machine(),
            check_bluetooth(),
            check_launch_agents(),
        ]
    }, indent=2))

def network_audit():
    """Network-focused audit."""
    print(json.dumps({
        "audit_type": "network",
        "timestamp": datetime.now().isoformat(),
        "checks": [
            check_vpn(),
            check_firewall(),
            check_open_ports(),
            check_smb_sharing(),
            network_scan(),
            check_bluetooth(),
        ]
    }, indent=2))

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "--quick"
    if mode == "--full":
        full_audit()
    elif mode == "--network":
        network_audit()
    else:
        quick_audit()
