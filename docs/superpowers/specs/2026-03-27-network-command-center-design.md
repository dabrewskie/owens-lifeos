# Network Command Center — Design Spec

**Date:** 2026-03-27
**Status:** Approved
**Author:** Commander + Overwatch Staff (Devil's Advocate reviewed)

## Problem

The Owens home network has 30 devices across an eero mesh (5 nodes, 192.168.4.0/22). The current `network_watchdog.py` provides basic ARP monitoring and port checking, and `security_audit.py` audits the Mac's posture. But there is no:

- Interactive device management
- Traffic visibility per device
- Intrusion detection
- Behavioral anomaly detection
- External exposure monitoring
- Historical analysis capability
- Real-time dashboard with device-level drill-down

The network map (`network-map.html`) is static — hover-only tooltips, no backend, no actions.

## Solution

Build a **Network Command Center** — a persistent monitoring engine with IDS capabilities, SQLite backend, interactive dashboard, and MCP bridge for iPhone access.

## Architecture

### Three Components

```
┌─────────────────────────────────────────────────────────┐
│                  Network Map Dashboard                   │
│           (network-map.html → upgraded SPA)              │
│    Click device → slide-out panel (scans, traffic,       │
│    threats, actions) | Real-time via REST API polling     │
│                   Served on :8085                         │
├─────────────────────────────────────────────────────────┤
│              Network Command Engine                       │
│          (network_command_center.py :8085)                │
│                                                           │
│  ┌──────────┐ ┌──────────┐ ┌─────┐ ┌────────┐ ┌──────┐ │
│  │ Device   │ │ Traffic  │ │ IDS │ │Schedule│ │ API  │  │
│  │ Intel    │ │ Analysis │ │     │ │ Engine │ │Server│  │
│  └──────────┘ └──────────┘ └─────┘ └────────┘ └──────┘ │
│                      │                                    │
│               ┌──────┴──────┐                            │
│               │   SQLite    │                            │
│               │ network.db  │                            │
│               └─────────────┘                            │
├─────────────────────────────────────────────────────────┤
│                    MCP Bridge                             │
│   5 tools in lifeos_mcp_server.py for iPhone access      │
│   network_status | scan_device | network_threats          │
│   device_lookup  | isolate_device (Phase 2)              │
└─────────────────────────────────────────────────────────┘
```

### Key Design Constraint (from Devil's Advocate review)

**We are tenants on this network, not landlords.** eero owns routing, DHCP, DNS forwarding, mesh backhaul, and ARP tables. v1 is a **passive sensor** with excellent detection and alerting. Active response (ARP isolation, DNS sinkholing, TCP RST) is deferred to Phase 2 when either:
- A Pi-hole is deployed (DNS-level blocking within our control), or
- The network is upgraded to managed hardware (pfSense/OPNsense)

This prevents fighting the mesh infrastructure and avoids running root-privileged daemons on the primary workstation.

## Module 1: Device Intelligence

### Continuous Discovery (every 60s)
- ARP table scan via `arp -a`
- Track online/offline transitions with timestamps
- Detect new devices immediately

### Device Identity (multi-factor — addresses MAC randomization)
11 of 30 devices (37%) use randomized MACs. Identity is determined by:
1. **MAC address** (primary key for stable devices)
2. **DHCP hostname** (from `arp -a` output and mDNS)
3. **mDNS/Bonjour name** (via `dns-sd -B _services._dns-sd._udp.`)
4. **Traffic fingerprint** (typical destinations, protocols, packet sizes)
5. **Vendor OUI** (first 3 octets of MAC, when not randomized)

Devices with randomized MACs are classified as `known-untrackable` — they appear on the map, get alerts for dangerous behavior, but do NOT contribute to behavioral baselines (which would be noise).

### Device Profile (SQLite)
- First seen, last seen, all historical IPs and MACs
- OS guess (from nmap fingerprint or TCP stack heuristics)
- Authorization status: `trusted` | `untrusted` | `quarantined` | `pending`
- Owner, zone, location, notes, photo path
- Connection history (join/leave events with timestamps)

### On-Demand Deep Scan
- Triggered from dashboard "Scan Now" button or MCP `scan_device` tool
- Uses `nmap -sV -O --top-ports 1000` for full service detection + OS fingerprint
- Fallback to Python socket scanning if nmap unavailable
- Results stored in `scan_history` table

## Module 2: Traffic Analysis

### DNS Query Logging
- `tcpdump -i any port 53` captures DNS queries in real-time
- Parses query name, type, response IP, timestamp
- Attributes to source device by IP
- Stores in `dns_queries` table
- **Encryption blindness acknowledged:** devices using DoH (DNS-over-HTTPS) bypass this entirely. Chrome, Firefox, and many apps default to DoH. This gives us visibility into ~60-70% of DNS traffic (IoT, older devices, system-level queries). Pi-hole (Phase 2) would force all DNS through a visible path.

### Bandwidth Estimation
- `tcpdump` with packet length capture (no payload)
- 5-minute rollups: bytes in/out, packet count per device
- Stored in `traffic_rollups` table
- Top destinations extracted from IP headers

### Protocol Breakdown
- Classify by port/protocol: HTTP(S), DNS, mDNS, SSDP, MQTT, SSH, SMB, etc.
- Per-device protocol mix stored in rollup JSON column
- Unusual protocol for device type = anomaly signal

### Resource Budget
- tcpdump runs with `-c` packet count limits and BPF filters to minimize CPU
- Capture runs in a background thread, writes to ring buffer
- Rollup processing happens on the 5-minute schedule, not per-packet
- Target: <5% CPU sustained on M3 Pro

## Module 3: Intrusion Detection System

### Internal Threat Detection

| Rule | Detection Method | Severity |
|------|-----------------|----------|
| ARP Spoofing | Same IP claimed by different MAC within 60s | CRITICAL |
| Rogue DHCP | DHCP OFFER from non-gateway IP | CRITICAL |
| MAC Flooding | >50 new MACs in 5-minute window | HIGH |
| Internal Port Scan | Device probing >10 ports on another device in 60s | HIGH |
| Lateral Movement | Device connecting to >5 new internal hosts in 1 hour | HIGH |
| DNS Tunneling | DNS queries with >50 char subdomain or >100 queries/min to single domain | MEDIUM |
| Unauthorized Service | Known-safe device opens new listening port | MEDIUM |

### External Exposure Detection

| Check | Method | Schedule |
|-------|--------|----------|
| Public IP Monitor | `curl -s ifconfig.me` | Every 6h |
| Shodan Lookup | Shodan API on public IP | Every 6h |
| Expected vs Actual | Compare exposed services against whitelist (only Tailscale Funnel :443 should be visible) | Every 6h |
| UPnP Audit | Check for UPnP-forwarded ports (best-effort, eero may not expose) | Daily |
| DNS Leak Test | Verify DNS goes through Cloudflare, not ISP | Daily |
| Breach Check | HaveIBeenPwned API for family emails | Weekly |

### Behavioral Anomaly Detection

**Baseline period:** 7 days per device (stable-MAC devices only)
**Metrics baselined:** hourly traffic volume, destination set, protocol mix, active hours, DNS query rate

| Anomaly | Trigger | Confidence |
|---------|---------|------------|
| Traffic spike | >3x baseline for time-of-day | MEDIUM |
| New destination country | GeoIP lookup, never-seen country | MEDIUM |
| Off-hours activity | Device active outside normal hours (>2 stddev) | LOW |
| New protocol | Device using protocol never seen before | LOW |
| Newly-registered domain | Domain age <30 days (via WHOIS or threat intel) | HIGH |
| Known C2/malware domain | Match against threat intel feeds | CRITICAL |

### Threat Intel Feeds (refreshed daily 0300)
- **abuse.ch URLhaus** — malware distribution URLs
- **abuse.ch Feodo Tracker** — C2 botnet IPs
- **PhishTank** — verified phishing URLs
- **Emerging Threats** — open Suricata/Snort rules (IP/domain indicators only)

Feed staleness acknowledged: daily refresh means 0-24h lag. Acceptable for home network.

## Module 4: Alert & Response

### v1: Detect and Alert (no auto-response)

**CONFIRMED threats** (high confidence):
- iMessage FLASH via `s6_alert.py`
- Dashboard: device turns red, threat badge appears
- Logged to `threats` table + `alert_history.json`
- Includes specific remediation steps ("Open eero app > block device X")

**SUSPECTED threats** (medium confidence):
- iMessage PRIORITY (batched hourly)
- Dashboard: device turns amber, warning badge
- Logged to `threats` table

**INFORMATIONAL** (low confidence):
- Dashboard only, no notification
- Logged to `threats` table

### Phase 2: Auto-Response (deferred)
Requires one of:
- Pi-hole deployed (DNS-level blocking)
- Managed router (pfSense/OPNsense with firewall rules)
- Dedicated response device (Raspberry Pi, not Mac)

When implemented:
- Rate limiter: max 3 auto-responses per hour, then alert-only
- Circuit breaker: 5 false positives in 24h disables auto-response, alerts Commander
- Kill switch: MCP tool `disable_auto_response` from iPhone
- All actions reversible and logged

## Module 5: Scheduled Operations

| Interval | Task | Scope |
|----------|------|-------|
| 60s | ARP discovery + online/offline tracking | All devices |
| 5 min | Traffic rollup + anomaly check + IDS rule evaluation | All devices |
| 15 min | Critical port check (22, 23, 445, 3389, 5555) | Kids + IoT zones |
| 1 hour | Top-100 port scan | Kids + IoT zones |
| 6 hours | External exposure (public IP + Shodan + DNS leak) | Network perimeter |
| Daily 0300 | Threat intel feed refresh | Threat DB |
| Daily 0400 | SQLite backup to iCloud | Database |
| Weekly Sun 0200 | Full port scan all devices (top 1000) | All devices |
| Weekly Sun 0300 | Baseline recalculation + anomaly threshold adjustment | Stable-MAC devices |

## Database Schema (SQLite, WAL mode)

```sql
-- Core device tracking
CREATE TABLE devices (
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

-- Port scan results
CREATE TABLE scan_history (
    id INTEGER PRIMARY KEY,
    device_id INTEGER REFERENCES devices(id),
    timestamp TEXT NOT NULL,
    scan_type TEXT,
    ports_open TEXT,  -- JSON array
    services TEXT,    -- JSON object {port: service_info}
    os_fingerprint TEXT,
    raw_output TEXT
);

-- Traffic 5-minute rollups
CREATE TABLE traffic_rollups (
    id INTEGER PRIMARY KEY,
    device_id INTEGER REFERENCES devices(id),
    timestamp TEXT NOT NULL,
    bytes_in INTEGER DEFAULT 0,
    bytes_out INTEGER DEFAULT 0,
    packets INTEGER DEFAULT 0,
    top_destinations TEXT,  -- JSON array [{ip, domain, bytes, packets}]
    protocols TEXT          -- JSON object {protocol: packet_count}
);

-- DNS query log
CREATE TABLE dns_queries (
    id INTEGER PRIMARY KEY,
    device_id INTEGER REFERENCES devices(id),
    timestamp TEXT NOT NULL,
    domain TEXT NOT NULL,
    query_type TEXT,
    response_ip TEXT,
    flagged INTEGER DEFAULT 0,
    flag_reason TEXT
);

-- Detected threats
CREATE TABLE threats (
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

-- Behavioral anomalies
CREATE TABLE anomalies (
    id INTEGER PRIMARY KEY,
    device_id INTEGER REFERENCES devices(id),
    timestamp TEXT NOT NULL,
    anomaly_type TEXT NOT NULL,
    baseline_value REAL,
    observed_value REAL,
    deviation_pct REAL,
    detail TEXT
);

-- Per-device behavioral baselines
CREATE TABLE baselines (
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

-- Threat intelligence indicators
CREATE TABLE threat_intel (
    id INTEGER PRIMARY KEY,
    indicator_type TEXT NOT NULL,  -- domain, ip, url
    indicator_value TEXT NOT NULL,
    source TEXT,
    severity TEXT,
    added TEXT NOT NULL,
    expires TEXT
);

-- Auto-response log (Phase 2, table created now for schema stability)
CREATE TABLE auto_responses (
    id INTEGER PRIMARY KEY,
    threat_id INTEGER REFERENCES threats(id),
    action TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    reversed INTEGER DEFAULT 0,
    reversed_at TEXT,
    reversed_by TEXT
);

-- Device online/offline history
CREATE TABLE connection_history (
    id INTEGER PRIMARY KEY,
    device_id INTEGER REFERENCES devices(id),
    event TEXT NOT NULL,  -- 'online' | 'offline'
    timestamp TEXT NOT NULL
);

-- Public IP tracking
CREATE TABLE public_ip_history (
    id INTEGER PRIMARY KEY,
    ip TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    shodan_result TEXT  -- JSON
);

-- Indexes
CREATE INDEX idx_dns_device_ts ON dns_queries(device_id, timestamp);
CREATE INDEX idx_dns_domain ON dns_queries(domain);
CREATE INDEX idx_dns_flagged ON dns_queries(flagged) WHERE flagged = 1;
CREATE INDEX idx_traffic_device_ts ON traffic_rollups(device_id, timestamp);
CREATE INDEX idx_threats_device ON threats(device_id);
CREATE INDEX idx_threats_severity ON threats(severity);
CREATE INDEX idx_threats_unresolved ON threats(resolved) WHERE resolved = 0;
CREATE INDEX idx_scans_device ON scan_history(device_id);
CREATE INDEX idx_anomalies_device ON anomalies(device_id);
CREATE INDEX idx_baselines_device ON baselines(device_id, metric);
CREATE INDEX idx_intel_value ON threat_intel(indicator_value);
CREATE INDEX idx_connection_device ON connection_history(device_id);
```

## Dashboard — Click Panel

When a device is clicked on the network map, a slide-out panel appears from the right with tabs:

### Overview Tab
- Device card: name, IP, MAC, vendor, OS guess, zone, owner
- Online/offline status with uptime duration
- First seen / last seen timestamps
- Authorization badge (trusted/untrusted/pending/quarantined)
- Edit: name, zone, owner, notes (writes to SQLite via API)
- Connection history timeline (last 7 days of join/leave)

### Ports & Services Tab
- Current open ports table: port, protocol, service, version
- "Scan Now" button (triggers nmap via API)
- Historical port timeline: sparkline showing ports over time
- Service change alerts (new port appeared, port closed)

### Traffic Tab
- Bandwidth graph: 24h default, toggleable to 7d/30d
- Top 10 destinations table: IP, domain (reverse DNS), bytes, last seen
- Protocol pie chart
- DNS query log: scrollable table, threat-flagged entries highlighted red
- "Export PCAP" button for forensic capture (starts a 60s tcpdump filtered to this device)

### Security Tab
- Threat history: all threats for this device, severity-colored
- Active anomaly flags
- IDS rule matches
- External exposure status (if device has UPnP forwards)
- Vulnerability notes (manual, from scan results)

### Actions Tab
- **Scan Now** — full nmap scan
- **Quick Scan** — top 20 ports only
- **Capture Traffic** — 60s packet capture, download PCAP
- **Mark Trusted / Untrusted / Quarantined**
- **Add to Watch List** — increases scan frequency for this device
- **Add Notes** — free-text annotation
- **View in eero** — deep link to eero app device page (if possible)

## REST API Endpoints

```
GET  /api/devices                    — all devices with current status
GET  /api/devices/:id                — single device full profile
GET  /api/devices/:id/scans          — scan history
GET  /api/devices/:id/traffic        — traffic rollups (query: range=24h|7d|30d)
GET  /api/devices/:id/dns            — DNS queries (query: limit, flagged_only)
GET  /api/devices/:id/threats        — threat history
GET  /api/devices/:id/connection     — online/offline history
POST /api/devices/:id/scan           — trigger on-demand scan
POST /api/devices/:id/capture        — start packet capture (returns download URL)
PUT  /api/devices/:id                — update device metadata (name, zone, owner, auth, notes)
GET  /api/threats                    — all active threats (query: severity, unresolved)
GET  /api/threats/summary            — threat counts by severity
GET  /api/anomalies                  — active anomalies
GET  /api/network/status             — overall network health summary
GET  /api/network/topology           — device-to-eero-node mapping (best-effort)
GET  /api/network/external           — public IP, Shodan results, exposure status
GET  /api/network/stats              — aggregate bandwidth, device counts, uptime
GET  /api/intel/feeds                — threat intel feed status and counts
POST /api/intel/refresh              — force threat intel refresh
GET  /api/dashboard                  — pre-aggregated dashboard payload (single call for initial load)
```

## MCP Bridge Tools (added to lifeos_mcp_server.py)

| Tool | Description |
|------|-------------|
| `network_status` | Overall network health: device count, online/offline, active threats, last scan |
| `scan_device` | Trigger scan by device name or IP, return results |
| `network_threats` | List active threats with severity and detail |
| `device_lookup` | Get full device profile by name, IP, or MAC |
| `network_dashboard_url` | Return the dashboard URL for quick access |

## File Layout

```
~/Documents/S6_COMMS_TECH/scripts/
    network_command_center.py      — main server (all modules + API + scheduler)
    network_ids_rules.py           — IDS detection rules (separated for maintainability)
    network_threat_intel.py        — threat feed ingestion and matching
    network_db.py                  — SQLite schema, migrations, query helpers

~/Documents/S6_COMMS_TECH/dashboard/
    network-map.html               — upgraded interactive dashboard
    network.db                     — SQLite database
    network_backups/               — daily SQLite backups (also synced to iCloud)

~/Documents/S6_COMMS_TECH/scripts/network_data/
    captures/                      — on-demand PCAP files (auto-cleaned after 7 days)
    threat_feeds/                  — downloaded threat intel feed files
```

## Integration

- **Orchestrator:** add `network_command_center` task, health check via `/api/network/status`
- **Overwatch:** reads `/api/threats/summary` for network security posture in briefs
- **Alert system:** uses `s6_alert.py` for iMessage FLASH/PRIORITY
- **Remediation tracker:** integrates via `remediation_tracker.py` for closed-loop
- **Life OS Dashboard:** add "Network" tab linking to `:8085` or embed as iframe
- **LaunchAgent:** `com.lifeos.network-command.plist` with KeepAlive for persistence

## Dependencies

### Required
```bash
brew install nmap              # Port scanning, OS fingerprint, service detection
```

### Optional (enhance but not required)
```bash
pip3 install shodan            # External exposure API (free tier: 100 queries/mo)
brew install arp-scan          # Faster ARP discovery
pip3 install scapy             # Advanced packet analysis (Phase 2)
pip3 install geoip2            # GeoIP for destination country detection
```

### Already Available
- Python 3.9 (socket, http.server, sqlite3, subprocess, json, struct)
- tcpdump (macOS built-in, requires sudo for promiscuous mode)
- jq (installed)
- s6_alert.py, remediation_tracker.py, network_watchdog.py (existing infrastructure)

## Phasing

### Phase 1 (this build)
- Network Command Engine with all 5 modules
- SQLite database with full schema
- Interactive dashboard with click panels
- MCP bridge (4 tools, isolate_device deferred)
- IDS detection rules (internal + external + behavioral)
- Alert integration (iMessage FLASH/PRIORITY)
- LaunchAgent for persistence
- Orchestrator integration

### Phase 2 (future — requires hardware)
- Pi-hole deployment for DNS-level blocking + full DNS visibility
- DNS sinkholing auto-response via Pi-hole API
- `isolate_device` MCP tool (via Pi-hole blacklist)
- DoH detection and alerting (devices bypassing Pi-hole)

### Phase 3 (future — requires network upgrade)
- Managed router (pfSense/OPNsense) for true firewall rules
- VLAN segmentation (IoT, kids, primary, guest)
- Device-level bandwidth throttling
- Full auto-response engine on dedicated hardware
- WireGuard VPN for remote network access (replaces Tailscale for this use case)

## Success Criteria

- [ ] All 30 known devices appear on interactive map with correct metadata
- [ ] Click any device to see full profile, scan history, traffic, threats
- [ ] "Scan Now" returns results within 30 seconds
- [ ] New device detection fires within 60 seconds of device joining
- [ ] DNS query logging captures visible (non-DoH) queries
- [ ] IDS rules detect simulated ARP spoof and port scan
- [ ] External exposure check returns Shodan results for public IP
- [ ] Behavioral baselines established after 7 days for stable-MAC devices
- [ ] iMessage alerts fire for CONFIRMED and SUSPECTED threats
- [ ] SQLite backup runs daily to iCloud
- [ ] Dashboard loads in <2 seconds, API responses <500ms
- [ ] CPU usage <5% sustained on M3 Pro
- [ ] System runs 30 days without manual intervention
