# RCAEval trial handoff

Metadata-only full-scope feasibility run completed for 240 RE2/RE3 OB/TT index
cases. The exact CLI exited 0 and printed:

```text
RCAEVAL_SUITABILITY_PASS cases=240 groups=78 local=180
```

See `research/dataset_suitability_20261016/RCAEVAL.md` for suite imbalance,
hypothetical grouped folds, RE2→RE3 label overlap, protected-scope limits,
input/source hashes, and the exact monitor/session evidence. The JSON result is
`research/dataset_suitability_20261016/rcaeval_trial.json`.

No RCA performance or full raw-coverage claim is supported: RE3 telemetry was
not downloaded or opened, and existing final observations/predictions remain
untouched. The fixed development/final boundary was preserved.
