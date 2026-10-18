"""Inspect two approved validation windows for caller/callee provenance only."""
import hashlib
import importlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / "research/native_reproduction_20261013"
sys.path.insert(0, str(NATIVE))
json_array = importlib.import_module("native_data_profile").json_array


def inspect():
    meta = json.loads((NATIVE / "native_inputs/SN/metadata.json").read_text())
    split = json.loads((NATIVE / "calibration200/SN/diagmlp/seed_11/split.json").read_text())
    windows = {i: meta["windows"][i] for i in (112, 115)}
    assert set(windows) <= set(split["indices"]["validation"])
    run = windows[112]["run_id"]
    assert windows[115]["run_id"] == run
    relative = "data/" + run + "/spans.json"
    path = ROOT / "data/eadro_native/SN_Dataset/SN Dataset" / relative
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    assert digest.hexdigest() == meta["input_sha256"][relative]
    cases = {}
    with path.open("rb") as stream:
        for trace in json_array(stream, hashlib.sha256()):
            for span in trace["spans"]:
                stamp = span["startTime"] // 1000000 + 28800
                index = next((i for i, w in windows.items()
                              if w["start"] <= stamp < w["start"] + 10), None)
                if index is None or index in cases or span["operationName"] != "compose_media_client":
                    continue
                process = trace["processes"][span["processID"]]
                assert process["serviceName"] == "compose-post-service"
                children = []
                for child in trace["spans"]:
                    child_stamp = child["startTime"] // 1000000 + 28800
                    if not windows[index]["start"] <= child_stamp < windows[index]["start"] + 10:
                        continue
                    if any(ref.get("spanID") == span["spanID"] and
                           ref.get("traceID") == span["traceID"]
                           for ref in child.get("references", [])):
                        children.append({
                            "recording_service": trace["processes"][child["processID"]]["serviceName"],
                            "span": child,
                        })
                cases[index] = {
                    "original_index": index, "aligned_window": windows[index],
                    "recording_process": process, "client_span": span,
                    "same_window_direct_children": children,
                }
            if len(cases) == 2:
                break
    assert set(cases) == {112, 115}
    return {
        "source": str(path), "source_sha256": digest.hexdigest(),
        "scope": "Two allowed windows; structural JSON/timestamp routing traverses shared raw source.",
        "semantics": "Client duration is caller-observed elapsed time, not callee internal CPU/service time.",
        "cases": [cases[i] for i in (112, 115)],
    }


if __name__ == "__main__":
    print("ATTRIBUTION_JSON=" + json.dumps(inspect(), sort_keys=True), flush=True)
