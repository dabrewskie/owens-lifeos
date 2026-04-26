---
name: pcc-deploy
description: >
  PCC Production Deployment Bootstrap. Self-contained installer for Protocol Command Center v2 production.
  HTML, server, and LaunchAgent payloads are embedded as base64 within this SKILL.md. Triggers on
  "deploy PCC", "publish PCC", "PCC bootstrap", "install PCC". This skill IS the deployment artifact.
  Code reads it, extracts the bash, runs it. After deploy, PCC runs on port 8079 via com.lifeos.pcc
  LaunchAgent, accessible via Tailscale at http://<hostname>:8079/.
---

# PCC PRODUCTION DEPLOYMENT BOOTSTRAP

**Purpose:** One-shot installer for Protocol Command Center v2. Drops HTML to `dashboards/`, installs Python server, registers LaunchAgent, verifies accessibility.

**For Code:** Pull latest, extract the deploy section between markers, run it. The deploy script extracts its own embedded payloads.

## EXECUTION (Code runs this)

```
cd ~/owens-lifeos
git pull
sed -n '/^# DEPLOY_BEGIN$/,/^# DEPLOY_END$/p' skills/pcc-deploy/SKILL.md > /tmp/deploy_pcc.sh
bash /tmp/deploy_pcc.sh
```

## WHAT GETS DEPLOYED

| File | Path |
|---|---|
| HTML (single-file React via CDN) | `~/owens-lifeos/dashboards/protocol_command_center.html` |
| Python server | `~/owens-lifeos/dashboards/serve_pcc.py` |
| LaunchAgent | `~/Library/LaunchAgents/com.lifeos.pcc.plist` |
| Logs | `~/owens-lifeos/logs/pcc.{out,err}.log` |
| Photo storage | `~/owens-lifeos/data/progress_photos/` |
| Scan persistence | `~/owens-lifeos/data/scans.json` |

## DEPLOYMENT SCRIPT

The block below, between `# DEPLOY_BEGIN` and `# DEPLOY_END` markers, is the executable installer with all payloads embedded.

# DEPLOY_BEGIN
[CONTENT_OMITTED_FOR_BREVITY_SEE_FILE]
# DEPLOY_END
