"""Markdown -> A4 PDF with a hard page-count gate. Used by situation_report.py --one-page (limit 1)
and tools/build_report.py (limit 6).

Engine: headless Chrome, or Microsoft Edge (same flags) if Chrome is missing. Set CHROME=<path> to override."""
import os, shutil, subprocess, sys
from pathlib import Path
import markdown
from pypdf import PdfReader

CSS = ("<style>@page{size:A4;margin:12mm}body{font:9pt/1.25 'Segoe UI',Arial,sans-serif;color:#111}"
       "table{border-collapse:collapse;font-size:7.5pt;margin:3px 0}td,th{border:1px solid #999;padding:1px 4px;vertical-align:top}"
       "th{background:#eef}h1{font-size:13pt;margin:0 0 4px}h2{font-size:10pt;margin:6px 0 2px;color:#1e3a8a}"
       "p,li{margin:2px 0}ul{margin:2px 0;padding-left:16px}blockquote{margin:2px 0;color:#444}img{max-width:100%;max-height:92mm;display:block;margin:2px auto}</style>")
CSS_REPORT = CSS.replace("max-height:92mm;", "max-height:150mm;").replace("9pt/1.25", "9.5pt/1.32").replace("@page{size:A4;margin:12mm}", "@page{size:A4;margin:14mm}")

CANDIDATES = [os.environ.get("CHROME", ""),
              r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
              os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
              r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
              shutil.which("google-chrome") or "", shutil.which("chromium") or "", shutil.which("chrome") or "", shutil.which("msedge") or ""]

def find_browser(required=True):
    for c in CANDIDATES:
        if c and Path(c).exists(): return c
    if required: sys.exit("pdf_gate: no Chrome or Edge found; set CHROME=<path to chrome.exe or msedge.exe>")
    return None

def to_pdf(md_path, max_pages=1, css=None, label="situation report"):
    md_path = Path(md_path); html = md_path.with_suffix(".html"); pdf = md_path.with_suffix(".pdf")
    body = markdown.markdown(md_path.read_text(encoding="utf-8"), extensions=["tables"])
    html.write_text("<!doctype html><meta charset='utf-8'>" + (css or (CSS if max_pages == 1 else CSS_REPORT)) + body, encoding="utf-8")
    if pdf.exists(): pdf.unlink()
    b = find_browser(required=False)
    if b is None:                                       # no browser: WeasyPrint (pip install weasyprint) gives the same page gate
        try: import weasyprint
        except ImportError: sys.exit("pdf_gate: no Chrome/Edge and no weasyprint; set CHROME=<path> or pip install weasyprint")
        weasyprint.HTML(str(html), base_url=str(html.parent)).write_pdf(str(pdf)); b = "weasyprint"
    else:
      # both header/footer flags: new Chrome/Edge know the first, old ones the second; unknown flags are ignored
      subprocess.run([b, "--headless", "--disable-gpu", "--no-pdf-header-footer", "--print-to-pdf-no-header",
                      f"--print-to-pdf={pdf.resolve()}", html.resolve().as_uri()], check=True, capture_output=True)
    if not pdf.exists(): sys.exit(f"pdf_gate: {b} did not write {pdf}")
    n = len(PdfReader(str(pdf)).pages)
    if n > max_pages: sys.exit(f"{label} is {n} pages; cut content (limit: {max_pages} page{'s' if max_pages > 1 else ''})")
    print(f"{label}: {pdf} ({n} page{'s' if n > 1 else ''}, limit {max_pages})")
    return pdf

def screenshot(html_path, png_path, size="1100,800", budget_ms=8000):
    """Headless screenshot of the dashboard (tiles need internet)."""
    b = find_browser(); png = Path(png_path).resolve(); png.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([b, "--headless", "--disable-gpu", "--hide-scrollbars", f"--window-size={size}", f"--virtual-time-budget={budget_ms}",
                    f"--screenshot={png}", Path(html_path).resolve().as_uri()], check=True, capture_output=True)
    if not png.exists(): sys.exit(f"screenshot: {b} did not write {png}")
    print("screenshot:", png); return png

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("md"); ap.add_argument("--max-pages", type=int, default=1); a = ap.parse_args()
    to_pdf(a.md, a.max_pages)
