#!/usr/bin/env python3
"""One entry point (Step 10.4): every stage with fail-fast, timing and resume.

    python -m src.run --bbox W,S,E,N --event-date YYYY-MM-DD [--name X] [--profile fast|full] [--s1-source snap|pc]
                      [--clean] [--from-stage NAME]
    python -m src.run --restore runs/<stamp>          # put an archived run (e.g. the cached case study) back

--s1-source snap (default, the headline route): CDSE GRD download + SNAP sigma0 terrain correction. Needs
    COPERNICUS_USER / COPERNICUS_PASS in the environment, SNAP gpt and ~40 GB free.
--s1-source pc: Planetary Computer Sentinel-1 RTC (gamma0), no login, no SNAP. Replaces fetch_s1 / unzip_s1 / check_stack /
    snap / grid with src.processing.pc_stack, which writes the same s1_{split}_{pol}_30m.tif files on the same grid.
    Outputs are labelled "PC RTC gamma0, cross-check route": a cross-check, never the SNAP headline.
--profile fast skips Sentinel-2, the threshold-sensitivity runs and the AI layer, but keeps the null-calibrated gate.

A run directory that holds another run (different bbox / event / source in run.json, or stale scenes) is refused:
mixed scenes would silently corrupt the stacks. --clean archives the previous run under runs/<stamp>/ first
(never models/). Every module CLI called below was checked against its argparse."""
import argparse, json, os, shutil, subprocess, sys, time, zipfile
from datetime import datetime
from pathlib import Path

PY = sys.executable
mod = lambda m, *a: [PY, "-m", m, *map(str, a)]
S1 = "data/raw/sentinel1"                                                           # the folder every S1 stage reads
REF_SPLITS = ["pre", "placebo", "pre3", "pre4"]                                    # nearest pre-event date first
CLEAN = [f"{S1}/{s}" for s in REF_SPLITS + ["post", "pc_annotation"]] + [f"{S1}/selection.json", f"{S1}/pc_source.json",
         "data/raw/osm", "data/raw/s2", "data/raw/dem", "data/interim", "data/processed", "outputs", "run.json"]  # never 'models'
OPTIONAL = {"s2_search", "s2_ingest", "s2_detect", "ai_scenes", "situation_map"}
PC_LABEL = "PC RTC gamma0, cross-check route"


def gpt_found():
    return bool(os.environ.get("GPT") or shutil.which("gpt") or Path(r"C:\Program Files\esa-snap\bin\gpt.exe").exists())


def preflight(source):
    need_gb = 40 if source == "snap" else 5
    if shutil.disk_usage(".").free < need_gb * 1e9: sys.exit(f"less than {need_gb} GB free")
    if source == "pc":                                   # PC route: no CDSE credentials, no SNAP
        return
    miss = [v for v in ("COPERNICUS_USER", "COPERNICUS_PASS") if not os.environ.get(v)]
    if miss: sys.exit(f"missing environment variables: {miss} (or use --s1-source pc for the no-login cross-check route)")
    if not gpt_found(): sys.exit("SNAP gpt not found (set GPT), or use --s1-source pc")


def archive():
    dst = Path("runs") / datetime.now().strftime("%Y%m%d_%H%M%S"); dst.mkdir(parents=True, exist_ok=True)
    for p in map(Path, CLEAN):
        if p.exists(): shutil.move(str(p), str(dst / "__".join(p.parts)))
    print("previous run archived to", dst)
    return dst


def restore(src):
    src = Path(src)
    if not src.is_dir(): sys.exit(f"{src} is not an archived run folder")
    if any(Path(p).exists() for p in CLEAN): archive()
    for f in src.iterdir():
        dst = Path(*f.name.split("__")); dst.parent.mkdir(parents=True, exist_ok=True); shutil.move(str(f), str(dst))
    print("restored", src)


def refuse_dirty(a):
    """Refuse a run directory that already holds a different run."""
    p = Path("run.json")
    if not p.exists():
        if Path(f"{S1}/selection.json").exists() or Path("data/processed/s1_post_VV_30m.tif").exists():
            if a.from_stage is None: sys.exit("this folder holds data from a run without run.json (e.g. the case study): rerun with --clean")
        return
    old = json.loads(p.read_text())
    same = (old.get("bbox") == a.bbox and old.get("event_date") == a.event_date and old.get("s1_source", "snap") == a.s1_source)
    if not same: sys.exit(f"dirty run directory: run.json is for bbox {old.get('bbox')} event {old.get('event_date')} "
                          f"source {old.get('s1_source', 'snap')}: rerun with --clean")


def check_clean(sel, splits, dates):
    for sp, d in zip(splits, dates):
        want = {p["name"] for p in sel["products"][d]}
        for f in Path(S1, sp).glob("*"):
            if f.suffix in (".zip", ".SAFE") and f.name.removesuffix(".zip") not in want: sys.exit(f"stale file {f}: rerun with --clean")


def unzip_s1(splits):
    for sp in splits:
        for z in Path(S1, sp).glob("*.zip"):
            if not (z.parent / z.stem).exists() and not (z.parent / (z.stem + ".SAFE")).exists(): zipfile.ZipFile(z).extractall(z.parent)


def update_run(**kw):
    p = Path("run.json"); d = json.loads(p.read_text()) if p.exists() else {}; d.update(kw); p.write_text(json.dumps(d, indent=2))


def stages(a, sel, epsg, track):
    refs = REF_SPLITS[:len(sel["pre"])]; splits = refs + ["post"]
    R, S, b, full, pc = ",".join(refs), ",".join(splits), a.bbox, a.profile == "full", a.s1_source == "pc"
    st = []
    if not pc:
        st += [("fetch_s1", mod("src.fetch.fetch_sentinel1", "--selection", f"{S1}/selection.json", "--download")),
               ("unzip_s1", lambda: unzip_s1(splits)),
               ("check_stack", mod("src.processing.check_stack", S))]
    st += [("osm", mod("src.download.fetch_osm", "--bbox", b, "--event-date", a.event_date, "--out", "data/raw/osm")),
           ("dem", mod("src.fetch.fetch_dem", "--bbox", b))]
    if pc:
        st += [("pc_stack", mod("src.processing.pc_stack", "--bbox", b, "--epsg", epsg, "--selection", f"{S1}/selection.json",
                                *([] if full else ["--no-10m"]))),
               ("geometry", mod("src.analysis.geometry", "--bbox", b, "--ann-dir", f"{S1}/pc_annotation/pre"))]
    else:
        st += [("snap", mod("src.processing.s1_preprocess", "--bbox", b, "--epsg", epsg, "--splits", S)),
               ("grid", mod("src.processing.s1_to_grid", "--bbox", b, "--epsg", epsg, "--splits", S)),
               ("geometry", mod("src.analysis.geometry", "--bbox", b))]
    st += [("hand", mod("src.analysis.hand")), ("radar_mask", mod("src.analysis.radar_mask"))]
    if len(refs) >= 3: st.append(("null_calibration", mod("src.analysis.calibrate_null", "--ref", R)))
    st.append(("detect", mod("src.analysis.detect", "--ref", R, "--post", "post", "--track-id", track)))
    if full:
        st += [("s2_search", mod("src.fetch.s2_search", "--bbox", b, "--event-date", a.event_date, "--n-pre", 6)),
               ("s2_ingest", lambda: mod("src.processing.s2_ingest", "--bbox", b, "--epsg", epsg, "--dates", Path("data/raw/s2/dates.txt").read_text().strip())),
               ("s2_detect", mod("src.analysis.s2_detect", "--event", a.event_date))]
    st += [("fuse", mod("src.analysis.fuse"))]
    if full:
        st += [("sens_masks", [PY, "tools/make_sens_masks.py", "--ref", R]),
               ("ai_scenes", mod("src.modeling.predict_scene", "--run", "models", "--splits", S) if not pc else None)]
    st += [("damage", mod("src.processing.damage_v2")), ("cutoff", mod("src.processing.cutoff_v2")),
           ("dashboard", mod("src.report.dashboard")),
           ("situation_map", [PY, "tools/make_situation_map.py"]),
           ("report", [PY, "src/report/situation_report.py"])]
    return st


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--bbox"); ap.add_argument("--event-date")
    ap.add_argument("--name", default="area"); ap.add_argument("--profile", choices=["fast", "full"], default="full")
    ap.add_argument("--s1-source", choices=["snap", "pc"], default="snap")
    ap.add_argument("--clean", action="store_true"); ap.add_argument("--from-stage"); ap.add_argument("--restore")
    a = ap.parse_args()
    if a.restore: return restore(a.restore)
    if not (a.bbox and a.event_date): ap.error("--bbox and --event-date are required")
    preflight(a.s1_source)
    if a.clean: archive()
    else: refuse_dirty(a)
    times, sel_p, t_all = {}, Path(f"{S1}/selection.json"), time.time()
    tp = Path("outputs/timings.json")
    if a.from_stage and tp.exists(): times.update({k: v for k, v in json.loads(tp.read_text()).items() if k != "total_s"})

    def run(name, cmd, optional=False):
        t0 = time.time(); print(f"\n=== {name} ===", flush=True)
        try:
            cmd = cmd() if callable(cmd) else cmd
            if cmd: subprocess.run(cmd, check=True)
            else: print("(skipped)")
        except (subprocess.CalledProcessError, OSError, FileNotFoundError) as e:
            times[name] = round(time.time() - t0); save_times()
            if not optional: sys.exit(f"STAGE FAILED: {name}: {e}\nresume with --from-stage {name}")
            print(f"optional stage {name} failed: {e}")
        times[name] = round(time.time() - t0); save_times()

    def save_times():
        Path("outputs").mkdir(exist_ok=True)
        tp.write_text(json.dumps({**times, "total_s": sum(v for k, v in times.items() if k != "total_s")}, indent=2))

    update_run(name=a.name, bbox=a.bbox, event_date=a.event_date, profile=a.profile, s1_source=a.s1_source,
               s1_source_label=PC_LABEL if a.s1_source == "pc" else "SNAP sigma0 (terrain-corrected), headline route",
               started=datetime.now().isoformat(timespec="seconds"))
    if not sel_p.exists() or a.from_stage in (None, "select_s1"):
        run("select_s1", mod("src.fetch.select_s1", "--bbox", a.bbox, "--event-date", a.event_date,
                             "--source", "pc" if a.s1_source == "pc" else "cdse", "--out", sel_p))
    sel = json.loads(sel_p.read_text()); refs = REF_SPLITS[:len(sel["pre"])]; splits = refs + ["post"]
    if a.s1_source == "snap": check_clean(sel, splits, sel["pre"] + [sel["post"]])
    from src.processing.grid import utm_epsg
    w, s, e, n = map(float, a.bbox.split(",")); epsg = str(utm_epsg((w + e) / 2, (s + n) / 2))
    track = ("asc" if sel["pass"].upper().startswith("ASC") else "desc") + str(sel["rel_orbit"])
    update_run(epsg=epsg, track=track, pre_dates=sel["pre"], post_date=sel["post"], ref_splits=refs,
               calibrated_possible=len(refs) >= 3)
    started = a.from_stage in (None, "select_s1")
    for name, cmd in stages(a, sel, epsg, track):
        started = started or name == a.from_stage
        if not started: continue
        run(name, cmd, name in OPTIONAL)
        if name == "osm": update_run(osm_snapshot=json.loads(Path("data/raw/osm/manifest.json").read_text())["snapshot"])
        if name == "detect":
            d = json.loads(Path(f"outputs/diagnostics/detect_{track}.json").read_text())
            update_run(detect_status=d["status"], calibrated=d["calibrated"])
    update_run(finished=datetime.now().isoformat(timespec="seconds"), wall_s=round(time.time() - t_all))
    print(json.dumps(times, indent=2))


if __name__ == "__main__":
    main()
