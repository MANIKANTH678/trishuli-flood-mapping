"""Step 11: small, tested text helpers shared by the situation report and the dashboard (review items 1, 3 and 5).

Every sentence that depends on a count or on the calibration state is built here, so the zero/plural/conditional rules
are tested once (tests/test_textbits.py) instead of being re-typed in two templates."""

# Review item 1: RTC is a third-party product derived from GRD, so it is labelled that way, never "GRD".
PC_SOURCE = "Sentinel-1 RTC (Planetary Computer sentinel-1-rtc, third-party processed from GRD)"
SNAP_SOURCE = "Sentinel-1 GRD (Copernicus Data Space Ecosystem), SNAP sigma0 terrain correction"
# Result of the Step 11 route-equivalence test on the case study (docs/validation_log.md, 2026-10-12).
PC_ROUTE_STATUS = "cross-check only"
PC_ROUTE_NOTE = ("PC RTC gamma0 route: cross-check only. It failed the pre-registered route-equivalence test against the "
                 "SNAP sigma0 case study (docs/validation_log.md, 2026-10-12), so these numbers are not the validated result.")


def source_label(pc):
    return PC_SOURCE if pc else SNAP_SOURCE


def plural(n, one, many=None):
    """plural(1, 'settlement') -> '1 settlement'; plural(3, 'settlement') -> '3 settlements'; many for irregular forms."""
    return f"{n:,} {one if n == 1 else (many or one + 's')}"


def cal_state(det):
    """'ok' (alpha met), 'target_not_met' (>= 3 refs, no threshold met alpha) or 'none' (< 3 refs: no null calibration)."""
    if det.get("null_far_max") is None and det.get("gate_threshold") is None: return "none"
    if det.get("calibrated") is False or det.get("alpha_met") is False: return "target_not_met"
    return "ok"


def mda_text(det):
    v = det.get("min_detectable_km2")
    if v is None and det.get("gate_threshold") is not None and det.get("floor_km2") is not None:
        v = det["gate_threshold"] * det["floor_km2"]
    if v is None: return None
    return f"{v:.0f}" if v >= 10 else (f"{v:.1f}" if v >= 1 else f"{v:.2f}")


def cal_phrase(det):
    """The calibration clause used in every headline. 'calibrated against nulls' only when the alpha target was met."""
    st, mda = cal_state(det), mda_text(det)
    if st == "none": return "UNCALIBRATED: no null gate (fewer than 3 reference dates)"
    if st == "target_not_met":
        return "calibration target not met" + (f"; minimum detectable area ≈ {mda} km²" if mda else "")
    far = det.get("null_far_max")
    return ("calibrated against pre-event nulls" + (f", null false-alarm max {100 * far:.3f}%" if far is not None else "")
            + (f"; minimum detectable area ≈ {mda} km²" if mda else ""))


def cal_phrase_ne(det):
    st, mda = cal_state(det), mda_text(det)
    if st == "none": return "क्यालिब्रेट नगरिएको (३ भन्दा कम सन्दर्भ मिति)"
    tr = str.maketrans("0123456789", "०१२३४५६७८९")
    m = f"; न्यूनतम पत्ता लाग्ने क्षेत्र ≈ {mda.translate(tr)} वर्ग कि.मि." if mda else ""
    if st == "target_not_met": return "क्यालिब्रेसन लक्ष्य पूरा भएन (calibration target not met)" + m
    return "पूर्व-घटना नल मितिहरूसँग क्यालिब्रेट गरिएको" + m


def no_route_text(n):
    """'(1 settlement has no pre-flood route)' / '(141 settlements have no pre-flood route)'; '' for 0."""
    if not n: return ""
    return f" ({plural(n, 'settlement')} {'has' if n == 1 else 'have'} no pre-flood route)"


def next_steps(has_ranges, n_cut):
    """Numbered next-step lines. The 'second track' line only when scenario ranges exist; the first-break line only when
    there are cut-off settlements; the OSM refresh line always."""
    s = []
    if has_ranges:
        s.append("Add a second Sentinel-1 track or a closer post scene and rerun unchanged; the headline should stay inside the ranges above.")
    else:
        s.append("Add a second Sentinel-1 track or a closer post scene and rerun unchanged, with the threshold-sensitivity runs (--profile full) to get scenario ranges.")
    if n_cut:
        s.append(f"Check the {plural(n_cut, 'cut-off first-break point')} against field or imagery reports.")
    s.append("Refresh OSM after the event and rerun cut-off to separate missing roads from real loss.")
    return [f"{i}. {x}" for i, x in enumerate(s, 1)]



def scenario_range(imp):
    """impact_summary 'sensitivity.range', or {} when only the base scenario ran (--profile fast): a one-scenario 'range'
    is not a range, so no range column value and no 'stay inside the ranges' sentence (review item 5)."""
    sens = (imp or {}).get("sensitivity") or {}
    return (sens.get("range") or {}) if len(sens.get("scenarios") or {}) > 1 else {}
