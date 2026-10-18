# RCA port: normalization unit, fixed before model results

The target is offline **incident-level root-service diagnosis** using the
provided case recording, not forecasting from only the first ten seconds.
Every window of one RCA case stays in the same frozen incident partition.

The public native preprocessing standardizes a service's recording using that
recording's values. For the RCA port, preserve this **stateless per-case**
operation rather than automatically replacing it with a global fitted scaler.
Compute metric/trace mean and population standard deviation separately inside
each provided case, per service/channel; retain the source epsilon. Null
observations are not observed zero errors: exclude them from statistics, use
zero standardized input for unavailable values, and record observation counts
and wholly unavailable channels. This null handling is a disclosed common
domain adapter; it changes no raw files.

Using a case's own supplied measurements is not fitting shared parameters on
other validation/test examples. It is legitimate only under this full-case,
offline query contract. It must NOT be presented as ten-second online diagnosis
without future observations.

Learned templates, any inferred static graph, model weights and any shared
fitted transformation remain training-only. No pooled validation/test scaling.
Apply the same case-local transformation to every compared method and freeze
it before RCA model scores. Do not select a normalization variant according to
whether the named failure becomes correct.

This prospective domain decision does not alter the completed Eadro calibration:
its random window split shares recordings across partitions, so its explicitly
declared training-only scaler remains unchanged. No RCA native model result
has yet been produced or used for this decision.
