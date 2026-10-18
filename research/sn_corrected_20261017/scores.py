"""Event-only root scoring and fixed-prediction paired cluster bootstrap."""

import numpy as np


def _float_array(values, name):
    array = np.asarray(values)
    if array.dtype.kind not in "iuf":
        raise ValueError("{} must contain real numbers".format(name))
    array = array.astype(np.float64)
    if not np.all(np.isfinite(array)):
        raise ValueError("{} must be finite".format(name))
    return array


def event_metrics(root_logits, labels, event_ids):
    """Pool window probabilities, giving every fault event equal weight.

    Inputs have shapes (windows, candidates), (windows,), and (windows,).
    Labels must have an integer dtype: -1 denotes normal; other labels are
    candidate indices. Event IDs are nonempty strings for faults and "" for
    normals. All windows of an event must agree on the root. Normal windows
    never enter a root score; there is no detector gate.

    Rankings use uncapped, unrounded float64 log probabilities. Exact ties
    receive their expected credit under a uniform ordering of tied candidates.
    """
    logits = _float_array(root_logits, "root_logits")
    if logits.ndim != 2 or not all(logits.shape):
        raise ValueError("root_logits must have nonempty shape (windows, candidates)")
    rows, candidates = logits.shape
    roots = np.asarray(labels)
    ids = np.asarray(event_ids, dtype=object)
    if roots.shape != (rows,) or ids.shape != (rows,):
        raise ValueError("labels and event_ids must each have shape (windows,)")
    if roots.dtype.kind not in "iu":
        raise ValueError("labels must have an integer dtype")
    if np.any(roots < -1) or np.any(roots >= candidates):
        raise ValueError("labels must be -1 or a valid candidate index")

    groups = {}
    for index, (root, event_id) in enumerate(zip(roots, ids)):
        if not isinstance(event_id, str):
            raise ValueError("event_ids must be strings")
        if root == -1:
            if event_id != "":
                raise ValueError("normal windows must have empty event IDs")
            continue
        if not event_id.strip():
            raise ValueError("fault windows must have nonempty event IDs")
        if event_id not in groups:
            groups[event_id] = (int(root), [])
        event_root, indices = groups[event_id]
        if event_root != root:
            raise ValueError("inconsistent roots for event {!r}".format(event_id))
        indices.append(index)
    if not groups:
        raise ValueError("no fault events")

    shifted = logits - np.max(logits, axis=1, keepdims=True)
    log_probabilities = shifted - np.logaddexp.reduce(
        shifted, axis=1, keepdims=True
    )
    events = []
    losses = []
    for event_id in sorted(groups):
        root, indices = groups[event_id]
        pooled = (
            np.logaddexp.reduce(log_probabilities[indices], axis=0)
            - np.log(float(len(indices)))
        )
        truth = pooled[root]
        greater = int(np.count_nonzero(pooled > truth))
        ties = int(np.count_nonzero(pooled == truth))
        events.append(
            {
                "event_id": event_id,
                "root": root,
                "windows": len(indices),
                "log_probabilities": pooled.tolist(),
                "top1": float(min(max(1 - greater, 0), ties) / ties),
                "top3": float(min(max(3 - greater, 0), ties) / ties),
            }
        )
        losses.append(-float(truth))
    return {
        "event_nll": float(np.mean(losses)),
        "top1": float(np.mean([event["top1"] for event in events])),
        "top3": float(np.mean([event["top3"] for event in events])),
        "events": events,
    }


def paired_cluster_bootstrap(
    event_differences, event_recordings, samples=5000, seed=20261017
):
    """Return {"lower", "upper"} for the 2.5/97.5 percentiles of paired means.

    Each difference is an already paired, fixed per-event score difference.
    Draw as many recording clusters as observed, with replacement, retaining
    every event in each selected cluster (including repeated clusters). The
    statistic is the event-weighted mean, not the mean of cluster means.
    Recording IDs may be nonempty strings or integers.

    No fitting or retraining occurs. With the protocol's four recording
    clusters, this is an exploratory range conditional on fixed predictions,
    shared training, and the observed environment, not evidence of significance
    for an independent operational population.
    """
    differences = _float_array(event_differences, "event_differences")
    recordings = np.asarray(event_recordings, dtype=object)
    if differences.ndim != 1 or differences.size == 0:
        raise ValueError("event_differences must be a nonempty vector")
    if recordings.shape != differences.shape:
        raise ValueError("event_recordings must match event_differences exactly")
    if isinstance(samples, (bool, np.bool_)) or not isinstance(
        samples, (int, np.integer)
    ) or samples <= 0:
        raise ValueError("samples must be a positive integer")
    if isinstance(seed, (bool, np.bool_)) or not isinstance(
        seed, (int, np.integer)
    ) or seed < 0:
        raise ValueError("seed must be a nonnegative integer")

    clusters = {}
    for difference, recording in zip(differences, recordings):
        if (
            isinstance(recording, (bool, np.bool_))
            or not isinstance(recording, (str, int, np.integer))
            or (isinstance(recording, str) and not recording.strip())
        ):
            raise ValueError("recording IDs must be nonempty strings or integers")
        clusters.setdefault(recording, []).append(difference)
    # Canonical cluster order makes a seeded result independent of input order.
    keys = sorted(clusters, key=lambda key: (type(key).__name__, str(key)))
    sums = np.array([np.sum(clusters[key]) for key in keys], dtype=np.float64)
    counts = np.array([len(clusters[key]) for key in keys], dtype=np.int64)
    rng = np.random.default_rng(seed)
    means = np.empty(samples, dtype=np.float64)
    for index in range(samples):
        selected = rng.integers(len(keys), size=len(keys))
        means[index] = np.sum(sums[selected]) / np.sum(counts[selected])
    lower, upper = np.percentile(means, [2.5, 97.5])
    return {"lower": float(lower), "upper": float(upper)}
