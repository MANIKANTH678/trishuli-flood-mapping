EMSR927 damage-point recall: 0.000
Flooded buildings: 61,977
Flood mask: 47 kmý
U-Net val IoU: 0.523 (mean of per-batch IoUs) and 0.574 (pooled)



\## Rebuilt pipeline (ohsome pre-event OSM, snap bug fixed)



Generated 2026-10-04 from the rebuilt pipeline. Study area: bbox 84.95, 27.80, 85.55, 28.35 (Rasuwa corridor). OSM: ohsome API snapshot 2026-07-27, manifest in `data/raw/osm/manifest.json`.



| Metric | New (ohsome pre-event, snap bug fixed) |

|---|---|

| Buildings total | 189,503 |

| Flooded / debris-affected buildings | 423 / 432 |

| Roads (excl. bridges) / flooded | 14,151 / 33 |

| Bridges / flooded | 385 / 1 |

| Hospitals / settlements | 20 / 446 |

| Settlements snapped to road graph | 444 |

| Reachable pre / post flood | 379 / 379 |

| Not connected to any hospital (pre-flood) | 65 |

| Cut off by flood mask | 0 |

| Flood mask | 2,176 px (1.96 km²) |

| EMSR927 damage-point recall | 26 of 3,816 (0.7%) |



Notes:



1\. The earlier cut-off results (431/430/1 and 444/444/0) are invalid because of a snapping defect in `cutoff\_v2.py`, fixed in commit fb7c624. Damage figures were unaffected.

2\. The old and new columns are not comparable: the bbox was tightened to the Rasuwa corridor, OSM changed from a post-event download to a pre-event snapshot, and the flood mask was rebuilt.

