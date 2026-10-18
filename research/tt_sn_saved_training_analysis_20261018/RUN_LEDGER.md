# Saved training run ledger

Pinned evidence snapshot: 2026-10-18. Scope is the 18 runs in
`calibration50/{TT,SN}/{diagmlp,eadro}/seed_{11,23,37}` and
`calibration200/SN/{diagmlp,eadro}/seed_{11,23,37}`. DiagMLP is primary;
Eadro is a separate supplementary table. TT200, corrected SN rotation, and
RE2 are excluded.

## How to read the receipts

- **Configured/planned** is arithmetic from saved config and split:
  `ceil(TRAIN count / batch size)` batches per epoch, the planned batch-size
  sequence, and planned updates over configured epochs.
- **Recorded** comes from each `history.json` and is cross-checked against
  `summary.json`: actual history row/epoch sequence, per-epoch
  `optimizer_updates`, their sum, summary totals, and earliest full-validation
  `validation_joint_loss` minimum (selection rule: strict minimum, earliest
  tie).
- The pinned `native_train.py` calls `optimizer.step()` once per batch and
  increments the history counter. Thus logged update counts also provide a
  **derived batch count** per epoch. No batch IDs or observed batch-size
  sequence were saved; only the configured minibatch sizes below are direct
  arithmetic. Actual batch-size details remain unknown.
- Train normal/fault counts are from the allowed metadata window identities;
  validation labels are from saved predictions and checked against those
  identities. Counts below use `normal/fault` order.
- Four SHA-256 values per run (config, split, history, saved validation
  predictions) match the corresponding summary artifact hashes. Configured
  source hashes match current trainer/model/protocol files. Metadata hashes
  are recorded. `raw.npz` was not opened and its configured hash was not
  independently rechecked. No checkpoint was loaded/deserialized; no training
  or inference was run.

## Primary: DiagMLP

| Cohort | Seed | Config epochs | TRAIN / validation (normal/fault) | Planned batch sizes; batches/epoch | Planned updates | History epochs; logged updates/epoch | History sum / summary updates | Earliest selected epoch |
|---|---:|---:|---|---|---:|---|---:|---:|
| TT50 | 11 | 50 | 3256 (491/2765) / 813 (127/686) | 256×12, 184×1; 13 | 650 | 1–50; 13×50 | 650 / 650 | 27 |
| TT50 | 23 | 50 | 3256 (491/2765) / 813 (127/686) | 256×12, 184×1; 13 | 650 | 1–50; 13×50 | 650 / 650 | 23 |
| TT50 | 37 | 50 | 3256 (491/2765) / 813 (127/686) | 256×12, 184×1; 13 | 650 | 1–50; 13×50 | 650 / 650 | 24 |
| SN50 | 11 | 50 | 316 (56/260) / 78 (13/65) | 256×1, 60×1; 2 | 100 | 1–50; 2×50 | 100 / 100 | 49 |
| SN50 | 23 | 50 | 316 (56/260) / 78 (13/65) | 256×1, 60×1; 2 | 100 | 1–50; 2×50 | 100 / 100 | 48 |
| SN50 | 37 | 50 | 316 (56/260) / 78 (13/65) | 256×1, 60×1; 2 | 100 | 1–50; 2×50 | 100 / 100 | 50 |
| SN200 | 11 | 200 | 316 (56/260) / 78 (13/65) | 256×1, 60×1; 2 | 400 | 1–200; 2×200 | 400 / 400 | 192 |
| SN200 | 23 | 200 | 316 (56/260) / 78 (13/65) | 256×1, 60×1; 2 | 400 | 1–200; 2×200 | 400 / 400 | 78 |
| SN200 | 37 | 200 | 316 (56/260) / 78 (13/65) | 256×1, 60×1; 2 | 400 | 1–200; 2×200 | 400 / 400 | 200 |

## Supplementary: Eadro

| Cohort | Seed | Config epochs | TRAIN / validation (normal/fault) | Planned batch sizes; batches/epoch | Planned updates | History epochs; logged updates/epoch | History sum / summary updates | Earliest selected epoch |
|---|---:|---:|---|---|---:|---|---:|---:|
| TT50 | 11 | 50 | 3256 (491/2765) / 813 (127/686) | 256×12, 184×1; 13 | 650 | 1–50; 13×50 | 650 / 650 | 48 |
| TT50 | 23 | 50 | 3256 (491/2765) / 813 (127/686) | 256×12, 184×1; 13 | 650 | 1–50; 13×50 | 650 / 650 | 50 |
| TT50 | 37 | 50 | 3256 (491/2765) / 813 (127/686) | 256×12, 184×1; 13 | 650 | 1–50; 13×50 | 650 / 650 | 46 |
| SN50 | 11 | 50 | 316 (56/260) / 78 (13/65) | 256×1, 60×1; 2 | 100 | 1–50; 2×50 | 100 / 100 | 31 |
| SN50 | 23 | 50 | 316 (56/260) / 78 (13/65) | 256×1, 60×1; 2 | 100 | 1–50; 2×50 | 100 / 100 | 33 |
| SN50 | 37 | 50 | 316 (56/260) / 78 (13/65) | 256×1, 60×1; 2 | 100 | 1–50; 2×50 | 100 / 100 | 40 |
| SN200 | 11 | 200 | 316 (56/260) / 78 (13/65) | 256×1, 60×1; 2 | 400 | 1–200; 2×200 | 400 / 400 | 31 |
| SN200 | 23 | 200 | 316 (56/260) / 78 (13/65) | 256×1, 60×1; 2 | 400 | 1–200; 2×200 | 400 / 400 | 90 |
| SN200 | 37 | 200 | 316 (56/260) / 78 (13/65) | 256×1, 60×1; 2 | 400 | 1–200; 2×200 | 400 / 400 | 200 |

## Reconciliation and pinning

Across all 18 runs, configured arithmetic is **6,900 planned optimizer
updates** over 1,800 configured epochs; histories record **6,900 updates**,
and every history sum equals its summary total. Every run has the configured
epoch count and contiguous epoch sequence; recomputed earliest validation-loss
minimum matches summary `best_epoch`.

For each of the six same-model/same-seed SN50↔SN200 pairs, configured input
hashes, split SHA-256, and configured scaler SHA-256 match; the first 50
history rows match exactly in all numeric fields when `seconds` is excluded.
These are distinct 50- and 200-epoch saved runs, not evidence that a 50-epoch
optimizer state was resumed: the pinned trainer constructs a new model and
Adam optimizer per invocation. No optimizer-state continuation is recorded.

Existing `tt50_verification.json`, `sn50_verification.json`, and
`sn200_verification.json` each report PASS, 6/6 runs checked, and zero
failures. Exact per-run SHA-256 values, compressed exact epoch/update
sequences, pair checks, source hashes, and verifier receipts are in
`RUN_LEDGER.json`. The run sequences use lossless ranges/RLE: for example,
`[2, 50]` for logged updates means 2 updates in each of 50 consecutive epochs.
