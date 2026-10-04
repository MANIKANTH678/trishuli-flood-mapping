import argparse, os, shutil, subprocess, sys
from pathlib import Path

GRAPH = Path("graphs/s1_grd_sigma0_tc.xml")
S1, OUT = Path("data/raw/sentinel1"), Path("data/interim/s1_tc")

def gpt_exe():
    for c in (os.environ.get("GPT"), shutil.which("gpt"),
              r"C:\Program Files\esa-snap\bin\gpt.exe"):
        if c and Path(c).exists():
            return c
    sys.exit("gpt not found: install SNAP or set GPT=<path to gpt.exe>")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", required=True); ap.add_argument("--epsg", required=True)
    ap.add_argument("--dem", default="data/raw/dem/dem_glo30_wgs84.tif")
    ap.add_argument("--spacing", default="10"); ap.add_argument("--margin", type=float, default=0.05)
    a = ap.parse_args()
    w, s, e, n = map(float, a.bbox.split(","))
    m = a.margin
    wkt = f"POLYGON(({w-m} {s-m}, {e+m} {s-m}, {e+m} {n+m}, {w-m} {n+m}, {w-m} {s-m}))"
    done = {"pre": 0, "post": 0}
    for split in done:
        for safe in sorted((S1 / split).glob("*.SAFE")):
            out = OUT / split / f"{safe.stem}.dim"
            out.parent.mkdir(parents=True, exist_ok=True)
            if out.exists():
                done[split] += 1; continue
            cmd = [gpt_exe(), str(GRAPH), f"-Pinput={safe / 'manifest.safe'}",
                   f"-Pdem={Path(a.dem).resolve()}", f"-Pregion={wkt}", f"-Pspacing={a.spacing}",
                   f"-Pcrs=EPSG:{a.epsg}", f"-Poutput={out.resolve()}",
                   "-c", "3G", "-q", str(os.cpu_count())]
            print(f"[{split}] {safe.name[:60]} ...")
            r = subprocess.run(cmd, capture_output=True, text=True)
            log = (r.stdout + r.stderr)
            if r.returncode != 0:
                if "intersect" in log.lower():
                    print("   no overlap with bbox, skipped"); continue
                sys.exit(f"gpt failed:\n{log[-1500:]}")
            done[split] += 1
    if not all(done.values()):
        sys.exit(f"no processed scenes for: {[k for k, v in done.items() if not v]}")

if __name__ == "__main__":
    main()