"""Native modality encoders and joint heads; explicitly declared DiagMLP wiring."""
import hashlib
import importlib.util
from pathlib import Path

import dgl
import numpy as np
import torch
from torch import nn

BASE = Path(__file__).resolve().parents[2]
SOURCE = BASE / "research/mlp_prerequisites/eadro_corrected_model.py"
SOURCE_BLOB = "d0cf0560a4a2ad0f5d9814f7d6118fc6d989bbbc"


def load_reference():
    raw = SOURCE.read_bytes()
    assert hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == SOURCE_BLOB
    spec = importlib.util.spec_from_file_location("native_eadro_public_fork", SOURCE)
    if spec is None or spec.loader is None:
        raise ImportError(str(SOURCE))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REFERENCE = load_reference()


class EquationDiagEncoder(nn.Module):
    """Eq.(2)-(3) before GLU: preserve the three author modality encoders."""

    def __init__(self, original, node_count, output_dim=64, hidden=64, position_dim=64, dropout=.1):
        super().__init__()
        self.node_count = node_count
        self.metric_model = original.metric_model
        self.trace_model = original.trace_model
        self.log_model = original.log_model
        input_dim = (self.metric_model.out_dim + self.trace_model.out_dim
                     + self.log_model.embedder.out_features)
        self.position = nn.Embedding(node_count, position_dim)
        self.modal = nn.Sequential(nn.Linear(input_dim + position_dim, hidden),
                                   nn.LayerNorm(hidden), nn.ReLU(), nn.Dropout(dropout))
        self.node = nn.Sequential(nn.Linear(node_count * hidden, output_dim),
                                  nn.LayerNorm(output_dim), nn.ReLU(), nn.Dropout(dropout))
        self.feat_out_dim = output_dim

    def forward(self, graph):
        batch = graph.batch_size
        values = torch.cat((self.metric_model(graph.ndata["metrics"]),
                            self.log_model(graph.ndata["logs"]),
                            self.trace_model(graph.ndata["traces"])), dim=-1)
        values = values.reshape(batch, self.node_count, -1)
        position = self.position.weight.unsqueeze(0).expand(batch, -1, -1)
        return self.node(self.modal(torch.cat((values, position), -1)).reshape(batch, -1))


class NativeReference(nn.Module):
    def __init__(self, kind, node_count, event_count, metric_count=7, length=10, dropout=None):
        super().__init__()
        if kind not in ("eadro", "diagmlp"):
            raise ValueError("Unknown native model kind")
        if min(node_count, event_count, metric_count, length) < 2:
            raise ValueError("Native profile needs at least two nodes/events/features/time steps")
        if dropout is None:
            dropout = 0.0 if kind == "eadro" else 0.1
        self.kind, self.node_count, self.length = kind, node_count, length
        self.event_count, self.metric_count = event_count, metric_count
        self.config = {"kind": kind, "node_count": node_count, "event_count": event_count,
                       "metric_count": metric_count, "length": length, "dropout": dropout,
                       "alpha": .5, "modality_widths": [64, 16, 64],
                       "graph_or_node_output": 64, "diag_position_width": 64,
                       "diag_modal_width": 64}
        self.core = REFERENCE.MainModel(
            event_num=event_count, metric_num=metric_count, node_num=node_count, device="cpu",
            alpha=.5, self_attn=True, chunk_lenth=length,
            log_dim=16, fuse_dim=128,
            metric_hiddens=[64], metric_kernel_sizes=[2],
            trace_hiddens=[64], trace_kernel_sizes=[2],
            graph_hiddens=[64], attn_head=4, attn_drop=dropout,
            detect_hiddens=[64], locate_hiddens=[64],
        )
        if kind == "diagmlp":
            self.core.encoder = EquationDiagEncoder(
                self.core.encoder, node_count, output_dim=64,
                hidden=64, position_dim=64, dropout=dropout)

    def forward(self, graph):
        batch = graph.batch_size
        if batch < 1 or not torch.all(graph.batch_num_nodes() == self.node_count):
            raise ValueError("Graph batch does not match the fixed node inventory")
        shapes = {
            "metrics": (batch * self.node_count, self.length, self.metric_count),
            "traces": (batch * self.node_count, self.length, 2),
            "logs": (batch * self.node_count, self.event_count),
        }
        for key, expected in shapes.items():
            value = graph.ndata[key]
            if tuple(value.shape) != expected or not torch.isfinite(value).all():
                raise ValueError("Invalid native input: " + key)
        embedding = self.core.encoder(graph)
        return self.core.locator(embedding), self.core.detector(embedding)


def joint_loss(root_logits, detection_logits, labels, alpha=.5):
    if labels.ndim != 1 or labels.shape[0] != root_logits.shape[0]:
        raise ValueError("Invalid label shape")
    if labels.dtype != torch.long or ((labels < -1) | (labels >= root_logits.shape[1])).any():
        raise ValueError("Root labels outside fixed inventory")
    if not torch.isfinite(root_logits).all() or not torch.isfinite(detection_logits).all():
        raise ValueError("Non-finite native logits")
    faulty = labels >= 0
    detection = nn.functional.cross_entropy(detection_logits, faulty.long())
    # With no root labels, the intended ignored-label term is zero, not mean(0/0).
    localization = (nn.functional.cross_entropy(root_logits[faulty], labels[faulty])
                    if faulty.any() else root_logits.sum() * 0)
    return alpha * detection + (1 - alpha) * localization


def native_scores(root_logits, detection_logits, labels):
    roots = root_logits.detach().cpu().numpy()
    detected = detection_logits.detach().argmax(dim=1).cpu().numpy().astype(bool)
    truth = labels.detach().cpu().numpy()
    faulty = truth >= 0
    tp, fp, fn = int(np.sum(detected & faulty)), int(np.sum(detected & ~faulty)), int(np.sum(~detected & faulty))
    scores = {"windows": len(truth), "fault_windows": int(faulty.sum()),
              "tp": tp, "fp": fp, "fn": fn, "tn": int(np.sum(~detected & ~faulty)),
              "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0}
    if not faulty.any():
        scores.update({"conditional_top1": None, "end_to_end_top1": None})
        return scores
    conditional, gated = [], []
    for i in np.flatnonzero(faulty):
        row = roots[i]
        greater = int(np.sum(row > row[truth[i]]))
        ties = int(np.sum(row == row[truth[i]]))
        expected_hit = 1.0 / ties if greater == 0 else 0.0
        conditional.append(expected_hit)
        gated.append(expected_hit * detected[i])
    scores["conditional_top1"] = float(np.mean(conditional))
    scores["end_to_end_top1"] = float(np.mean(gated))
    return scores


def synthetic_graph(node_count=2, batch=2, length=10, events=5):
    graph = dgl.batch([dgl.graph((list(range(node_count)), list(range(node_count))),
                                 num_nodes=node_count) for _ in range(batch)])
    graph.ndata["metrics"] = torch.randn(batch * node_count, length, 7)
    graph.ndata["traces"] = torch.randn(batch * node_count, length, 2)
    graph.ndata["logs"] = torch.rand(batch * node_count, events)
    return graph


def self_check():
    from importlib.metadata import version
    from tick.hawkes import HawkesADM4
    torch.set_num_threads(2)
    torch.manual_seed(31)
    graph = synthetic_graph()
    labels = torch.tensor([0, -1])
    baseline = NativeReference("eadro", 2, 5)
    baseline.eval()
    original = baseline.core(graph, labels)
    roots, detects = baseline(graph)
    torch.testing.assert_close(joint_loss(roots, detects, labels), original["loss"])
    np.testing.assert_allclose(torch.softmax(roots, -1).detach().numpy(),
                               original["pred_prob"], atol=1e-7)
    for kind in ("eadro", "diagmlp"):
        model = NativeReference(kind, 2, 5)
        model.train()
        roots, detects = model(graph)
        assert roots.shape == (2, 2) and detects.shape == (2, 2)
        joint_loss(roots, detects, labels).backward()
        gradients = [p.grad for p in model.parameters() if p.grad is not None]
        assert gradients and all(torch.isfinite(g).all() for g in gradients)
        assert sum(g.abs().sum().item() for g in gradients) > 0
        assert torch.isfinite(joint_loss(roots, detects, torch.tensor([-1, -1])))
        model.eval()
        single = model(synthetic_graph(batch=1))
        assert single[0].shape == (1, 2)
    perfect = native_scores(torch.tensor([[3., 0.], [0., 0.]]),
                            torch.tensor([[0., 3.], [3., 0.]]), labels)
    assert perfect["conditional_top1"] == perfect["end_to_end_top1"] == perfect["f1"] == 1
    assert perfect["fault_windows"] == 1 and perfect["tn"] == 1
    knots = [np.array([0., 1., 3.]), np.array([0., 2., 4.])]
    hawkes = HawkesADM4(3)
    hawkes.fit(knots, 10., baseline_start=np.ones(2) * .2)
    fitted_baseline = getattr(hawkes, "baseline", None)
    assert isinstance(fitted_baseline, np.ndarray)
    assert fitted_baseline.shape == (2,) and np.isfinite(fitted_baseline).all()
    report = {"status": "passed_synthetic_only", "source_blob": SOURCE_BLOB,
              "checks": ["native_mixed_loss_equivalence", "root_prob_equivalence",
                         "both_full_encoders_backward", "normal_only_loss_finite",
                         "single_window_forward", "normal_excluded_from_root_denominator",
                         "author_pinned_hawkes_fit"],
              "versions": {name: version(name) for name in
                           ("tick", "torch", "dgl", "numpy", "pandas", "scikit-learn", "drain3")},
              "hawkes_baseline_fixture": fitted_baseline.tolist()}
    return report


if __name__ == "__main__":
    import json
    print("NATIVE_SELF_CHECK", json.dumps(self_check()), flush=True)
