"""Bounded TRAIN-only parser0.4 port; not literal preprocessing or a model result."""
import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.metadata
import inspect
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict

OUT = Path(__file__).resolve().parent
BASE = OUT.parents[1]
ROOT = OUT / "parser04"
INPUTS = OUT / "rca_audit_inputs"
CONFIG = OUT / "native_inputs/drain3.ini"
SPLIT = "1644bb875d061884b8dff37203b07761bd5f11ae3f3e9ed7f8f44687eb3142e5"
THREADS = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")
READS: Counter = Counter()
DENIED: Counter = Counter()
SOURCES = ("parser_transfer.py", "parser_transfer_tests.py", "native_data.py",
           "native_data_profile.py", "rca_native_cost.py", "rca_native_cost.json",
           "rca_schema_audit.json")
OUTPUT_NAMES = {"miner.bin", "metadata.json", "report.md", "report.json", "report.json.partial"}


def guard(event, args):
    if event != "open" or isinstance(args[0], int):
        return
    path = Path(os.fsdecode(args[0])).resolve()
    mode, flags = args[1:3]
    writing = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
        isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)))
    output = path.parent.parent == ROOT and path.parent.name in ("OB", "TT", "selfcheck")
    allowed = output and path.name in OUTPUT_NAMES
    if path == Path(os.devnull):
        return  # Nonpersistent dill import probe.
    if writing:
        permitted = allowed
    elif BASE / "data" == path or BASE / "data" in path.parents:
        permitted = False
    elif OUT in path.parents:
        permitted = allowed or path == CONFIG or path in {OUT / s for s in SOURCES}
        permitted |= path.parent == OUT / "__pycache__" and any(
            path.name.startswith(s[:-3] + ".") for s in SOURCES if s.endswith(".py"))
        permitted |= path.parent.parent == INPUTS and path.parent.name in ("OB", "TT") and (
            path.name in ("manifest.json", "normal_logs.jsonl", "profile_windows.json"))
    elif BASE in path.parents:
        permitted = any(BASE / s in path.parents for s in (".venv-eadro", ".python-native"))
    else:
        permitted = True  # Standard library and pinned dependencies outside the research tree.
    if not permitted:
        DENIED[str(path)] += 1
        raise PermissionError("Parser04 boundary rejected: " + str(path))
    if not writing and OUT in path.parents:
        READS[str(path.relative_to(OUT))] += 1


sys.dont_write_bytecode = True
sys.addaudithook(guard)
tempfile.tempdir = "/tmp"
import numpy as np
from drain3 import TemplateMiner
from drain3.memory_buffer_persistence import MemoryBufferPersistence
from drain3.template_miner_config import TemplateMinerConfig
import native_data as native


def environment():
    versions = {n: importlib.metadata.version(n) for n in ("numpy", "pandas", "tick", "drain3")}
    assert sys.version_info[:2] == (3, 8) and Path(sys.prefix).resolve() == BASE / ".venv-eadro"
    assert versions == dict(numpy="1.21.5", pandas="1.4.2", tick="0.7.0.1", drain3="0.9.11")
    assert all(os.environ.get(k) == "1" for k in THREADS) and not os.environ.get("PYTHONPATH")
    defaults = {k: v.default for k, v in inspect.signature(native.HawkesADM4).parameters.items()
                if v.default is not inspect.Parameter.empty}
    assert defaults == dict(C=1000., lasso_nuclear_ratio=.5, max_iter=50, tol=1e-5,
                           n_threads=1, verbose=False, print_every=10, record_every=10,
                           rho=.1, approx=0, em_max_iter=30, em_tol=None)
    return dict(python=sys.version, prefix=sys.prefix, versions=versions, solver_defaults=defaults,
                threads={k: os.environ[k] for k in THREADS}, decay=3, baseline_start=.2, end_times=10)


def digest(body):
    return hashlib.sha256(body).hexdigest()


def stable_chunks(path):
    before = path.stat()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            yield chunk
        opened = os.fstat(stream.fileno())
    after = path.stat()
    assert all((s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns) ==
               (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
               for s in (opened, after)), "Input changed while reading"


def sha(path):
    h = hashlib.sha256()
    for chunk in stable_chunks(path):
        h.update(chunk)
    return h.hexdigest()


def load(path):
    body = b"".join(stable_chunks(path))
    return json.loads(body), digest(body)


def save(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def configuration():
    body = b"".join(stable_chunks(CONFIG))
    original = body[:-1] if body.endswith(b"\n") else body
    blob = hashlib.sha1(("blob {}\0".format(len(original))).encode() + original).hexdigest()
    assert blob == "a391102e3e8c66ac125fad082e619a2b180e0dcf"
    config = TemplateMinerConfig()
    assert config.drain_sim_th == .4
    config.load(str(CONFIG))
    assert sha(CONFIG) == digest(body)
    values = dict(vars(config), masking_instructions=[
        dict(pattern=m.pattern, mask_with=m.mask_with) for m in config.masking_instructions])
    assert (config.drain_sim_th, config.drain_depth, config.drain_max_children,
            config.drain_max_clusters) == (.9, 4, 100, 1024)
    config.drain_sim_th = .4
    effective = dict(values, drain_sim_th=.4)
    assert {k for k in values if values[k] != effective[k]} == {"drain_sim_th"}
    return config, dict(original_ini_sha256=digest(body), upstream_git_blob_sha1=blob,
                        original=values, effective=effective,
                        effective_sha256=digest(json.dumps(effective, sort_keys=True).encode()))


def inputs(system):
    audit, audit_sha = load(OUT / "rca_schema_audit.json")
    old, old_sha = load(OUT / "rca_native_cost.json")
    assert audit["split_sha256"] == SPLIT == old["provenance"]["manifests"][system]["split_sha256"]
    assert audit_sha == old["provenance"]["input_hashes"]["audit_json_sha256"]
    manifest, manifest_sha = load(INPUTS / system / "manifest.json")
    profiles, profile_sha = load(INPUTS / system / "profile_windows.json")
    hashes = {"rca_schema_audit.json": audit_sha, "rca_native_cost.json": old_sha,
              str(Path("rca_audit_inputs") / system / "manifest.json"): manifest_sha,
              str(Path("rca_audit_inputs") / system / "profile_windows.json"): profile_sha}
    assert manifest == audit["systems"][system] == old["provenance"]["manifests"][system]
    assert len(manifest["train_cases"]) == 54 and len(profiles["samples"]) == manifest["profile_sample_count"] == 10
    assert profiles["system"] == system and profiles["split_sha256"] == SPLIT
    assert profiles["seconds"] == profiles["stride"] == 10
    for name, actual in (("manifest.json", manifest_sha), ("profile_windows.json", profile_sha)):
        item = next(x for x in audit["outputs"] if x["path"] == str((INPUTS / system / name).relative_to(BASE)))
        assert actual == item["sha256"] == old["provenance"]["input_hashes"][item["path"]]
    for name in ("native_data.py", "native_data_profile.py", "rca_native_cost.py"):
        hashes[name] = sha(OUT / name)
    assert hashes["native_data.py"] == old["native_source_sha256"]
    assert hashes["rca_native_cost.py"] == old["cost_source_sha256"]
    return audit, manifest, profiles["samples"], old["systems"][system], hashes


def message(event):
    if "message" not in event:
        return None, "missing_message"
    value = event["message"]
    if value is None:
        return None, "null_message"
    if not isinstance(value, str):
        raise ValueError("No message coercion")
    return value, "observed_string"


def mine(system, audit, manifest, miner) -> Dict[str, Any]:
    path = INPUTS / system / "normal_logs.jsonl"
    before = path.stat()
    h, per_case, counts, rows = hashlib.sha256(), defaultdict(hashlib.sha256), Counter(), Counter()
    last, size, begin = None, 0, time.perf_counter()
    with path.open("rb") as stream:
        for line in stream:
            h.update(line)
            size += len(line)
            row = json.loads(line)
            assert {"case", "service", "timestamp"} <= set(row) <= {"case", "service", "timestamp", "message"}
            case, service, stamp = row["case"], row["service"], row["timestamp"]
            card = audit["cases"][case]
            assert case in manifest["train_cases"] and card["partition"] == "train" and card["dataset"] == "RE2-" + system
            assert type(stamp) is int and card["metric_range_inclusive"][0] <= stamp <= card["metric_range_inclusive"][1]
            assert stamp < card["inject_time"] and (service is None or isinstance(service, str))
            key = (case, (service is not None, service or ""), stamp)
            assert last is None or last <= key
            last = key
            per_case[case].update(line)
            rows[case] += 1
            value, status = message(row)
            counts.update(["rows", status])
            counts["null_service_rows"] += service is None
            if value is not None:
                miner.add_log_message(value)
            if counts["rows"] % 100000 == 0:
                print("MINING", system, counts["rows"], flush=True)
        opened = os.fstat(stream.fileno())
    after = path.stat()
    assert all((s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns) ==
               (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
               for s in (opened, after))
    expected = manifest["normal_output"]
    assert (h.hexdigest(), size, counts["rows"]) == (expected["sha256"], expected["bytes"], expected["rows"])
    assert counts["rows"] == manifest["normal_export_rows"] == expected["lines"]
    for case in manifest["train_cases"]:
        card = audit["cases"][case]
        if "log_export" in card:
            assert rows[case] == card["log_export"]["exported_normal_rows"]
            assert per_case[case].hexdigest() == card["log_export"]["exported_original_objects_sha256"]
        else:
            assert card["failures"] and rows[case] == 0
    return dict(counts=dict(counts), mining_seconds=time.perf_counter() - begin,
                normal_sha256=h.hexdigest(), training_order=manifest["normal_export_order"],
                supervisor_peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024)


def enumeration(miner):
    return [dict(cluster_id=c.cluster_id, size=c.size, template=c.get_template()) for c in miner.drain.clusters]


def snapshot(miner):
    handler = MemoryBufferPersistence()
    miner.persistence_handler = handler
    miner.save_state("completed training")
    miner.persistence_handler = None
    return handler.state


def restore(path, expected_sha, config):
    body = b"".join(stable_chunks(path))
    assert digest(body) == expected_sha, "Snapshot hash mismatch; refusing deserialization"
    handler = MemoryBufferPersistence()
    handler.state = body
    miner = TemplateMiner(persistence_handler=handler, config=config)
    return miner


def bridge(sample, miner, templates):
    mapping = {t: i + 1 for i, t in enumerate(templates)}
    mapping["Unseen"] = 0
    times, ids, counts = [], [], Counter()
    assert sample["end"] == sample["start"] + 10
    for event in sample["events"]:
        stamp = event["timestamp"]
        assert type(stamp) is int and sample["start"] <= stamp < sample["end"]
        value, status = message(event)
        counts[status] += 1
        if value is not None:
            match = miner.match(value)
            index = mapping.get(match.get_template() if match is not None else "Unseen", 0)
            times.append(stamp)
            ids.append(index)
            counts["unseen_observed_strings"] += index == 0
    observed, unseen = counts["observed_string"], counts["unseen_observed_strings"]
    info: Dict[str, Any] = dict(message_counts=dict(counts), source_events=len(sample["events"]),
                seen_rate=(observed - unseen) / observed if observed else None,
                unseen_rate=unseen / observed if observed else None,
                matched_indices_sha256=digest(json.dumps(ids).encode()), E=len(templates) + 1)
    unavailable = counts["null_message"] or counts["missing_message"] or sample["service"] is None or not times
    info["status"] = "unavailable" if unavailable else "ready"
    knots = None if unavailable else native.make_knots(np.asarray(times, dtype=np.float64),
        np.asarray(ids, dtype=np.int64), float(sample["start"]), len(templates) + 1)
    if knots is not None:
        info.update(knots_sha256=digest(b"".join(k.tobytes() for k in knots)),
                    relative_horizon=10, occupied_bins=len(set(ids)), native_jitter=1e-5)
    return knots, info


def bounded_fit(knots, coords):
    command = [sys.executable, "-B", str(OUT / "rca_native_cost.py"), "--worker"]
    payload = json.dumps(dict(knots=[k.tolist() for k in knots], coordinates=coords), allow_nan=False)
    begin = time.perf_counter()
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, start_new_session=True)
    status = None
    try:
        stdout, stderr = process.communicate(payload, timeout=120)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
        status = "timeout"
    result: Dict[str, Any] = dict(status=status or ("completed" if process.returncode == 0 else "failed"),
                  command=command, returncode=process.returncode, deadline_seconds=120,
                  process_wall_seconds=time.perf_counter() - begin, stdout=stdout, stderr=stderr)
    if result["status"] == "completed":
        lines = [x[11:] for x in stdout.splitlines() if x.startswith("FIT_RESULT ")]
        assert len(lines) == 1
        result["fit"] = fit = json.loads(lines[0])
        assert fit["finite_baseline"] and fit["baseline_min"] >= 0 and fit["baseline_shape"] == [len(knots)]
        assert (fit["window"], fit["node"]) == (coords["window"], coords["node"])
    if status == "timeout":
        result.update(completed_fit_seconds=None, censored_process_wall_lower_bound_seconds=120,
                      warnings_limit="stderr preserved; killed native warning buffer unavailable",
                      censor_scope="120s process wall includes imports/initialization, not pure solver CPU")
    return result


def measure(samples, miner, templates, original):
    results, attempts = [], []
    for i, sample in enumerate(samples):
        old = original["samples"][i]
        identity = {k: sample[k] for k in ("case", "service", "start", "end", "period", "selected_for")}
        assert old["sample_index"] == i and all(old[k] == v for k, v in identity.items())
        knots, matching = bridge(sample, miner, templates)
        row: Dict[str, Any] = dict(sample_index=i, **identity, matching=matching, status=matching["status"])
        if knots is not None:
            if attempts == ["timeout", "timeout"]:
                row["status"] = "not_run_first_two_timeouts"
            else:
                coords = old["coordinates"]
                assert coords["seed"] == 42 + coords["window"] * coords["node_num"] + coords["node"]
                row.update(bounded_fit(knots, coords), coordinates=coords)
                if len(attempts) < 2:
                    attempts.append(row["status"])
        else:
            assert old["status"] == "unavailable", "Original null policy changed"
        results.append(row)
        print("SAMPLE", i, row["status"], flush=True)
    return results


def planning(manifest, E, samples):
    times = [r["fit"]["seconds"] for r in samples if r["status"] == "completed"]
    usable = manifest["train_drain_usable_nonempty_fit_count"]
    return dict(TRAIN_string_usable_groups=usable,
                TRAIN_raw_nonempty_groups=manifest["train_nonempty_window_raw_service_fit_count"],
                completed_mean_seconds=sum(times) / len(times) if times else None,
                completed_max_seconds=max(times) if times else None,
                TRAIN_mean_serial_seconds=sum(times) / len(times) * usable if times else None,
                TRAIN_mean_ideal_two_worker_seconds=sum(times) / len(times) * usable / 2 if times else None,
                TRAIN_max_sample_serial_scenario_seconds=max(times) * usable if times else None,
                sample_status_counts=dict(Counter(r["status"] for r in samples)),
                single_float64_matrix_bytes=8 * E * E, seven_dense_matrices_bytes=56 * E * E,
                two_workers_seven_matrices_bytes=112 * E * E,
                TRAIN_arrays=[dict(a, log_float64_bytes_W_N_E=a["log_float64_bytes_per_template_W_N_E"] * E)
                              for a in manifest["TRAIN_array_estimates"]["estimates"]],
                limits="TRAIN-only purposive samples; completed-fit projections are not upper bounds. "
                "String-usable audit groups may be partially null: full-fit count uncertified. "
                "TT high-event null profiles remain a coverage limit. Matrix payloads are lower bounds, "
                "not RSS ceilings; full matching/I/O costs, validation/final36 and accuracy unmeasured.")


def execute(system, env):
    destination = ROOT / system
    destination.mkdir(parents=True, exist_ok=False)  # Partial directories are never automatically reused.
    audit, manifest, samples, original, hashes = inputs(system)
    config, config_info = configuration()
    assert config_info["original_ini_sha256"] == original["templates"]["config"]["sha256"]
    miner = TemplateMiner(config=config)
    metadata = mine(system, audit, manifest, miner)
    hashes["rca_audit_inputs/" + system + "/normal_logs.jsonl"] = metadata["normal_sha256"]
    clusters = enumeration(miner)
    templates = [c["template"] for c in clusters]
    mapping = {t: i + 1 for i, t in enumerate(templates)}
    mapping["Unseen"] = 0
    state = snapshot(miner)
    with (destination / "miner.bin").open("xb") as stream:
        stream.write(state)
    reloaded = restore(destination / "miner.bin", digest(state), config)
    assert enumeration(reloaded) == clusters and snapshot(reloaded) == state
    matching = [bridge(s, miner, templates)[1] for s in samples]
    assert matching == [bridge(s, reloaded, templates)[1] for s in samples]
    metadata.update(system=system, split_sha256=SPLIT, config=config_info, input_hashes=hashes,
                    clusters=clusters, templates=templates, template_to_index=mapping, unseen_index=0,
                    template_order="Final Drain enumeration; duplicate text maps to last index, native Unseen=0",
                    E=len(templates) + 1, clusters_created=miner.drain.clusters_counter,
                    clusters_evicted=miner.drain.clusters_counter - len(clusters),
                    state_sha256=digest(state), snapshot_format="Drain3 0.9.11 library compressed jsonpickle",
                    restored_profile_matching=matching, full_drain_roundtrip_equal=True,
                    null_policy="Never mine null/missing; partially null/unidentified groups unavailable")
    save(destination / "metadata.json", metadata)
    results = measure(samples, reloaded, templates, original)
    plan = planning(manifest, metadata["E"], results)
    report = dict(status="complete", system=system, environment=env, E=metadata["E"], samples=results,
                  metadata_sha256=sha(destination / "metadata.json"), state_sha256=digest(state),
                  input_hashes=hashes, config=config_info, planning=plan,
                  original_config_comparison={k: original["templates"][k] for k in (
                      "E", "clusters_created", "intrinsic_pinned_lru_evictions", "config")},
                  original_profile_comparison=[dict(
                      {k: r[k] for k in ("sample_index", "status", "message_counts") if k in r},
                      fit=r.get("fit")) for r in original["samples"]],
                  original_projection=original["projection"], invocation=[sys.executable, *sys.argv],
                  verification=dict(raw_reads=0, validation_message_reads=0, final36_reads=0, model_runs=0,
                                    restored_matching=True, allowed_reads=dict(READS), rejected_reads=dict(DENIED)))
    markdown = "# {} parser0.4 bounded transfer\n\n".format(system) + (
        "TRAIN-normal mining only; only drain_sim_th changed 0.9→0.4. E={}; created={}; evicted={}.\n\n"
        "Sample statuses: {}. Timing/iterations, warnings, stderr, unseen rates and TRAIN-only planning "
        "are in report.json. Actual final tree/cache snapshot and fixed native enumeration are saved.\n\n"
        "{}\n\nThis is a named dataset port, not literal reproduction, model accuracy or scientific improvement.\n"
    ).format(metadata["E"], metadata["clusters_created"], metadata["clusters_evicted"],
             plan["sample_status_counts"], plan["limits"])
    with (destination / "report.md").open("x") as stream:
        stream.write(markdown)
    report["report_md_sha256"] = sha(destination / "report.md")
    save(destination / "report.json.partial", report)
    (destination / "report.json.partial").rename(destination / "report.json")
    print("PARSER04_COMPLETE", system, flush=True)


def verify(system):
    destination = ROOT / system
    report, _ = load(destination / "report.json")
    audit, manifest, samples, original, hashes = inputs(system)
    config, config_info = configuration()
    hashes["rca_audit_inputs/" + system + "/normal_logs.jsonl"] = sha(INPUTS / system / "normal_logs.jsonl")
    assert hashes["rca_audit_inputs/" + system + "/normal_logs.jsonl"] == manifest["normal_output"]["sha256"]
    metadata, metadata_sha = load(destination / "metadata.json")
    assert report["status"] == "complete" and report["system"] == metadata["system"] == system
    assert metadata_sha == report["metadata_sha256"] and sha(destination / "report.md") == report["report_md_sha256"]
    assert report["input_hashes"] == metadata["input_hashes"] == hashes
    assert report["config"] == metadata["config"] == config_info
    assert report["state_sha256"] == metadata["state_sha256"]
    assert config_info["original_ini_sha256"] == original["templates"]["config"]["sha256"]
    miner = restore(destination / "miner.bin", metadata["state_sha256"], config)
    assert enumeration(miner) == metadata["clusters"] and digest(snapshot(miner)) == metadata["state_sha256"]
    assert metadata["templates"] == [c["template"] for c in enumeration(miner)]
    assert report["E"] == metadata["E"] == len(metadata["templates"]) + 1 and metadata["unseen_index"] == 0
    mapping = {t: i + 1 for i, t in enumerate(metadata["templates"])}
    mapping["Unseen"] = 0
    assert mapping == metadata["template_to_index"]
    assert metadata["clusters_created"] == miner.drain.clusters_counter
    assert metadata["clusters_evicted"] == miner.drain.clusters_counter - len(metadata["templates"])
    matching = [bridge(s, miner, metadata["templates"])[1] for s in samples]
    assert matching == metadata["restored_profile_matching"] == [r["matching"] for r in report["samples"]]
    assert len(report["samples"]) == 10 and report["planning"] == planning(manifest, metadata["E"], report["samples"])
    assert all(report["verification"][k] == 0 for k in ("raw_reads", "validation_message_reads", "final36_reads", "model_runs"))
    for row, old in zip(report["samples"], original["samples"]):
        assert row["status"] in ("completed", "timeout", "failed", "unavailable", "not_run_first_two_timeouts")
        assert all(row[k] == old[k] for k in ("sample_index", "case", "service", "start", "end", "period", "selected_for"))
        if row["status"] == "completed":
            fit = row["fit"]
            assert fit["finite_baseline"] and fit["baseline_min"] >= 0 and fit["baseline_shape"] == [metadata["E"]]
        if "coordinates" in row:
            assert row["coordinates"] == old["coordinates"]
        if row["status"] == "timeout":
            assert row["deadline_seconds"] == 120 and row["completed_fit_seconds"] is None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-check", action="store_true")
    mode.add_argument("--system", choices=("OB", "TT"))
    mode.add_argument("--verify-all", action="store_true")
    args = parser.parse_args()
    env = environment()
    if args.self_check:
        from parser_transfer_tests import self_check
        print("PARSER04_SELF_CHECK", json.dumps(self_check(sys.modules[__name__])), flush=True)
    elif args.verify_all:
        for system in ("OB", "TT"):
            verify(system)
        print("PARSER04_VERIFIED", flush=True)
    else:
        execute(args.system, env)


if __name__ == "__main__":
    main()
