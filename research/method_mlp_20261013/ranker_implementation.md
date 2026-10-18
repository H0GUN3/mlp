# Independent matched MLP rankers

`ranker.py` defines a standalone `Ranker(feature_dim, relative)` that returns one
logit for every candidate service. It has no service identity, position embedding,
graph input, or inheritance from the paper implementation.

Inputs are finite floating-point `x` and `coverage` tensors with shape `[B,N,F]`,
and a boolean `mask` of the same shape. Masked feature values are zeroed before
scoring. In relative mode, each feature channel's context is the mean among
observed services; `x - context` is supplied only for observed candidates and
channels. Context availability is shared across candidate rows per channel.

Both modes use the exact shared `5F -> 32 -> 16 -> 1` ReLU MLP and candidate
ordering `[x, relative, own_mask, coverage, context_mask]`. Local mode supplies
zero relative and context-mask slots. Equal seeded initialization and parameter
counts therefore hold, but the local mode's zero slots have inactive input
connections and do not imply equal effective expressivity.

Candidates are never filtered by observation mask; all-missing inputs still
produce finite scores. These models implement the protocol only; this file does
not train models, run experiments, or make performance/generalization claims.
