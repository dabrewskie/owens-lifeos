---
name: protocol-command-center
description: >
  Health protocol execution dashboard ("PCC") for Operation Iron Discipline Phase 3. Mobile-first passive
  interface that pulls from Apple Health for ambient status, requires active engagement only on Wednesdays
  (Hume scan import + photos + week-over-week analysis) or when triggers fire. Toward end state 10-12% BF
  with lean mass held or increased. V2 production deployed via Tailscale on port 8079. Triggers on
  (1) "PCC", "Protocol Command Center", (2) "Scan import", "Wednesday check-in", (3) "Phase A/B/C",
  (4) "Protocol trigger". When commander references PCC deployment or production build, execute the
  CODE BUILD ORDER below.
---

# Protocol Command Center (PCC) — V2 PRODUCTION

**Status:** V2 PRODUCTION DEPLOYED — 2026-04-24
**Owner:** Commander Owens
**URL:** `https://torys-macbook-pro.<tailnet>.ts.net:8079/` (verify tailnet hostname)
**Service:** `com.lifeos.pcc` LaunchAgent on port 8079

---

## QUICK START FOR COMMANDER

**On iPhone:**
1. Connect to Tailscale (already running)
2. Open Safari → `https://torys-macbook-pro.<tailnet>.ts.net:8079/`
3. Tap Share → Add to Home Screen → name "PCC"
4. PCC icon now opens fullscreen — bookmark this

**On Mac:**
- Browser: `http://localhost:8079/`
- Logs: `~/owens-lifeos/logs/pcc.{out,err}.log`
- Service control: `launchctl {load,unload} ~/Library/LaunchAgents/com.lifeos.pcc.plist`

---

## V1 POST-MORTEM (kept for institutional memory)

V1 daily morning check-in killed same day. Root cause: daily-input compliance tracker conflicts with ISTJ-A model. All four data points already in Apple Health. Manual entry was ceremony, not signal.

**Principle codified:**
> Ambient by Default, Active by Exception. If the data exists, read it. Don't collect it daily.

---

## V2 ARCHITECTURE

```
Apple Watch → Apple Health → Health Auto Export
       ↓
~/Documents/S6_COMMS_TECH/dashboard/health/health_data.json   (canonical iCloud)
       ↓
[orchestrator task: pcc_mirror_health, every 15 min — runs in FDA context]
       ↓
~/owens-lifeos/data/health_data.json   (TCC-safe local mirror)
       ↓
serve_pcc.py (port 8079, LaunchAgent com.lifeos.pcc — no FDA needed)
       ↓
Tailscale → iPhone Safari → "PCC" home screen icon
```

### Why the mirror?
The PCC LaunchAgent does not have Full Disk Access — so it cannot read
iCloud-mirrored paths under `~/Documents/`. The orchestrator's LaunchAgent
DOES have FDA, so a small mirror task copies the canonical file to the
non-protected repo path on a 15-minute interval (idempotent, SHA-gated).
PCC reads the mirror; canonical file remains the single source of truth.

If the mirror is missing, PCC tries the iCloud path directly (works only
when invoked from a foreground/FDA context). If both fail, deterministic
mock keeps the UI rendering. Header shows `LIVE` vs `MOCK` either way.

### Data Flow
- **Read:** PCC fetches `/api/health_data` → `serve_pcc.py` reads `health_data.json` → returns adapted shape
- **Write:** Wednesday scan submit → POST `/api/save_scan` → writes `scans.json` + photos to `progress_photos/YYYY-MM-DD/`
- **Insight:** POST `/api/insight` → invokes Claude CLI (subscription, $0 marginal) → returns OverwatchTDO weekly insight

### File Locations
| File | Path |
|---|---|
| HTML (single-file React via CDN) | `~/owens-lifeos/dashboards/protocol_command_center.html` |
| Server | `~/owens-lifeos/dashboards/serve_pcc.py` |
| LaunchAgent | `~/Library/LaunchAgents/com.lifeos.pcc.plist` |
| Mirror script | `~/Documents/S6_COMMS_TECH/scripts/pcc_mirror_health.py` |
| Health data canonical | `~/Documents/S6_COMMS_TECH/dashboard/health/health_data.json` |
| Health data mirror | `~/owens-lifeos/data/health_data.json` |
| Scan persistence | `~/owens-lifeos/data/scans.json` |
| Photos | `~/owens-lifeos/data/progress_photos/YYYY-MM-DD/{front,side,back}.jpg` |
| Logs | `~/owens-lifeos/logs/pcc.{out,err}.log` |

---

## CODE BUILD ORDER

When Commander invokes "deploy PCC" or "publish PCC to Tailscale", execute these steps in order:

### Step 1: Locate source files
The Commander will provide three files (downloaded from Claude.ai):
- `protocol_command_center.html`
- `serve_pcc.py`
- `com.lifeos.pcc.plist`

These should be saved by Commander to `~/Downloads/` first. Confirm locations before proceeding.

### Step 2: Deploy to repo
```bash
mkdir -p ~/owens-lifeos/dashboards
mkdir -p ~/owens-lifeos/data/progress_photos
mkdir -p ~/owens-lifeos/logs

cp ~/Downloads/protocol_command_center.html ~/owens-lifeos/dashboards/
cp ~/Downloads/serve_pcc.py ~/owens-lifeos/dashboards/
chmod +x ~/owens-lifeos/dashboards/serve_pcc.py

# Test the server runs
python3 ~/owens-lifeos/dashboards/serve_pcc.py --port 8079 &
SERVER_PID=$!
sleep 2
curl -sf http://localhost:8079/api/health_data | head -50
kill $SERVER_PID
```

### Step 3: Install LaunchAgent
```bash
# Stop any existing PCC service
launchctl unload ~/Library/LaunchAgents/com.lifeos.pcc.plist 2>/dev/null || true

# Install plist
cp ~/Downloads/com.lifeos.pcc.plist ~/Library/LaunchAgents/

# Load and start
launchctl load ~/Library/LaunchAgents/com.lifeos.pcc.plist

# Verify
sleep 2
curl -sf http://localhost:8079/ | head -5
ps aux | grep serve_pcc | grep -v grep
```

### Step 4: Verify Tailscale exposure
```bash
# Get tailnet hostname
TAILSCALE_NAME=$(tailscale status --json 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('Self',{}).get('DNSName','').rstrip('.'))")
echo "Tailscale URL: https://${TAILSCALE_NAME}:8079/"

# Verify port is bound to 0.0.0.0 (not just localhost)
lsof -iTCP:8079 -sTCP:LISTEN | grep -E '\*:8079|0\.0\.0\.0:8079' || echo "WARN: not bound to all interfaces"

# macOS firewall — allow incoming on 8079 if not already
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add /usr/bin/python3 2>/dev/null || true
```

### Step 5: Commit and report
```bash
cd ~/owens-lifeos
git add dashboards/protocol_command_center.html dashboards/serve_pcc.py
git commit -m "deploy: PCC v2 production server on :8079"
git push
```

Report to Commander:
- ✅ HTML deployed to dashboards/
- ✅ Server running as LaunchAgent on :8079
- ✅ Tailscale URL: https://<hostname>:8079/
- ✅ Health data adapter: live | mock-fallback (depending on health_data.json presence)
- Next action for Commander: Open Safari on iPhone → URL → Add to Home Screen

---

## HEALTH DATA ADAPTER

`serve_pcc.py` includes `load_health_data()` which adapts whatever shape `health_data.json` has into the shape PCC expects. The adapter is conservative — if the file already matches PCC shape (has `history`, `latest`, `avg_30d`), it passes through. Otherwise it builds the shape from `metrics.weight.history`, `metrics.sleep.history`, etc.

**If the actual `health_data.json` schema differs from the adapter's assumptions:** modify `load_health_data()` in `serve_pcc.py`. The PCC HTML expects this returned shape:

```json
{
  "updated_at": "ISO timestamp",
  "source": "live",
  "latest": {
    "weight": float, "sleep_total": float, "sleep_deep": float, "sleep_rem": float,
    "hrv": int, "rhr": int, "steps": int, "active_cal": int,
    "workout_today": { "type": str, "duration_min": int } | null
  },
  "avg_30d": { "hrv": int, "sleep_total": float, "sleep_deep": float },
  "history": [
    { "date": "YYYY-MM-DD", "dow": int (0=Sun),
      "weight": float, "sleep_total": float, "sleep_deep": float, "sleep_rem": float,
      "hrv": int, "rhr": int, "steps": int, "active_cal": int,
      "workout": { "type": str, "duration_min": int } | null }
  ]
}
```

If the live endpoint fails, PCC HTML automatically falls back to a mock so the UI still renders. The header shows `LIVE` vs `MOCK` so Commander knows which is active.

---

## PROTOCOL DATA (embedded in HTML — authoritative reference here)

### Phase A — Foundation Recomp (19.5% → 16% BF)
Avg 2,470 kcal · 0.5-0.7 lb/wk · Diet break every 6 wk @ 2,800 kcal × 5-7 days

| Day | Days | Cal | P | C | F |
|---|---|---|---|---|---|
| HIGH | Mon, Thu | 2,600 | 220 | 280 | 70 |
| MODERATE | Tue, Fri | 2,450 | 220 | 230 | 70 |
| ACTIVE REC | Sat | 2,400 | 220 | 200 | 75 |
| REST | Wed, Sun | 2,200 | 220 | 130 | 80 |

### Phase B — Precision Cut (16% → 13% BF)
Avg 2,290 kcal · 0.4-0.5 lb/wk · Diet break every 4-5 wk × 5 days

### Phase C — Single Digits (13% → 10-12% BF)
Avg 2,200 kcal · 0.25-0.4 lb/wk · Diet break every 3-4 wk × 5-7 days MANDATORY

### Training Split
Mon UPush · Tue LStr · Wed Z2/Mob · Thu UPull · Fri LPow · Sat Z2 · Sun Rest

### Triggers
LM drop Δ≤-2lb/3scans (RED) · Weight stall 3wk flat (AMB) · Sleep <6h 3+nights (RED) · HRV -15% (AMB) · Hct ≥54% (RED) · Deep sleep 14d<0.5h (AMB)

### Phase Gates
A→B: BF≤16.5% × 2wk + LM≥161 | B→C: BF≤13.2% × 2wk + LM≥161 | C→M: BF≤12% × 4wk

---

## V2 PRODUCTION ENHANCEMENTS (Code post-deploy iteration)

After Commander has used the deployed PCC for 1-2 weeks, evaluate these enhancements:

### Push Notifications
- Wed 0700 reminder: "Hume scan + photos today"
- Trigger fires (RED only): "PCC ALERT: Lean mass dropping — check dashboard"
- Implementation: Pushover API (verify Commander has account) → orchestrator task fires curl

### Anticipation Engine Integration
- New task: `protocol_trigger_scan` every 6h
- Reads `scans.json` + `health_data.json`, runs trigger detection, emits to morning sweep
- Surfaces RED triggers in Morning Sweep priority slot

### COP Writeback
- New MCP tool: `lifeos:log_protocol_day` — daily compliance signals
- Wednesday scan submit auto-fires `lifeos:log_completion` for Medical domain

### Real Cron-Aware Reminders
- Wed 0700 calendar event auto-created if missing
- "Scan day" presence detected by checking `scans.json` for current week

### Model Upgrade (Hard Deadline)
- `claude-sonnet-4-20250514` deprecated June 15
- `serve_pcc.py` uses Claude CLI (no model lock-in) — but if anywhere hardcoded, upgrade

---

## TROUBLESHOOTING

| Symptom | Likely Cause | Fix |
|---|---|---|
| 502 / connection refused | LaunchAgent not loaded | `launchctl load ~/Library/LaunchAgents/com.lifeos.pcc.plist` |
| Header shows "MOCK" | health_data.json missing or shape mismatch | Check `~/owens-lifeos/data/health_data.json` exists; review adapter |
| Photos not saving | `progress_photos/` not writable | `mkdir -p ~/owens-lifeos/data/progress_photos && chmod 755` |
| AI insight is fallback text | Claude CLI hangs under launchd context (config-bootstrap or TCC path) | Known V2.1 limitation. Fallback is graceful. To diagnose: `launchctl unload com.lifeos.pcc.plist`, run server in foreground, retry `/api/insight` — if it works there, daemon-context auth is the issue |
| Tailscale 401 / blocked | Firewall or wrong host | `tailscale status` → verify hostname; check macOS Firewall |
| Server crashes | Check logs | `tail -50 ~/owens-lifeos/logs/pcc.err.log` |

---

## ITERATION LOG

| Date | Version | Change |
|---|---|---|
| 2026-04-24 | 1.0 | V1 artifact deployed |
| 2026-04-24 | 1.0 KILLED | Daily check-in anti-pattern |
| 2026-04-24 | 2.0 prototype | V2: passive + Wed-centric + trigger-driven |
| 2026-04-24 | 2.0 production | Single-file HTML + serve_pcc.py + LaunchAgent. Tailscale-published. CODE BUILD ORDER documented in this skill. |
| 2026-04-25 | 2.1 production | RCA fix: PCC LaunchAgent lacks FDA → cannot read iCloud `~/Documents/`. Solution: TCC-safe local mirror at `~/owens-lifeos/data/health_data.json`, refreshed every 15min by `pcc_mirror_health.py` task in orchestrator (which has FDA). Triple-validated per SO #14. Insight via Claude CLI gracefully falls back under launchd (known limitation). |

---

*"Ambient by default. Active by exception. Read the data, don't collect it."*
