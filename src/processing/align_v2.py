"""align_v2.py - alignment with orbit-direction and temporal checks."""
import os, sys, re, json, glob
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.config import S1_DIR, PROCESSED_DIR

# Regex for standard Sentinel-1 SAFE folder name
def parse_safe_name(name):
    """Extract fields from a SAFE folder or zip name via simple split."""
    base = name
    for suffix in (".SAFE.zip", ".SAFE", ".zip"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    parts = base.split("_")
    if len(parts) < 6 or not parts[0].startswith("S1"):
        return None
    start = parts[4]  # 20260816T122116
    return {
        "platform":     parts[0],                  # S1D
        "mode":         parts[1],                  # IW
        "product":      parts[2],                  # GRDH
        "polarisation": parts[3],                  # 1SDV
        "start_date":   start.split("T")[0],       # 20260816
        "start_time":   start.split("T")[1] if "T" in start else "",
        "safe_name":    name,
    }


def get_orbit_direction(folder):
    """Read manifest.safe; return ASCENDING / DESCENDING / None."""
    for root, dirs, files in os.walk(folder):
        for f in files:
            if f.lower() == "manifest.safe":
                try:
                    text = Path(os.path.join(root, f)).read_text(errors="ignore")
                except Exception:
                    continue
                m = re.search(r">\s*(ASCENDING|DESCENDING)\s*<", text, re.IGNORECASE)
                if m:
                    return m.group(1).upper()
    return None


def list_scenes(folder):
    """Return deduped list of scenes (skip .zip when extracted .SAFE exists)."""
    entries = sorted(os.listdir(folder))
    safe_stems = {e[:-5] for e in entries if e.endswith(".SAFE")}

    scenes = []
    seen = set()
    for entry in entries:
        full = os.path.join(folder, entry)
        is_dir = os.path.isdir(full)
        is_zip = entry.endswith(".zip")
        if not is_dir and not is_zip:
            continue
        # skip the .SAFE.zip if the .SAFE folder is already there
        if is_zip and entry.endswith(".SAFE.zip"):
            stem = entry[:-4]  # strip .zip
            if stem in safe_stems:
                continue
        info = parse_safe_name(entry)
        if not info:
            continue
        if info["safe_name"] in seen:
            continue
        seen.add(info["safe_name"])
        info["folder"] = full
        info["orbit_direction"] = get_orbit_direction(full)
        scenes.append(info)
    return scenes


def validate_pair(pre_scenes, post_scenes):
    """Return (ok, report). ok=True only if orbit matches and dates are sane."""
    report = {"checks": [], "passed": True, "reason": None}

    if not pre_scenes or not post_scenes:
        report["passed"] = False
        report["reason"] = "missing pre or post scenes"
        report["checks"].append({"name": "scenes_present", "ok": False})
        return False, report

    pre = pre_scenes[0]
    post = post_scenes[0]

    # Orbit direction check
    same_dir = (pre["orbit_direction"] is not None
                and pre["orbit_direction"] == post["orbit_direction"])
    report["checks"].append({
        "name": "same_orbit_direction",
        "ok": same_dir,
        "pre": pre["orbit_direction"],
        "post": post["orbit_direction"],
    })

    # Mode check (IW vs EW)
    same_mode = pre["mode"] == post["mode"]
    report["checks"].append({
        "name": "same_acquisition_mode",
        "ok": same_mode,
        "pre": pre["mode"], "post": post["mode"],
    })

    # Temporal separation
    pre_date = datetime.strptime(pre["start_date"], "%Y%m%d")
    post_date = datetime.strptime(post["start_date"], "%Y%m%d")
    gap = abs((post_date - pre_date).days)
    # S1 repeat cycle is 12 days (S1A) or 6 days (S1A+S1B constellation)
    ideal = gap in (6, 12, 18, 24)
    sane = 1 <= gap <= 30
    report["checks"].append({
        "name": "temporal_separation",
        "ok": sane,
        "ideal_match": ideal,
        "gap_days": gap,
        "ideal_values": [6, 12, 18, 24],
    })

    report["pre_scene"] = pre["safe_name"]
    report["post_scene"] = post["safe_name"]
    report["gap_days"] = gap
    report["orbit_direction"] = pre["orbit_direction"]

    all_ok = same_dir and same_mode and sane
    report["passed"] = all_ok
    if not all_ok:
        report["reason"] = "orbit direction mismatch or temporal separation out of range"
    return all_ok, report


def main():
    pre_dir  = os.path.join(S1_DIR, "pre")
    post_dir = os.path.join(S1_DIR, "post")

    print("=" * 60)
    print("ALIGNMENT VALIDATION")
    print("=" * 60)

    if not (os.path.isdir(pre_dir) and os.path.isdir(post_dir)):
        print(f"missing pre/post dirs: {pre_dir} | {post_dir}")
        sys.exit(1)

    print(f"pre dir:  {pre_dir}")
    print(f"post dir: {post_dir}")

    pre_scenes  = list_scenes(pre_dir)
    post_scenes = list_scenes(post_dir)
    print(f"\nfound {len(pre_scenes)} pre scene(s), {len(post_scenes)} post scene(s)")

    for s in pre_scenes:
        print(f"  PRE   {s['safe_name']}  orbit={s['orbit_direction']}  {s['start_date']}")
    for s in post_scenes:
        print(f"  POST  {s['safe_name']}  orbit={s['orbit_direction']}  {s['start_date']}")

    ok, report = validate_pair(pre_scenes, post_scenes)

    print("\n" + "-" * 60)
    print("CHECKS:")
    for c in report["checks"]:
        status = "PASS" if c["ok"] else "FAIL"
        print(f"  [{status}] {c['name']}: {c}")

    meta = {
        "validation": report,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    out = os.path.join(PROCESSED_DIR, "align_metadata.json")
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    with open(out, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"\nwrote {out}")
    print("OVERALL:", "PASS" if ok else "FAIL")

    if not ok:
        print("\nWARNING: validation failed but proceeding with alignment.")
        print("Fix by picking a pre/post pair from the SAME orbit direction.")
        sys.exit(2)


if __name__ == "__main__":
    main()
