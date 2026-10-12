"""Render an HTML page to PNG with headless Chromium (playwright), e.g. the dashboard:
python tools/screenshot.py outputs/dashboard/index.html outputs/reports/dashboard.png [--offline]
--offline blocks every non-file request, which proves the page draws from vendor/ alone."""
import argparse, os, sys
from pathlib import Path

def shot(src, dst, offline=False, w=1400, h=900, wait_ms=4000):
    from playwright.sync_api import sync_playwright
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=os.environ.get("CHROME") or None);   # CHROME = headless shell path (Kaggle)
        pg = b.new_page(viewport={"width": w, "height": h})
        if offline: pg.route("**/*", lambda r: r.abort() if not r.request.url.startswith(("file:", "data:")) else r.continue_())
        errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(Path(src).resolve().as_uri(), wait_until="load"); pg.wait_for_timeout(wait_ms)
        ok = pg.evaluate("typeof L !== 'undefined' && document.querySelectorAll('.leaflet-container').length > 0")
        pg.screenshot(path=str(dst)); b.close()
    print(f"wrote {dst} (leaflet loaded: {ok}; js errors: {errs[:3]})")
    return ok

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("dst"); ap.add_argument("--offline", action="store_true")
    a = ap.parse_args(); sys.exit(0 if shot(a.src, a.dst, a.offline) else 1)
