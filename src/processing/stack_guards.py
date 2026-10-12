"""Step 11 stack guards shared by both routes (CDSE/SNAP check_stack and the PC-route selection).

A same-track stack should be one relative orbit, one pass and (almost) the same time of day. Sentinel-1A and -1D can fly
the same relative orbit at a different orbital phase, so a reference date can sit off the 12-day grid (e.g. 06-22 S1A
next to 06-29 S1D): same geometry, but a different sensor. Both cases only WARN; orbit/pass mismatch stays fatal elsewhere."""
import re
from datetime import datetime

NAME_RE = re.compile(r"^(S1[A-D])_.*?_(\d{8}T\d{6})_")


def tod_warning(times, max_min=10):
    """times: datetimes of each split's first frame. Returns the warning text or None (the reviewer's rule)."""
    tod = [t.hour * 60 + t.minute for t in times]
    if tod and max(tod) - min(tod) > max_min:
        return f"WARNING: acquisition times differ by {max(tod) - min(tod)} min: not the same orbit track?"
    return None


def parse_name(name):
    """'S1D_IW_GRDH_1SDV_20260804T122140_...' -> ('S1D', datetime(2026, 8, 4, 12, 21, 40)); (None, None) if not a S1 name."""
    m = NAME_RE.match(name or "")
    return (m.group(1), datetime.strptime(m.group(2), "%Y%m%dT%H%M%S")) if m else (None, None)


def acquisitions(products):
    """products: {date: [{'name': ...}, ...]} (selection.json) -> {date: {'platforms': [...], 'start_utc': first frame start}}."""
    out = {}
    for d, ps in products.items():
        parsed = [parse_name(p.get("name") or p.get("id")) for p in ps]
        parsed = [(pl, t) for pl, t in parsed if pl]
        if parsed:
            out[d] = {"platforms": sorted({pl for pl, _ in parsed}), "start_utc": min(t for _, t in parsed).isoformat() + "Z"}
    return out


def stack_warnings(products, max_min=10):
    acq = acquisitions(products); w = []
    t = tod_warning([datetime.fromisoformat(a["start_utc"][:-1]) for a in acq.values()], max_min)
    if t: w.append(t)
    plats = sorted({p for a in acq.values() for p in a["platforms"]})
    if len(plats) > 1:
        by = {p: sorted(d for d, a in acq.items() if p in a["platforms"]) for p in plats}
        w.append("WARNING: the stack mixes platforms " + ", ".join(f"{p} ({', '.join(ds)})" for p, ds in by.items())
                 + ": same relative orbit and pass, but a different satellite and orbital phase (dates can sit off the 12-day grid)")
    return acq, w
