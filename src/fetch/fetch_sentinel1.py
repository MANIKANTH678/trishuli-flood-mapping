#!/usr/bin/env python3
"""
fetch_sentinel1.py — Find and download Sentinel-1 GRD scenes covering
the Trishuli GLOF source (Rasuwa, Nepal, ~85.35E 28.17N).

Search-only mode (NO credentials needed):
    python src/fetch/fetch_sentinel1.py --dry-run

Download mode (requires credentials in src/config.py):
    python src/fetch/fetch_sentinel1.py --download
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
)
from src.config import S1_DIR, COPERNICUS_USER, COPERNICUS_PASS

# --- Search parameters -------------------------------------------------------
# GLOF source + downstream corridor. Must include Rasuwa (lat 28.15-28.28).
FOOTPRINT_WKT = (
    "POLYGON(("
    "84.90 27.70, 85.70 27.70, 85.70 28.40, 84.90 28.40, 84.90 27.70"
    "))"
)
DATE_RANGES = [
    ("pre3", "2026-07-21T00:00:00.000Z", "2026-07-25T23:59:59.999Z"),
    ("pre4", "2026-07-09T00:00:00.000Z", "2026-07-13T23:59:59.999Z"),
    ("pre",  "2026-08-13T00:00:00.000Z", "2026-08-19T23:59:59.999Z"),
    ("post", "2026-08-25T00:00:00.000Z", "2026-08-31T23:59:59.999Z"),
    ("placebo", "2026-08-01T00:00:00.000Z", "2026-08-07T23:59:59.999Z"),
    ("pre3", "2026-07-21T00:00:00.000Z", "2026-07-25T23:59:59.999Z"),
    ("pre4", "2026-07-09T00:00:00.000Z", "2026-07-13T23:59:59.999Z"),
]
TARGET_REL_ORBIT  = 85
TARGET_PASS_DIR   = "ASCENDING"
PRODUCT_TYPE      = "IW_GRDH_1S"

# --- Endpoints ---------------------------------------------------------------
ODATA   = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
TOKEN   = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
ZIPPER  = "https://zipper.dataspace.copernicus.eu/odata/v1/Products"


# ---------- helpers ----------------------------------------------------------

def get_token() -> str:
    if not COPERNICUS_USER or "example.com" in COPERNICUS_USER:
        raise SystemExit(
            "❌ No Copernicus credentials. Set COPERNICUS_USER / COPERNICUS_PASS "
            "in src/config.py. Register free at https://dataspace.copernicus.eu/"
        )
    r = requests.post(
        TOKEN,
        data={
            "client_id": "cdse-public",
            "grant_type": "password",
            "username": COPERNICUS_USER,
            "password": COPERNICUS_PASS,
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def odata_filter(bbox_wkt: str, dt_start: str, dt_end: str) -> str:
    return (
        f"Collection/Name eq 'SENTINEL-1'"
        f" and Attributes/OData.CSC.StringAttribute/any("
        f"att:att/Name eq 'productType'"
        f" and att/OData.CSC.StringAttribute/Value eq '{PRODUCT_TYPE}')"
        f" and ContentDate/Start gt {dt_start}"
        f" and ContentDate/Start lt {dt_end}"
        f" and OData.CSC.Intersects(area=geography'SRID=4326;{bbox_wkt}')"
    )


def search(bbox_wkt: str, dt_start: str, dt_end: str) -> list[dict]:
    params = {
        "$filter":  odata_filter(bbox_wkt, dt_start, dt_end),
        "$expand":  "Attributes",
        "$top":     100,
        "$orderby": "ContentDate/Start asc",
    }
    r = requests.get(ODATA, params=params, timeout=60)
    r.raise_for_status()
    return r.json().get("value", [])


def attrs_of(product: dict) -> dict:
    out = {}
    for a in product.get("Attributes", []):
        name = a.get("Name")
        val = a.get("Value")
        if name and val is not None:
            out[name] = val
    return out


def summarize(product: dict) -> dict:
    a = attrs_of(product)
    return {
        "id":         product["Id"],
        "name":       product["Name"],
        "date":       product["ContentDate"]["Start"],
        "relOrbit":   int(a.get("relativeOrbitNumber", -1)),
        "pass":       a.get("orbitDirection", "?"),
        "polarisation": a.get("polarisation", "?"),
        "online":     product.get("Online", False),
        "size_mb":    round(product.get("ContentLength", 0) / 1e6, 1),
    }


def download(product_id: str, name: str, token: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    # accept either naming convention already on disk
    candidates = [out_dir / f"{name}.zip", out_dir / f"{name}.SAFE.zip"]
    for c in candidates:
        if c.exists() and c.stat().st_size > 1_000_000:
            print(f"   already exists: {c.name} ({c.stat().st_size/1e6:.0f} MB)")
            return c
    dest = out_dir / f"{name}.zip"   # write without double suffix
    part = out_dir / f"{name}.zip.part"
    url = f"{ZIPPER}({product_id})/$value"
    for attempt in range(1, 6):
        have = part.stat().st_size if part.exists() else 0
        headers = {"Authorization": f"Bearer {token}"}
        if have:
            headers["Range"] = f"bytes={have}-"
        try:
            with requests.get(url, headers=headers, stream=True, timeout=600, allow_redirects=True) as r:
                r.raise_for_status()
                resumed = have > 0 and r.status_code == 206
                start = have if resumed else 0
                total = int(r.headers.get("content-length", 0)) + start
                done = start
                with open(part, "ab" if resumed else "wb") as f:
                    for chunk in r.iter_content(chunk_size=1 << 20):
                        f.write(chunk)
                        done += len(chunk)
                        if total:
                            print(f"\r   {done/total*100:5.1f}%  {done/1e6:.0f}/{total/1e6:.0f} MB",
                                  end="", flush=True)
            print()
            if total and done < total:
                raise IOError(f"short download {done} of {total}")
            part.replace(dest)
            return dest
        except (requests.RequestException, OSError) as e:
            print(f"\n   attempt {attempt} failed: {e}")
            resp = getattr(e, "response", None)
            if resp is not None and resp.status_code == 416 and part.exists():
                print("   server rejected resume; restarting this file from zero")
                part.unlink()
    raise RuntimeError(f"download failed after retries: {name}")


# ---------- main -------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="Search only; print candidates; don't download.")
    ap.add_argument("--download", action="store_true",
                    help="Download matching scenes to data/raw/sentinel1/{pre,post}.")
    ap.add_argument("--any-orbit", action="store_true",
                    help="Don't filter on relOrbit=85 / ASCENDING.")
    args = ap.parse_args()

    if not args.dry_run and not args.download:
        args.dry_run = True  # default safe

    print(f"🔍 Footprint: {FOOTPRINT_WKT}")
    print(f"   relOrbit filter: {TARGET_REL_ORBIT}  pass: {TARGET_PASS_DIR}")
    print()

    picks: list[tuple[str, dict]] = []  # (label, product summary)

    for label, dt_start, dt_end in DATE_RANGES:
        print(f"── {label.upper()} window: {dt_start} .. {dt_end} ──")
        try:
            products = search(FOOTPRINT_WKT, dt_start, dt_end)
        except requests.HTTPError as e:
            print(f"   search failed: {e}")
            print(f"   body: {getattr(e.response, 'text', '')[:300]}")
            continue

        print(f"   {len(products)} raw hits")

        for p in products:
            s = summarize(p)
            if not args.any_orbit:
                if s["relOrbit"] != TARGET_REL_ORBIT:  continue
                if s["pass"]     != TARGET_PASS_DIR:   continue
            print(f"   ✅ {s['name']}")
            print(f"      date={s['date']}  relOrbit={s['relOrbit']}  "
                  f"pass={s['pass']}  pol={s['polarisation']}  "
                  f"size={s['size_mb']} MB  online={s['online']}")
            picks.append((label, s))
        print()

    if not picks:
        print("❌ No scenes matched. Try --any-orbit to see what IS available "
              "over the footprint in these date windows.")
        return

    print(f"Found {len(picks)} matching scene(s):")
    for label, s in picks:
        print(f"  [{label}] {s['name']}")

    if not args.download:
        print("\n(dry-run) Not downloading. Re-run with --download to fetch.")
        return

    out_dir = Path(S1_DIR)
    token = None  # fetched lazily, only if something is actually missing
    for label, s in picks:
        sub = out_dir / label
        print(f"\n⬇️  downloading {label}: {s['name']}")
        have = any(
            (sub / f"{s['name']}{suf}").exists()
            and (sub / f"{s['name']}{suf}").stat().st_size > 1_000_000
            for suf in (".zip", ".SAFE.zip")
        )
        if not have and token is None:
            token = get_token()
        try:
            path = download(s["id"], s["name"], token, sub)
        except requests.HTTPError as e:
            print(f"   download failed: {e}")
            print(f"   body: {getattr(e.response, 'text', '')[:300]}")


if __name__ == "__main__":
    main()
