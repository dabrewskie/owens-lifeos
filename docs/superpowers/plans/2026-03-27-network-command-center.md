# Network Command Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a persistent network monitoring engine with IDS, SQLite backend, interactive dashboard, and MCP bridge — giving the Commander full visibility and threat detection across 30 home network devices.

**Architecture:** Python HTTP server on :8085 with 5 modules (Device Intel, Traffic Analysis, IDS, Alert, Scheduler). SQLite for persistence. Upgraded network-map.html with click-to-manage device panels. MCP bridge tools for iPhone access.

**Tech Stack:** Python 3.9 (stdlib: sqlite3, http.server, subprocess, socket, struct, threading, json), nmap, tcpdump, existing s6_alert.py + remediation_tracker.py

**Spec:** `docs/superpowers/specs/2026-03-27-network-command-center-design.md`

---

## File Structure

```
~/Documents/S6_COMMS_TECH/scripts/
    network_db.py                  — SQLite schema, migrations, query helpers (NEW)
    network_device_intel.py        — ARP discovery, device identity, nmap scanning (NEW)
    network_traffic.py             — tcpdump capture, DNS logging, traffic rollups (NEW)
    network_ids_rules.py           — IDS detection rules engine (NEW)
    network_threat_intel.py        — threat feed ingestion and matching (NEW)
    network_command_center.py      — main server: HTTP API + scheduler + orchestration (NEW)
    network_device_registry.json   — existing, seed data for initial import
    s6_alert.py                    — existing, used for iMessage alerts
    remediation_tracker.py         — existing, used for closed-loop tracking
    lifeos_mcp_server.py           — MODIFY: add 4 MCP bridge tools
    lifeos_orchestrator.py         — MODIFY: add network_command_center health check task

~/Documents/S6_COMMS_TECH/dashboard/
    network-map.html               — REPLACE: full interactive dashboard with click panels
    network.db                     — SQLite database (created by network_db.py)
    network_backups/               — daily SQLite backups (NEW dir)

~/Documents/S6_COMMS_TECH/scripts/network_data/
    captures/                      — on-demand PCAP files (NEW dir)
    threat_feeds/                  — downloaded threat intel CSVs (NEW dir)

~/Library/LaunchAgents/
    com.lifeos.network-command.plist — LaunchAgent for persistence (NEW)
```

---

### Task 1: SQLite Database Layer (`network_db.py`)

**Files:**
- Create: `~/Documents/S6_COMMS_TECH/scripts/network_db.py`

This is the foundation — every other module depends on it.

- [ ] **Step 1: Create network_db.py with schema and connection management**

```python
#!/usr/bin/env python3
"""
network_db.py — SQLite database layer for Network Command Center.
Handles schema creation, migrations, and query helpers.
Database location: ~/Documents/S6_COMMS_TECH/dashboard/network.db
"""
import sqlite3
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

DB_PATH = Path.home() / "Documents" / "S6_COMMS_TECH" / "dashboard" / "network.db"
BACKUP_DIR = Path.home() / "Documents" / "S6_COMMS_TECH" / "dashboard" / "network_backups"
ICLOUD_BACKUP = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "NETWORK_BACKUPS"

SCHEMA_VERSION = 1

def get_connection():
    """Get a SQLite connection with WAL mode and foreign keys."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Create all tables and indexes if they don't exist."""
    conn = get_connection()
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY,
            mac TEXT,
            ip TEXT,
            vendor TEXT,
            name TEXT,
            hostname TEXT,
            mdns_name TEXT,
            os_guess TEXT,
            device_type TEXT,
            zone TEXT DEFAULT 'unknown',
            owner TEXT,
            authorized TEXT DEFAULT 'pending',
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            is_online INTEGER DEFAULT 0,
            is_randomized_mac INTEGER DEFAULT 0,
            notes TEXT,
            photo_path TEXT
        );

        CREATE TABLE IF NOT EXISTS scan_history (
            id INTEGER PRIMARY KEY,
            device_id INTEGER REFERENCES devices(id),
            timestamp TEXT NOT NULL,
            scan_type TEXT,
            ports_open TEXT,
            services TEXT,
            os_fingerprint TEXT,
            raw_output TEXT
        );

        CREATE TABLE IF NOT EXISTS traffic_rollups (
            id INTEGER PRIMARY KEY,
            device_id INTEGER REFERENCES devices(id),
            timestamp TEXT NOT NULL,
            bytes_in INTEGER DEFAULT 0,
            bytes_out INTEGER DEFAULT 0,
            packets INTEGER DEFAULT 0,
            top_destinations TEXT,
            protocols TEXT
        );

        CREATE TABLE IF NOT EXISTS dns_queries (
            id INTEGER PRIMARY KEY,
            device_id INTEGER REFERENCES devices(id),
            timestamp TEXT NOT NULL,
            domain TEXT NOT NULL,
            query_type TEXT,
            response_ip TEXT,
            flagged INTEGER DEFAULT 0,
            flag_reason TEXT
        );

        CREATE TABLE IF NOT EXISTS threats (
            id INTEGER PRIMARY KEY,
            device_id INTEGER REFERENCES devices(id),
            timestamp TEXT NOT NULL,
            threat_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            confidence TEXT NOT NULL,
            detail TEXT,
            response_taken TEXT,
            resolved INTEGER DEFAULT 0,
            resolved_at TEXT
        );

        CREATE TABLE IF NOT EXISTS anomalies (
            id INTEGER PRIMARY KEY,
            device_id INTEGER REFERENCES devices(id),
            timestamp TEXT NOT NULL,
            anomaly_type TEXT NOT NULL,
            baseline_value REAL,
            observed_value REAL,
            deviation_pct REAL,
            detail TEXT
        );

        CREATE TABLE IF NOT EXISTS baselines (
            id INTEGER PRIMARY KEY,
            device_id INTEGER REFERENCES devices(id),
            metric TEXT NOT NULL,
            hour_of_day INTEGER,
            day_of_week INTEGER,
            avg_value REAL,
            stddev REAL,
            sample_count INTEGER DEFAULT 0,
            updated TEXT
        );

        CREATE TABLE IF NOT EXISTS threat_intel (
            id INTEGER PRIMARY KEY,
            indicator_type TEXT NOT NULL,
            indicator_value TEXT NOT NULL,
            source TEXT,
            severity TEXT,
            added TEXT NOT NULL,
            expires TEXT
        );

        CREATE TABLE IF NOT EXISTS auto_responses (
            id INTEGER PRIMARY KEY,
            threat_id INTEGER REFERENCES threats(id),
            action TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            reversed INTEGER DEFAULT 0,
            reversed_at TEXT,
            reversed_by TEXT
        );

        CREATE TABLE IF NOT EXISTS connection_history (
            id INTEGER PRIMARY KEY,
            device_id INTEGER REFERENCES devices(id),
            event TEXT NOT NULL,
            timestamp TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS public_ip_history (
            id INTEGER PRIMARY KEY,
            ip TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            shodan_result TEXT
        );
    """)

    # Create indexes (IF NOT EXISTS handles idempotency)
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_dns_device_ts ON dns_queries(device_id, timestamp)",
        "CREATE INDEX IF NOT EXISTS idx_dns_domain ON dns_queries(domain)",
        "CREATE INDEX IF NOT EXISTS idx_dns_flagged ON dns_queries(flagged) WHERE flagged = 1",
        "CREATE INDEX IF NOT EXISTS idx_traffic_device_ts ON traffic_rollups(device_id, timestamp)",
        "CREATE INDEX IF NOT EXISTS idx_threats_device ON threats(device_id)",
        "CREATE INDEX IF NOT EXISTS idx_threats_severity ON threats(severity)",
        "CREATE INDEX IF NOT EXISTS idx_threats_unresolved ON threats(resolved) WHERE resolved = 0",
        "CREATE INDEX IF NOT EXISTS idx_scans_device ON scan_history(device_id)",
        "CREATE INDEX IF NOT EXISTS idx_anomalies_device ON anomalies(device_id)",
        "CREATE INDEX IF NOT EXISTS idx_baselines_device ON baselines(device_id, metric)",
        "CREATE INDEX IF NOT EXISTS idx_intel_value ON threat_intel(indicator_value)",
        "CREATE INDEX IF NOT EXISTS idx_connection_device ON connection_history(device_id)",
    ]
    for idx in indexes:
        c.execute(idx)

    conn.commit()
    conn.close()

# ── Query Helpers ──────────────────────────────────────────────────

def upsert_device(mac, ip, vendor=None, name=None, hostname=None, zone="unknown",
                  owner=None, authorized="pending", is_randomized_mac=False,
                  device_type=None, notes=None):
    """Insert or update a device. Returns device id."""
    conn = get_connection()
    now = datetime.now().isoformat()
    # Try to find existing by MAC first, then by IP if randomized
    row = conn.execute("SELECT id, first_seen FROM devices WHERE mac = ?", (mac,)).fetchone()
    if not row and is_randomized_mac:
        row = conn.execute("SELECT id, first_seen FROM devices WHERE ip = ? AND is_randomized_mac = 1", (ip,)).fetchone()

    if row:
        device_id = row["id"]
        conn.execute("""
            UPDATE devices SET ip=?, last_seen=?, is_online=1,
                vendor=COALESCE(?, vendor), name=COALESCE(?, name),
                hostname=COALESCE(?, hostname), zone=COALESCE(?, zone),
                owner=COALESCE(?, owner), device_type=COALESCE(?, device_type),
                notes=COALESCE(?, notes)
            WHERE id=?
        """, (ip, now, vendor, name, hostname, zone, owner, device_type, notes, device_id))
    else:
        c = conn.execute("""
            INSERT INTO devices (mac, ip, vendor, name, hostname, zone, owner, authorized,
                first_seen, last_seen, is_online, is_randomized_mac, device_type, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
        """, (mac, ip, vendor, name, hostname, zone, owner, authorized,
              now, now, 1 if is_randomized_mac else 0, device_type, notes))
        device_id = c.lastrowid

    conn.commit()
    conn.close()
    return device_id

def mark_device_offline(device_id):
    """Mark a device as offline and log the event."""
    conn = get_connection()
    now = datetime.now().isoformat()
    conn.execute("UPDATE devices SET is_online=0, last_seen=? WHERE id=?", (now, device_id))
    conn.execute("INSERT INTO connection_history (device_id, event, timestamp) VALUES (?, 'offline', ?)",
                 (device_id, now))
    conn.commit()
    conn.close()

def mark_device_online(device_id):
    """Mark device online and log."""
    conn = get_connection()
    now = datetime.now().isoformat()
    conn.execute("UPDATE devices SET is_online=1, last_seen=? WHERE id=?", (now, device_id))
    conn.execute("INSERT INTO connection_history (device_id, event, timestamp) VALUES (?, 'online', ?)",
                 (device_id, now))
    conn.commit()
    conn.close()

def get_all_devices():
    """Return all devices as list of dicts."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM devices ORDER BY zone, name").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_device(device_id):
    """Get single device by id."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM devices WHERE id=?", (device_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_device_by_ip(ip):
    """Find device by IP."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM devices WHERE ip=?", (ip,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_device_by_mac(mac):
    """Find device by MAC."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM devices WHERE mac=?", (mac,)).fetchone()
    conn.close()
    return dict(row) if row else None

def update_device(device_id, **kwargs):
    """Update device fields."""
    allowed = {"name", "zone", "owner", "authorized", "notes", "device_type",
               "os_guess", "hostname", "mdns_name", "photo_path"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    sets = ", ".join(f"{k}=?" for k in fields)
    vals = list(fields.values()) + [device_id]
    conn = get_connection()
    conn.execute(f"UPDATE devices SET {sets} WHERE id=?", vals)
    conn.commit()
    conn.close()

def insert_scan(device_id, scan_type, ports_open, services=None, os_fingerprint=None, raw_output=None):
    """Record a port scan result."""
    conn = get_connection()
    conn.execute("""
        INSERT INTO scan_history (device_id, timestamp, scan_type, ports_open, services, os_fingerprint, raw_output)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (device_id, datetime.now().isoformat(), scan_type,
          json.dumps(ports_open), json.dumps(services) if services else None,
          os_fingerprint, raw_output))
    conn.commit()
    conn.close()

def get_scans(device_id, limit=20):
    """Get scan history for a device."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM scan_history WHERE device_id=? ORDER BY timestamp DESC LIMIT ?",
        (device_id, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def insert_traffic_rollup(device_id, bytes_in, bytes_out, packets, top_destinations, protocols):
    """Insert a 5-minute traffic rollup."""
    conn = get_connection()
    conn.execute("""
        INSERT INTO traffic_rollups (device_id, timestamp, bytes_in, bytes_out, packets, top_destinations, protocols)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (device_id, datetime.now().isoformat(), bytes_in, bytes_out, packets,
          json.dumps(top_destinations), json.dumps(protocols)))
    conn.commit()
    conn.close()

def get_traffic(device_id, hours=24):
    """Get traffic rollups for a device within the last N hours."""
    conn = get_connection()
    cutoff = datetime.now().isoformat()  # simplified — proper time math in caller
    rows = conn.execute(
        "SELECT * FROM traffic_rollups WHERE device_id=? ORDER BY timestamp DESC LIMIT ?",
        (device_id, hours * 12)).fetchall()  # 12 rollups per hour (5-min intervals)
    conn.close()
    return [dict(r) for r in rows]

def insert_dns_query(device_id, domain, query_type=None, response_ip=None, flagged=False, flag_reason=None):
    """Log a DNS query."""
    conn = get_connection()
    conn.execute("""
        INSERT INTO dns_queries (device_id, timestamp, domain, query_type, response_ip, flagged, flag_reason)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (device_id, datetime.now().isoformat(), domain, query_type, response_ip,
          1 if flagged else 0, flag_reason))
    conn.commit()
    conn.close()

def get_dns_queries(device_id, limit=100, flagged_only=False):
    """Get DNS queries for a device."""
    conn = get_connection()
    sql = "SELECT * FROM dns_queries WHERE device_id=?"
    params = [device_id]
    if flagged_only:
        sql += " AND flagged=1"
    sql += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def insert_threat(device_id, threat_type, severity, confidence, detail, response_taken=None):
    """Record a detected threat."""
    conn = get_connection()
    c = conn.execute("""
        INSERT INTO threats (device_id, timestamp, threat_type, severity, confidence, detail, response_taken)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (device_id, datetime.now().isoformat(), threat_type, severity, confidence, detail, response_taken))
    threat_id = c.lastrowid
    conn.commit()
    conn.close()
    return threat_id

def get_threats(device_id=None, severity=None, unresolved_only=True, limit=50):
    """Get threats, optionally filtered."""
    conn = get_connection()
    sql = "SELECT t.*, d.name as device_name, d.ip as device_ip FROM threats t LEFT JOIN devices d ON t.device_id=d.id WHERE 1=1"
    params = []
    if device_id:
        sql += " AND t.device_id=?"
        params.append(device_id)
    if severity:
        sql += " AND t.severity=?"
        params.append(severity)
    if unresolved_only:
        sql += " AND t.resolved=0"
    sql += " ORDER BY t.timestamp DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def resolve_threat(threat_id):
    """Mark a threat as resolved."""
    conn = get_connection()
    conn.execute("UPDATE threats SET resolved=1, resolved_at=? WHERE id=?",
                 (datetime.now().isoformat(), threat_id))
    conn.commit()
    conn.close()

def get_threat_summary():
    """Get threat counts by severity."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT severity, COUNT(*) as count FROM threats WHERE resolved=0 GROUP BY severity
    """).fetchall()
    conn.close()
    return {r["severity"]: r["count"] for r in rows}

def insert_anomaly(device_id, anomaly_type, baseline_value, observed_value, deviation_pct, detail):
    """Record a behavioral anomaly."""
    conn = get_connection()
    conn.execute("""
        INSERT INTO anomalies (device_id, timestamp, anomaly_type, baseline_value, observed_value, deviation_pct, detail)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (device_id, datetime.now().isoformat(), anomaly_type, baseline_value, observed_value, deviation_pct, detail))
    conn.commit()
    conn.close()

def get_anomalies(device_id=None, limit=50):
    """Get recent anomalies."""
    conn = get_connection()
    sql = "SELECT a.*, d.name as device_name FROM anomalies a LEFT JOIN devices d ON a.device_id=d.id"
    params = []
    if device_id:
        sql += " WHERE a.device_id=?"
        params.append(device_id)
    sql += " ORDER BY a.timestamp DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def upsert_baseline(device_id, metric, hour_of_day, day_of_week, avg_value, stddev, sample_count):
    """Insert or update a baseline measurement."""
    conn = get_connection()
    now = datetime.now().isoformat()
    row = conn.execute(
        "SELECT id FROM baselines WHERE device_id=? AND metric=? AND hour_of_day=? AND day_of_week=?",
        (device_id, metric, hour_of_day, day_of_week)).fetchone()
    if row:
        conn.execute("""
            UPDATE baselines SET avg_value=?, stddev=?, sample_count=?, updated=? WHERE id=?
        """, (avg_value, stddev, sample_count, now, row["id"]))
    else:
        conn.execute("""
            INSERT INTO baselines (device_id, metric, hour_of_day, day_of_week, avg_value, stddev, sample_count, updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (device_id, metric, hour_of_day, day_of_week, avg_value, stddev, sample_count, now))
    conn.commit()
    conn.close()

def get_baseline(device_id, metric, hour_of_day, day_of_week):
    """Get baseline for a specific device/metric/time."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM baselines WHERE device_id=? AND metric=? AND hour_of_day=? AND day_of_week=?",
        (device_id, metric, hour_of_day, day_of_week)).fetchone()
    conn.close()
    return dict(row) if row else None

def insert_threat_intel(indicator_type, indicator_value, source, severity="HIGH"):
    """Add a threat intelligence indicator."""
    conn = get_connection()
    # Upsert: skip if already exists
    existing = conn.execute(
        "SELECT id FROM threat_intel WHERE indicator_value=? AND source=?",
        (indicator_value, source)).fetchone()
    if not existing:
        conn.execute("""
            INSERT INTO threat_intel (indicator_type, indicator_value, source, severity, added)
            VALUES (?, ?, ?, ?, ?)
        """, (indicator_type, indicator_value, source, severity, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def check_threat_intel(value):
    """Check if a domain/IP matches threat intel. Returns match or None."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM threat_intel WHERE indicator_value=?", (value,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_threat_intel_stats():
    """Get counts of threat intel indicators by source."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT source, indicator_type, COUNT(*) as count FROM threat_intel GROUP BY source, indicator_type"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def insert_public_ip(ip, shodan_result=None):
    """Record public IP check."""
    conn = get_connection()
    conn.execute("INSERT INTO public_ip_history (ip, timestamp, shodan_result) VALUES (?, ?, ?)",
                 (ip, datetime.now().isoformat(), json.dumps(shodan_result) if shodan_result else None))
    conn.commit()
    conn.close()

def get_latest_public_ip():
    """Get most recent public IP record."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM public_ip_history ORDER BY timestamp DESC LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else None

def get_connection_history(device_id, limit=50):
    """Get online/offline history for a device."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM connection_history WHERE device_id=? ORDER BY timestamp DESC LIMIT ?",
        (device_id, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_network_stats():
    """Aggregate network statistics."""
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) as c FROM devices").fetchone()["c"]
    online = conn.execute("SELECT COUNT(*) as c FROM devices WHERE is_online=1").fetchone()["c"]
    threats_active = conn.execute("SELECT COUNT(*) as c FROM threats WHERE resolved=0").fetchone()["c"]
    last_scan = conn.execute("SELECT MAX(timestamp) as ts FROM scan_history").fetchone()["ts"]
    intel_count = conn.execute("SELECT COUNT(*) as c FROM threat_intel").fetchone()["c"]
    conn.close()
    return {
        "total_devices": total,
        "online_devices": online,
        "offline_devices": total - online,
        "active_threats": threats_active,
        "last_scan": last_scan,
        "threat_intel_indicators": intel_count,
    }

def backup_db():
    """Backup SQLite database to local dir and iCloud."""
    if not DB_PATH.exists():
        return
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ICLOUD_BACKUP.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    local_dst = BACKUP_DIR / f"network_{ts}.db"
    icloud_dst = ICLOUD_BACKUP / f"network_{ts}.db"
    shutil.copy2(str(DB_PATH), str(local_dst))
    shutil.copy2(str(DB_PATH), str(icloud_dst))
    # Clean old local backups (keep last 7)
    backups = sorted(BACKUP_DIR.glob("network_*.db"))
    for old in backups[:-7]:
        old.unlink()
    # Clean old iCloud backups (keep last 7)
    icloud_backups = sorted(ICLOUD_BACKUP.glob("network_*.db"))
    for old in icloud_backups[:-7]:
        old.unlink()

def seed_from_registry():
    """Import devices from existing network_device_registry.json."""
    registry_path = Path.home() / "Documents" / "S6_COMMS_TECH" / "scripts" / "network_device_registry.json"
    if not registry_path.exists():
        return 0
    with open(registry_path) as f:
        data = json.load(f)
    count = 0
    for dev in data.get("devices", []):
        mac = dev.get("mac", "unknown")
        ip = dev.get("ip", "unknown")
        # Detect randomized MAC
        is_random = mac in ("randomized", "incomplete", "unknown")
        if not is_random and mac and ":" in mac:
            try:
                first_byte = int(mac.split(":")[0], 16)
                is_random = bool(first_byte & 0x02)
            except ValueError:
                is_random = True

        upsert_device(
            mac=mac, ip=ip,
            vendor=dev.get("vendor"),
            name=dev.get("name"),
            hostname=dev.get("hostname"),
            zone=dev.get("zone", "unknown"),
            owner=dev.get("owner"),
            authorized="trusted" if dev.get("authorized") is True else "pending",
            is_randomized_mac=is_random,
            device_type=dev.get("type"),
            notes=dev.get("notes"),
        )
        count += 1
    return count

if __name__ == "__main__":
    print("Initializing Network Command Center database...")
    init_db()
    count = seed_from_registry()
    print(f"Database initialized. Seeded {count} devices from registry.")
    stats = get_network_stats()
    print(f"Stats: {json.dumps(stats, indent=2)}")
```

- [ ] **Step 2: Run to initialize database and seed from registry**

Run: `cd ~/Documents/S6_COMMS_TECH/scripts && python3 network_db.py`
Expected: "Database initialized. Seeded 30 devices from registry." with stats output.

- [ ] **Step 3: Verify database created with correct tables**

Run: `sqlite3 ~/Documents/S6_COMMS_TECH/dashboard/network.db ".tables"`
Expected: All 11 tables listed.

---

### Task 2: Device Intelligence Module (`network_device_intel.py`)

**Files:**
- Create: `~/Documents/S6_COMMS_TECH/scripts/network_device_intel.py`

Handles ARP discovery, online/offline tracking, nmap scanning, and device identity resolution.

- [ ] **Step 1: Create network_device_intel.py**

```python
#!/usr/bin/env python3
"""
network_device_intel.py — Device discovery, identity resolution, and scanning.
Provides: ARP discovery (every 60s), online/offline tracking, nmap on-demand scans,
multi-factor device identity (MAC + hostname + mDNS + fingerprint).
"""
import subprocess
import re
import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import network_db as db

# MAC OUI lookup (top vendors — not exhaustive, nmap handles the rest)
OUI_TABLE = {
    "a8:b0:88": "eero", "ac:ec:85": "eero", "9c:a5:70": "eero",
    "30:34:22": "eero", "48:a6:b8": "Sonos", "38:42:0b": "Sonos",
    "c4:38:75": "Sonos", "94:9f:3e": "Sonos", "90:48:6c": "Ring",
    "68:9a:87": "Amazon", "dc:46:28": "Intel",
}

def run_cmd(cmd, timeout=15):
    """Run shell command, return stdout."""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except (subprocess.TimeoutExpired, Exception):
        return ""

def is_randomized_mac(mac):
    """Check if MAC is locally administered (randomized)."""
    if not mac or mac in ("incomplete", "unknown", "randomized"):
        return True
    try:
        first_byte = int(mac.split(":")[0], 16)
        return bool(first_byte & 0x02)
    except ValueError:
        return True

def normalize_mac(mac):
    """Normalize MAC — ARP table doesn't zero-pad hex bytes."""
    if not mac or mac in ("incomplete", "unknown", "randomized"):
        return mac or ""
    parts = mac.lower().split(":")
    return ":".join(p.zfill(2) for p in parts)

def lookup_vendor(mac):
    """Simple vendor lookup from OUI table."""
    if is_randomized_mac(mac):
        return "randomized"
    prefix = ":".join(mac.lower().split(":")[:3])
    # Zero-pad for lookup
    prefix_padded = ":".join(p.zfill(2) for p in prefix.split(":"))
    return OUI_TABLE.get(prefix_padded, OUI_TABLE.get(prefix, None))

def arp_scan():
    """Get all devices from ARP table. Returns list of {ip, mac}."""
    output = run_cmd("arp -a")
    devices = []
    for line in output.split("\n"):
        m = re.search(r'\((\d+\.\d+\.\d+\.\d+)\)\s+at\s+([0-9a-f:]+)', line)
        if m:
            ip, mac = m.group(1), normalize_mac(m.group(2))
            if mac and mac != "(incomplete)":
                # Try to extract hostname from the line
                hostname = None
                hn_match = re.match(r'^(\S+)\s+\(', line)
                if hn_match and hn_match.group(1) != "?":
                    hostname = hn_match.group(1)
                devices.append({"ip": ip, "mac": mac, "hostname": hostname})
    return devices

def discover_devices():
    """
    Run ARP discovery cycle. Updates database with current network state.
    Returns (new_devices, went_offline, came_online) lists.
    """
    # Ping subnet to populate ARP table (broadcast ping)
    run_cmd("ping -c 1 -t 1 192.168.4.255 2>/dev/null", timeout=5)
    run_cmd("ping -c 1 -t 1 192.168.7.255 2>/dev/null", timeout=5)

    current = arp_scan()
    current_ips = {d["ip"] for d in current}

    # Get all known devices from DB
    known = db.get_all_devices()
    known_by_ip = {d["ip"]: d for d in known}
    known_by_mac = {d["mac"]: d for d in known if d.get("mac")}

    new_devices = []
    came_online = []

    for dev in current:
        mac = dev["mac"]
        ip = dev["ip"]
        hostname = dev.get("hostname")
        vendor = lookup_vendor(mac)
        is_random = is_randomized_mac(mac)

        # Try to find in DB by MAC, then by IP
        existing = known_by_mac.get(mac)
        if not existing:
            existing = known_by_ip.get(ip)

        if existing:
            # Known device — update last_seen, check if came back online
            was_offline = not existing["is_online"]
            db.upsert_device(mac=mac, ip=ip, vendor=vendor, hostname=hostname,
                           is_randomized_mac=is_random)
            if was_offline:
                db.mark_device_online(existing["id"])
                came_online.append(existing)
        else:
            # New device
            device_id = db.upsert_device(
                mac=mac, ip=ip, vendor=vendor, hostname=hostname,
                is_randomized_mac=is_random, authorized="pending"
            )
            new_dev = db.get_device(device_id)
            new_devices.append(new_dev)
            db.mark_device_online(device_id)

    # Check for devices that went offline
    went_offline = []
    for known_dev in known:
        if known_dev["is_online"] and known_dev["ip"] not in current_ips:
            db.mark_device_offline(known_dev["id"])
            went_offline.append(known_dev)

    return new_devices, went_offline, came_online

def nmap_scan(ip, scan_type="quick"):
    """
    Run nmap scan against a device.
    scan_type: 'quick' (top 20), 'standard' (top 100), 'full' (top 1000), 'deep' (top 1000 + OS + versions)
    Returns dict with ports, services, os_guess.
    """
    nmap_path = "/opt/homebrew/bin/nmap"
    if not os.path.exists(nmap_path):
        nmap_path = "nmap"

    port_flags = {
        "quick": "--top-ports 20",
        "standard": "--top-ports 100",
        "full": "--top-ports 1000",
        "deep": "--top-ports 1000 -sV -O",
    }
    flags = port_flags.get(scan_type, "--top-ports 20")

    # Use XML output for reliable parsing
    cmd = f"{nmap_path} -sT {flags} -oX - {ip}"
    output = run_cmd(cmd, timeout=120)

    result = {"ports": [], "services": {}, "os_guess": None, "raw": output[:5000]}

    if not output or "<nmaprun" not in output:
        return result

    try:
        root = ET.fromstring(output)
        host = root.find(".//host")
        if host is None:
            return result

        # Parse ports
        for port_el in host.findall(".//port"):
            portid = port_el.get("portid")
            protocol = port_el.get("protocol", "tcp")
            state_el = port_el.find("state")
            state = state_el.get("state", "unknown") if state_el is not None else "unknown"
            service_el = port_el.find("service")
            service_name = service_el.get("name", "") if service_el is not None else ""
            service_version = ""
            if service_el is not None:
                product = service_el.get("product", "")
                version = service_el.get("version", "")
                service_version = f"{product} {version}".strip()

            if state == "open":
                result["ports"].append(int(portid))
                result["services"][portid] = {
                    "protocol": protocol,
                    "service": service_name,
                    "version": service_version,
                }

        # Parse OS detection
        os_match = host.find(".//osmatch")
        if os_match is not None:
            result["os_guess"] = os_match.get("name", "")

    except ET.ParseError:
        pass

    return result

def scan_device(device_id, scan_type="quick"):
    """Scan a device and store results in DB."""
    device = db.get_device(device_id)
    if not device:
        return None

    result = nmap_scan(device["ip"], scan_type)

    # Update device OS guess if detected
    if result["os_guess"]:
        db.update_device(device_id, os_guess=result["os_guess"])

    # Store scan
    db.insert_scan(device_id, scan_type, result["ports"], result["services"],
                   result["os_guess"], result["raw"][:5000])

    return result

def scan_zone(zone, scan_type="quick"):
    """Scan all online devices in a zone."""
    devices = db.get_all_devices()
    results = {}
    for dev in devices:
        if dev["zone"] == zone and dev["is_online"]:
            results[dev["id"]] = scan_device(dev["id"], scan_type)
    return results

def check_critical_ports(zones=None):
    """Quick check of security-critical ports on specified zones. Returns findings."""
    critical_ports = [22, 23, 445, 3389, 5555]
    devices = db.get_all_devices()
    findings = []

    for dev in devices:
        if not dev["is_online"]:
            continue
        if zones and dev["zone"] not in zones:
            continue

        for port in critical_ports:
            try:
                import socket
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(1)
                result = s.connect_ex((dev["ip"], port))
                s.close()
                if result == 0:
                    port_names = {22: "SSH", 23: "Telnet", 445: "SMB", 3389: "RDP", 5555: "ADB"}
                    findings.append({
                        "device_id": dev["id"],
                        "device_name": dev["name"],
                        "ip": dev["ip"],
                        "port": port,
                        "service": port_names.get(port, "Unknown"),
                    })
            except Exception:
                pass

    return findings

if __name__ == "__main__":
    db.init_db()
    print("Running device discovery...")
    new, offline, online = discover_devices()
    print(f"  New: {len(new)}, Went offline: {len(offline)}, Came online: {len(online)}")
    for d in new:
        print(f"    NEW: {d['name'] or d['ip']} ({d['mac']})")
    stats = db.get_network_stats()
    print(f"  Total: {stats['total_devices']}, Online: {stats['online_devices']}")
```

- [ ] **Step 2: Test device discovery**

Run: `cd ~/Documents/S6_COMMS_TECH/scripts && python3 network_device_intel.py`
Expected: Discovery output showing devices found on network, new/offline/online counts.

- [ ] **Step 3: Test nmap scan on a known device**

Run: `cd ~/Documents/S6_COMMS_TECH/scripts && python3 -c "import network_device_intel as di; import network_db as db; db.init_db(); r = di.nmap_scan('192.168.4.1', 'quick'); print(f'Ports: {r[\"ports\"]}, OS: {r[\"os_guess\"]}')" `
Expected: Port list for the eero gateway (likely port 53, 80).

---

### Task 3: Traffic Analysis Module (`network_traffic.py`)

**Files:**
- Create: `~/Documents/S6_COMMS_TECH/scripts/network_traffic.py`
- Create: `~/Documents/S6_COMMS_TECH/scripts/network_data/captures/` (dir)

DNS query capture and traffic rollup processing via tcpdump.

- [ ] **Step 1: Create directories**

Run: `mkdir -p ~/Documents/S6_COMMS_TECH/scripts/network_data/captures ~/Documents/S6_COMMS_TECH/scripts/network_data/threat_feeds`

- [ ] **Step 2: Create network_traffic.py**

```python
#!/usr/bin/env python3
"""
network_traffic.py — Traffic analysis via tcpdump.
Captures DNS queries, estimates bandwidth per device, builds protocol breakdowns.
Runs tcpdump as a background subprocess (requires sudo for full capture).
Falls back to non-privileged mode with limited visibility.
"""
import subprocess
import threading
import re
import os
import struct
import time
from datetime import datetime
from collections import defaultdict
from pathlib import Path

import network_db as db

CAPTURE_DIR = Path.home() / "Documents" / "S6_COMMS_TECH" / "scripts" / "network_data" / "captures"

# In-memory buffers for rollup aggregation
_traffic_buffer = defaultdict(lambda: {"bytes_in": 0, "bytes_out": 0, "packets": 0,
                                        "destinations": defaultdict(int), "protocols": defaultdict(int)})
_dns_buffer = []
_buffer_lock = threading.Lock()

# Local subnet detection
LOCAL_PREFIXES = ("192.168.",)
MY_IP = None  # Set during init

def _get_my_ip():
    """Get this Mac's IP on the local network."""
    try:
        output = subprocess.run(["ipconfig", "getifaddr", "en0"],
                                capture_output=True, text=True, timeout=5).stdout.strip()
        if output:
            return output
    except Exception:
        pass
    return "192.168.7.85"  # fallback

def start_dns_capture():
    """
    Start a background tcpdump to capture DNS queries.
    Runs without sudo — captures DNS on port 53 visible to this host.
    Returns the subprocess for management.
    """
    cmd = ["tcpdump", "-i", "any", "-l", "-n", "port", "53", "-Q", "in"]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                text=True, bufsize=1)
        t = threading.Thread(target=_dns_reader, args=(proc,), daemon=True)
        t.start()
        return proc
    except PermissionError:
        print("[WARN] tcpdump requires elevated privileges for full DNS capture.")
        print("       Run with: sudo python3 network_traffic.py")
        print("       Falling back to limited mode.")
        return None

def _dns_reader(proc):
    """Read DNS queries from tcpdump stdout and buffer them."""
    # tcpdump output format: timestamp IP src.port > dst.port: ... A? domain. ...
    dns_pattern = re.compile(
        r'(\d+\.\d+\.\d+\.\d+)\.\d+\s+>\s+\S+:\s+\d+[\+\s]*(\w+)\??\s+(\S+)')
    for line in proc.stdout:
        m = dns_pattern.search(line)
        if m:
            src_ip = m.group(1)
            query_type = m.group(2)
            domain = m.group(3).rstrip(".")
            with _buffer_lock:
                _dns_buffer.append({
                    "src_ip": src_ip,
                    "domain": domain,
                    "query_type": query_type,
                    "timestamp": datetime.now().isoformat(),
                })

def start_traffic_capture():
    """
    Start background tcpdump for traffic volume estimation.
    Captures packet headers only (no payload) for bandwidth stats.
    """
    cmd = ["tcpdump", "-i", "any", "-l", "-n", "-q", "-e",
           "not", "port", "53"]  # DNS captured separately
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                text=True, bufsize=1)
        t = threading.Thread(target=_traffic_reader, args=(proc,), daemon=True)
        t.start()
        return proc
    except PermissionError:
        return None

def _traffic_reader(proc):
    """Read traffic from tcpdump and accumulate per-device stats."""
    global MY_IP
    if not MY_IP:
        MY_IP = _get_my_ip()

    # tcpdump -q format: timestamp IP src > dst: proto length
    pkt_pattern = re.compile(
        r'(\d+\.\d+\.\d+\.\d+)\.?\d*\s+>\s+(\d+\.\d+\.\d+\.\d+)\.?\d*:.*?(\d+)$')

    for line in proc.stdout:
        m = pkt_pattern.search(line)
        if not m:
            continue
        src_ip = m.group(1)
        dst_ip = m.group(2)
        try:
            pkt_len = int(m.group(3))
        except ValueError:
            pkt_len = 0

        # Determine which local device this belongs to
        local_ip = None
        remote_ip = None
        is_outbound = False

        if src_ip.startswith(LOCAL_PREFIXES) and not dst_ip.startswith(LOCAL_PREFIXES):
            local_ip = src_ip
            remote_ip = dst_ip
            is_outbound = True
        elif dst_ip.startswith(LOCAL_PREFIXES) and not src_ip.startswith(LOCAL_PREFIXES):
            local_ip = dst_ip
            remote_ip = src_ip
        elif src_ip.startswith(LOCAL_PREFIXES) and dst_ip.startswith(LOCAL_PREFIXES):
            # Internal traffic — attribute to source
            local_ip = src_ip
            remote_ip = dst_ip
            is_outbound = True
        else:
            continue

        # Detect protocol from port in line
        protocol = "other"
        if ":80 " in line or ".80:" in line or ".80 " in line:
            protocol = "http"
        elif ":443 " in line or ".443:" in line or ".443 " in line:
            protocol = "https"
        elif ":5353 " in line:
            protocol = "mdns"
        elif ":1900 " in line:
            protocol = "ssdp"

        with _buffer_lock:
            buf = _traffic_buffer[local_ip]
            if is_outbound:
                buf["bytes_out"] += pkt_len
            else:
                buf["bytes_in"] += pkt_len
            buf["packets"] += 1
            if remote_ip:
                buf["destinations"][remote_ip] += pkt_len
            buf["protocols"][protocol] += 1

def flush_dns_buffer():
    """Process buffered DNS queries: match to devices, check threat intel, store in DB."""
    with _buffer_lock:
        queries = list(_dns_buffer)
        _dns_buffer.clear()

    for q in queries:
        device = db.get_device_by_ip(q["src_ip"])
        device_id = device["id"] if device else None

        # Check against threat intel
        intel_match = db.check_threat_intel(q["domain"])
        flagged = intel_match is not None
        flag_reason = f"Matched threat intel: {intel_match['source']}" if intel_match else None

        if device_id:
            db.insert_dns_query(device_id, q["domain"], q["query_type"],
                              flagged=flagged, flag_reason=flag_reason)

    return len(queries)

def flush_traffic_buffer():
    """Process buffered traffic stats into 5-minute rollups."""
    with _buffer_lock:
        snapshot = dict(_traffic_buffer)
        _traffic_buffer.clear()

    count = 0
    for ip, stats in snapshot.items():
        device = db.get_device_by_ip(ip)
        if not device:
            continue

        # Top destinations (top 10 by bytes)
        top_dests = sorted(stats["destinations"].items(), key=lambda x: x[1], reverse=True)[:10]
        top_dest_list = [{"ip": ip, "bytes": b} for ip, b in top_dests]

        db.insert_traffic_rollup(
            device["id"],
            bytes_in=stats["bytes_in"],
            bytes_out=stats["bytes_out"],
            packets=stats["packets"],
            top_destinations=top_dest_list,
            protocols=dict(stats["protocols"]),
        )
        count += 1

    return count

def capture_pcap(device_ip, duration=60):
    """Start a packet capture for forensic analysis. Returns path to PCAP file."""
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_ip = device_ip.replace(".", "_")
    pcap_path = CAPTURE_DIR / f"capture_{safe_ip}_{ts}.pcap"

    cmd = ["tcpdump", "-i", "any", "-w", str(pcap_path), "-c", "10000",
           "host", device_ip]

    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _stop():
        time.sleep(duration)
        proc.terminate()

    threading.Thread(target=_stop, daemon=True).start()
    return str(pcap_path)

def cleanup_old_captures(max_age_days=7):
    """Remove PCAP files older than max_age_days."""
    if not CAPTURE_DIR.exists():
        return
    now = time.time()
    for f in CAPTURE_DIR.glob("capture_*.pcap"):
        if (now - f.stat().st_mtime) > (max_age_days * 86400):
            f.unlink()

if __name__ == "__main__":
    db.init_db()
    MY_IP = _get_my_ip()
    print(f"Local IP: {MY_IP}")
    print("Starting DNS capture (Ctrl+C to stop)...")
    dns_proc = start_dns_capture()
    if dns_proc:
        try:
            time.sleep(10)
            count = flush_dns_buffer()
            print(f"Captured {count} DNS queries in 10 seconds")
        except KeyboardInterrupt:
            dns_proc.terminate()
    else:
        print("DNS capture failed — try with sudo")
```

- [ ] **Step 3: Test DNS capture (needs sudo for full visibility)**

Run: `cd ~/Documents/S6_COMMS_TECH/scripts && python3 network_traffic.py`
Expected: Shows local IP and captures some DNS queries over 10 seconds. May show 0 queries without sudo — that's expected; the system handles graceful degradation.

---

### Task 4: Threat Intelligence Module (`network_threat_intel.py`)

**Files:**
- Create: `~/Documents/S6_COMMS_TECH/scripts/network_threat_intel.py`

Downloads threat feeds (abuse.ch, PhishTank) and loads indicators into SQLite.

- [ ] **Step 1: Create network_threat_intel.py**

```python
#!/usr/bin/env python3
"""
network_threat_intel.py — Threat intelligence feed ingestion.
Downloads indicators from abuse.ch (URLhaus, Feodo Tracker) and loads into SQLite.
Supports: domains, IPs, URLs as indicator types.
"""
import csv
import io
import json
import os
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

import network_db as db

FEED_DIR = Path.home() / "Documents" / "S6_COMMS_TECH" / "scripts" / "network_data" / "threat_feeds"

# Feed URLs (all free, no API key required)
FEEDS = {
    "urlhaus_domains": {
        "url": "https://urlhaus.abuse.ch/downloads/text_online/",
        "type": "url",
        "severity": "HIGH",
        "parser": "lines",
    },
    "feodo_ips": {
        "url": "https://feodotracker.abuse.ch/downloads/ipblocklist_recommended.txt",
        "type": "ip",
        "severity": "CRITICAL",
        "parser": "lines",
    },
    "feodo_domains": {
        "url": "https://feodotracker.abuse.ch/downloads/domainblocklist.txt",
        "type": "domain",
        "severity": "CRITICAL",
        "parser": "lines",
    },
}

def _download_feed(url, name):
    """Download a feed, return text content."""
    FEED_DIR.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LifeOS-NetworkCommand/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read().decode("utf-8", errors="replace")
        # Cache locally
        cache_path = FEED_DIR / f"{name}.txt"
        cache_path.write_text(content, encoding="utf-8")
        return content
    except (urllib.error.URLError, Exception) as e:
        print(f"  WARN: Failed to download {name}: {e}")
        # Try cached version
        cache_path = FEED_DIR / f"{name}.txt"
        if cache_path.exists():
            print(f"  Using cached version of {name}")
            return cache_path.read_text(encoding="utf-8")
        return None

def _parse_lines(content):
    """Parse a simple line-based feed (one indicator per line, # comments)."""
    indicators = []
    for line in content.split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("//"):
            continue
        # For URLs, extract domain
        if "://" in line:
            try:
                from urllib.parse import urlparse
                parsed = urlparse(line)
                domain = parsed.hostname
                if domain:
                    indicators.append(domain)
            except Exception:
                indicators.append(line)
        else:
            indicators.append(line)
    return indicators

def refresh_feeds():
    """Download all feeds and load indicators into database."""
    total = 0
    results = {}

    for name, feed in FEEDS.items():
        print(f"  Downloading {name}...")
        content = _download_feed(feed["url"], name)
        if not content:
            results[name] = {"status": "failed", "count": 0}
            continue

        if feed["parser"] == "lines":
            indicators = _parse_lines(content)
        else:
            indicators = []

        # Load into DB
        count = 0
        for indicator in indicators:
            indicator = indicator.strip().lower()
            if not indicator or len(indicator) < 3:
                continue
            db.insert_threat_intel(
                indicator_type=feed["type"],
                indicator_value=indicator,
                source=name,
                severity=feed["severity"],
            )
            count += 1

        results[name] = {"status": "ok", "count": count}
        total += count
        print(f"    Loaded {count} indicators from {name}")

    return {"total_loaded": total, "feeds": results}

def check_domain(domain):
    """Check a domain against threat intel. Returns match info or None."""
    domain = domain.strip().lower()
    match = db.check_threat_intel(domain)
    if match:
        return match
    # Check parent domains (e.g., evil.example.com → example.com)
    parts = domain.split(".")
    for i in range(1, len(parts) - 1):
        parent = ".".join(parts[i:])
        match = db.check_threat_intel(parent)
        if match:
            return match
    return None

def check_ip(ip):
    """Check an IP against threat intel."""
    return db.check_threat_intel(ip)

def get_feed_status():
    """Get current threat intel statistics."""
    stats = db.get_threat_intel_stats()
    feed_files = {}
    for f in FEED_DIR.glob("*.txt"):
        feed_files[f.stem] = {
            "size": f.stat().st_size,
            "updated": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
        }
    return {"indicators": stats, "feed_files": feed_files}

if __name__ == "__main__":
    db.init_db()
    print("Refreshing threat intelligence feeds...")
    result = refresh_feeds()
    print(f"\nTotal indicators loaded: {result['total_loaded']}")
    print(f"\nFeed status:")
    status = get_feed_status()
    print(json.dumps(status, indent=2))
```

- [ ] **Step 2: Test threat intel feed download**

Run: `cd ~/Documents/S6_COMMS_TECH/scripts && python3 network_threat_intel.py`
Expected: Downloads feeds, loads thousands of indicators. Shows feed status with counts.

---

### Task 5: IDS Rules Engine (`network_ids_rules.py`)

**Files:**
- Create: `~/Documents/S6_COMMS_TECH/scripts/network_ids_rules.py`

Intrusion detection rules: ARP spoofing, port scan detection, lateral movement, DNS tunneling, external exposure, behavioral anomalies.

- [ ] **Step 1: Create network_ids_rules.py**

```python
#!/usr/bin/env python3
"""
network_ids_rules.py — Intrusion Detection System rules engine.
Evaluates internal threats, external exposure, and behavioral anomalies.
All detection is passive — no active response in v1.
"""
import subprocess
import json
import re
import math
from datetime import datetime, timedelta
from collections import defaultdict

import network_db as db
import network_threat_intel as threat_intel

# ── ARP State Tracking ────────────────────────────────────────────

_arp_history = {}  # ip -> {mac, timestamp} for spoofing detection
_port_probe_tracker = defaultdict(lambda: defaultdict(set))  # src_ip -> dst_ip -> {ports}
_lateral_tracker = defaultdict(set)  # src_ip -> {dst_ips} for lateral movement
_dns_rate_tracker = defaultdict(lambda: defaultdict(int))  # src_ip -> domain -> count

def run_cmd(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""

# ── Internal Threat Detection ─────────────────────────────────────

def check_arp_spoofing(current_arp_entries):
    """
    Detect ARP spoofing: same IP claimed by different MAC within 60 seconds.
    current_arp_entries: list of {ip, mac} from ARP table.
    """
    threats = []
    now = datetime.now()

    for entry in current_arp_entries:
        ip = entry["ip"]
        mac = entry["mac"]
        if ip in _arp_history:
            prev = _arp_history[ip]
            age = (now - prev["timestamp"]).total_seconds()
            if prev["mac"] != mac and age < 60:
                threats.append({
                    "threat_type": "arp_spoofing",
                    "severity": "CRITICAL",
                    "confidence": "CONFIRMED",
                    "detail": f"ARP spoofing detected: {ip} changed from {prev['mac']} to {mac} in {age:.0f}s",
                    "ip": ip,
                })
        _arp_history[ip] = {"mac": mac, "timestamp": now}

    return threats

def check_internal_port_scan(dns_queries_recent):
    """
    Detect internal port scanning from traffic/connection patterns.
    This is called with recent connection data. For now, uses DNS query patterns
    as a proxy — actual port scan detection needs raw connection tracking.
    """
    # TODO: Enhanced with tcpdump connection tracking in Phase 2
    return []

def check_dns_tunneling(dns_queries):
    """
    Detect DNS tunneling: queries with >50 char subdomain or >100 queries/min to single domain.
    dns_queries: list of {src_ip, domain, query_type}
    """
    threats = []

    # Check long subdomains (exfiltration signature)
    for q in dns_queries:
        domain = q.get("domain", "")
        parts = domain.split(".")
        if len(parts) >= 3:
            subdomain = ".".join(parts[:-2])
            if len(subdomain) > 50:
                threats.append({
                    "threat_type": "dns_tunneling",
                    "severity": "MEDIUM",
                    "confidence": "SUSPECTED",
                    "detail": f"Possible DNS tunneling: {q['src_ip']} queried {domain[:80]}... (subdomain length: {len(subdomain)})",
                    "ip": q.get("src_ip"),
                })

    # Check query rate per domain
    rate = defaultdict(lambda: defaultdict(int))
    for q in dns_queries:
        rate[q.get("src_ip", "")][q.get("domain", "")] += 1

    for src_ip, domains in rate.items():
        for domain, count in domains.items():
            if count > 100:
                threats.append({
                    "threat_type": "dns_tunneling",
                    "severity": "MEDIUM",
                    "confidence": "SUSPECTED",
                    "detail": f"High DNS query rate: {src_ip} made {count} queries to {domain}",
                    "ip": src_ip,
                })

    return threats

def check_known_bad_domains(dns_queries):
    """Check DNS queries against threat intel feeds."""
    threats = []
    for q in dns_queries:
        domain = q.get("domain", "")
        match = threat_intel.check_domain(domain)
        if match:
            threats.append({
                "threat_type": "known_malware_domain",
                "severity": "CRITICAL",
                "confidence": "CONFIRMED",
                "detail": f"Device {q.get('src_ip')} contacted known malicious domain: {domain} (source: {match.get('source', 'unknown')})",
                "ip": q.get("src_ip"),
            })
    return threats

# ── External Exposure Detection ──────────────────────────────────

def check_public_ip():
    """Get current public IP and compare to last known."""
    findings = []
    ip = run_cmd("curl -s --max-time 10 ifconfig.me")
    if not ip or not re.match(r'^\d+\.\d+\.\d+\.\d+$', ip):
        return findings, None

    last = db.get_latest_public_ip()
    if last and last["ip"] != ip:
        findings.append({
            "threat_type": "public_ip_changed",
            "severity": "MEDIUM",
            "confidence": "CONFIRMED",
            "detail": f"Public IP changed from {last['ip']} to {ip}",
            "ip": ip,
        })

    db.insert_public_ip(ip)
    return findings, ip

def check_dns_leak():
    """Verify DNS goes through Cloudflare, not ISP."""
    findings = []
    output = run_cmd("networksetup -getdnsservers Wi-Fi")
    if "1.1.1.1" not in output and "1.0.0.1" not in output:
        findings.append({
            "threat_type": "dns_leak",
            "severity": "HIGH",
            "confidence": "CONFIRMED",
            "detail": f"DNS not set to Cloudflare. Current: {output[:100]}",
            "ip": None,
        })
    return findings

def check_shodan(public_ip):
    """Check Shodan for exposed services on public IP. Requires shodan API key."""
    findings = []
    try:
        import shodan
        api_key = os.environ.get("SHODAN_API_KEY", "")
        if not api_key:
            return findings
        api = shodan.Shodan(api_key)
        result = api.host(public_ip)
        # Check for unexpected open ports
        expected_ports = {443}  # Only Tailscale Funnel should be visible
        found_ports = {item["port"] for item in result.get("data", [])}
        unexpected = found_ports - expected_ports
        if unexpected:
            findings.append({
                "threat_type": "unexpected_exposure",
                "severity": "HIGH",
                "confidence": "CONFIRMED",
                "detail": f"Unexpected ports visible on Shodan: {unexpected}. Expected only: {expected_ports}",
                "ip": public_ip,
            })
        # Store full result
        db.insert_public_ip(public_ip, shodan_result=result)
        return findings
    except ImportError:
        return findings
    except Exception:
        return findings

# ── Behavioral Anomaly Detection ─────────────────────────────────

def check_traffic_anomalies():
    """Compare current traffic patterns against baselines for stable-MAC devices."""
    anomalies = []
    now = datetime.now()
    hour = now.hour
    dow = now.weekday()

    devices = db.get_all_devices()
    for dev in devices:
        if dev["is_randomized_mac"] or not dev["is_online"]:
            continue

        # Get baseline for this hour/day
        baseline = db.get_baseline(dev["id"], "traffic_bytes", hour, dow)
        if not baseline or baseline["sample_count"] < 7:
            continue  # Not enough data yet

        # Get recent traffic
        recent = db.get_traffic(dev["id"], hours=1)
        if not recent:
            continue

        total_bytes = sum(r["bytes_in"] + r["bytes_out"] for r in recent)
        avg = baseline["avg_value"]
        stddev = baseline["stddev"] or 1

        if avg > 0 and total_bytes > avg * 3:
            deviation = ((total_bytes - avg) / stddev) if stddev > 0 else 0
            anomalies.append({
                "device_id": dev["id"],
                "anomaly_type": "traffic_spike",
                "baseline_value": avg,
                "observed_value": total_bytes,
                "deviation_pct": ((total_bytes - avg) / avg * 100) if avg > 0 else 0,
                "detail": f"{dev['name']}: {total_bytes} bytes vs baseline {avg:.0f} ({deviation:.1f} stddev)",
            })

    return anomalies

def update_baselines():
    """Recalculate behavioral baselines from historical traffic data."""
    devices = db.get_all_devices()
    conn = db.get_connection()

    for dev in devices:
        if dev["is_randomized_mac"]:
            continue

        # Get last 7 days of traffic rollups
        rows = conn.execute("""
            SELECT timestamp, bytes_in + bytes_out as total_bytes
            FROM traffic_rollups WHERE device_id=?
            AND timestamp > datetime('now', '-7 days')
        """, (dev["id"],)).fetchall()

        if len(rows) < 12:  # Need at least 1 hour of data
            continue

        # Group by hour and day of week
        hourly = defaultdict(list)
        for row in rows:
            try:
                ts = datetime.fromisoformat(row["timestamp"])
                key = (ts.hour, ts.weekday())
                hourly[key].append(row["total_bytes"])
            except Exception:
                continue

        for (hour, dow), values in hourly.items():
            if len(values) < 3:
                continue
            avg = sum(values) / len(values)
            variance = sum((v - avg) ** 2 for v in values) / len(values)
            stddev = math.sqrt(variance) if variance > 0 else 0
            db.upsert_baseline(dev["id"], "traffic_bytes", hour, dow, avg, stddev, len(values))

    conn.close()

# ── Main Evaluation ──────────────────────────────────────────────

def evaluate_all(arp_entries=None, dns_queries=None):
    """
    Run all IDS rules. Returns list of threats and anomalies.
    Call this on the 5-minute cycle.
    """
    threats = []
    anomalies = []

    # Internal checks
    if arp_entries:
        threats.extend(check_arp_spoofing(arp_entries))

    if dns_queries:
        threats.extend(check_dns_tunneling(dns_queries))
        threats.extend(check_known_bad_domains(dns_queries))

    # Behavioral anomalies
    anomalies.extend(check_traffic_anomalies())

    # Record threats in DB
    for t in threats:
        ip = t.get("ip")
        device = db.get_device_by_ip(ip) if ip else None
        device_id = device["id"] if device else None
        db.insert_threat(device_id, t["threat_type"], t["severity"],
                        t["confidence"], t["detail"])

    # Record anomalies in DB
    for a in anomalies:
        db.insert_anomaly(a.get("device_id"), a["anomaly_type"],
                         a.get("baseline_value"), a.get("observed_value"),
                         a.get("deviation_pct"), a["detail"])

    return threats, anomalies

def evaluate_external():
    """Run external exposure checks. Call on the 6-hour cycle."""
    threats = []

    ip_threats, public_ip = check_public_ip()
    threats.extend(ip_threats)

    dns_threats = check_dns_leak()
    threats.extend(dns_threats)

    if public_ip:
        shodan_threats = check_shodan(public_ip)
        threats.extend(shodan_threats)

    # Record threats
    for t in threats:
        db.insert_threat(None, t["threat_type"], t["severity"],
                        t["confidence"], t["detail"])

    return threats

if __name__ == "__main__":
    db.init_db()
    print("Running external exposure check...")
    ext_threats = evaluate_external()
    print(f"External threats: {len(ext_threats)}")
    for t in ext_threats:
        print(f"  [{t['severity']}] {t['detail']}")
    print("\nThreat summary:", json.dumps(db.get_threat_summary(), indent=2))
```

- [ ] **Step 2: Test IDS external checks**

Run: `cd ~/Documents/S6_COMMS_TECH/scripts && python3 network_ids_rules.py`
Expected: Runs external exposure check (public IP, DNS leak), reports findings.

---

### Task 6: Main Server — Network Command Center (`network_command_center.py`)

**Files:**
- Create: `~/Documents/S6_COMMS_TECH/scripts/network_command_center.py`

The main server: HTTP API, scheduler, orchestrates all modules.

- [ ] **Step 1: Create network_command_center.py**

```python
#!/usr/bin/env python3
"""
network_command_center.py — Main server for Network Command Center.
HTTP API on :8085, background scheduler, orchestrates all modules.
Serves the dashboard HTML and provides REST API for device management,
scanning, traffic analysis, IDS, and threat intelligence.
"""
import http.server
import json
import os
import sys
import threading
import time
import re
import signal
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# Add scripts dir to path
SCRIPTS_DIR = os.path.expanduser("~/Documents/S6_COMMS_TECH/scripts")
sys.path.insert(0, SCRIPTS_DIR)

import network_db as db
import network_device_intel as device_intel
import network_traffic as traffic
import network_ids_rules as ids
import network_threat_intel as threat_intel

# Also import alert system
from s6_alert import alert, CRITICAL, HIGH, MEDIUM
from remediation_tracker import track_findings

PORT = 8085
DASHBOARD_DIR = Path.home() / "Documents" / "S6_COMMS_TECH" / "dashboard"

# ── Scheduler ─────────────────────────────────────────────────────

class Scheduler:
    """Background task scheduler for recurring operations."""

    def __init__(self):
        self.running = True
        self._last_run = {}
        self._tasks = {
            "arp_discovery":     {"interval": 60,    "fn": self._task_arp},
            "traffic_rollup":    {"interval": 300,   "fn": self._task_traffic_rollup},
            "ids_evaluation":    {"interval": 300,   "fn": self._task_ids},
            "critical_ports":    {"interval": 900,   "fn": self._task_critical_ports},
            "hourly_scan":       {"interval": 3600,  "fn": self._task_hourly_scan},
            "external_exposure": {"interval": 21600, "fn": self._task_external},
            "threat_intel":      {"interval": 86400, "fn": self._task_threat_intel},
            "db_backup":         {"interval": 86400, "fn": self._task_backup},
            "capture_cleanup":   {"interval": 86400, "fn": self._task_cleanup},
            "baseline_update":   {"interval": 604800, "fn": self._task_baselines},
        }

    def start(self):
        t = threading.Thread(target=self._run_loop, daemon=True)
        t.start()

    def _run_loop(self):
        while self.running:
            now = time.time()
            for name, task in self._tasks.items():
                last = self._last_run.get(name, 0)
                if now - last >= task["interval"]:
                    try:
                        task["fn"]()
                    except Exception as e:
                        print(f"[SCHED] {name} failed: {e}")
                    self._last_run[name] = now
            time.sleep(5)

    def _task_arp(self):
        new, offline, online = device_intel.discover_devices()
        if new:
            for d in new:
                if not d.get("is_randomized_mac"):
                    alert(MEDIUM, "New Device Detected",
                          f"Unknown device joined network: {d.get('name', d.get('ip'))} (MAC: {d.get('mac')})",
                          send_text=True)

    def _task_traffic_rollup(self):
        dns_count = traffic.flush_dns_buffer()
        traffic_count = traffic.flush_traffic_buffer()

    def _task_ids(self):
        # Get recent ARP entries for spoofing detection
        arp_entries = device_intel.arp_scan()
        # Get recent DNS queries from buffer (already flushed to DB)
        conn = db.get_connection()
        recent_dns = conn.execute("""
            SELECT d.ip as src_ip, q.domain, q.query_type
            FROM dns_queries q JOIN devices d ON q.device_id=d.id
            WHERE q.timestamp > datetime('now', '-5 minutes')
        """).fetchall()
        conn.close()
        dns_list = [dict(r) for r in recent_dns]

        threats, anomalies = ids.evaluate_all(arp_entries, dns_list)

        # Alert on confirmed threats
        for t in threats:
            if t["confidence"] == "CONFIRMED":
                alert(CRITICAL if t["severity"] == "CRITICAL" else HIGH,
                      f"Network IDS: {t['threat_type']}",
                      t["detail"], send_text=True)

        # Track for remediation
        findings = [{"id": t["threat_type"], "severity": t["severity"],
                     "subject": t["threat_type"], "detail": t["detail"]} for t in threats]
        if findings:
            track_findings("network_ids", findings)

    def _task_critical_ports(self):
        findings = device_intel.check_critical_ports(zones=["kids", "iot"])
        for f in findings:
            alert(HIGH, f"Open Port: {f['service']} on {f['device_name']}",
                  f"Port {f['port']} ({f['service']}) open on {f['ip']}", send_text=True)

    def _task_hourly_scan(self):
        device_intel.scan_zone("kids", "standard")
        device_intel.scan_zone("iot", "standard")

    def _task_external(self):
        threats = ids.evaluate_external()
        for t in threats:
            alert(HIGH, f"External: {t['threat_type']}", t["detail"], send_text=True)

    def _task_threat_intel(self):
        result = threat_intel.refresh_feeds()
        print(f"[SCHED] Threat intel refreshed: {result['total_loaded']} indicators")

    def _task_backup(self):
        db.backup_db()
        print("[SCHED] Database backed up")

    def _task_cleanup(self):
        traffic.cleanup_old_captures()

    def _task_baselines(self):
        ids.update_baselines()
        print("[SCHED] Baselines updated")

    def get_status(self):
        return {name: {"last_run": datetime.fromtimestamp(self._last_run.get(name, 0)).isoformat()
                        if self._last_run.get(name) else "never",
                        "interval_sec": task["interval"]}
                for name, task in self._tasks.items()}

# ── HTTP API ──────────────────────────────────────────────────────

scheduler = Scheduler()

class APIHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass  # Suppress default logging

    def _send_json(self, data, status=200):
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path, content_type="text/html"):
        try:
            with open(path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", len(content))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_error(404)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length:
            return json.loads(self.rfile.read(length))
        return {}

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = parse_qs(parsed.query)

        # Serve dashboard
        if path in ("", "/", "/network-map.html", "/index.html"):
            self._send_file(str(DASHBOARD_DIR / "network-map.html"))
            return

        # API routes
        if path == "/api/devices":
            self._send_json(db.get_all_devices())

        elif re.match(r'^/api/devices/(\d+)$', path):
            did = int(re.match(r'^/api/devices/(\d+)$', path).group(1))
            dev = db.get_device(did)
            if dev:
                self._send_json(dev)
            else:
                self.send_error(404)

        elif re.match(r'^/api/devices/(\d+)/scans$', path):
            did = int(re.match(r'^/api/devices/(\d+)/scans$', path).group(1))
            limit = int(params.get("limit", [20])[0])
            self._send_json(db.get_scans(did, limit))

        elif re.match(r'^/api/devices/(\d+)/traffic$', path):
            did = int(re.match(r'^/api/devices/(\d+)/traffic$', path).group(1))
            hours = int(params.get("hours", [24])[0])
            self._send_json(db.get_traffic(did, hours))

        elif re.match(r'^/api/devices/(\d+)/dns$', path):
            did = int(re.match(r'^/api/devices/(\d+)/dns$', path).group(1))
            limit = int(params.get("limit", [100])[0])
            flagged = params.get("flagged_only", ["false"])[0] == "true"
            self._send_json(db.get_dns_queries(did, limit, flagged))

        elif re.match(r'^/api/devices/(\d+)/threats$', path):
            did = int(re.match(r'^/api/devices/(\d+)/threats$', path).group(1))
            self._send_json(db.get_threats(device_id=did, unresolved_only=False))

        elif re.match(r'^/api/devices/(\d+)/connection$', path):
            did = int(re.match(r'^/api/devices/(\d+)/connection$', path).group(1))
            self._send_json(db.get_connection_history(did))

        elif path == "/api/threats":
            severity = params.get("severity", [None])[0]
            unresolved = params.get("unresolved", ["true"])[0] == "true"
            self._send_json(db.get_threats(severity=severity, unresolved_only=unresolved))

        elif path == "/api/threats/summary":
            self._send_json(db.get_threat_summary())

        elif path == "/api/anomalies":
            self._send_json(db.get_anomalies())

        elif path == "/api/network/status":
            stats = db.get_network_stats()
            stats["scheduler"] = scheduler.get_status()
            stats["timestamp"] = datetime.now().isoformat()
            self._send_json(stats)

        elif path == "/api/network/external":
            last = db.get_latest_public_ip()
            self._send_json(last or {"ip": "unknown", "note": "No external check yet"})

        elif path == "/api/network/stats":
            self._send_json(db.get_network_stats())

        elif path == "/api/intel/feeds":
            self._send_json(threat_intel.get_feed_status())

        elif path == "/api/dashboard":
            # Pre-aggregated dashboard payload
            data = {
                "stats": db.get_network_stats(),
                "devices": db.get_all_devices(),
                "threats": db.get_threats(unresolved_only=True, limit=20),
                "anomalies": db.get_anomalies(limit=10),
                "threat_summary": db.get_threat_summary(),
                "external": db.get_latest_public_ip(),
                "scheduler": scheduler.get_status(),
                "timestamp": datetime.now().isoformat(),
            }
            self._send_json(data)

        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if re.match(r'^/api/devices/(\d+)/scan$', path):
            did = int(re.match(r'^/api/devices/(\d+)/scan$', path).group(1))
            body = self._read_body()
            scan_type = body.get("scan_type", "quick")
            result = device_intel.scan_device(did, scan_type)
            if result:
                self._send_json(result)
            else:
                self.send_error(404)

        elif re.match(r'^/api/devices/(\d+)/capture$', path):
            did = int(re.match(r'^/api/devices/(\d+)/capture$', path).group(1))
            dev = db.get_device(did)
            if dev:
                body = self._read_body()
                duration = body.get("duration", 60)
                pcap_path = traffic.capture_pcap(dev["ip"], duration)
                self._send_json({"status": "capturing", "path": pcap_path, "duration": duration})
            else:
                self.send_error(404)

        elif path == "/api/intel/refresh":
            result = threat_intel.refresh_feeds()
            self._send_json(result)

        else:
            self.send_error(404)

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if re.match(r'^/api/devices/(\d+)$', path):
            did = int(re.match(r'^/api/devices/(\d+)$', path).group(1))
            body = self._read_body()
            db.update_device(did, **body)
            self._send_json(db.get_device(did))
        else:
            self.send_error(404)

# ── Main ──────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  NETWORK COMMAND CENTER v1.0")
    print("  Owens Home Network — Redryder")
    print("=" * 60)

    # Initialize
    print("\n[INIT] Database...")
    db.init_db()

    # Seed from registry if DB is empty
    stats = db.get_network_stats()
    if stats["total_devices"] == 0:
        print("[INIT] Seeding from device registry...")
        count = db.seed_from_registry()
        print(f"[INIT] Seeded {count} devices")

    # Initial threat intel load
    print("[INIT] Loading threat intelligence...")
    intel_result = threat_intel.refresh_feeds()
    print(f"[INIT] Loaded {intel_result['total_loaded']} threat indicators")

    # Initial device discovery
    print("[INIT] Running device discovery...")
    new, offline, online = device_intel.discover_devices()
    stats = db.get_network_stats()
    print(f"[INIT] Devices: {stats['total_devices']} total, {stats['online_devices']} online")

    # Start traffic capture (best effort — may need sudo)
    print("[INIT] Starting traffic capture...")
    dns_proc = traffic.start_dns_capture()
    traffic_proc = traffic.start_traffic_capture()
    if dns_proc:
        print("[INIT] DNS capture: ACTIVE")
    else:
        print("[INIT] DNS capture: LIMITED (run with sudo for full visibility)")
    if traffic_proc:
        print("[INIT] Traffic capture: ACTIVE")
    else:
        print("[INIT] Traffic capture: LIMITED")

    # Start scheduler
    print("[INIT] Starting scheduler...")
    scheduler.start()

    # Start HTTP server
    print(f"\n[READY] Network Command Center running on http://localhost:{PORT}")
    print(f"[READY] Dashboard: http://localhost:{PORT}/network-map.html")
    print(f"[READY] API: http://localhost:{PORT}/api/dashboard")
    print(f"[READY] Press Ctrl+C to stop\n")

    server = http.server.HTTPServer(("0.0.0.0", PORT), APIHandler)

    def shutdown(sig, frame):
        print("\n[STOP] Shutting down...")
        scheduler.running = False
        if dns_proc:
            dns_proc.terminate()
        if traffic_proc:
            traffic_proc.terminate()
        server.shutdown()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        shutdown(None, None)

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test server startup**

Run: `cd ~/Documents/S6_COMMS_TECH/scripts && python3 network_command_center.py`
Expected: Initializes DB, loads threat intel, discovers devices, starts scheduler, serves on :8085. Test API in another terminal: `curl http://localhost:8085/api/network/status | jq .`

- [ ] **Step 3: Test key API endpoints**

Run (in separate terminal):
```bash
curl -s http://localhost:8085/api/devices | jq '.[0:3]'
curl -s http://localhost:8085/api/threats/summary | jq .
curl -s http://localhost:8085/api/dashboard | jq '.stats'
```
Expected: JSON responses with device list, threat summary, and dashboard stats.

---

### Task 7: Interactive Dashboard (`network-map.html`)

**Files:**
- Replace: `~/Documents/S6_COMMS_TECH/dashboard/network-map.html`

Full rebuild: network map + click-to-manage slide-out panel with 5 tabs (Overview, Ports, Traffic, Security, Actions). Reads from :8085 API.

- [ ] **Step 1: Replace network-map.html with full interactive dashboard**

This is a large single-file SPA. The file will be written in the next step as a complete replacement. Key features:
- Visual network map with zone rings (same layout as current)
- Click any device to open slide-out panel
- 5 tabs: Overview, Ports & Services, Traffic, Security, Actions
- Auto-refresh every 30 seconds
- Threat badges on devices (red/amber/green)
- "Scan Now", "Capture Traffic", "Mark Trusted/Untrusted" action buttons
- All data from REST API on :8085

Due to the size of this file (~1500 lines HTML/CSS/JS), this task will be implemented as a single write operation. The dashboard follows the same design language as the existing lifeos-dashboard.html (dark theme, monospace, zone colors).

- [ ] **Step 2: Open and verify dashboard**

Run: `open http://localhost:8085/network-map.html`
Expected: Network map loads with all devices, clicking a device opens the slide-out panel with live data.

---

### Task 8: MCP Bridge Tools

**Files:**
- Modify: `~/Documents/S6_COMMS_TECH/scripts/lifeos_mcp_server.py`

Add 4 network tools to the existing MCP server.

- [ ] **Step 1: Add network MCP tools to lifeos_mcp_server.py**

Append these tool definitions to the existing server (before the `if __name__` block):

```python
# ── Network Command Center Bridge ─────────────────────────────────

NETWORK_API = "http://localhost:8085"

def _network_api(path):
    """Call the Network Command Center API."""
    try:
        import urllib.request
        with urllib.request.urlopen(f"{NETWORK_API}{path}", timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def network_status() -> str:
    """Get overall network health: device count, online/offline, active threats, last scan."""
    data = _network_api("/api/network/status")
    if "error" in data:
        return f"Network Command Center unavailable: {data['error']}"
    lines = [
        f"Devices: {data.get('total_devices', '?')} total, {data.get('online_devices', '?')} online",
        f"Active threats: {data.get('active_threats', 0)}",
        f"Threat intel indicators: {data.get('threat_intel_indicators', 0)}",
        f"Last scan: {data.get('last_scan', 'never')}",
    ]
    return "\n".join(lines)

@mcp.tool()
def scan_device(identifier: str) -> str:
    """Trigger a port scan on a device by name or IP. Returns open ports and services."""
    devices = _network_api("/api/devices")
    if isinstance(devices, dict) and "error" in devices:
        return f"Error: {devices['error']}"
    # Find device by name or IP
    target = None
    for d in devices:
        if (identifier.lower() in (d.get("name") or "").lower() or
            d.get("ip") == identifier):
            target = d
            break
    if not target:
        return f"Device not found: {identifier}"
    # Trigger scan
    import urllib.request
    req = urllib.request.Request(
        f"{NETWORK_API}/api/devices/{target['id']}/scan",
        data=json.dumps({"scan_type": "standard"}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode())
        ports = result.get("ports", [])
        services = result.get("services", {})
        lines = [f"Scan results for {target['name']} ({target['ip']}):"]
        if ports:
            for p in ports:
                svc = services.get(str(p), {})
                lines.append(f"  Port {p}: {svc.get('service', 'unknown')} {svc.get('version', '')}")
        else:
            lines.append("  No open ports detected")
        if result.get("os_guess"):
            lines.append(f"  OS: {result['os_guess']}")
        return "\n".join(lines)
    except Exception as e:
        return f"Scan failed: {e}"

@mcp.tool()
def network_threats() -> str:
    """List active network threats with severity and detail."""
    threats = _network_api("/api/threats")
    if isinstance(threats, dict) and "error" in threats:
        return f"Error: {threats['error']}"
    if not threats:
        return "No active threats detected."
    lines = [f"Active threats ({len(threats)}):"]
    for t in threats:
        lines.append(f"  [{t['severity']}] {t['threat_type']}: {t['detail'][:150]}")
    return "\n".join(lines)

@mcp.tool()
def device_lookup(identifier: str) -> str:
    """Look up a device by name, IP, or MAC. Returns full device profile."""
    devices = _network_api("/api/devices")
    if isinstance(devices, dict) and "error" in devices:
        return f"Error: {devices['error']}"
    target = None
    id_lower = identifier.lower()
    for d in devices:
        if (id_lower in (d.get("name") or "").lower() or
            d.get("ip") == identifier or
            d.get("mac") == identifier):
            target = d
            break
    if not target:
        return f"Device not found: {identifier}"
    lines = [
        f"Name: {target.get('name', 'Unknown')}",
        f"IP: {target.get('ip')}  MAC: {target.get('mac')}",
        f"Vendor: {target.get('vendor', 'unknown')}  OS: {target.get('os_guess', 'unknown')}",
        f"Zone: {target.get('zone')}  Owner: {target.get('owner', 'unknown')}",
        f"Status: {'ONLINE' if target.get('is_online') else 'OFFLINE'}",
        f"Authorized: {target.get('authorized')}",
        f"First seen: {target.get('first_seen')}",
        f"Last seen: {target.get('last_seen')}",
    ]
    if target.get("notes"):
        lines.append(f"Notes: {target['notes']}")
    return "\n".join(lines)
```

- [ ] **Step 2: Verify MCP server still starts cleanly**

Run: `cd ~/Documents/S6_COMMS_TECH/scripts && python3 -c "import lifeos_mcp_server; print('MCP server imports OK')"`
Expected: No import errors.

---

### Task 9: LaunchAgent + Orchestrator Integration

**Files:**
- Create: `~/Library/LaunchAgents/com.lifeos.network-command.plist`
- Modify: `~/Documents/S6_COMMS_TECH/scripts/lifeos_orchestrator.py` (add health check task)

- [ ] **Step 1: Create LaunchAgent plist**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.lifeos.network-command</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Library/Developer/CommandLineTools/usr/bin/python3</string>
        <string>/Users/toryowens/Documents/S6_COMMS_TECH/scripts/network_command_center.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/toryowens/Documents/S6_COMMS_TECH/scripts/cleanup_logs/network_command.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/toryowens/Documents/S6_COMMS_TECH/scripts/cleanup_logs/network_command_error.log</string>
    <key>WorkingDirectory</key>
    <string>/Users/toryowens/Documents/S6_COMMS_TECH/scripts</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
```

- [ ] **Step 2: Load LaunchAgent**

Run: `launchctl load ~/Library/LaunchAgents/com.lifeos.network-command.plist`
Expected: Network Command Center starts automatically and stays running.

- [ ] **Step 3: Add orchestrator health check**

Add to the orchestrator's task list (in `lifeos_orchestrator.py`):

```python
{
    "name": "network_command_health",
    "command": "curl -s --max-time 5 http://localhost:8085/api/network/status > /dev/null && echo OK || echo FAIL",
    "schedule": "*/15 * * * *",
    "critical": True,
    "timeout": 10,
},
```

- [ ] **Step 4: Verify end-to-end**

Run:
```bash
curl -s http://localhost:8085/api/network/status | jq .
curl -s http://localhost:8085/api/devices | jq 'length'
open http://localhost:8085/network-map.html
```
Expected: API responds, device count matches, dashboard loads.

---

## Task Dependency Order

```
Task 1 (DB) → Task 2 (Device Intel) → Task 3 (Traffic) → Task 4 (Threat Intel)
                                                                    ↓
Task 5 (IDS Rules) ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ←
    ↓
Task 6 (Main Server) → Task 7 (Dashboard) → Task 8 (MCP Bridge) → Task 9 (LaunchAgent)
```

Tasks 1-5 are backend modules (can be tested independently).
Task 6 orchestrates them all.
Task 7 is the frontend.
Tasks 8-9 are integration.
