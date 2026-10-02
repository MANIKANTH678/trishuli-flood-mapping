"""fetch_sentinel1.py - download Sentinel-1 GRD from CDSE.

Usage:
    export CDSE_USER=<username>
    export CDSE_PASS=<password>
    python -m src.download.fetch_sentinel1 \
        --bbox 84.30,27.85,84.45,28.00 \
        --start 2026-08-20 --end 2026-08-30 \
        --out data/raw/s1
"""
import argparse, os, sys, json, zipfile, io
from pathlib import Path
import requests

TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
SEARCH_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
DOWNLOAD_BASE = "https://download.dataspace.copernicus.eu/odata/v1/Products"


def get_token(client_id, client_secret):
    r = requests.post(TOKEN_URL, data={
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def search(w, s, e, n, start, end, limit=20):
    filt = (
        "Collection/Name eq 'SENTINEL-1' and "
        f"OData.CSC.Intersects(area=geography'SRID=4326;POLYGON(({w} {s},{e} {s},{e} {n},{w} {n},{w} {s}))') and "
        f"ContentDate/Start gt {start}T00:00:00.000Z and "
        f"ContentDate/Start lt {end}T23:59:59.000Z and "
        "Attributes/OData.CSC.StringAttribute/any("
        "a:a/Name eq 'productType' and a/OData.CSC.StringAttribute/Value eq 'GRD')"
    )
    r = requests.get(SEARCH_URL, params={"$filter": filt, "$top": limit, "$orderby": "ContentDate/Start asc"}, timeout=60)
    r.raise_for_status()
    return r.json().get("value", [])


def download(product_id, name, out_dir, token):
    out = Path(out_dir) / f"{name}.zip"
    if out.exists() and out.stat().st_size > 1_000_000:
        print(f"  already exists: {out.name} ({out.stat().st_size/1e6:.1f} MB)")
        return out
    url = f"{DOWNLOAD_BASE}({product_id})/$value"
    print(f"  downloading {name} ...")
    with requests.get(url, headers={"Authorization": f"Bearer {token}"}, stream=True, timeout=120) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        done = 0
        with open(out, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                if chunk:
                    f.write(chunk)
                    done += len(chunk)
                    if total and done % (10 << 20) < (1 << 20):
                        print(f"    {done/1e6:.0f}/{total/1e6:.0f} MB", flush=True)
    print(f"  ✅ {out} ({out.stat().st_size/1e6:.1f} MB)")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", required=True, help="W,S,E,N in decimal degrees")
    ap.add_argument("--start", required=True, help="YYYY-MM-DD")
    ap.add_argument("--end", required=True, help="YYYY-MM-DD")
    ap.add_argument("--out", default="data/raw/s1")
    ap.add_argument("--max", type=int, default=3, help="max products to download")
    args = ap.parse_args()

    cid = os.environ.get("CDSE_CLIENT_ID")
    cs = os.environ.get("CDSE_CLIENT_SECRET")
    if not cid or not cs:
        sys.exit("Set CDSE_CLIENT_ID and CDSE_CLIENT_SECRET first.")

    w, s, e, n = [float(x) for x in args.bbox.split(",")]
    print(f"→ bbox W{w} S{s} E{e} N{n}")
    print(f"→ date {args.start} .. {args.end}")

    print("Authenticating ...")
    token = get_token(cid, cs)
    print("  ✅ token acquired")

    print("Searching catalogue ...")
    products = search(w, s, e, n, args.start, args.end)
    print(f"  found {len(products)} Sentinel-1 GRD products")
    if not products:
        print("  nothing to download — widen the date range or bbox")
        return

    for i, p in enumerate(products[: args.max]):
        print(f"[{i+1}] {p['Name']}")
        print(f"    date: {p['ContentDate']['Start']} | size: {p.get('ContentLength', 0)/1e6:.0f} MB")
        try:
            download(p["Id"], p["Name"], args.out, token)
        except Exception as ex:
            print(f"    ⚠️  download failed: {ex}")

    print("\n✅ done")


if __name__ == "__main__":
    main()
