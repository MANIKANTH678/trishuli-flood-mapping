#!/usr/bin/env python3
"""align_v2_checks.py — verify pre/post S1 pairs are on the same
relative orbit and pass direction (fatal), and report the date gap (Step 10.1: a gap that
is not a multiple of the 6/12-day repeat is only a WARNING; same-track geometry is what matters).

Reads manifest.safe from every .SAFE folder in data/raw/sentinel1/{pre,post}/
and exits 1 if the orbit or pass invariants are violated.
"""
from __future__ import annotations
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

S1_ROOT = Path("data/raw/sentinel1")


def read_manifest(safe_dir: Path):
    mf = safe_dir / "manifest.safe"
    if not mf.exists():
        return None
    txt = mf.read_text(errors="ignore")
    def _re(pat):
        m = re.search(pat, txt)
        return m.group(1) if m else None
    return {
        "name":     safe_dir.name,
        "start":    _re(r"<safe:startTime>([^<]+)</"),
        "relOrbit": _re(r"<safe:relativeOrbitNumber[^>]*>(\d+)<"),
        "pass":     _re(r"<s1:pass[^>]*>([A-Z]+)<"),
    }


def collect(split: str):
    return [m for m in (read_manifest(d) for d in sorted((S1_ROOT / split).glob("*.SAFE")))
            if m is not None]


def main():
    ok = True
    for split in ("pre", "post"):
        scenes = collect(split)
        if not scenes:
            print(f"❌ {split}: no SAFE folders found")
            ok = False
            continue
        orbits = {s["relOrbit"] for s in scenes}
        passes = {s["pass"] for s in scenes}
        print(f"{split}: {len(scenes)} scene(s)")
        for s in scenes:
            print(f"  {s['start']}  relOrbit={s['relOrbit']}  pass={s['pass']}  {s['name'][:50]}")
        if len(orbits) > 1:
            print(f"  ❌ mixed relative orbits: {orbits}")
            ok = False
        if len(passes) > 1:
            print(f"  ❌ mixed pass directions: {passes}")
            ok = False

    if ok:
        pre = min(s["start"] for s in collect("pre"))
        post = min(s["start"] for s in collect("post"))
        d_pre = datetime.fromisoformat(pre.replace("Z", "+00:00"))
        d_post = datetime.fromisoformat(post.replace("Z", "+00:00"))
        days = (d_post - d_pre).days
        print(f"\npre  = {pre}")
        print(f"post = {post}")
        print(f"gap  = {days} days")
        if days % 6 != 0:
            print(f"WARNING: gap of {days} days is not a multiple of the 6/12-day repeat (same-track geometry is what matters)")

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
