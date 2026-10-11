import subprocess, sys
from pathlib import Path
import markdown
from pypdf import PdfReader

CSS = "<style>@page{size:A4;margin:12mm}body{font:9pt/1.25 sans-serif}table{border-collapse:collapse;font-size:8pt}td,th{border:1px solid #999;padding:1px 4px}h1{font-size:13pt;margin:0}h2{font-size:10pt;margin:6px 0 2px}img{max-width:100%}</style>"
def to_pdf(md_path, chrome=r"C:\Program Files\Google\Chrome\Application\chrome.exe"):
    html = Path(md_path).with_suffix(".html"); pdf = html.with_suffix(".pdf")
    html.write_text(CSS + markdown.markdown(Path(md_path).read_text(encoding="utf-8"), extensions=["tables"]), encoding="utf-8")
    subprocess.run([chrome, "--headless", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={pdf.resolve()}", html.resolve().as_uri()], check=True)
    n = len(PdfReader(pdf).pages)
    if n != 1: sys.exit(f"situation report is {n} pages; cut content (limit: ONE page)")
    return pdf
