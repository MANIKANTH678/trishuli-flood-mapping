"""The one place the required attribution strings live. Every deliverable imports them from here
(dashboard, situation reports EN / NE / one-page, docs/REPORT.md via tools/build_report.py) and
tests/test_attribution.py checks that each generated file carries them verbatim.

Exact wording from the hackathon brief; do not paraphrase, re-dash or re-encode them."""

SENTINEL = "Contains modified Copernicus Sentinel data 2026."
DEM = ("Produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 "
       "provided under COPERNICUS by the European Union and ESA; all rights reserved.")
OSM = "© OpenStreetMap contributors."
EMS = "European Union, Copernicus Emergency Management Service data"      # wherever EMS products appear

REQUIRED = (SENTINEL, DEM, OSM)           # in every deliverable
DISCLAIMER = "Educational prototype, not an operational tool."
EMS_HOLDINGS = ("EMSR927 GRA products held locally (checked 2026-10-11) contain landslide polygons and damage points, "
                "no flood-extent layer.")


def text(with_ems=False, sep=" "):
    """The required strings (plus the EMS credit when EMS data is shown), joined by `sep`."""
    parts = list(REQUIRED) + ([EMS + "."] if with_ems else [])
    return sep.join(parts)


def markdown_list(with_ems=False, ems_note="validation only"):
    lines = [f"- {s}" for s in REQUIRED]
    if with_ems:
        lines.append(f"- {EMS} ({ems_note}).")
    return "\n".join(lines)


def html(with_ems=False):
    """HTML-safe copy (the strings contain only ©, en dashes and ';', which are valid UTF-8 in a UTF-8 page)."""
    import html as _h
    return _h.escape(text(with_ems), quote=False)
