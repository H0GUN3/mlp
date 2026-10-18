"""Bounded common-input references, not author-model score reproductions."""
from functools import lru_cache
import importlib.util
from pathlib import Path

import torch
from torch import nn


def _validate_dimensions(node_count, input_dim, hidden_dim, dropout):
    if any(type(size) is not int or size < 1 for size in (node_count, input_dim, hidden_dim)):
        raise ValueError("node_count, input_dim and hidden_dim must be positive integers")
    if hidden_dim < 2:
        raise ValueError("hidden_dim must be at least 2 (LayerNorm and author squeeze)")
    if not 0 <= dropout < 1:
        raise ValueError("dropout must be in [0, 1)")


def _validate_input(x, node_count, input_dim):
    if x.ndim != 3 or x.shape[0] < 1 or tuple(x.shape[1:]) != (node_count, input_dim):
        raise ValueError(f"expected nonempty (B, {node_count}, {input_dim}) input")
    if not x.is_floating_point() or not torch.isfinite(x).all():
        raise ValueError("input must contain finite floating-point features")


@lru_cache(maxsize=1)
def _eadro_module():
    path = Path(__file__).resolve().parents[1] / "research/mlp_prerequisites/eadro_model.py"
    spec = importlib.util.spec_from_file_location("eadro_original_reference", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load Eadro source: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DiagMLPCommonInput(nn.Module):
    """Paper §III-C Eqs. (2)-(3), with numerical inputs and a root-service head."""

    def __init__(self, node_count, input_dim, hidden_dim=32, dropout=0.1):
        super().__init__()
        _validate_dimensions(node_count, input_dim, hidden_dim, dropout)
        self.node_count, self.input_dim = node_count, input_dim
        self.position = nn.Embedding(node_count, hidden_dim)
        self.modal_fusion = nn.Sequential(
            nn.Linear(input_dim + hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim), nn.ReLU(), nn.Dropout(dropout),
        )
        self.node_fusion = nn.Sequential(
            nn.Linear(node_count * hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim), nn.ReLU(), nn.Dropout(dropout),
        )
        self.root_head = nn.Linear(hidden_dim, node_count)

    def forward(self, x):
        _validate_input(x, self.node_count, self.input_dim)
        # Eq. (2) concatenates position BEFORE modal fusion, not after it.
        position = self.position.weight.unsqueeze(0).expand(x.shape[0], -1, -1)
        nodes = self.modal_fusion(torch.cat((x, position), dim=-1))
        return self.root_head(self.node_fusion(nodes.flatten(start_dim=1)))


class EadroGATCommonInput(nn.Module):
    """Unmodified author GraphModel on common features, plus a root-service head.

    edges: length-B list of lists of (source, destination) pairs; alternatively
    shared integer Tensor[2,E], (sources, destinations), or per-case lists of
    those Tensor/tuple forms. Node IDs are local 0..N-1.
    The caller supplies observed directed calls and any self loops. None is an
    error; explicitly empty edges are allowed. No edges are added or reversed.
    """

    def __init__(self, node_count, input_dim, hidden_dim=32, dropout=0.1):
        super().__init__()
        _validate_dimensions(node_count, input_dim, hidden_dim, dropout)
        self.node_count, self.input_dim = node_count, input_dim
        self.graph_model = _eadro_module().GraphModel(
            in_dim=input_dim, graph_hiddens=[hidden_dim, hidden_dim],
            attn_head=4, attn_drop=dropout,
        )
        self.root_head = nn.Linear(hidden_dim, node_count)

    def _batch_graph(self, x, edges):
        import dgl

        if edges is None:
            raise ValueError("explicit observed edges are required; topology is never inferred")
        per_case = edges if isinstance(edges, list) else [edges] * x.shape[0]
        if len(per_case) != x.shape[0]:
            raise ValueError("per-case edges must have length B")
        graphs = []
        for case_edges in per_case:
            if isinstance(case_edges, list):
                if not case_edges:
                    edge_index = torch.empty((2, 0), dtype=torch.long, device=x.device)
                else:
                    pairs = torch.as_tensor(case_edges, device=x.device)
                    if pairs.ndim != 2 or pairs.shape[1] != 2:
                        raise ValueError("list edges must contain (source, destination) pairs")
                    edge_index = pairs.t()
            elif isinstance(case_edges, tuple) and len(case_edges) == 2:
                endpoints = [torch.as_tensor(row, device=x.device) for row in case_edges]
                if any(row.ndim != 1 for row in endpoints) or endpoints[0].shape != endpoints[1].shape:
                    raise ValueError("sources and destinations must be equal-length vectors")
                edge_index = torch.stack(endpoints)
            else:
                edge_index = torch.as_tensor(case_edges, device=x.device)
            if edge_index.ndim != 2 or edge_index.shape[0] != 2:
                raise ValueError("each edge specification must have shape (2, E)")
            if edge_index.numel() and edge_index.dtype not in (torch.int32, torch.int64):
                raise ValueError("edge endpoints must be integer node IDs")
            if edge_index.numel() and (
                (edge_index < 0).any() or (edge_index >= self.node_count).any()
            ):
                raise ValueError("edge endpoint outside 0..N-1")
            edge_index = edge_index.long()
            graphs.append(dgl.graph(
                (edge_index[0], edge_index[1]),
                num_nodes=self.node_count, device=x.device,
            ))
        return dgl.batch(graphs)

    def forward(self, x, edges=None):
        _validate_input(x, self.node_count, self.input_dim)
        if x.shape[0] * self.node_count < 2:
            raise ValueError("author GraphModel.squeeze requires at least two total nodes")
        graph = self._batch_graph(x, edges)
        embedding = self.graph_model(graph, x.reshape(-1, self.input_dim))
        return self.root_head(embedding)


def _assert_gradients(module):
    gradients = [p.grad for p in module.parameters() if p.grad is not None]
    assert gradients and all(torch.isfinite(g).all() for g in gradients)
    assert sum(g.abs().sum().item() for g in gradients) > 0


def original_main_smoke():
    """Attempt full author metric/log/trace forward+backward, reporting blockers."""
    import dgl

    graph = dgl.batch([
        dgl.graph(([0, 1, 0], [0, 1, 1]), num_nodes=2),
        dgl.graph(([0, 1, 1], [0, 1, 0]), num_nodes=2),
    ])
    graph.ndata["metrics"] = torch.randn(4, 8, 3)
    graph.ndata["logs"] = torch.randn(4, 4)
    graph.ndata["traces"] = torch.randn(4, 8, 1)
    try:
        model = _eadro_module().MainModel(
            event_num=4, metric_num=3, node_num=2, device="cpu",
            trace_hiddens=[8, 8], metric_hiddens=[8, 8],
            graph_hiddens=[8, 8], detect_hiddens=[8], locate_hiddens=[8],
        )
    except NameError as error:
        if "trace_dropout" not in str(error):
            raise
        return {
            "status": "blocked_upstream", "error": f"{type(error).__name__}: {error}",
            "forward_backward_completed": False,
        }
    result = model(graph, torch.tensor([0, 1]))
    assert torch.isfinite(result["loss"])
    result["loss"].backward()
    _assert_gradients(model)
    return {"status": "passed", "forward_backward_completed": True}


def corrected_main_smoke():
    """Full synthetic forward/backward through the exact public bug-fix fork."""
    import dgl

    path = Path(__file__).resolve().parents[1] / "research/mlp_prerequisites/eadro_corrected_model.py"
    spec = importlib.util.spec_from_file_location("eadro_corrected_reference", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load corrected Eadro source: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(23)
        graph = dgl.batch([
            dgl.graph(([0, 1, 0], [0, 1, 1]), num_nodes=2),
            dgl.graph(([0, 1, 1], [0, 1, 0]), num_nodes=2),
        ])
        inputs = {
            "metrics": torch.randn(4, 8, 3, requires_grad=True),
            "logs": torch.randn(4, 4, requires_grad=True),
            "traces": torch.randn(4, 8, 2, requires_grad=True),
        }
        for name, features in inputs.items():
            graph.ndata[name] = features
        model = module.MainModel(
            event_num=4, metric_num=3, node_num=2, device="cpu",
            trace_hiddens=[8, 8], metric_hiddens=[8, 8],
            graph_hiddens=[8, 8], detect_hiddens=[8], locate_hiddens=[8],
            log_dim=8, fuse_dim=16,
        )
        result = model(graph, torch.tensor([0, -1]))
        assert result["loss"].ndim == 0 and torch.isfinite(result["loss"])
        probabilities = torch.from_numpy(result["pred_prob"])
        assert probabilities.shape == (2, 2) and torch.isfinite(probabilities).all()
        torch.testing.assert_close(probabilities.sum(-1), torch.ones(2))
        torch.testing.assert_close(torch.from_numpy(result["y_prob"]),
                                   torch.tensor([[1., 0.], [0., 0.]]))
        assert len(result["y_pred"]) == 2
        result["loss"].backward()
        for component in (
            model.encoder.metric_model, model.encoder.log_model,
            model.encoder.trace_model, model.encoder.fuse,
            model.encoder.status_model, model.detector, model.locator,
        ):
            _assert_gradients(component)
        for features in inputs.values():
            assert features.grad is not None and torch.isfinite(features.grad).all()
            assert features.grad.abs().sum() > 0
    return {
        "status": "passed", "forward_backward_completed": True,
        "input_gradients": "metrics_logs_traces_nonzero",
        "component_gradients": "passed",
    }


def self_check():
    """Synthetic CPU checks only; return no incident-performance measurements."""
    def rejects(call):
        try:
            call()
        except ValueError:
            return
        raise AssertionError("invalid input was accepted")

    report = {"scope": "synthetic_only", "adapted": []}
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(17)
        input_dim = 17
        for node_count in (2, 5):
            loops = torch.arange(node_count)
            first = torch.stack((torch.cat((loops, torch.tensor([0]))),
                                 torch.cat((loops, torch.tensor([1])))))
            second = torch.stack((torch.cat((loops, torch.tensor([1]))),
                                  torch.cat((loops, torch.tensor([0])))))
            for model_type in (DiagMLPCommonInput, EadroGATCommonInput):
                model = model_type(node_count, input_dim)
                x = torch.randn(2, node_count, input_dim, requires_grad=True)
                is_graph = isinstance(model, EadroGATCommonInput)
                edges = [list(zip(first[0].tolist(), first[1].tolist())),
                         list(zip(second[0].tolist(), second[1].tolist()))]
                logits = model(x, edges=edges) if is_graph else model(x)
                assert logits.shape == (2, node_count) and torch.isfinite(logits).all()
                nn.functional.cross_entropy(logits, torch.tensor([0, 1])).backward()
                _assert_gradients(model.root_head)
                if is_graph:
                    for layer in model.graph_model.net:
                        _assert_gradients(layer)
                    _assert_gradients(model.graph_model.pooling)
                    graph = model._batch_graph(x, edges)
                    assert graph.batch_num_nodes().tolist() == [node_count, node_count]
                    src, dst = graph.edges()
                    torch.testing.assert_close(src, torch.cat((first[0], second[0] + node_count)))
                    torch.testing.assert_close(dst, torch.cat((first[1], second[1] + node_count)))
                else:
                    for component in (model.position, model.modal_fusion, model.node_fusion):
                        _assert_gradients(component)
                assert x.grad is not None and torch.isfinite(x.grad).all()
                assert x.grad.abs().sum() > 0
                model.eval()
                with torch.no_grad():
                    if is_graph:
                        batched = model(x, edges)
                        separate = torch.cat([model(x[i:i+1], edges=[edges[i]]) for i in range(2)])
                        torch.testing.assert_close(batched, separate)
                        torch.testing.assert_close(model(x, first), model(x, [first, first]))
                        torch.testing.assert_close(
                            model(x, (first[0].tolist(), first[1].tolist())),
                            model(x, first),
                        )
                        torch.testing.assert_close(model(x, (first[0], first[1])), model(x, first))
                        empty = torch.empty((2, 0), dtype=torch.long)
                        empty_graph = model._batch_graph(x, [empty, empty])
                        assert empty_graph.num_nodes() == 2 * node_count
                        assert empty_graph.num_edges() == 0
                        assert torch.isfinite(model(x, [empty, empty])).all()
                        torch.testing.assert_close(model(x, [[], []]), model(x, [empty, empty]))
                        observed_only = [[(0, 1)], [(1, 0)]]
                        assert model._batch_graph(x, observed_only).num_edges() == 2
                        assert torch.isfinite(model(x, edges=observed_only)).all()
                        rejects(lambda: model(x))
                        rejects(lambda: model(x, [first]))
                        rejects(lambda: model(x, torch.tensor([[0], [node_count]])))
                        rejects(lambda: model(x, torch.tensor([[-1], [0]])))
                        rejects(lambda: model(x, first.float()))
                        rejects(lambda: model(x, first.flatten()))
                        rejects(lambda: model(x, ([0, 1], [0])))
                    else:
                        position = model.position.weight.unsqueeze(0).expand(2, -1, -1)
                        expected = model.root_head(model.node_fusion(
                            model.modal_fusion(torch.cat((x, position), -1)).flatten(1)
                        ))
                        torch.testing.assert_close(model(x), expected)
                        assert model(x[:1]).shape == (1, node_count)
                rejects(lambda: model(torch.randn(2, node_count + 1, input_dim)))
                rejects(lambda: model(torch.full((2, node_count, input_dim), float("nan"))))
                rejects(lambda: model_type(node_count, input_dim, dropout=1.0))
                report["adapted"].append({"model": model_type.__name__, "nodes": node_count,
                                          "forward_backward": "passed"})
        report["original_main"] = original_main_smoke()
        report["corrected_main"] = corrected_main_smoke()
    return report


if __name__ == "__main__":
    import json

    print(json.dumps(self_check(), indent=2))
