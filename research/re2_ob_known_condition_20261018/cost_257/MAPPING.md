# Frozen 257-event mapping and coverage

The map keeps the 256 templates with the most matched occurrences in the
48-case TRAIN partition strictly before each case's injection time. Ties rank
by original integer `cluster_id`; their new feature ids are assigned in
ascending `cluster_id` order. Existing unknown event 0 stays 0, and all other
frozen templates pool into feature 0. This is a 257-dimensional mapping, not a
refit or a model change.

`mapping.json` is exclusively created and hashed before any validation cache
is opened in the resumed producer. The earlier stopped producer read one
validation cache JSON metadata file before this freeze; see `../RECOVERY.md`.
That historical read is disclosed and does not alter the deterministic TRAIN
frequency rule. The resumed producer's explicit cache-load guard permits TRAIN
cache paths only until the saved mapping hash is checked, then permits
validation paths for coverage. It is not a process-wide filesystem audit hook.

`selection.json` chooses one TRAIN case per root by the specified case hash,
then one fully normal (`start + 9 < inject_time`) and one fault window per
chosen case by the specified window hash. All 14 services accompany each
window. Missing layers are reported, never substituted.

`coverage.json` reports TRAIN/validation × pre/post × service totals, kept
rows, newly pooled rows, prior unknown rows, combined other ratio, distinct
pooled templates, and a bounded list of sanitized summaries. Every cache row
is assigned exactly once. Empty service/phase buckets have `other_ratio: null`.
No observations are rematched and no solver is run.

See `mapping_evidence/completion.json` and `mapping_evidence/verification.json`
for input/source hashes, output hashes, and actual command exits.
