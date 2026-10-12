"""Vendor every CDN file folium's map loads (plus the fonts / images their CSS points at) under src/report/vendor/,
mirroring the URL path (vendor/<host>/<path>) so relative url(...) references inside the CSS keep working offline.
src/report/dashboard.py copies that tree to outputs/dashboard/vendor/ and rewrites the URLs in the saved HTML.

python tools/vendor_assets.py            # (re)download for the installed folium version; needs internet once"""
import re, sys, urllib.parse, urllib.request
from pathlib import Path

VENDOR = Path(__file__).resolve().parents[1] / "src" / "report" / "vendor"
UA = {"User-Agent": "Mozilla/5.0 (trishuli-flood-mapping vendor script)"}


def local_path(url):
    u = urllib.parse.urlsplit(url)
    return VENDOR / u.netloc / u.path.lstrip("/")


def fetch(url, seen):
    url = url.split("#")[0].split("?")[0]
    if url in seen: return
    seen.add(url); dst = local_path(url)
    if not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            dst.write_bytes(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read())
        except Exception as e:
            print(f"  FAILED {url}: {e}"); return
    print(f"  {dst.relative_to(VENDOR)} ({dst.stat().st_size:,} B)")
    if dst.suffix == ".css":
        for ref in re.findall(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)", dst.read_text(encoding="utf-8", errors="ignore")):
            if ref.startswith("data:"): continue
            fetch(urllib.parse.urljoin(url, ref), seen)


def folium_urls():
    import folium
    m = folium.Map(tiles=None)
    return [u for _, u in m.default_js + m.default_css]


def main(extra=()):
    seen = set()
    leaf = [u for u in folium_urls() if u.endswith("leaflet.js")]          # Leaflet loads these two by name, not via CSS
    extra = list(extra) + [u.replace("leaflet.js", f"images/{n}") for u in leaf for n in ("marker-icon-2x.png", "marker-shadow.png")]
    for u in list(folium_urls()) + extra: fetch(u, seen)
    print(f"{len(seen)} files under {VENDOR}")


if __name__ == "__main__":
    main(sys.argv[1:])
