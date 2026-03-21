#!/usr/bin/env python3
"""
S6 Alert System — Send alerts to Commander via iMessage and macOS notifications.
Supports: iMessage (via AppleScript), macOS notification center, log file.
"""

import subprocess
import sys
import os
import json
from datetime import datetime

# Load .env file if present (no external dependency)
def _load_dotenv():
    env_paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
        os.path.expanduser("~/Documents/S6_COMMS_TECH/scripts/.env"),
    ]
    for env_path in env_paths:
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
            break

_load_dotenv()

# Commander's phone number — set via env var or .env file
COMMANDER_PHONE = os.environ.get("COMMANDER_PHONE", "")
ALERT_LOG = os.path.expanduser("~/Documents/S6_COMMS_TECH/scripts/alert_logs")

# Severity levels
CRITICAL = "CRITICAL"
HIGH = "HIGH"
MEDIUM = "MEDIUM"
LOW = "LOW"
INFO = "INFO"

def ensure_log_dir():
    os.makedirs(ALERT_LOG, exist_ok=True)

def log_alert(severity, subject, body):
    """Log alert to file regardless of delivery method."""
    ensure_log_dir()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = {
        "timestamp": timestamp,
        "severity": severity,
        "subject": subject,
        "body": body,
        "delivered_imessage": False,
        "delivered_notification": False
    }
    log_file = os.path.join(ALERT_LOG, f"alerts_{datetime.now().strftime('%Y-%m-%d')}.jsonl")
    with open(log_file, "a") as f:
        f.write(json.dumps(log_entry) + "\n")
    return log_entry

def send_imessage(phone, message):
    """Send iMessage via AppleScript."""
    # Escape special characters for AppleScript
    safe_message = message.replace('\\', '\\\\').replace('"', '\\"').replace("'", "\\'")

    script = f'''
    tell application "Messages"
        set targetService to 1st account whose service type = iMessage
        set targetBuddy to participant "{phone}" of targetService
        send "{safe_message}" to targetBuddy
    end tell
    '''

    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            return True
        else:
            # Fallback: try direct chat approach
            script2 = f'''
            tell application "Messages"
                send "{safe_message}" to chat id "iMessage;-;{phone}"
            end tell
            '''
            result2 = subprocess.run(
                ["osascript", "-e", script2],
                capture_output=True, text=True, timeout=15
            )
            return result2.returncode == 0
    except Exception:
        return False

def send_notification(title, message, subtitle="S6 Alert"):
    """Send macOS notification center alert."""
    script = f'''
    display notification "{message}" with title "{title}" subtitle "{subtitle}" sound name "Sosumi"
    '''
    try:
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=10)
        return True
    except Exception:
        return False

def alert(severity, subject, body, send_text=True):
    """
    Main alert function. Logs, sends notification, and optionally texts Commander.

    Args:
        severity: CRITICAL, HIGH, MEDIUM, LOW, INFO
        subject: Short alert title
        body: Detailed alert message
        send_text: Whether to send iMessage (default True for CRITICAL/HIGH)
    """
    entry = log_alert(severity, subject, body)

    # Always send macOS notification
    notif_sent = send_notification(f"S6 {severity}: {subject}", body[:200])
    entry["delivered_notification"] = notif_sent

    # Send iMessage for CRITICAL and HIGH, or if explicitly requested
    if send_text and severity in [CRITICAL, HIGH]:
        msg = f"S6 {severity} ALERT\n{subject}\n---\n{body[:300]}"
        imsg_sent = send_imessage(COMMANDER_PHONE, msg)
        entry["delivered_imessage"] = imsg_sent
        if not imsg_sent:
            print(f"[WARN] iMessage delivery failed for: {subject}")

    # Console output
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] S6 {severity}: {subject}")
    if severity in [CRITICAL, HIGH]:
        print(f"  >> {body}")

    return entry

def test_alert():
    """Test the alert system."""
    print("=== S6 Alert System Test ===")

    # Test notification
    print("1. Testing macOS notification...")
    send_notification("S6 Test", "Alert system test — ignore this")

    # Test iMessage
    print("2. Testing iMessage to Commander...")
    success = send_imessage(COMMANDER_PHONE, "S6 Alert System Test — This is an automated test. If you received this, alerting is operational.")
    if success:
        print("   iMessage: SENT (check phone)")
    else:
        print("   iMessage: FAILED — may need Messages.app permissions")

    # Test logging
    print("3. Testing alert log...")
    alert(INFO, "System Test", "Alert system self-test completed", send_text=False)
    print(f"   Log written to: {ALERT_LOG}")

    print("=== Test Complete ===")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_alert()
    elif len(sys.argv) > 3:
        severity = sys.argv[1].upper()
        subject = sys.argv[2]
        body = sys.argv[3]
        alert(severity, subject, body)
    else:
        print("Usage:")
        print("  python3 s6_alert.py --test")
        print("  python3 s6_alert.py CRITICAL 'Subject' 'Body message'")
        print("  Import: from s6_alert import alert, CRITICAL, HIGH, MEDIUM, LOW")
