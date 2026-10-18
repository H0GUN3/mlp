"""Audit pinned Eadro evaluation semantics; not a model-performance experiment."""

import ast
import hashlib
import json
import logging
from contextlib import nullcontext
from types import SimpleNamespace
from urllib.request import urlopen


COMMIT = "82ff9c9a7a58a9cd2b713aa78754a73c543a15db"
ROOT = f"https://raw.githubusercontent.com/BEbillionaireUSD/Eadro/{COMMIT}/codes"
SOURCES = {
    "base.py": "d23cd5b8bc346e66a8bc267192477519ed20c47e",
    "preprocess/align.py": "03f17cd0e3dd523eadc7ab9bf8db1a9998ac5d39",
}


def source_tree(path):
    with urlopen(f"{ROOT}/{path}", timeout=30) as response:
        raw = response.read(64_001)
    assert len(raw) <= 64_000, "Unexpected source size"
    git_blob = b"blob " + str(len(raw)).encode() + b"\0" + raw
    assert hashlib.sha1(git_blob).hexdigest() == SOURCES[path], "Source drift"
    return ast.parse(raw.decode(), filename=path)


def function(tree, name):
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    assert len(matches) == 1, f"Ambiguous function: {name}"
    return matches[0]


def scalar(value):
    return SimpleNamespace(item=lambda: value)


def perfect_ndcg(truth, scores, k):
    # The fixture has a unique correct first item; no sklearn behavior is tested.
    assert truth == [[1, 0, 0, 0, 0]]
    assert scores == [[1, 0, 0, 0, 0]]
    assert 1 <= k <= 5
    return 1.0


def evaluate_fixture(evaluate, labels):
    predictions = [[-1] if label == -1 else list(range(5)) for label in labels]
    result = {
        "y_pred": predictions,
        "y_prob": [[1, 0, 0, 0, 0] for _ in labels],
        "pred_prob": [[1, 0, 0, 0, 0] for _ in labels],
        "loss": scalar(0.0),
    }
    model = SimpleNamespace(eval=lambda: None, forward=lambda *_: result)
    subject = SimpleNamespace(model=model, device="cpu")
    graph = SimpleNamespace(to=lambda _: None)
    loader = [(graph, [scalar(label) for label in labels])]
    return evaluate(subject, loader)["HR@1"]


def main():
    base = source_tree("base.py")
    align = source_tree("preprocess/align.py")

    # Execute only the inspected evaluator with in-memory model/tensor fixtures.
    namespace = {
        "np": SimpleNamespace(zeros=lambda size: [0.0] * size),
        "torch": SimpleNamespace(no_grad=nullcontext),
        "ndcg_score": perfect_ndcg,
        "logging": logging,
    }
    evaluate_ast = ast.Module(body=[function(base, "evaluate")], type_ignores=[])
    exec(compile(evaluate_ast, "pinned_eadro_evaluate", "exec"), namespace)
    fault_only = evaluate_fixture(namespace["evaluate"], [0])
    mixed = evaluate_fixture(namespace["evaluate"], [0, -1])
    assert fault_only == 1.0
    assert mixed == 0.5

    fit = function(base, "fit")
    calls_test_loader = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "evaluate"
        and node.args
        and isinstance(node.args[0], ast.Name)
        and node.args[0].id == "test_loader"
        for node in ast.walk(fit)
    )
    selects_test_score = any(
        isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Subscript)
        and ast.unparse(node.test.left) == "test_results['HR@1']"
        and any(
            isinstance(child, ast.Name) and child.id == "best_state"
            for statement in node.body
            for child in ast.walk(statement)
        )
        for node in ast.walk(fit)
    )
    assert calls_test_loader and selects_test_score

    intervals = function(align, "get_basic")
    ranges = [
        node
        for node in ast.walk(intervals)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "range"
    ]
    assert len(ranges) == 1 and len(ranges[0].args) == 2
    assert ast.unparse(ranges[0]) == "range(start, end - chunk_lenth + 1)"
    split = function(align, "split_chunks")
    assert any(
        isinstance(node, ast.Call)
        and ast.unparse(node) == "np.random.shuffle(chunk_idx)"
        for node in ast.walk(split)
    )
    adjacent_overlap = len(set(range(0, 10)) & set(range(1, 11)))
    assert adjacent_overlap == 9

    print("PASS pinned-source protocol checks; baseline readiness remains NO-GO")
    print(json.dumps({
        "commit": COMMIT,
        "scope": "synthetic evaluator fixture and static source checks only",
        "fault_only_perfect_hr1": fault_only,
        "add_correct_normal_window_hr1": mixed,
        "test_loader_drives_checkpoint_selection": calls_test_loader and selects_test_score,
        "unit_stride_windows_then_random_chunk_split": True,
        "adjacent_ten_step_window_overlap": adjacent_overlap,
        "trained_models": 0,
        "real_incidents_read": 0,
    }, indent=2))


if __name__ == "__main__":
    main()
