# Native Eadro + DiagMLP fidelity audit

## Evidence and status

Read-only audit; no installations, data downloads, training, or agents. All Eadro links below pin **FeiGSSS/Eadro `7d69281a80adce60067aa858729746fc6a362f53`**, a public repair fork, not the untouched ICSE artifact. Reused local `../mlp_prerequisites/{MODEL_PROVENANCE.md,eadro_corrected_model.py}` and `../reassessment_20261013/paper_diag.md`. Their common-input adapters are **not native reproductions**. The recorded fork smoke used synthetic inputs and mixed labels; it proves neither preprocessing fidelity nor published scores.

## Native input and preserved components

[`Info`, `__get_edges`](https://github.com/FeiGSSS/Eadro/blob/7d69281a80adce60067aa858729746fc6a362f53/codes/preprocess/util.py) fixes ordered service identities: SN N=12, TT N=27; M=7 metrics ordered `cpu_usage_system,cpu_usage_total,cpu_usage_user,memory_usage,memory_working_set,rx_bytes,tx_bytes`. Preserve that mapping across labels, concatenation, positions, and checkpoints.

[`chunkDataset`, `collate`](https://github.com/FeiGSSS/Eadro/blob/7d69281a80adce60067aa858729746fc6a362f53/codes/main.py) constructs directed DGL graphs with **all N nodes** and metadata’s static `Info.edges`, including only its listed self-edges—not dynamically inferred trace-call graphs. Batch contracts:

- `ndata["metrics"]`: float `[B*N,L,7]`;
- `ndata["traces"]`: float `[B*N,L,2]`;
- `ndata["logs"]`: float `[B*N,E]`, E=template count+1;
- `fault_indexs`: integer `[B]`, `-1` normal, otherwise `0..N-1`.

[`deal_traces`, `deal_logs`, `deal_metrics`](https://github.com/FeiGSSS/Eadro/blob/7d69281a80adce60067aa858729746fc6a362f53/codes/preprocess/single_process.py): trace channel 0 is per-service mean span duration/second; channel 1 remains **zero**. Invocation counts are calculated but not carried into `get_chunks`.

[`model.py`: `MetricModel`, `TraceModel`, `LogModel`, `MultiSourceEncoder`, `MainModel`](https://github.com/FeiGSSS/Eadro/blob/7d69281a80adce60067aa858729746fc6a362f53/codes/model.py) preserves temporal Conv1d–BatchNorm–ReLU–Chomp encoders, optional `SelfAttention` (otherwise last timestep), and linear Hawkes-log embedding. CLI defaults: L=10; metric/trace widths 64, kernels 2, self-attention enabled, log width 16; Linear(144,128)+GLU produces 64 features; GATv2 width 64, four-head max pooling, learned `GlobalAttentionPooling` produces `[B,64]`.

Keep `FullyConnected` detector `64→64→2`, locator `64→64→N`, detection target `fault_index>-1`, root CE `ignore_index=-1`, and `alpha*detect_CE+(1-alpha)*root_CE`, default alpha=.5. Preserve detector-gated descending root rankings; do not substitute a root-only classifier.

## Fusion boundary: supported versus unknown

**Literal paper:** [v2 §III-C/D, Fig.4, Eqs.(2)–(3)](https://arxiv.org/html/2501.02766v2#S3.SS3) concatenates **separate metric/log/trace embeddings plus position before Modal_Fusion**, then concatenates all N modal outputs before Node_Fusion. Each fusion is exactly one affine→LayerNorm→ReLU→Dropout.

Therefore an equation-faithful native wiring branches immediately after the three encoders: `[B,N,144] + concatenated positions [N,P] → Modal(144+P,H) → [B,N,H] → ordered reshape [B,N*H] → Node(N*H,64) → unchanged heads/objective`. This replaces **Linear+GLU and the entire GraphModel/pooling**, not modality encoders.

**Unresolved author integration:** §IV says only GNN components change and everything else stays fixed. Retaining Linear+GLU and putting DiagMLP downstream is consistent with that block-only prose, but loses the separate modality inputs required by Eq.(2). It is not established as the authors’ implementation. Eq.(1) assumes equal modality width d; native widths are unequal. P, H, dropout, width reconciliation, and actual GLU treatment are unpublished integration decisions. Declare the chosen variant; neither boundary can be asserted as recovered author wiring.

## Fairness and runtime hazards

- **Held-out normalization:** `deal_metrics` standardizes each complete service/run CSV before splitting. `deal_traces` standardizes channel 0 across every window/timepoint per service, including held-out and repeatedly overlapping observations.
- **Overlap/provenance:** [`align.py`: `get_basic`, `get_chunks`, `split_chunks`](https://github.com/FeiGSSS/Eadro/blob/7d69281a80adce60067aa858729746fc6a362f53/codes/preprocess/align.py) makes stride-1 length-L windows, randomly shuffles into train/test (CLI test=.3), and discards timestamps/run IDs behind random chunk IDs. Adjacent partitions can share L−1 samples. Its endpoint-based label overlap also misses faults entirely enclosed within a window. Chronological boundaries need a no-shared-sample purge; incident/run grouping must precede window generation.
- **Hawkes is essential:** `logHaw` calls `tick.hawkes.HawkesADM4(decay=3)` using other library defaults, `.fit(knots,end_time,baseline_start=ones(E)*.2)`, returning **baseline only**. `deal_logs` sorts timestamps, subtracts window start s, adds occurrence-index×1e−5, initializes absent templates to `[0.0]`, leaves absent-service vectors zero, but passes **absolute e+1** as horizon. This inconsistent relative-time exposure can distort baselines. A relative horizon `e-s+1` would be a declared correction, not source behavior. No count/rate or homemade estimator is equivalent. [`requirements.txt`](https://github.com/FeiGSSS/Eadro/blob/7d69281a80adce60067aa858729746fc6a362f53/requirements.txt) pins tick=0.7.0.1, torch=1.12.1, DGL=0.9.1, NumPy=1.21.5, pandas=1.4.2, scikit_learn=1.1.2; Drain3 is separately required without a pin.
- **Alignment/runtime:** [`parse_raw_logs.py`](https://github.com/FeiGSSS/Eadro/blob/7d69281a80adce60067aa858729746fc6a362f53/codes/preprocess/parse_raw_logs.py) writes `events`; `deal_logs` expects `event`. [`parse_raw_metrics.py`](https://github.com/FeiGSSS/Eadro/blob/7d69281a80adce60067aa858729746fc6a362f53/codes/preprocess/parse_raw_metrics.py)/[`parse_raw_records.py`](https://github.com/FeiGSSS/Eadro/blob/7d69281a80adce60067aa858729746fc6a362f53/codes/preprocess/parse_raw_records.py) add 16h; [`parse_raw_traces.py`](https://github.com/FeiGSSS/Eadro/blob/7d69281a80adce60067aa858729746fc6a362f53/codes/preprocess/parse_raw_traces.py) adds 8h. Independently sorted file enumerations require explicit cross-modality matching. Cached `split_chunks(concat=False)` references uninitialized `chunks`.
- **Loss/evaluation:** all-normal batches give mean root CE no valid denominator (NaN risk); `MainModel.inference.squeeze()` breaks B=1 indexing. [`BaseModel.fit/evaluate`](https://github.com/FeiGSSS/Eadro/blob/7d69281a80adce60067aa858729746fc6a362f53/codes/base.py) selects checkpoints on test HR@1 and counts correct normals as TP, contaminating detection and localization denominators.

## Missing artifacts and minimal execution path

§IV-A/Table I reports SN 316/78/169, TT 3256/813/1744 and corrected window splitting; §IV-B reports ten runs. Exact sample manifests, grouping/purge rules, preprocessing revision, seeds, fusion settings, and validation selection policy are unavailable in inspected evidence. Fork `result/{0aba95d5,78e573d7}/params.json` records default seed-42 configurations, not DiagMLP’s revised protocol.

Parent should checksum SN/TT archives; preserve run/incident/time provenance; verify pinned tick in an isolated compatible environment; validate schemas, alignment, tensors, tick horizon, mixed/all-normal loss, and B=1; then publish explicit corrections applied identically to both arms (train-only normalization, disjoint groups/windows, validation-only selection, evaluator/runtime repairs). A zero root-loss term only when every target is ignored requires an explicit shared guard. Choose and label the fusion boundary before paired training. These are recommendations, **not executed repairs**.

No GAIA catalog detour: it changes the backbone and cannot resolve Eadro fidelity. A corrected native controlled comparison is implementable; exact published-score reproduction is not established.
