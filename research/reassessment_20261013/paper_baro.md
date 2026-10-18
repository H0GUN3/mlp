# BARO and the frequency prior

## Evidence

- **Original task and method.** BARO addresses metric-based microservice failure troubleshooting end to end: detect an anomaly/failure, estimate its onset, then rank root-cause metrics and services (paper §§2.1, 3.2; Algorithm 1). Multivariate BOCPD models change points/dependencies and uses the first detected change point as onset; RobustScorer ranks each metric by its maximum post-onset absolute deviation from the pre-onset median divided by the pre-onset IQR (paper §§3.3–3.4, Eqs. 3–4). It is unsupervised and does not require call-graph knowledge (paper §1).
- **Paper datasets and experiment size.** Section 4.1 describes Online Boutique (12 services), Sock Shop (11), and Train Ticket (64). Across each system, four fault types—CPU hog, memory leak, network delay, packet loss—were injected into five named target services; each fault-type × target-service combination was repeated five times, yielding **100 failure cases per system** (paper §4.1). The paper reports metrics and service counts in Table 1. These are experimental failure cases, not this repository’s cases.
- **Paper results and units.** Detection is evaluated with Precision, Recall, and F1 (§4.2.1; unitless scores). Table 2 gives BARO on Train Ticket as Precision **0.68**, Recall **1.00**, F1 **0.81**. Service RCA uses AC@k (whether the true root service is within top k) and Avg@k, the mean of AC@1 through AC@k (§4.2.2); Table 3 reports Train Ticket BARO **Avg@5 = 0.81** (unitless). Avg@5 is not Top5 hit rate: the latter is AC@5 alone.
- **Publication.** Crossref DOI metadata verifies *Proceedings of the ACM on Software Engineering*, volume 1, issue FSE, 2024-07-12, pages 2214–2237 (DOI 10.1145/3660805). The arXiv full-text header contains malformed-looking “FSE987” text; use Crossref’s explicit metadata, not that header, for venue/year/pages.
- **Local BARO comparison.** `research/BASELINE_PROTOCOL.md` defines a NumPy reimplementation of only BARO’s scoring path, pinned to `phamquiluan/baro` commit `582d4ead3d3301a34fea4e395bfa3f750fc9a40d`. It receives the known injection/onset boundary; it does not execute BOCPD, detect onset, or reproduce the complete paper. `scripts/baseline_dev.py::baro_preprocess` and `baro_rank` implement preprocessing/scoring; `research/mlp_prerequisites/baro_validation.json` field `method` confirms “not BOCPD or full paper reproduction.” Its `summary.RE2-OB` and `summary.RE2-TT` are local validation aggregates, not paper results.
- **Absolute/signed discrepancy.** Paper Eq. 3 and Algorithm 1 specify absolute deviation. In the pinned public `root_cause_analysis.py::robust_scorer`, RobustScaler-transformed post-onset values are aggregated with Python `max(zscores)`, a signed maximum. Locally `baro_signed` follows this public code path; `baro_absolute_variant` changes only this operation as a diagnostic. It is not a separate paper method or full reproduction.
- **Frequency prior.** `scripts/mlp_readiness.py::run` counts TRAIN root-service labels with `np.bincount(a[1])`, repeats that vector over validation cases, and scores using `rank_metrics`; tied scores receive expected Top-1/Top-3/MRR ranks. `research/mlp_prerequisites/verification.json::prior_validation` reports, for each system, 18 validation cases: Top-1 **0.1667**, Top-3 **0.5**, MRR **0.4181** (unitless). It is the historical root-service frequency control, not a paper or SOTA method.

## Answer

These comparisons answer different questions. **BARO** is a published research comparator for anomaly detection plus root-cause ranking; our limited adaptation asks how its score/ranking component behaves when onset is supplied. **The frequency prior** is a sanity control asking how well training-label frequency alone ranks validation roots, without case-specific diagnostic evidence.

Beating the frequency prior is insufficient to claim meaningful RCA improvement: it only exceeds a weak memorization control, not BARO or another substantive comparator, and does not establish use of causal, case-specific evidence or generalization. The local BARO comparison also cannot establish end-to-end performance because onset detection is omitted. Do not call the adapted local score a reproduction of original BARO.

## Unknown

- No Top5 hit-rate number is asserted here; Table 3’s cited number is Avg@5, a different measure.
- Results for other datasets/methods and generalization beyond the cited paper experiment or local validation split are not stated.
- Local validation does not establish performance on any final-test data.

## Sources

- BARO full text: https://arxiv.org/html/2405.09330v1 — §§2.1, 3.2–3.4, Algorithm 1, Eqs. 3–4, §§4.1–4.2.2, Tables 1–3.
- arXiv record: https://arxiv.org/abs/2405.09330
- Crossref DOI record: https://api.crossref.org/works/10.1145%2F3660805 — `container-title`, `volume`, `issue`, `published-print`, `page`.
- Pinned public scorer: https://raw.githubusercontent.com/phamquiluan/baro/582d4ead3d3301a34fea4e395bfa3f750fc9a40d/baro/root_cause_analysis.py — `robust_scorer`.
- Local: `research/BASELINE_PROTOCOL.md`; `scripts/baseline_dev.py::baro_preprocess`, `baro_rank`; `research/mlp_prerequisites/baro_validation.json::{method,summary}`; `scripts/mlp_readiness.py::{rank_metrics,run}`; `research/mlp_prerequisites/verification.json::prior_validation`.
