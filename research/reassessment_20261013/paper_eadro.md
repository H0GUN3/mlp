# Eadro: paper evidence vs. local GAT adaptation

## Evidence

**Original paper.** Eadro targets end-to-end microservice troubleshooting: detect whether an observation window is anomalous, then rank the responsible microservice. It jointly trains detection and localization rather than chaining separate detectors/localizers (arXiv §II-B, §IV-C, Eqs. 4–5). It is multimodal: Drain-parsed log events become Hawkes-process intensity vectors; per-second KPI series and per-callee average-latency trace series are processed with dilated causal convolutions and self-attention. The modality embeddings are concatenated, projected and GLU-fused per service; a directed historical-invocation graph feeds GAT and global attention pooling; shared representations support both task heads (§IV-A–C, Fig. 5). This is not a GAT-only method.

**Data.** The paper’s TrainTicket (TT) is a railway-ticketing benchmark with 41 interacting microservices (27 business-related); SocialNetwork (SN) is a broadcast-style social network with 21 services (14 business-related), communicating via Thrift RPC (§V-A1). The authors collected logs, KPIs (seven named CPU/memory/network indicators sampled per second) and traces. They injected CPU exhaustion, network delay and packet loss into one service per injection. TT/SN used 0.2–0.5 / 2–3 requests per second; normal-only collection lasted 7 / 1.2 hours; there were 162 / 72 injections. The paper reports 48,296 TT and 126,384 SN traces, split by time into 60% training and 40% testing (§V-A1–2). These are the paper’s benchmark facts, not the local RE2 experiment.

**Published results.** Detection is binary classification evaluated by precision, recall and F1; localization uses HR@k and NDCG@k for k=1,3,5 (§V-D). In RQ1, Table II / §V-E reports Eadro F1=0.988, recall=0.996 and precision=0.981, and states F1 improvement of 53.82%–92.68% over prior baselines and 3.13%–25.32% over derived methods. In RQ2, Table III / §V-F reports average HR@1=0.982, HR@5=0.990 and NDCG@5=0.989; HR@1 improvements are reported as 290%–5068% over five advanced baselines and 26.93%–66.16% over derived methods. F1/precision/recall and HR/NDCG are dimensionless rates (paper presents scores as decimals; percentage improvements are relative gains). Table III gives baseline localizers ground-truth anomaly existence, whereas Eadro uses its predicted detector results (§V-F).

**Local adaptation.** `MODEL_PROVENANCE.md` says `EadroGATCommonInput` directly instantiates the pinned author `GraphModel`; its limited rationale is to test the paper’s dependency-aware GAT component as a common-input comparison. It replaces the paper’s log/KPI/trace encoders and Linear+GLU fusion with one common numerical feature vector, and replaces the joint detector/localizer and objective with a local `Linear(H,N)` root-service head. The parent supplies edges. Thus it is a GAT-module adaptation, not full Eadro or an original-paper reproduction.

The local 68.5% (RE2-OB) and 24.1% (RE2-TT) figures are mean validation Top-1 over three seeds, each evaluated on 18 cases: OB seed Top-1s are 8/18, 15/18, 14/18 (mean 68.5%); TT are 6/18, 3/18, 4/18 (mean 24.1%). These are local adapted root-service ranking validation results—not paper scores: different data/splits, inputs, task head, metric aggregation, and no reproduction of Eadro’s full multimodal/joint setup. Provenance specifies validation-loss checkpoint selection and common-input adaptation. `model_checks.json` itself is explicitly `synthetic_only`: adapter forward/backward checks pass for 2- and 5-node inputs; the original full `MainModel` smoke is blocked by upstream undefined `trace_dropout`; a separate corrected public fork passes a synthetic full-model forward/backward smoke. Neither smoke establishes performance.

## Answer

The paper’s Eadro is the complete logs+KPIs+traces, invocation-graph, jointly trained detection-and-localization framework described above. The local result isolates only an adapted graph module within a different common-input root-ranking experiment. Therefore 68.5%/24.1% must not be labeled Eadro’s published performance or a paper reproduction.

## Unknown

The local `model_checks.json` contains no 68.5%/24.1% performance fields; the validation metrics are in `training_results.json` (`runs[].validation.top1`, `cases`; `system`, `seed`, `method`). Per-system paper table cells are not reproduced here; reported paper result summaries above are the prose summaries in §V-E/§V-F. No model was rerun. Corrected-fork synthetic success does not show real-data accuracy, and public-code defects do not by themselves establish a defect in the paper’s reported experiments.

## Sources

- Primary paper, *Eadro: An End-to-End Troubleshooting Framework for Microservices on Multi-source Data*, ICSE 2023, arXiv:2302.05092: https://arxiv.org/abs/2302.05092 ; full text: https://arxiv.org/html/2302.05092v1 (sections/tables cited inline).
- Local provenance: `research/mlp_prerequisites/MODEL_PROVENANCE.md` (Eadro adaptation, synthetic checks, upstream blockers, corrected-fork distinction).
- Local checks: `research/mlp_prerequisites/model_checks.json` (`scope`, `adapted`, `original_main`, `corrected_main`).
- Local validation: `research/mlp_prerequisites/training_results.json` (`runs[].method="eadro_gat_common"`, `system`, `seed`, `validation.cases`, `validation.top1`; three records per system). Run records verified at lines 5141/6186/7231 (RE2-OB) and 17243/20232/23221 (RE2-TT).
