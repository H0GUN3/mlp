# Parser0.4 launch gate

**Launch/readiness: PASS. Final feasibility: NOT DETERMINED.**

Reviewed `RCA_PARSER_TRANSFER_CHECK.md`, `parser_transfer.py`, its self-check
summary and OB/TT fixture evidence, plus both launch registrations.

The implementation evidence supports a bounded launch: configuration assertions
preserve the original configuration and establish that only `drain_sim_th`
changes from 0.9 to 0.4; depth 4, child limit 100, cap 1024, source masks,
training input/order, null handling, and exact original profile identities and
seeds remain constrained by provenance/hash checks. Native HawkesADM4 defaults
are asserted, rather than replaced or tuned. Snapshot bytes are hashed before
deserialization; save/reload, enumeration and profile matching are compared.
Self-check flags also report corruption rejection and write/read guards.

`launch_OB.json` and `launch_TT.json` register separate commands ending in
`--system OB` and `--system TT`, respectively, with no trailing punctuation.
Both are marked launched, not measured. Runner boundaries and report fields
exclude raw/model/validation/final36 access; the self-check records zero such
reads/runs. Fixture reports are implementation evidence, not full-data results.

**Unmet before measurement can be assessed:** wait for the final
`parser04/OB/report.json` and `parser04/TT/report.json`, then run
`parser_transfer.py --verify-all`. Do not count process/node completion as
measurement completion. Reports must pass verification and be reviewed for
coverage, cost and limits; current purposive TRAIN-only projections, partially
null groups, TT high-event null profiles, and lower-bound memory estimates do
not establish full-run feasibility. Validation/final36 and model accuracy
remain unmeasured and out of scope for this gate.
