---
name: pcc-deploy
description: >
  PCC v2 production deployment instructions for Claude Code. Triggers on "deploy PCC", "publish PCC",
  "install PCC", "PCC to Tailscale". This skill orchestrates Code to build three artifacts (HTML,
  Python server, LaunchAgent), drop them into the right paths, and bring up the service on port 8079
  with Tailscale exposure. The full architectural spec lives in the companion skill
  `protocol-command-center` — read that first.
---

# PCC v2 PRODUCTION DEPLOYMENT — CODE BUILD ORDER

**Audience:** Claude Code (running on Tory's Mac)
**Prerequisites:** `~/owens-lifeos` repo cloned, `python3` available, `tailscale` running
**Outcome:** PCC accessible at `http://localhost:8079/` and via Tailscale on iPhone

---

## STEP 0 — READ THE SPEC

Before writing any code, read the full architecture spec:

```
cat ~/owens-lifeos/skills/protocol-command-center/SKILL.md
```

That skill contains: data flow, file locations, data contracts, protocol constants (Phase A/B/C macros, training split, triggers, gates), V1 post-mortem, principle ("Ambient by Default, Active by Exception").

Build to that spec. The three deliverables below implement it.

---

## STEP 1 — CREATE DIRECTORIES

```bash
mkdir -p ~/owens-lifeos/dashboards
mkdir -p ~/owens-lifeos/data/progress_photos
mkdir -p ~/owens-lifeos/logs
mkdir -p ~/Library/LaunchAgents
```

---

## STEP 2 — BUILD `protocol_command_center.html`

**Path:** `~/owens-lifeos/dashboards/protocol_command_center.html`
**Type:** Single-file React app via CDN (no build step)

**Required CDN imports:**
- React 18 (`https://unpkg.com/react@18/umd/react.production.min.js`)
- ReactDOM 18 (`https://unpkg.com/react-dom@18/umd/react-dom.production.min.js`)
- Recharts 2.12.7 (`https://unpkg.com/recharts@2.12.7/umd/Recharts.js`)
- Lucide latest (`https://unpkg.com/lucide@latest/dist/umd/lucide.min.js`)
- Babel standalone (`https://unpkg.com/@babel/standalone/babel.min.js`)
- Google Fonts: Bebas Neue, JetBrains Mono, Manrope

**Aesthetic (HUD/tactical):**
- Background `#0a0a0a`, accent `#d4a017`, text `#e5e5e5`
- Mobile-first, viewport-fit=cover for iPhone notch
- PWA meta tags so "Add to Home Screen" gives fullscreen

**Architecture:**
- Smart fetcher: tries `/api/health_data` → `/health_data.json` → mock fallback
- Header shows `LIVE` vs `MOCK` badge so Tory knows which is active
- localStorage persistence for scans (`pcc:scan:YYYY-MM-DD`), phase state (`pcc:phase_state`), trigger acks (`pcc:acked_triggers`)
- Seed `pcc:scan:2026-04-15` and `pcc:scan:2026-04-22` from real Hume scans on first load (see protocol-command-center skill)

**Four tabs:**
1. **OVERVIEW** — ambient landing. Wednesday banner if today=Wed. Active trigger banners (dismissable). Fuel card (today's day type → kcal/P/C/F). Training card (today's split → movements). Last night recovery (sleep/deep/HRV/RHR/steps/weight). Last scan delta strip.
2. **WEDNESDAY** — scan import form (date, weight, BF%, fat mass, lean mass, skeletal, body water, visceral, optional Hct) + photo capture (front/side/back via `<input type="file" capture="environment">`) + AI insight panel + phase gate progress + scan history list.
3. **TRENDS** — Weight 21d (daily + 7d rolling), BF% scan trend with phase gate ReferenceLines, Lean Mass scan trend with floor line, Sleep 14d (total + deep stacked), HRV 14d vs 30d baseline, 28d workout heatmap, trigger status panel.
4. **PROTOCOL** — Phase A/B/C selector, day-type macros table, gate criteria, advance-phase button (current phase only), trigger status with action statements.

**Phase data (from protocol-command-center spec):**
- Phase A (19.5→16% BF): High M/Th 2600·220·280·70 | Mod T/F 2450·220·230·70 | ActRec Sat 2400·220·200·75 | Rest W/Sun 2200·220·130·80. Gate: BF≤16.5% × 2wk + LM≥161.
- Phase B (16→13% BF): Refeed M/Th 2600·230·320·60 | Mod T/F 2300·230·200·65 | ActRec Sat 2200·230·170·65 | Rest W/Sun 2000·230·100·75. Gate: BF≤13.2% × 2wk + LM≥161.
- Phase C (13→10-12% BF): Refeed M/Th 2500·240·320·55 | Mod T/F 2200·240·180·60 | ActRec Sat 2100·240·140·65 | Rest W/Sun 1900·240·80·70. Gate: BF≤12% × 4wk.

**Training:** Mon UPush · Tue LStr · Wed Z2/Mob · Thu UPull · Fri LPow · Sat Z2 · Sun Rest. Movement lists in protocol-command-center spec.

**Triggers (computed from scans + health data):**
- Lean mass drop: Δ ≤ -2lb over 3 scans → RED. Δ ≤ -1lb → AMBER.
- Weight stall: 3+ of last 4 weeks <0.5lb change → AMBER.
- Sleep crater: 3+ nights <6h in last 7 → RED. 2 → AMBER.
- HRV drop: 7d avg ≥15% below 30d baseline → AMBER.
- Hct: ≥54 → RED, ≥52 → AMBER (from latest scan if Hct field present).
- Deep sleep chronic: 14d avg <0.5h → AMBER.

**API integration:**
- POST `/api/save_scan` on form submit (server persists to scans.json + photos to disk)
- POST `/api/insight` after scan save → renders OverwatchTDO weekly insight in card

---

## STEP 3 — BUILD `serve_pcc.py`

**Path:** `~/owens-lifeos/dashboards/serve_pcc.py`
**Type:** Standalone Python HTTP server, stdlib only (no Flask/Django)

**Responsibilities:**
1. Serve `protocol_command_center.html` at `/`, `/pcc`, `/index.html`
2. `GET /api/health_data` → read `~/owens-lifeos/data/health_data.json`, adapt to PCC schema (see below), return JSON. Also serve at `/health_data.json` for fallback path.
3. `POST /api/save_scan` → write to `~/owens-lifeos/data/scans.json`, decode base64 photos to `~/owens-lifeos/data/progress_photos/YYYY-MM-DD/{front,side,back}.{jpg,png}`
4. `POST /api/insight` → invoke `claude -p "<prompt>"` subprocess (Code subscription, $0 marginal), 30s timeout, fall back to deterministic summary if CLI unavailable
5. Serve photos at their relative paths (so HTML can display them later)
6. CORS enabled (`Access-Control-Allow-Origin: *`) for Tailscale and localhost
7. Bind to `0.0.0.0` by default for Tailscale exposure
8. ThreadingMixIn so concurrent requests don't block
9. CLI args: `--port 8079`, `--data-dir ~/owens-lifeos/data`, `--bind 0.0.0.0`

**Health data adapter (`load_health_data`):**
- If `health_data.json` already has `history`, `latest`, `avg_30d` keys → pass through
- Otherwise, build from `metrics.{weight,sleep,hrv,rhr,steps}.history` and `metrics.workouts`
- Return shape: `{updated_at, source: "live", latest: {weight, sleep_total, sleep_deep, sleep_rem, hrv, rhr, steps, workout_today}, avg_30d: {hrv, sleep_total, sleep_deep}, history: [{date, dow, weight, sleep_total, sleep_deep, sleep_rem, hrv, rhr, steps, workout}]}`

**Insight prompt template (OverwatchTDO voice):**
```
You are OverwatchTDO, Tory "Commander" Owens' superagent. 43yo ISTJ-A, retired First Sergeant.
On TRT (Xyosted+AI) + CJC/Ipa + Tadalafil. Operation Iron Discipline Phase {phase} toward 10-12% BF.
Voice: Southern gentleman, formal/casual blend, direct, evidence-based. Address as "Commander". 3-4 sentences max.

Scan {date}: {weight}lb · {bf_pct}%BF · {lean_mass}lb LM
Prior {prior_date}: ... (or "No prior scan.")
Active triggers: {comma-separated keys, or "none"}

Generate this week's insight: what happened → what it means → what's next.
```

---

## STEP 4 — BUILD `com.lifeos.pcc.plist`

**Path:** `~/Library/LaunchAgents/com.lifeos.pcc.plist`

**Required keys:**
- Label: `com.lifeos.pcc`
- ProgramArguments: `/usr/bin/python3 /Users/toryowens/owens-lifeos/dashboards/serve_pcc.py --port 8079 --bind 0.0.0.0 --data-dir /Users/toryowens/owens-lifeos/data`
- WorkingDirectory: `/Users/toryowens/owens-lifeos/dashboards`
- RunAtLoad: true
- KeepAlive: true
- StandardOutPath: `/Users/toryowens/owens-lifeos/logs/pcc.out.log`
- StandardErrorPath: `/Users/toryowens/owens-lifeos/logs/pcc.err.log`
- EnvironmentVariables: `PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin`

---

## STEP 5 — SMOKE TEST

```bash
# Stop any existing service
launchctl unload ~/Library/LaunchAgents/com.lifeos.pcc.plist 2>/dev/null || true

# Run server in foreground briefly
python3 ~/owens-lifeos/dashboards/serve_pcc.py --port 8079 &
SMOKE_PID=$!
sleep 2

curl -sf http://localhost:8079/api/health_data | head -50
curl -sf http://localhost:8079/ | grep -q "Protocol Command Center" && echo "HTML OK" || echo "HTML FAIL"

kill $SMOKE_PID 2>/dev/null
```

If both pass, proceed.

---

## STEP 6 — LOAD LAUNCHAGENT

```bash
launchctl load ~/Library/LaunchAgents/com.lifeos.pcc.plist
sleep 2
curl -sf http://localhost:8079/ >/dev/null && echo "Service up" || tail -20 ~/owens-lifeos/logs/pcc.err.log
```

---

## STEP 7 — VERIFY TAILSCALE EXPOSURE

```bash
TAILSCALE_HOST=$(tailscale status --json | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['Self']['DNSName'].rstrip('.'))")
echo "Tailscale URL: http://${TAILSCALE_HOST}:8079/"

# Verify port bound to all interfaces
lsof -iTCP:8079 -sTCP:LISTEN | grep -E '\*:8079|0\.0\.0\.0:8079' && echo "Bound to all interfaces" || echo "WARN: localhost only"

# macOS Firewall allow (if needed)
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add /usr/bin/python3 2>/dev/null || true
```

---

## STEP 8 — COMMIT TO REPO

```bash
cd ~/owens-lifeos
git add dashboards/protocol_command_center.html dashboards/serve_pcc.py
git commit -m "deploy: PCC v2 production on :8079 (Tailscale-exposed)"
git push
```

LaunchAgent plist lives in `~/Library/LaunchAgents/` (outside the repo) — that's correct, don't commit it.

---

## STEP 9 — REPORT TO COMMANDER

```
✅ PCC DEPLOYED
   Local:     http://localhost:8079/
   Tailscale: http://<TAILSCALE_HOST>:8079/
   Logs:      ~/owens-lifeos/logs/pcc.{out,err}.log
   Service:   launchctl list | grep pcc

NEXT (Commander action):
1. Open Safari on iPhone → http://<TAILSCALE_HOST>:8079/
2. Tap Share → Add to Home Screen → name "PCC"
3. First Wednesday scan import test: 2026-04-29
```

---

## ROLLBACK

```bash
launchctl unload ~/Library/LaunchAgents/com.lifeos.pcc.plist
rm ~/Library/LaunchAgents/com.lifeos.pcc.plist
rm -f ~/owens-lifeos/dashboards/protocol_command_center.html
rm -f ~/owens-lifeos/dashboards/serve_pcc.py
```

User data (`scans.json`, `progress_photos/`) is preserved across redeploys.

---

## TROUBLESHOOTING

| Symptom | Fix |
|---|---|
| Connection refused on :8079 | `launchctl load ~/Library/LaunchAgents/com.lifeos.pcc.plist` |
| Header shows `MOCK` instead of `LIVE` | `health_data.json` missing or schema differs — adjust `load_health_data()` adapter |
| Photos don't save | `chmod 755 ~/owens-lifeos/data/progress_photos` |
| AI insight is generic fallback | `which claude` — verify Code CLI is in PATH for user toryowens |
| Tailscale 401 / unreachable from iPhone | `tailscale status` → confirm hostname; check macOS Firewall allows 8079 |
| Server crashes silently | `tail -50 ~/owens-lifeos/logs/pcc.err.log` |
| HTML loads but blank screen | Check browser console — likely CDN block or JSX error in Babel |

---

## ARCHITECTURE REFERENCE

The full spec — data contracts, principle, V1 post-mortem, iteration log — lives in companion skill `protocol-command-center`. Read that for any design decisions not covered here.

---

*Build to spec. Test before loading. Verify Tailscale. Commit. Report. Done.*
