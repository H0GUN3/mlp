# Bounded reference model provenance

## Scope and API

`scripts/mlp_reference.py` provides two **common-input adaptations**:

```python
from scripts.mlp_reference import DiagMLPCommonInput, EadroGATCommonInput, self_check

mlp = DiagMLPCommonInput(node_count, input_dim, hidden_dim=32, dropout=0.1)
gat = EadroGATCommonInput(node_count, input_dim, hidden_dim=32, dropout=0.1)
mlp_logits = mlp(x)             # x: floating Tensor[B,N,D]; output: Tensor[B,N]
gat_logits = gat(x, edges)      # same input/output shapes; unnormalized root logits
report = self_check()          # synthetic CPU assertions, not performance results
```

`EadroGATCommonInput.forward(x, edges=None)` requires explicitly supplied edges.
The parent-facing format is a length-B list with each element a
`list[(source, destination)]` (including `[]` for an explicit empty graph).
Also supported: shared integer `Tensor[2,E]` or `(sources, destinations)` tuple,
or a length-B list of those Tensor/tuple specifications. Python lists inside a
case are **E-by-2 pairs**, not two endpoint vectors; Tensor inputs are **2-by-E**.
The outer Python list always means per-case graphs; use a Tensor or tuple for
shared edges. Endpoints are local indices in `0..N-1`, with direction
`source -> destination`. The parent supplies observed call edges and self loops.
The adapter adds, removes, reverses and deduplicates **no edges**. `None` raises
`ValueError`; explicitly empty `(2,0)` edge tensors are allowed, not inferred.
Every DGL graph uses `num_nodes=N`, retaining services with no observed calls.

Input shape, finiteness and integer edge bounds are validated. Models are bound
to N and D; node counts 2 and 5 require separate models, not resizing a trained
model. Hidden width must be at least 2. The unmodified Eadro `squeeze()` cannot
handle a single total node, so the adapter rejects `B*N < 2`. Keep a fixed
service-to-index mapping within each experiment. Move model and input together
using normal PyTorch `.to(device)`; checks here target CPU only.

## DiagMLP: primary paper architecture, not author code

Primary source: [arXiv 2501.02766v2, §III-C/D, Eqs. (2)-(3)](
https://arxiv.org/html/2501.02766v2#S3.SS3).
The equations, rather than a generic MLP or an informal ordering description,
control this reimplementation:

1. Eq. (2): `z_i = x_i^metric ⊕ x_i^log ⊕ x_i^trace ⊕ p_i`.
2. `h_i = Modal_Fusion_MLP(z_i)`.
3. `h_g = h_1 ⊕ ... ⊕ h_N`.
4. `y_g = Node_Fusion_MLP(h_g)`, then the downstream task module.
5. Eq. (3), for **each** fusion: `Dropout(ReLU(LayerNorm(Wx + b)))`.
   §III-D explicitly specifies single-layer fusion and concatenation.

**Position embeddings are concatenated BEFORE modal fusion.** They are not
added to a fused node feature or placed after modal fusion. The supplied task's
informal sequence differed here; its requirement to verify exact paper equations
takes precedence. Both fusion modules have exactly one Linear followed by
LayerNorm, ReLU and Dropout.

Adaptation choices and deviations:

- The parent's common numerical incident feature vector replaces the original
  metric/log/trace preprocessing and embedding outputs. It is treated as the
  already concatenated node feature; no modality encoder is reproduced.
- The paper writes `p_i ∈ R^d`, with each original modality embedding also
  having width d. Common input D has no canonical three-way modality split;
  this adapter chooses position width H (`hidden_dim`), not an inferred D/3.
  Shapes are `Linear(D+H,H)`, position `[N,H]`, `Linear(N*H,H)`.
- `H=32`, dropout `0.1`, standard PyTorch initialization and position embedding
  initialization are local bounded choices, **not claimed paper defaults**.
  The topology-agnostic representation is followed by a local `Linear(H,N)`
  root-service head. Detection/classification tasks and original task heads
  are not reproduced.
- This is explicitly a **paper-architecture common-input reimplementation**,
  not an author implementation, full pipeline replication or reproduction of
  original published scores. Parameter size depends on the fixed node count.

## Eadro: exact vendored author source, separate adapted wrapper

Original file: `codes/model.py` from `BEbillionaireUSD/Eadro`.

- Commit: `82ff9c9a7a58a9cd2b713aa78754a73c543a15db`.
- [Pinned original raw source](
  https://raw.githubusercontent.com/BEbillionaireUSD/Eadro/82ff9c9a7a58a9cd2b713aa78754a73c543a15db/codes/model.py).
- [Pinned repository file](
  https://github.com/BEbillionaireUSD/Eadro/blob/82ff9c9a7a58a9cd2b713aa78754a73c543a15db/codes/model.py).
- Git blob SHA-1: `cdc188dcdcb972e7d6a7b200f549600e10ee7aaa`.
- File SHA-256: `3ac6338c94946658ef735b7bf607568e9347a0f3f56a7a26258e583d6661510c`.
- Size: 10,508 bytes. Vendored at `research/mlp_prerequisites/eadro_model.py`
  **without modifications**, including whitespace and existing defects.

The adapter imports and directly instantiates the author `GraphModel`;
it does not rewrite, subclass, monkeypatch or replace its forward method.
Its two GATv2Conv layers, max-pooling across four attention heads, and
`GlobalAttentionPooling` with a learned linear gate remain author code.

Adaptation choices and deviations:

- Common numerical features go directly into `GraphModel`, replacing original
  temporal metric/trace encoders, log encoder and Linear+GLU multimodal fusion.
  This is **not the original full Eadro model**.
- Graph hidden widths are `[H,H]` (default `[32,32]`), instead of the author
  constructor's `[64,128]`; the author head count 4 and negative slope 0.2
  are retained. `dropout=0.1` maps to author `attn_drop`, whose constructor
  default is 0. No additional feature dropout is introduced.
- A local `Linear(H,N)` root-service head replaces original detection and
  localization heads and joint detection/localization objective. The parent
  supplies the training loss and identical common features for both adapters.
- The parent supplies graph topology; there is no fabricated complete graph,
  chain, reverse edge, automatic self loop, or graph inferred from labels.
- No author dataset preprocessing, training settings or published scores are
  reproduced. The common-input experiment cannot establish full Eadro fidelity.

## Synthetic checks and original MainModel smoke

`self_check()` uses only generated random features and clearly synthetic graphs.
For **both N=2 and N=5**, with the parent's input width D=17 and default H=32,
dropout=0.1, separate instances of both adapters check:

- `(B,N,D) -> (B,N)` finite logits, cross-entropy backward, finite/nonzero input
  gradients and nonzero gradients in each fusion/GAT/pooling/head component.
- B=1 forward; graph batching with different pair lists per case agrees with
  separate inference; shared Tensor and source/destination tuple forms agree.
- Exact supplied edge direction/order, all N nodes including services isolated
  from call edges, and explicitly empty edge graphs without invented topology.
- Rejection of wrong input shapes, missing graphs, per-case length mismatch,
  out-of-range endpoints and floating-point endpoint tensors.
- The explicit DiagMLP concatenation-before-modal-fusion computation.

`original_main_smoke()` separately prepares a synthetic two-case DGL batch:
metrics `[4,8,3]`, logs `[4,4]`, traces `[4,8,1]`, and fault indices `[0,1]`.
It attempts the **unmodified original MainModel** constructor, then would run
its original forward, loss.backward and gradient assertions if construction
succeeded. At this pinned revision construction is blocked by the upstream
undefined `trace_dropout`. The report explicitly returns
`status="blocked_upstream"` and `forward_backward_completed=False`, rather than
silently treating that as a passed full-model smoke.

Further upstream blockers visible in the exact source, not repaired here:
`metric_dropout` is also undefined; both encoder constructors pass unsupported
`dropout=` to `ConvNet`; MainModel constructs `localizer`/`detecter` and their
criteria but forward references `locator`/`detector`, `locator_criterion` and
`decoder_criterion`. Single-case inference also uses an unconstrained squeeze.
These defects do not affect the independently used author GraphModel.

Re-run in the parent-managed environment:

```sh
DGLBACKEND=pytorch OMP_NUM_THREADS=1 .venv-mlp/bin/python -B scripts/mlp_reference.py
```

Only synthetic execution/gradient checks are provided. They are **not trained
performance, ranking accuracy, evidence for real incidents, or published score
reproduction**. No real incident data, installation, split, evaluator or training
loop belongs to these files.

### Execution evidence

The final direct `.venv-mlp` synthetic check exited **0**, with torch
`2.5.1+cpu`, DGL `1.1.3`, NumPy `1.26.4` and packaging `24.2`.
All four adapter/node-count combinations passed forward/backward assertions
using D=17, H=32, dropout=0.1 and the parent's per-case pair-list edge contract.
Pyright with the explicit `.venv-mlp/bin/python` interpreter also exited 0:
**0 errors, 0 warnings, 0 informations** for `scripts/mlp_reference.py`.
The original MainModel attempt reported the upstream `trace_dropout` NameError;
its full metric/log/trace forward/backward **did not complete**.

Initial DGL import failed because `packaging` was undeclared/missing.
An interim synthetic run used the already-installed user-site packaging `25.0`
via a process-local search-path append; no fallback is embedded in the modules.
The parent then installed packaging `24.2`, and the final direct command above
passed **without** the search-path fallback. This worker installed no packages
and accessed no incident data. The exact vendored source retains its upstream
type/name diagnostics; it was not patched to silence them.

## Separate public bug-fix fork: full-model runtime smoke only

`research/mlp_prerequisites/eadro_corrected_model.py` vendors **exactly**
`FeiGSSS/Eadro/codes/model.py` at commit
`7d69281a80adce60067aa858729746fc6a362f53`, without local source edits,
monkeypatches, attribute aliases or invented repairs.

- [Pinned GitHub contents API](
  https://api.github.com/repos/FeiGSSS/Eadro/contents/codes/model.py?ref=7d69281a80adce60067aa858729746fc6a362f53).
- [Pinned fork source](
  https://github.com/FeiGSSS/Eadro/blob/7d69281a80adce60067aa858729746fc6a362f53/codes/model.py).
- API-reported Git blob SHA-1:
  `d0cf0560a4a2ad0f5d9814f7d6118fc6d989bbbc`.
  This value was fetched from the API and independently recomputed from decoded
  source bytes, **not taken from the contradictory hash text in the request**.
- SHA-256:
  `1e6579d4656d0a040ef2cf3e3375a11e75cfd9b90cac2736bfb61998d8d12b0b`.
- Size: 10,435 bytes; original whitespace is preserved.

Differences observed in this pinned public source versus the separately
preserved original: `TraceModel` constructs `ConvNet(2, ...)`, so trace width
is **2** despite its stale width-1 comment; the invalid encoder `dropout=`
arguments and undefined dropout variables are removed; detector/locator and
criterion constructor names now match forward. `GraphModel` is unchanged
between these two files. Remaining source annotation/optional-argument
diagnostics and single-case inference squeeze limitations are not repaired.

New API:

```python
from scripts.mlp_reference import corrected_main_smoke, self_check
corrected_main_smoke()          # full fork MainModel synthetic CPU smoke
self_check()["corrected_main"] # separate result; original_main is retained
```

The smoke supplies two synthetic two-node graphs with explicit computational
self loops and one directed synthetic call each. Metrics `[4,8,3]`, logs
`[4,4]`, and traces `[4,8,2]` pass through the fork's original metric/log/trace
encoders, Linear+GLU fusion, GATv2/pooling, detection and localization heads.
Fault indices `[0,-1]` exercise an anomalous case and a normal case with the
fork's original localization ignore-index and joint loss. It checks finite
scalar loss, finite normalized root probabilities, label probabilities,
backward, nonzero gradients in all three inputs and all encoder/fusion/graph/
head components. Failures propagate; no exception is converted to a pass.

Smoke-only choices/deviations: seed 23, CPU, batch size 2, N=2, window length 8,
all temporal/graph hidden lists `[8,8]`, head hidden lists `[8]`, log width 8,
fusion width 16, default alpha 0.5 and self-attention disabled. These are small
runtime fixtures, **not original published settings, preprocessing replication,
training, ranking performance or score reproduction**. Optional self-attention
and single-case inference are not covered.

The combined direct `.venv-mlp` self-check exited **0**: the fork MainModel
completed full forward/backward with nonzero metric/log/trace input and component
gradients; all four common-input adapter checks still passed; the original
MainModel result remains `blocked_upstream` for undefined `trace_dropout`.

The training adapter still uses the unchanged **original** author GraphModel,
not this fork MainModel. `original_main_smoke()` and exact original source remain
unchanged and retain the explicit upstream blocked result. Parent-supplied
computational self loops for observed nodes are distinct from observed call
edges and are **not inferred causal edges**; this worker did not change topology
construction, extraction, training or any incident data.
