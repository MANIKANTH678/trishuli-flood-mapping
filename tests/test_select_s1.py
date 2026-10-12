import pytest
from datetime import date
from src.fetch.select_s1 import choose

def test_prefers_track_with_enough_refs_over_a_closer_post_scene():
    ev = date(2026, 8, 26)
    d = {(85, "ASCENDING"): {date(2026, 8, 28): 1.0, date(2026, 8, 16): 1.0, date(2026, 8, 4): 1.0, date(2026, 7, 23): 1.0},
         (19, "DESCENDING"): {date(2026, 8, 27): 1.0, date(2026, 8, 15): 1.0}}
    r = choose(d, ev); assert (r["rel_orbit"], r["pass"], r["post"]) == (85, "ASCENDING", date(2026, 8, 28))

def test_rejects_low_coverage_and_missing_sides():
    ev = date(2026, 8, 26)
    with pytest.raises(ValueError): choose({(85, "ASCENDING"): {date(2026, 8, 28): 0.4, date(2026, 8, 16): 1.0}}, ev)
    with pytest.raises(ValueError): choose({(85, "ASCENDING"): {date(2026, 8, 16): 1.0}}, ev)
