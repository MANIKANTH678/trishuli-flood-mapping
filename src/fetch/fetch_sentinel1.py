#!/usr/bin/env python3
"""
fetch_sentinel1.py — download the Sentinel-1 GRD scenes chosen by src/fetch/select_s1.py (Step 10.2).

    python -m src.fetch.select_s1 --bbox W,S,E,N --event-date YYYY-MM-DD      # writes data/raw/sentinel1/selection.json
    python -m src.fetch.fetch_sentinel1 --selection data/raw/sentinel1/selection.json            # list only
    python -m src.fetch.fetch_sentinel1 --selection data/raw/sentinel1/selection.json --download # needs credentials

Credentials come ONLY from the environment (COPERNICUS_USER / COPERNICUS_PASS) and are read lazily, at download time,
so listing works on a clean clone without them.
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
import json
from src.config import S1_DIR

# --- Scene list: from the selection (src/fetch/select_s1.py) -----------------
SPLITS = ["pre", "placebo", "pre3", "pre4"]          # nearest pre-event date first
def picks_from_selection(path):
    sel = json.loads(Path(path).read_text()); out = [("post", p) for p in sel["products"][sel["post"]]]
    for sp, d in zip(SPLITS, sel["pre"]): out += [(sp, p) for p in sel["products"][d]]
    return out                                        # [(split, {"id", "name", "size_mb"})]


# --- Endpoints ---------------------------------------------------------------
ODATA   = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
TOKEN   = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
ZIPPER  = "https://zipper.dataspace.copernicus.eu/odata/v1/Products"


# ---------- helpers ----------------------------------------------------------

def get_token() -> str:
    user = os.environ.get("COPERNICUS_USER", "").strip().strip("\"'").strip()
    pw = os.environ.get("COPERNICUS_PASS", "").strip().strip("\"'").strip()
    if not user or not pw or "example.com" in user:
        raise SystemExit(
            "No Copernicus credentials. Set the environment variables COPERNICUS_USER / COPERNICUS_PASS "
            "(cmd: set COPERNICUS_USER=you@example.com). Register free at https://dataspace.copernicus.eu/"
        )
    r = requests.post(
        TOKEN,
        data={
            "client_id": "cdse-public",
            "grant_type": "password",
            "username": user,
            "password": pw,
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
    ap.add_argument("--selection", default=str(Path(S1_DIR) / "selection.json"),
                    help="JSON written by src.fetch.select_s1 (track, dates, product ids)")
    ap.add_argument("--dry-run", action="store_true", help="List the scenes; don't download.")
    ap.add_argument("--download", action="store_true", help="Download to data/raw/sentinel1/<split>/.")
    args = ap.parse_args()
    if not Path(args.selection).exists():
        raise SystemExit(f"{args.selection} not found: run python -m src.fetch.select_s1 --bbox W,S,E,N --event-date YYYY-MM-DD first")
    picks = picks_from_selection(args.selection)
    sel = json.loads(Path(args.selection).read_text())
    if sel.get("source", "cdse") != "cdse":
        raise SystemExit(f"{args.selection} lists Planetary Computer items (source={sel.get('source')}); use the PC route (src.processing.pc_stack)")
    print(f"track {sel['rel_orbit']} {sel['pass']}  post {sel['post']}  pre {sel['pre']}")
    for label, s in picks:
        print(f"  [{label}] {s['name']}  {s.get('size_mb', '?')} MB")
    if not args.download:
        print("\n(list only) Re-run with --download to fetch.")
        return
    out_dir = Path(S1_DIR)
    token = None  # fetched lazily, only if something is actually missing
    for label, s in picks:
        sub = out_dir / label
        print(f"\ndownloading {label}: {s['name']}")
        have = any((sub / f"{s['name']}{suf}").exists() and (sub / f"{s['name']}{suf}").stat().st_size > 1_000_000
                   for suf in (".zip", ".SAFE.zip"))
        if not have and token is None:
            token = get_token()
        try:
            download(s["id"], s["name"], token, sub)
        except requests.HTTPError as e:
            raise SystemExit(f"download failed: {e}\nbody: {getattr(e.response, 'text', '')[:300]}")


if __name__ == "__main__":
    main()
