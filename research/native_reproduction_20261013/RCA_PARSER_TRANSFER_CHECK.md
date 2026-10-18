# Bounded parser-transfer check — before any RCA model result

Literal public preprocessing was measured, not assumed feasible:
both systems hit1024 retained templates (E1025); OB created376565 clusters and
all1629 observed profile messages matched the unseen bin. Mean-fit TRAIN-only
projections sum to1205.21 CPU-worker hours, or about25.1 days for two ideal
workers. Purposive samples and unmeasured large/null TT groups make this an
uncertain planning projection, not observed full-build time.

This does not establish a neural-model defect. Do not replace Hawkes with
counts/rates or shrink its bins and still call that the native method.

## One prospective transfer configuration

Test **only similarity threshold0.4**, the default explicitly present in
installed Drain3 0.9.11 `template_miner_config.py` and the library documentation:
https://github.com/logpai/drain3/blob/master/_autodocs/configuration.md

Keep source masking, depth4, max_children100, cap1024, input rows/order,
match/unseen semantics, missing-message policy, native Hawkes/default solver
and exact profile samples/seeds unchanged. This is one named dataset-port
configuration, **not literal original preprocessing or exact-paper reproduction**.
It is not the proposed scientific method, and its effects cannot be advertised
as a new neural-model contribution. Any later comparison must share the adopted
preprocessing across the reference and proposal.

Fit only existing TRAIN-normal exports; do not inspect model accuracy.
Measure template count/eviction, fixed-profile match coverage, exact native
fit time and memory. No further threshold search is authorized by this check.
If it still fails to give usable coverage/cost, report that before deciding
another route; do not keep tuning until a model wins.

Save the final trained miner state with its config/input hashes and verify
restored matching, so later use does not need to retrain it or reconstruct a
possibly different tree from template strings. In-progress state is never a
completed artifact.

Outputs go to a new `parser04/` path; preserve all0.9 code and evidence.
