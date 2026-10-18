# RCA native Drain/Hawkes feasibility

Only hash-verified guarded TRAIN exports were read. No RCA raw files, validation messages, final36 files, full feature arrays or models were read/built. Frozen split SHA256: `1644bb875d061884b8dff37203b07761bd5f11ae3f3e9ed7f8f44687eb3142e5`.

## Actual dimensions and measurements
|System|normal rows / observed strings|templates / E|Drain wall seconds|sample completed / timeout / unavailable / stopped|
|---|---:|---:|---:|---:|
|OB|4771132 / 4771132|1024 / 1025|775.792|10 / 0 / 0 / 0|
|TT|6669330 / 6668862|1024 / 1025|820.058|8 / 0 / 2 / 0|

Every available nominal-normal TRAIN string was mined in exported case/service/time/source-row order; empty strings are observed messages, not missing. Null/missing messages are unavailable, never invented or assigned unseen events; partially missing profile groups are not fitted. Unidentified services remain unavailable for fits. Native final cluster enumeration and duplicate template texts are retained. The pinned INI's intrinsic 1024-cluster LRU is unchanged; no extra truncation, subsampling, rate/count surrogate or configuration change.
- **OB:** 376565 clusters created, 375541 intrinsic evictions; missing/null normal messages 0 / 0. Single E×E float64 matrix 8.02 MiB; seven simultaneous source matrix payloads 56.11 MiB/fit (112.22 MiB for two), excluding SVD/C++/Python overhead. Supervisor cumulative peak RSS after mining 510.71 MiB.
- **OB completed fits:** mean 26.771859s, max 70.718858s; measured iteration counts [11, 21, 11, 21, 21, 11, 11, 11, 50, 50]; peak worker RSS 376.12 MiB. TRAIN 69254 string-usable groups imply 515.02h serial / 257.51h ideal two-worker mean-fit estimate; max-sample scenario 1360.43h serial. These are completed-only projections, not upper bounds.
- **OB canonical audit footprint:** W=7732, N=15, E=1025: dense log payload 0.886 GiB; metric float32 0.035 GiB; trace float32 0.009 GiB. Exact TRAIN/validation-schema array estimates for all audit candidate bases are in JSON; none is adopted.
- **TT:** 17069 clusters created, 16045 intrinsic evictions; missing/null normal messages 0 / 468. Single E×E float64 matrix 8.02 MiB; seven simultaneous source matrix payloads 56.11 MiB/fit (112.22 MiB for two), excluding SVD/C++/Python overhead. Supervisor cumulative peak RSS after mining 510.71 MiB.
- **TT completed fits:** mean 14.969411s, max 21.184287s; measured iteration counts [21, 11, 11, 11, 11, 21, 11, 21]; peak worker RSS 362.62 MiB. TRAIN 165983 string-usable groups imply 690.19h serial / 345.09h ideal two-worker mean-fit estimate; max-sample scenario 976.73h serial. These are completed-only projections, not upper bounds.
- **TT canonical audit footprint:** W=7776, N=69, E=1025: dense log payload 4.098 GiB; metric float32 0.160 GiB; trace float32 0.040 GiB. Exact TRAIN/validation-schema array estimates for all audit candidate bases are in JSON; none is adopted.

## Estimator, limits and verification
Python3.8, tick0.7.0.1, drain3==0.9.11, NumPy1.21.5; one unmixed `.venv-eadro`. Pinned INI upstream blob `a391102e3e8c66ac125fad082e619a2b180e0dcf` verified. Native `make_knots`/`fit_hawkes` reused: source match/unseen index0, absent-bin [0], per-bin 1e−5 jitter, relative horizon10, HawkesADM4(decay3), baseline initialization.2. Defaults: C1000, lasso/nuclear.5, max_iter50, tol1e−5, rho.1, em_max_iter30, em_tol=None, approx0, n_threads1. NumPy seed42+window*N+node uses deterministic TRAIN case/window and unchanged audited canonical service coordinates. OMP/MKL/OPENBLAS=1; measurement is sequential (≤2 concurrent fits).
Dimensions/memory were written before any actual sample fit. Completed baselines are finite, nonnegative and E-dimensional; knot bounds are relative [0,10). Reaching iteration50 does not establish convergence. Warnings, failures, worker output and timeout censoring remain in JSON; native in-flight captured warnings cannot be recovered after SIGKILL.
Both final manifests were required before mining; exporter closure checks and independently measured SHA256/byte/line counts passed. Per-case original-object hashes and all TRAIN row counts/order/bounds were checked during mining. Nine new bridge/controller/gate self-checks and seven prior native synthetic tests passed; native Python3.8 Pyright: 0 errors, 0 warnings. Artifact/source hashes and output verification passed.

All 18 real fits completed within the 120s subprocess deadline (maximum wall 73.109s), with zero solver warnings; no measured timeout or censored fit timing exists. The kill/reap and first-two-timeout stop policy passed mocked controller tests. Two OB fits reached iteration50.

Observed coverage limits are material: every OB profile string (1629/1629) matched unseen index0, with 1024 dummy bins per fit. TT completed profiles contain only 29 strings from one service/case, with 1023-1024 dummy bins. Its largest groups (1840 and 1587 events) are unavailable because 32 and 24 messages are null; high-event TT timing remains unmeasured. No parameters were changed to improve this coverage.

A conditional TRAIN memory planning sum (dense audit-dtype outputs + two measured worker RSS peaks + cumulative mining RSS) is OB 2.162 GiB / TT 5.504 GiB. It is not observed aggregate peak memory or a ceiling; full event tables, caches, missing masks and native float64 metric/trace expansion are excluded.

Confidence is limited by purposive ≤12 exported profiles, intrinsic LRU, dummy-bin overhead, unknown/partially null groups, host contention and solver convergence. Full TRAIN cost uses audited actual nonempty/string-usable group counts; no statistical confidence interval, full matching/I/O timing or final36 time/memory claim. Mining wall includes JSON decoding and row verification; matrix payloads are not peak-memory ceilings. Input resolution, labels, candidates and scientific mechanism remain unchanged.
