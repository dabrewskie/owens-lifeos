#!/usr/bin/env python3
"""
S3 File Cleanup Agent — Autonomous file organization daemon.
Matches Tory Owens' CoS staff section structure across all storage locations.

Scans: ~/Downloads, iCloud Drive, OneDrive, ~/Documents
Cadence: Daily at 0600 via LaunchAgent
Safety: Audit trail, protected paths, dry-run mode

Usage:
    python3 file_cleanup_agent.py                # Dry run (default) — shows what would happen
    python3 file_cleanup_agent.py --execute      # Live run — moves files
    python3 file_cleanup_agent.py --report       # Just print current state
    python3 file_cleanup_agent.py --purge        # Also purge stale DMGs/screenshots
"""

import os
import sys
import shutil
import json
import re
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# ─── CONFIGURATION ──────────────────────────────────────────────────────────

HOME = Path.home()
ICLOUD = HOME / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
ONEDRIVE = HOME / "Library" / "CloudStorage" / "OneDrive-Personal"
DOWNLOADS = HOME / "Downloads"
DOCUMENTS = HOME / "Documents"

# Script's own location — used to avoid self-disruption
SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPT_ROOT = SCRIPT_DIR.parent  # S6_COMMS_TECH

LOG_DIR = DOCUMENTS / "S6_COMMS_TECH" / "scripts" / "cleanup_logs"
AUDIT_LOG = LOG_DIR / f"cleanup_audit_{datetime.now().strftime('%Y-%m-%d')}.jsonl"

# Purge thresholds
DMG_MAX_AGE_DAYS = 7
SCREENSHOT_MAX_AGE_DAYS = 14

# Body Recomp photo staging and destination
BODY_RECOMP_STAGING = DOWNLOADS / "body-recomp"
BODY_RECOMP_DEST = ICLOUD / "MEDICAL_HEALTH_PERFORMANCE" / "Body_Recomp_Photos"

# ─── CANONICAL S-SECTION TAXONOMY ───────────────────────────────────────────

S_SECTIONS = [
    "00_COS_COMMAND",
    "S1_PERSONNEL_FAMILY",
    "S2_INTELLIGENCE_DEVELOPMENT",
    "S3_OPERATIONS_ADMIN",
    "S4_LOGISTICS_FINANCIAL",
    "S5_PLANS_INNOVATION",
    "S6_COMMS_TECH",
    "S7_TRAINING_READINESS",
    "MEDICAL_HEALTH_PERFORMANCE",
    "MILITARY_LEGACY",
    "RECREATION",
    "ARCHIVE",
]

# Locations that get the full S-section structure
MANAGED_ROOTS = {
    "icloud": ICLOUD,
    "onedrive": ONEDRIVE,
    "documents": DOCUMENTS,
}

# ─── PROTECTED PATHS (never touch) ──────────────────────────────────────────

PROTECTED_PATHS = {
    # Core Life OS files
    ICLOUD / "TORY_OWENS_PROFILE.md",
    ICLOUD / "TORY_OWENS_HISTORY.md",
    ICLOUD / "TORY_OWENS_TIMELINE.html",
    ICLOUD / "COP.md",
    ICLOUD / "COS_Apple_Calendar_Sync.command",
    ICLOUD / "COS_Apple_Calendar_Sync_Playbook.md",
    # Health infrastructure
    ICLOUD / "Health",
    ICLOUD / "apple_health_export",
    # Claude config
    ICLOUD / ".claude",
    ONEDRIVE / ".claude",
    HOME / ".claude",
    # Desktop/Documents symlinks in iCloud
    ICLOUD / "Desktop",
    ICLOUD / "Documents",
    # Financial plan (canonical location)
    ICLOUD / "Family" / "Financial-Plan",
    # OneDrive system
    ONEDRIVE / ".Trash",
    ONEDRIVE / "Icon\r",
    ONEDRIVE / "Icon",
    ONEDRIVE / "OneDrive",  # symlink
    # Documents system
    DOCUMENTS / "life-os",
    DOCUMENTS / "Claude",
    DOCUMENTS / "_REVIEW-DELETE",
}

PROTECTED_PREFIXES = [
    ICLOUD / "Health",
    ICLOUD / "apple_health_export",
    ICLOUD / ".claude",
    ONEDRIVE / ".claude",
    ONEDRIVE / ".Trash",
    DOCUMENTS / "life-os",
    DOCUMENTS / "Claude",
    DOCUMENTS / "_REVIEW-DELETE",
    # Don't re-process already-archived content
    ICLOUD / "ARCHIVE",
    ONEDRIVE / "ARCHIVE",
    DOCUMENTS / "ARCHIVE",
]

# Files to always skip
SKIP_NAMES = {".DS_Store", ".localized", "Icon\r", "Icon", ".849C9593-D756-4E56-8D6E-42412F2A707B", ".env"}

# ─── FILING RULES ───────────────────────────────────────────────────────────
# Pattern → (S-section, optional subfolder)
# Checked in order; first match wins.

FILING_RULES = [
    # ── S4: Logistics & Financial (FIRST — catch tax/financial before generic keywords) ──
    (r"(?i)(tax.?return|individual.?tax|w-?2|1098|1099|irs|turbotax)", "S4_LOGISTICS_FINANCIAL", "Taxes"),
    (r"(?i)(budget|transaction|rocket.?money|mint|ynab)", "S4_LOGISTICS_FINANCIAL", "Budget"),
    (r"(?i)(bank|statement|checking|savings|closing.?disclosure|mortgage)", "S4_LOGISTICS_FINANCIAL", "Banking"),
    (r"(?i)(financial.?plan|net.?worth|retirement|invest)", "S4_LOGISTICS_FINANCIAL", None),
    (r"(?i)(oddsjam|bet|gambl|wager|fantasy.?lab)", "S4_LOGISTICS_FINANCIAL", "Gambling_Tracking"),

    # ── Recreation (before S2 to catch HBO/entertainment before education) ──
    (r"(?i)(hbo|netflix|streaming|entertainment|movie|tv\b|roblox)", "RECREATION", "Entertainment"),
    (r"(?i)(game|xbox|playstation|nintendo|steam)", "RECREATION", "Entertainment"),
    (r"(?i)(fantasy.?football)", "RECREATION", "Fantasy_Football"),
    (r"(?i)(book|reading|minimalist.?habit|reframe)", "RECREATION", "Books"),

    # ── S1: Personnel & Family ──
    (r"(?i)(birth.?cert|childcare|progressive.?home|guardianship|custody|adoption)", "S1_PERSONNEL_FAMILY", None),
    (r"(?i)(usaa|insurance.*doc|claim.?letter|beneficiary)", "S1_PERSONNEL_FAMILY", "Insurance"),
    (r"(?i)(marriage|divorce|spouse|spousal|lindsey)", "S1_PERSONNEL_FAMILY", "Partner"),
    (r"(?i)(emory|harlan|rylan|child|kid|school)", "S1_PERSONNEL_FAMILY", "Children"),
    (r"(?i)(will|trust|poa|power.?of.?attorney|estate|living.?will|healthcare.?directive)", "S1_PERSONNEL_FAMILY", "Legal_Documents"),

    # ── S2: Intelligence & Development ──
    (r"(?i)(resume|cv|career|job|interview|linkedin|promotion|comp.*review|acr)", "S2_INTELLIGENCE_DEVELOPMENT", "Career_Strategy"),
    (r"(?i)(lilly|eli.?lilly|surpass|clinical.?dev|trial.?cap)", "S2_INTELLIGENCE_DEVELOPMENT", "Eli_Lilly"),
    (r"(?i)(maxwell|leadership|impact.?player|multiplier|management)", "S2_INTELLIGENCE_DEVELOPMENT", "Leadership"),
    (r"(?i)(mba|education|degree|transcript|gpa|university|course|learning)", "S2_INTELLIGENCE_DEVELOPMENT", "Education"),
    (r"(?i)(simplify.?to.?amplify|personal.?statement|professional.?dev)", "S2_INTELLIGENCE_DEVELOPMENT", "Career_Strategy"),
    (r"(?i)(chatgpt|prompt|ai.?tool)", "S2_INTELLIGENCE_DEVELOPMENT", None),
    (r"(?i)(diabetes|research|playbook)", "S2_INTELLIGENCE_DEVELOPMENT", "Eli_Lilly"),

    # ── S3: Operations & Admin ──
    (r"(?i)(receipt|uber|lyft|expense|reimburs)", "S3_OPERATIONS_ADMIN", "Receipts"),
    (r"(?i)(rental|renter|landlord|tenant|lease)", "S3_OPERATIONS_ADMIN", "Rental"),
    (r"(?i)(parking|pass)", "S3_OPERATIONS_ADMIN", "Parking"),
    (r"(?i)(apple.?support|apple.*confirm)", "S3_OPERATIONS_ADMIN", "Apple_Support"),
    (r"(?i)(amazon|prime.?member|subscription)", "S3_OPERATIONS_ADMIN", "Subscriptions"),
    (r"(?i)(shipping|label|shark|tracking)", "S3_OPERATIONS_ADMIN", "Shipping"),
    (r"(?i)(scheduling|calendar|appointment)", "S3_OPERATIONS_ADMIN", None),

    # ── S6: Comms & Tech ──
    (r"(?i)(network|security|vpn|firewall|config)", "S6_COMMS_TECH", None),
    (r"(?i)(copilot|microsoft|onedrive)", "S6_COMMS_TECH", None),

    # ── S7: Training & Readiness ──
    (r"(?i)(training|cert|certification|badge|credential)", "S7_TRAINING_READINESS", None),

    # ── Medical / Health / Performance ──
    (r"(?i)(body.?recomp|recomp.?photo|progress.?photo|trt.?photo)", "MEDICAL_HEALTH_PERFORMANCE", "Body_Recomp_Photos"),
    (r"(?i)(health.?record|medical|lab.?result|prescription|diagnosis|doctor|va.?exam|ptsd|dbq|disability|blue.?button)", "MEDICAL_HEALTH_PERFORMANCE", "Medical_Records"),
    (r"(?i)(claim|va.?claim|appeal|nexus|service.?connect)", "MEDICAL_HEALTH_PERFORMANCE", "VA_Claims"),
    (r"(?i)(champva|tricare|healthcare)", "MEDICAL_HEALTH_PERFORMANCE", None),
    (r"(?i)(health.?auto.?export|cronometer|hume|body.?comp|weight)", "MEDICAL_HEALTH_PERFORMANCE", "Health_Exports"),
    (r"(?i)(lab.?result)", "MEDICAL_HEALTH_PERFORMANCE", "Lab_Results"),

    # ── Military Legacy ──
    (r"(?i)(military|army|guard|nco|erb|srb|ngb|dd.?214|enlist|deploy|orders|mos|rank|1sg|first.?sergeant|service.?verif)", "MILITARY_LEGACY", "Military_Records"),
    (r"(?i)(va.?blue.?button|va.*report|disability.*rating)", "MILITARY_LEGACY", "VA_Documents"),
    (r"(?i)(transitioning|veteran|gi.?bill)", "MILITARY_LEGACY", None),
    (r"(?i)(g6|signal)", "MILITARY_LEGACY", None),
]

# ─── LEGACY FOLDER MAPPING ──────────────────────────────────────────────────
# Old folder names → new S-section destinations (for both OneDrive and iCloud)

LEGACY_FOLDER_MAP = {
    "HR": "S2_INTELLIGENCE_DEVELOPMENT/Career_Strategy",
    "HR_PROFESSIONAL": "S2_INTELLIGENCE_DEVELOPMENT/Career_Strategy",
    "Career": "S2_INTELLIGENCE_DEVELOPMENT/Career_Strategy",
    "Education": "S2_INTELLIGENCE_DEVELOPMENT/Education",
    "Military": "MILITARY_LEGACY/Military_Records",
    "Military_OneNote": "MILITARY_LEGACY",
    "Owens_Family": "S1_PERSONNEL_FAMILY",
    "Personal": "S1_PERSONNEL_FAMILY",
    "Pictures": "ARCHIVE/Pictures",
    "Video": "ARCHIVE/Video",
    "Desktop": "ARCHIVE/Desktop_Legacy",
    "Documents": "ARCHIVE/Documents_Legacy",
    "Apps": "ARCHIVE/Apps",
    "Attachments": "ARCHIVE/Attachments",
    "Fantasy_Football": "RECREATION/Fantasy_Football",
    "Fantasy_football": "RECREATION/Fantasy_Football",
    "Books": "RECREATION/Books",
    "Lilly Learning": "S2_INTELLIGENCE_DEVELOPMENT/Eli_Lilly",
    "Lilly_Learning": "S2_INTELLIGENCE_DEVELOPMENT/Eli_Lilly",
    "Lilly_Receipts": "S3_OPERATIONS_ADMIN/Receipts",
    "Maxwell_Leadership": "S2_INTELLIGENCE_DEVELOPMENT/Leadership",
    "Gale OneFile Military and Intelligence": "MILITARY_LEGACY",
    "Microsoft Copilot Chat Files": "S6_COMMS_TECH",
    "Rylan": "S1_PERSONNEL_FAMILY/Children",
    "Harlan": "S1_PERSONNEL_FAMILY/Children",
    "docs": "ARCHIVE",
}

# Documents folder rename map (hyphen → underscore standardization)
# IMPORTANT: S6_COMMS_TECH is excluded — it's the script's own parent
DOCUMENTS_RENAME_MAP = {
    "S1-PERSONNEL": "S1_PERSONNEL_FAMILY",
    "S2-INTELLIGENCE": "S2_INTELLIGENCE_DEVELOPMENT",
    "S3-OPERATIONS": "S3_OPERATIONS_ADMIN",
    "S4-LOGISTICS-FINANCE": "S4_LOGISTICS_FINANCIAL",
    "S5-PLANS": "S5_PLANS_INNOVATION",
    "S7-TRAINING": "S7_TRAINING_READINESS",
}


# ─── AUDIT LOGGING ──────────────────────────────────────────────────────────

class AuditLogger:
    def __init__(self, log_path, dry_run=True):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.dry_run = dry_run
        self.actions = []
        self.errors = []
        self.stats = {"moved": 0, "purged": 0, "folders_created": 0, "skipped": 0, "errors": 0}

    def log(self, action, src, dst=None, reason=""):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "src": str(src),
            "dst": str(dst) if dst else None,
            "reason": reason,
            "dry_run": self.dry_run,
        }
        self.actions.append(entry)
        prefix = "[DRY RUN] " if self.dry_run else ""
        if action == "move":
            print(f"  {prefix}MOVE: {Path(src).name} → {dst}")
            self.stats["moved"] += 1
        elif action == "purge":
            print(f"  {prefix}PURGE: {Path(src).name} ({reason})")
            self.stats["purged"] += 1
        elif action == "mkdir":
            self.stats["folders_created"] += 1
        elif action == "skip":
            self.stats["skipped"] += 1
        elif action == "error":
            print(f"  ERROR: {src} — {reason}")
            self.errors.append(entry)
            self.stats["errors"] += 1

    def flush(self):
        # Re-resolve log path in case directories changed
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        if self.actions:
            with open(self.log_path, "a") as f:
                for entry in self.actions:
                    f.write(json.dumps(entry) + "\n")

    def summary(self):
        mode = "DRY RUN" if self.dry_run else "EXECUTED"
        print(f"\n{'='*60}")
        print(f"  FILE CLEANUP AGENT — {mode}")
        print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        print(f"  Files moved:      {self.stats['moved']}")
        print(f"  Files purged:     {self.stats['purged']}")
        print(f"  Folders created:  {self.stats['folders_created']}")
        print(f"  Files skipped:    {self.stats['skipped']}")
        print(f"  Errors:           {self.stats['errors']}")
        if self.errors:
            print(f"\n  ERRORS:")
            for e in self.errors:
                print(f"    {e['src']}: {e['reason']}")
        print(f"{'='*60}")
        if self.dry_run:
            print(f"  Run with --execute to apply these changes.")
        else:
            print(f"  Audit log: {self.log_path}")


# ─── CORE FUNCTIONS ─────────────────────────────────────────────────────────

def is_protected(path):
    """Check if a path is protected from cleanup."""
    path = Path(path).resolve()
    if path.name in SKIP_NAMES:
        return True
    for pp in PROTECTED_PATHS:
        pp = Path(pp).resolve()
        if path == pp:
            return True
    for prefix in PROTECTED_PREFIXES:
        prefix = Path(prefix).resolve()
        try:
            path.relative_to(prefix)
            return True
        except ValueError:
            pass
    # Protect the script's own directory tree
    try:
        path.relative_to(SCRIPT_DIR.resolve())
        return True
    except ValueError:
        pass
    return False


def is_s_section(name):
    """Check if a folder name is already an S-section."""
    return name in S_SECTIONS or name == "ARCHIVE"


def classify_file(filename):
    """Match a filename against filing rules. Returns (section, subfolder) or None."""
    for pattern, section, subfolder in FILING_RULES:
        if re.search(pattern, filename):
            return (section, subfolder)
    return None


def ensure_s_sections(root, logger):
    """Create canonical S-section folders if they don't exist."""
    root = Path(root)
    for section in S_SECTIONS:
        section_path = root / section
        if not section_path.exists():
            if not logger.dry_run:
                section_path.mkdir(parents=True, exist_ok=True)
            logger.log("mkdir", section_path, reason=f"Create S-section in {root.name}")


def safe_move(src, dst, logger):
    """Move a file/folder safely with collision handling."""
    src = Path(src)
    dst = Path(dst)

    # Never move to same location
    if src.resolve() == dst.resolve():
        logger.log("skip", src, reason="source == destination")
        return False

    if logger.dry_run:
        logger.log("move", src, dst)
        return True

    try:
        # Ensure destination parent exists
        dst.parent.mkdir(parents=True, exist_ok=True)

        # Handle name collision
        if dst.exists():
            stem = dst.stem
            suffix = dst.suffix
            counter = 1
            while dst.exists():
                dst = dst.parent / f"{stem}_{counter}{suffix}"
                counter += 1

        shutil.move(str(src), str(dst))
        logger.log("move", src, dst)
        return True
    except Exception as e:
        logger.log("error", src, dst, reason=str(e))
        return False


def safe_delete(path, logger, reason=""):
    """Delete a file safely."""
    path = Path(path)
    if logger.dry_run:
        logger.log("purge", path, reason=reason)
        return True
    try:
        path.unlink()
        logger.log("purge", path, reason=reason)
        return True
    except Exception as e:
        logger.log("error", path, reason=str(e))
        return False


# ─── CLEANUP PASSES ─────────────────────────────────────────────────────────

def pass_ensure_structure(logger):
    """Pass 0: Ensure all managed roots have canonical S-section folders."""
    print("\n── Pass 0: Ensure S-section structure ──")
    for name, root in MANAGED_ROOTS.items():
        if root.exists():
            print(f"  [{name}] {root}")
            ensure_s_sections(root, logger)


def pass_clean_downloads(logger, purge=False):
    """Pass 1: File documents from Downloads, optionally purge stale installers/screenshots."""
    print("\n── Pass 1: Clean ~/Downloads ──")
    if not DOWNLOADS.exists():
        print("  Downloads folder not found, skipping.")
        return

    now = datetime.now()

    for item in sorted(DOWNLOADS.iterdir()):
        if item.name.startswith(".") or item.name in SKIP_NAMES:
            continue
        if is_protected(item):
            logger.log("skip", item, reason="protected")
            continue
        if not item.is_file():
            continue

        name = item.name
        suffix = item.suffix.lower()

        # Purge: DMG installers older than threshold
        if purge and suffix == ".dmg":
            age = now - datetime.fromtimestamp(item.stat().st_mtime)
            if age.days >= DMG_MAX_AGE_DAYS:
                safe_delete(item, logger, reason=f"DMG older than {DMG_MAX_AGE_DAYS} days ({age.days}d)")
                continue
            else:
                logger.log("skip", item, reason=f"DMG only {age.days}d old (threshold: {DMG_MAX_AGE_DAYS}d)")
                continue

        # Purge: Screenshots older than threshold
        if purge and name.lower().startswith("screenshot") and suffix in (".png", ".jpg", ".jpeg"):
            age = now - datetime.fromtimestamp(item.stat().st_mtime)
            if age.days >= SCREENSHOT_MAX_AGE_DAYS:
                safe_delete(item, logger, reason=f"Screenshot older than {SCREENSHOT_MAX_AGE_DAYS} days ({age.days}d)")
                continue

        # Try to classify and file
        classification = classify_file(name)
        if classification:
            section, subfolder = classification
            dst_base = ICLOUD / section  # Downloads → iCloud as primary destination
            if subfolder:
                dst_base = dst_base / subfolder
            safe_move(item, dst_base / name, logger)
        else:
            logger.log("skip", item, reason="unclassified")


def pass_body_recomp_photos(logger):
    """Pass 1b: File body recomp photos from staging folder with date-stamped names."""
    print("\n── Pass 1b: Body Recomp Photos ──")
    if not BODY_RECOMP_STAGING.exists():
        print("  No body-recomp staging folder, skipping.")
        return

    IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".heic"}
    images = [f for f in sorted(BODY_RECOMP_STAGING.iterdir())
              if f.is_file() and f.suffix.lower() in IMAGE_EXTS]

    if not images:
        print("  No image files found in staging folder.")
        return

    # Try to import PIL for EXIF reading
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS
        has_pil = True
    except ImportError:
        has_pil = False
        print("  (Pillow not available — using file modification time for dates)")

    # Track per-date counters for naming
    date_counters = {}

    for img in images:
        if img.name.startswith(".") or img.name in SKIP_NAMES:
            continue

        # Determine photo date
        photo_date = None

        if has_pil:
            try:
                with Image.open(img) as pil_img:
                    exif_data = pil_img._getexif()
                    if exif_data and 36867 in exif_data:
                        # Tag 36867 = DateTimeOriginal
                        dt_str = exif_data[36867]
                        photo_date = datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
            except Exception:
                pass

        # Fall back to file modification time
        if photo_date is None:
            photo_date = datetime.fromtimestamp(img.stat().st_mtime)

        date_key = photo_date.strftime("%Y-%m-%d")
        date_counters[date_key] = date_counters.get(date_key, 0) + 1
        counter = date_counters[date_key]

        new_name = f"{date_key}_photo_{counter}{img.suffix.lower()}"
        dst = BODY_RECOMP_DEST / new_name
        safe_move(img, dst, logger)


def pass_file_loose_files(root, root_name, logger):
    """Pass 2: File loose files at root level of a managed location."""
    print(f"\n── Pass 2: File loose files [{root_name}] ──")
    root = Path(root)
    if not root.exists():
        print(f"  {root_name} not found, skipping.")
        return

    for item in sorted(root.iterdir()):
        if item.name.startswith(".") or item.name in SKIP_NAMES:
            continue
        if is_protected(item):
            logger.log("skip", item, reason="protected")
            continue
        # Skip directories entirely — only file loose files
        if item.is_dir():
            continue
        # Skip symlinks
        if item.is_symlink():
            continue

        classification = classify_file(item.name)
        if classification:
            section, subfolder = classification
            dst_base = root / section
            if subfolder:
                dst_base = dst_base / subfolder
            safe_move(item, dst_base / item.name, logger)
        else:
            logger.log("skip", item, reason="unclassified loose file")


def pass_consolidate_legacy_folders(root, root_name, logger):
    """Pass 3: Move contents of legacy folders into S-sections."""
    print(f"\n── Pass 3: Consolidate legacy folders [{root_name}] ──")
    root = Path(root)
    if not root.exists():
        return

    for legacy_name, target in LEGACY_FOLDER_MAP.items():
        if target is None:
            continue
        legacy_path = root / legacy_name
        if not legacy_path.exists():
            continue

        # If it's a file (not folder), move directly
        if legacy_path.is_file():
            dst = root / target
            if not Path(target).suffix:  # target is a folder path
                dst = root / target / legacy_name
            safe_move(legacy_path, dst, logger)
            continue

        if not legacy_path.is_dir():
            continue

        # Never follow symlinks (e.g., iCloud Desktop/Documents → ~/Desktop, ~/Documents)
        if legacy_path.is_symlink():
            print(f"  SKIP: {legacy_name} (symlink)")
            continue

        print(f"  Consolidating: {legacy_name} → {target}")
        target_path = root / target

        # Move all contents from legacy folder into target
        for item in sorted(legacy_path.rglob("*")):
            if item.name in SKIP_NAMES or item.name.startswith("."):
                continue
            if item.is_file():
                rel = item.relative_to(legacy_path)
                dst = target_path / rel
                safe_move(item, dst, logger)

        # Remove empty legacy folder after moving contents
        if not logger.dry_run:
            try:
                _remove_empty_dirs(legacy_path)
            except Exception:
                pass


def pass_rename_documents_sections(logger):
    """Pass 4: Rename Documents S-sections from hyphens to underscores.
    NOTE: S6-COMMS-TECH is excluded — it contains this script."""
    print(f"\n── Pass 4: Standardize Documents folder names ──")
    for old_name, new_name in DOCUMENTS_RENAME_MAP.items():
        old_path = DOCUMENTS / old_name
        new_path = DOCUMENTS / new_name
        if not old_path.exists():
            continue
        if old_path == SCRIPT_ROOT:
            print(f"  SKIP: {old_name} (contains this script)")
            continue
        if not new_path.exists():
            print(f"  Rename: {old_name} → {new_name}")
            if not logger.dry_run:
                old_path.rename(new_path)
            logger.log("move", old_path, new_path, reason="standardize naming")
        elif old_path.exists() and new_path.exists():
            print(f"  Merge: {old_name} → {new_name}")
            for item in sorted(old_path.rglob("*")):
                if item.is_file() and item.name not in SKIP_NAMES:
                    rel = item.relative_to(old_path)
                    safe_move(item, new_path / rel, logger)
            if not logger.dry_run:
                try:
                    _remove_empty_dirs(old_path)
                except Exception:
                    pass


def pass_clean_icloud_downloads(logger):
    """Pass 5: Clean iCloud Downloads subfolder."""
    print(f"\n── Pass 5: Clean iCloud Downloads ──")
    icloud_dl = ICLOUD / "Downloads"
    if not icloud_dl.exists():
        return

    for item in sorted(icloud_dl.iterdir()):
        if item.name.startswith(".") or item.name in SKIP_NAMES:
            continue
        if not item.is_file():
            continue

        classification = classify_file(item.name)
        if classification:
            section, subfolder = classification
            dst_base = ICLOUD / section
            if subfolder:
                dst_base = dst_base / subfolder
            safe_move(item, dst_base / item.name, logger)
        else:
            logger.log("skip", item, reason="unclassified iCloud download")


def pass_deduplicate_icloud_roots(logger):
    """Pass 6: Move files from old iCloud root folders that now have S-section homes."""
    print(f"\n── Pass 6: Deduplicate iCloud root folders ──")

    icloud_legacy_map = {
        "Family": {
            "_default": "S1_PERSONNEL_FAMILY",
            "_subdirs_skip": ["Financial-Plan", "Taxes"],
        },
        "Taxes": {
            "_default": "S4_LOGISTICS_FINANCIAL/Taxes",
        },
    }

    for folder_name, config in icloud_legacy_map.items():
        folder = ICLOUD / folder_name
        if not folder.exists():
            continue

        default_target = config.get("_default", "ARCHIVE")
        skip_subdirs = config.get("_subdirs_skip", [])

        for item in folder.iterdir():
            if item.name.startswith(".") or item.name in SKIP_NAMES:
                continue
            if item.is_dir():
                if item.name in skip_subdirs:
                    continue
                # Move subdirectory contents
                for subfile in item.rglob("*"):
                    if subfile.is_file() and subfile.name not in SKIP_NAMES:
                        rel = subfile.relative_to(folder)
                        classification = classify_file(subfile.name)
                        if classification:
                            section, subfolder = classification
                            dst = ICLOUD / section
                            if subfolder:
                                dst = dst / subfolder
                            safe_move(subfile, dst / subfile.name, logger)
                        else:
                            safe_move(subfile, ICLOUD / default_target / rel, logger)
                continue

            if item.is_file():
                classification = classify_file(item.name)
                if classification:
                    section, subfolder = classification
                    dst = ICLOUD / section
                    if subfolder:
                        dst = dst / subfolder
                    safe_move(item, dst / item.name, logger)
                else:
                    safe_move(item, ICLOUD / default_target / item.name, logger)


# ─── UTILITIES ───────────────────────────────────────────────────────────────

def _remove_empty_dirs(path):
    """Recursively remove empty directories."""
    path = Path(path)
    if not path.is_dir():
        return
    for child in path.iterdir():
        if child.is_dir():
            _remove_empty_dirs(child)
    remaining = [c for c in path.iterdir() if c.name not in SKIP_NAMES and not c.name.startswith(".")]
    if not remaining:
        for c in path.iterdir():
            if c.name == ".DS_Store":
                c.unlink()
        try:
            path.rmdir()
        except OSError:
            pass


def report_state():
    """Print current file organization state across all locations."""
    print(f"\n{'='*60}")
    print(f"  FILE ORGANIZATION STATE REPORT")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    for name, root in MANAGED_ROOTS.items():
        if not root.exists():
            print(f"\n  [{name}] NOT FOUND")
            continue

        print(f"\n  [{name}] {root}")

        s_section_files = 0
        loose_files = 0
        legacy_folders = []

        for item in root.iterdir():
            if item.name.startswith(".") or item.name in SKIP_NAMES:
                continue
            if item.is_dir():
                if is_s_section(item.name):
                    s_section_files += sum(1 for _ in item.rglob("*") if _.is_file() and _.name not in SKIP_NAMES)
                elif item.name in LEGACY_FOLDER_MAP:
                    legacy_folders.append(item.name)
            elif item.is_file():
                loose_files += 1

        print(f"    S-section files: {s_section_files}")
        print(f"    Loose files:     {loose_files}")
        if legacy_folders:
            print(f"    Legacy folders:  {', '.join(legacy_folders)}")

    if DOWNLOADS.exists():
        dl_count = sum(1 for f in DOWNLOADS.iterdir() if f.is_file() and f.name not in SKIP_NAMES and not f.name.startswith("."))
        print(f"\n  [downloads] {DOWNLOADS}")
        print(f"    Files: {dl_count}")

    print(f"\n{'='*60}")


# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="S3 File Cleanup Agent")
    parser.add_argument("--execute", action="store_true", help="Actually move files (default is dry run)")
    parser.add_argument("--purge", action="store_true", help="Also purge stale DMGs and screenshots")
    parser.add_argument("--report", action="store_true", help="Just print current state")
    parser.add_argument("--downloads-only", action="store_true", help="Only clean Downloads folder")
    args = parser.parse_args()

    if args.report:
        report_state()
        return

    dry_run = not args.execute
    logger = AuditLogger(AUDIT_LOG, dry_run=dry_run)

    print(f"{'='*60}")
    print(f"  S3 FILE CLEANUP AGENT")
    print(f"  Mode: {'DRY RUN' if dry_run else 'EXECUTING'}")
    print(f"  Purge: {'ON' if args.purge else 'OFF'}")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    try:
        pass_ensure_structure(logger)
        pass_clean_downloads(logger, purge=args.purge)
        pass_body_recomp_photos(logger)

        if not args.downloads_only:
            for name, root in MANAGED_ROOTS.items():
                if root.exists():
                    pass_file_loose_files(root, name, logger)

            for name, root in [("onedrive", ONEDRIVE), ("icloud", ICLOUD)]:
                if root.exists():
                    pass_consolidate_legacy_folders(root, name, logger)

            pass_rename_documents_sections(logger)
            pass_clean_icloud_downloads(logger)
            pass_deduplicate_icloud_roots(logger)

    except Exception as e:
        logger.log("error", "AGENT", reason=f"Fatal: {e}")
        import traceback
        traceback.print_exc()

    logger.flush()
    logger.summary()


if __name__ == "__main__":
    main()
