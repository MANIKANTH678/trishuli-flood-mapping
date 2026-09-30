# Trishuli Flood Damage Mapping

Track B — Multimodal AI Hackathon 2026

Maps flood and debris damage from the 26 August 2026 Trishuli–Bhote Koshi
flood (Nepal) using free satellite data.

## Setup

```bash
python3 -m venv ~/flood-venv
source ~/flood-venv/bin/activate
pip install -r requirements.txt


python -m src.run_pipeline --bbox 84.50,27.40,86.00,28.40 \
                           --pre 2026-08-16 \
                           --post 2026-08-28 \
                           --out outputs/
