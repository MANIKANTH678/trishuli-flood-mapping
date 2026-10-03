# Flood Segmentation Model — Model Card

## Summary
Small U-Net (1.93 M params) that segments flood extent from dual-pol
Sentinel-1 GRD (VV + VH) imagery at 512x512 chip resolution.

## Data
- **Training dataset:** Sen1Floods11 v1.1 hand-labeled subset
  (Bonafilia et al., 2020, CVPR Workshops).
- **Chips:** 252 train / 89 validation / 90 test.
- **Labels:** hand-verified flood masks derived from Planet optical + Sentinel-1.
  Not derived from our own pipeline output — no circularity.
- **Known biases:** sampling skewed to Bolivia, India, US, and a few African sites.
  Himalayan glaciated terrain is under-represented.

## Model
- **Architecture:** 4-level U-Net, base=32, 1.93 M params.
- **Input:** 2 channels (VV, VH), rescaled from dB.
- **Output:** 1 channel pre-sigmoid logits; flood = logit > 0.
- **Loss:** BCEWithLogitsLoss, masked to valid pixels.

## Training
- **Optimizer:** Adam, lr=1e-3, cosine annealing over 20 epochs.
- **Batch size:** 4. Hardware: CPU-only (20 cores). Time: ~110 min.

## Metrics

| Split | Chips | Mean IoU | Mean F1 | Global IoU | Global F1 |
|---|---|---|---|---|---|
| Validation | 89 | 0.5170 | 0.6312 | — | — |
| Test (held-out) | 90 | 0.5534 | 0.6878 | 0.6387 | 0.7795 |

Confusion at test time: TP=1,865,791 | FP=355,230 | FN=700,310.

Reference points on Sen1Floods11 hand-labeled test set:
- Random baseline IoU: ~0.20
- Published U-Net baselines: 0.55-0.70
- Our model (global IoU): 0.64 — competitive, no augmentation, CPU-trained.

## Limitations
- **Domain shift:** trained mostly on non-Himalayan scenes. Applying directly
  to Trishuli SAR data without fine-tuning will degrade accuracy.
- **Resolution:** 512x512 chips at ~10 m; floods < ~1 ha may be missed.
- **Cloudy events** under-represented (labels depended on optical verification).
- **No permanent-water exclusion:** may confuse permanent water with floods.

## Intended use
- Research-grade flood extent estimation on Sentinel-1 GRD.
- NOT for operational emergency response without local validation.

## How to reproduce
python -m src.modeling.train_segmentation     # 20 epochs, ~2 hours CPU
python -m src.modeling.eval_segmentation      # held-out test split

## Checkpoints
- outputs/flood_unet.pt      — best val IoU (epoch 12)
- outputs/flood_unet_last.pt — last epoch

## Citations
- Bonafilia, D., Tellman, B., Anderson, T., & Issenberg, E. (2020).
  Sen1Floods11: a georeferenced dataset to train and test deep learning
  flood algorithms. CVPR Workshops.
