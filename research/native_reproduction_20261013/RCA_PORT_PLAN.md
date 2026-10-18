# Next stage: same-case native-method RCAEval port

Purpose: test whether the previously observed train-service/delay_2 mistake
remains when the original modality encoders and joint task are retained.
This is not exact Eadro-paper reproduction and not a proposed mechanism.
Use `RCA_BENCHMARK_LABEL_DECISION.md` for the nominal label contract.

## Dependency order

1. **Training-only input/schema and cost audit.** Read the locked split before
   every raw access. Inspect train data and necessary train/validation schemas;
   never open final36 telemetry. Reuse existing candidate order/exclusions where
   compatible; identify logs-only real services or aliases before freezing any
   new common inventory. Do not silently drop unknown services.
2. **Freeze the domain adapter.** Preserve ten-second metric/trace sequences,
   Drain→native Hawkes→log encoder, modality encoders, fusion definition and
   joint detector/localizer. RCA's eight metric families are not Eadro's seven
   channels; configure the input dimension rather than inventing absent
   original channels. Document trace duration units, nullable values,
   source-like per-case normalization (RCA_NORMALIZATION_SCOPE.md), candidate presence and a training-derived
   static call graph; never import the different Eadro TT deployment graph.
3. **Profile actual log vocabulary and native Hawkes cost before full build.**
   Train templates using only nominal normal logs of training incidents.
   Keep the source masking/solver choices; no count-only replacement or
   truncation chosen to make results attractive. Estimate fit count, time,
   array memory and storage. Existing `.venv-mlp` can read Parquet; `.venv-eadro`
   owns pinned native computation. Choose a small explicit data handoff or
   compatible private reader dependency, not mixed binary import paths.
4. **Build common train/validation inputs.** Keep all original incident groups
   together. Windows must lie wholly on one side of the supplied injection
   boundary. Start with full ten-second, nonoverlapping windows; any
   resource-motivated uniform sampling amendment must precede model results,
   be shared by every comparator, and remain distinct from full coverage.
   Do not select high-anomaly windows.
5. **Train the native reference before proposing changes.** Reuse checked
   batching/loss/prediction helpers without modifying currently running
   calibration sources. Freeze optimization budget and case aggregation before
   scores. Evaluate both individual windows and a predeclared case-level root
   ranking so multiple windows are not counted as independent incidents.
6. **Revisit the named validation failures.** Compare service names, not old
   numeric indices. If the mistake disappears, report that; restoring original
   processing is not a contribution. If it remains, diagnose retained evidence,
   missingness and learned ranking before defining at most two proposed changes.

## Required checks

Protected-file access guards; unchanged split hash; finite encoder inputs with
missingness recorded as missing rather than observed zero errors; training-only
learned templates/graph/shared transformations and case-local normalization; original roots present in the common candidate
set; matching per-model inputs and labels; actual optimizer updates; saved
checkpoint replay; independent case/window score calculation.

Unresolved adaptation choices above are audit questions, not permission to tune
input conditions after seeing accuracy. Preserve all old source, features,
models and results. No final-test model selection or repeated final evaluation.
