# Model card: Sentinel-1 open-water segmentation

## Model
ResNet34-encoder U-Net (segmentation-models-pytorch, ImageNet-pretrained encoder, 2-channel input). Input: Sentinel-1 VV+VH in dB, normalized as clip((x+25)/15, -3, 3). Output: per-pixel open-water probability. Threshold 0.4, chosen on validation only.

## Training data
Sen1Floods11 hand-labelled chips (Bonafilia et al., CVPR Workshops 2020), published train/valid splits. 40 epochs, AdamW, masked BCE + Dice, rot90/flip augmentation, seed 0. Checkpoint and threshold selected on validation pooled IoU. No EMS (EMSR927) data was used for training or tuning.

## What it detects
Open water only. No allowed dataset labels debris; debris and damage evidence come from the change detector.

## Results (pooled IoU, 95% chip-bootstrap CI)
| Row | Val IoU (pooled) | Test | Bolivia (unseen region) |
|---|---|---|---|
| Old checkpoint, thr 0.5 | 0.575 [0.49, 0.65] | 0.612 [0.49, 0.71] | 0.666 [0.48, 0.77] |
| U-Net, 20 epochs, thr 0.5 | 0.634 [0.55, 0.70] | 0.659 [0.54, 0.75] | 0.687 [0.50, 0.79] |
| **ResNet34-U-Net, 40 epochs, thr 0.4** | **0.672 [0.59, 0.74]** | **0.682 [0.57, 0.77]** | **0.680 [0.46, 0.80]** |


<!-- STEP8:seeds -->
## Seeds (training noise)

| Split | Mean IoU | SD (seeds) | Min | Max |
|---|---|---|---|---|
| valid | 0.672 | 0.005 | 0.667 | 0.677 |
| test | 0.682 | 0.002 | 0.680 | 0.683 |
| bolivia | 0.702 | 0.020 | 0.680 | 0.719 |

3 seeds (0, 1, 2); the **seed-0 model is the shipped model**; seeds 1-2 only measure training noise.
<!-- /STEP8:seeds -->

## Himalayan evidence

<!-- STEP8:himalaya -->
Himalayan hand-labelled chips: not evaluated yet.

Agreement with Sentinel-2 MNDWI water on clear valley-floor pixels (a pseudo-reference, **not accuracy**: turbid water fools MNDWI, S1 and S2 are 1–4 days apart, 30 m): post (20260827) IoU 0.06, P 0.51, R 0.07, n=31,000; pre (20260812) IoU 0.03, P 0.49, R 0.03, n=22,127.

Corridor test (prediction-only; shadow/layover masked, floor via HAND): new-water excess main − tributary floor 0.0086 vs largest leave-one-out null 0.0076: **not separable from the nulls**.

The model detects **open water only**: no allowed training dataset labels debris, so debris and mud come from the change detector, not the AI.
<!-- /STEP8:himalaya -->


## Failure modes
Radar shadow in mountains; turbid or sediment-laden water; urban areas; arid scenes. Weakest test regions: Pakistan 0.36 (n=6), Somalia 0.53 (n=6), USA 0.57 (n=14).

## Radiometry check (training chips vs Trishuli post-event scene)
- VV: Sen1Floods11 p5/p50/p95 = [-18.0, -9.8, -5.3]; Trishuli post = [-18.0, -8.2, 2.8]; median difference +1.6 dB
- VH: Sen1Floods11 p5/p50/p95 = [-26.5, -16.4, -11.9]; Trishuli post = [-24.1, -14.6, -4.8]; median difference +1.8 dB
- Medians are within about 3.5 dB of the training data.

## Licences and attribution
Sen1Floods11 (Bonafilia et al., 2020). ImageNet-pretrained ResNet34 weights via segmentation-models-pytorch; check and cite the weights' licence.
