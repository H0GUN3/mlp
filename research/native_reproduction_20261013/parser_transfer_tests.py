"""Small fixture-only regression checks; never mine real exports or invoke a solver."""
import io
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
from typing import Any, Dict
from unittest.mock import Mock, patch


def self_check(p):
    destination = p.ROOT / "selfcheck"
    destination.mkdir(parents=True, exist_ok=True)
    config, info = p.configuration()
    effective = dict(vars(config), masking_instructions=[
        dict(pattern=m.pattern, mask_with=m.mask_with) for m in config.masking_instructions])
    assert effective == info["effective"]
    assert {k for k in effective if effective[k] != info["original"][k]} == {"drain_sim_th"}
    assert p.message({}) == (None, "missing_message")
    assert p.message({"message": None}) == (None, "null_message")
    assert p.message({"message": ""}) == ("", "observed_string")
    try:
        p.message({"message": 5})
        raise AssertionError("Numeric messages accepted")
    except ValueError:
        pass
    miner = p.TemplateMiner(config=config)
    miner.add_log_message("observed alpha")
    miner.add_log_message("2024-01-01 10:00:00,123 accepted")
    templates = [c["template"] for c in p.enumeration(miner)]
    assert miner.match("2025-01-02 11:11:11,456 accepted") is not None
    sample: Dict[str, Any] = dict(case="case", service="s", start=100, end=110, period="nominal_normal",
                  selected_for=["fixture"], events=[
                      dict(timestamp=100, message="observed alpha"),
                      dict(timestamp=100, message="unknown different token length"),
                      dict(timestamp=100, message="observed alpha")])
    knots, matching = p.bridge(sample, miner, templates)
    assert matching["message_counts"]["unseen_observed_strings"] == 1
    p.np.testing.assert_array_equal(knots[0], [0])
    p.np.testing.assert_array_equal(knots[1], [0, 1e-5])
    p.np.testing.assert_array_equal(knots[2], [0])
    for event in ({}, {"message": None}):
        partial = dict(sample, events=sample["events"] + [dict(timestamp=101, **event)])
        assert p.bridge(partial, miner, templates)[0] is None
    assert p.bridge(dict(sample, service=None), miner, templates)[0] is None
    for stamp in (99, 110, 100.5):
        try:
            p.bridge(dict(sample, events=[dict(timestamp=stamp, message="observed alpha")]), miner, templates)
            raise AssertionError("Invalid half-open timestamp accepted")
        except AssertionError as exc:
            assert str(exc) != "Invalid half-open timestamp accepted"
    state = p.snapshot(miner)
    path = destination / "miner.bin"
    with path.open("wb") as stream:
        stream.write(state)
    restored = p.restore(path, p.digest(state), config)
    assert p.enumeration(restored) == p.enumeration(miner) and p.snapshot(restored) == state
    assert p.bridge(sample, restored, templates)[1] == matching
    evicting = p.TemplateMiner(config=config)
    for i in range(1030):
        word = "word" + "".join(chr(97 + (i // (26 ** j)) % 26) for j in range(3))
        evicting.add_log_message(word)
    assert evicting.drain.clusters_counter == 1030 and len(evicting.drain.clusters) == 1024
    eviction_state = p.snapshot(evicting)
    with path.open("wb") as stream:
        stream.write(eviction_state)
    reloaded_evictions = p.restore(path, p.digest(eviction_state), config)
    assert p.enumeration(reloaded_evictions) == p.enumeration(evicting)
    assert p.snapshot(reloaded_evictions) == eviction_state
    with path.open("wb") as stream:
        stream.write(state + b"corrupt")
    with patch.object(p, "TemplateMiner", side_effect=AssertionError("Deserialized corruption")):
        try:
            p.restore(path, p.digest(state), config)
            raise AssertionError("Corruption accepted")
        except AssertionError as exc:
            assert str(exc) == "Snapshot hash mismatch; refusing deserialization"
    with path.open("wb") as stream:
        stream.write(state)
    for forbidden in (p.BASE / "data/rcaeval/forbidden/logs.parquet",
                      p.OUT / "native_inputs/TT_prepared.npz"):
        try:
            forbidden.open("rb")
            raise AssertionError("Protected input accepted")
        except PermissionError:
            pass
    try:
        p.CONFIG.open("w")
        raise AssertionError("Original INI write accepted")
    except PermissionError:
        pass
    assert p.sha(p.CONFIG) == info["original_ini_sha256"]
    coords = dict(window=1, node=1, node_num=3, seed=46)
    process = Mock(pid=123, returncode=-9)
    process.communicate.side_effect = [subprocess.TimeoutExpired("fixture", 120),
                                       ("FIT_STARTED fixture\n", "fixture warning\n")]
    with patch.object(p.subprocess, "Popen", return_value=process) as popen, patch.object(p.os, "killpg") as kill:
        result = p.bounded_fit(knots, coords)
        assert popen.call_args.args[0] == [p.sys.executable, "-B", str(p.OUT / "rca_native_cost.py"), "--worker"]
        assert json.loads(process.communicate.call_args_list[0].args[0])["coordinates"] == coords
        assert process.communicate.call_args_list[0].kwargs["timeout"] == 120
        kill.assert_called_once_with(123, p.signal.SIGKILL)
        assert result["status"] == "timeout" and result["stderr"] == "fixture warning\n"
        assert result["completed_fit_seconds"] is None
    nullable = dict(sample, events=[dict(timestamp=100, message=None)])
    original = dict(samples=[dict(sample_index=i, coordinates=coords, status=(
        "unavailable" if i == 2 else "completed"), **{k: sample[k] for k in
        ("case", "service", "start", "end", "period", "selected_for")}) for i in range(4)])
    with patch.object(p, "bounded_fit", return_value=dict(status="timeout")) as fit:
        results = p.measure([sample, sample, nullable, sample], miner, templates, original)
        assert fit.call_count == 2
        assert [r["status"] for r in results] == ["timeout", "timeout", "unavailable", "not_run_first_two_timeouts"]
    body = b"".join((json.dumps(dict(case="case", service="s", timestamp=100 + i,
                                    message=value)) + "\n").encode() for i, value in enumerate(["fixture train", None]))
    stat = SimpleNamespace(st_dev=1, st_ino=1, st_size=len(body), st_mtime_ns=1, st_ctime_ns=1)
    card = dict(partition="train", dataset="RE2-OB", metric_range_inclusive=[100, 120], inject_time=110,
                log_export=dict(exported_normal_rows=2, exported_original_objects_sha256=p.digest(body)))
    manifest = dict(train_cases=["case"], normal_export_rows=2, normal_export_order="fixture",
                    normal_output=dict(sha256=p.digest(body), bytes=len(body), rows=2, lines=2))
    fake_miner = Mock()
    class FixtureStream(io.BytesIO):
        def fileno(self):
            return 123

    with patch.object(Path, "open", return_value=FixtureStream(body)), patch.object(Path, "stat", return_value=stat), (
            patch.object(p.os, "fstat", return_value=stat)):
        metadata = p.mine("OB", dict(cases={"case": card}), manifest, fake_miner)
    fake_miner.add_log_message.assert_called_once_with("fixture train")
    assert metadata["counts"]["null_message"] == 1
    verify_fixtures(p, destination, config, info)
    for system in ("OB", "TT"):
        p.inputs(system)  # Only permitted small provenance/profile files, no normal stream.
    assert not any(k.endswith("normal_logs.jsonl") for k in p.READS)
    assert "rca_native_cost" not in p.sys.modules
    checks = dict(threshold_only=True, unknown_null_timestamps_native_knots=True,
                  exact_library_snapshot_reload=True, corruption_rejected_before_deserialization=True,
                  raw_and_original_write_guard=True, mocked_worker_deadline_stderr_stop=True,
                  fixture_single_stream_hash_rows_null_policy=True, original_profile_provenance=True)
    checks["final_reports_verified_without_mining_or_fits"] = True
    with (destination / "report.json").open("w") as stream:
        json.dump(checks, stream, indent=2)
    return checks


def verify_fixtures(p, destination, config, info):
    root = Path(tempfile.mkdtemp(prefix="final_reports_", dir=str(destination)))
    normal_sha = p.digest(b"synthetic normal input")
    sample = dict(case="fixture", service="s", start=100, end=110, period="nominal_normal",
                  selected_for=["fixture"], events=[dict(timestamp=100, message="fixture train")])
    coords = dict(window=0, node=0, node_num=1, seed=42)
    original = dict(samples=[dict(sample_index=i, coordinates=coords, status="completed", **{k: sample[k] for k in
        ("case", "service", "start", "end", "period", "selected_for")}) for i in range(10)],
        templates=dict(E=2, clusters_created=1, intrinsic_pinned_lru_evictions=0,
                       config=dict(sha256=info["original_ini_sha256"])), projection={})
    manifest = dict(normal_output=dict(sha256=normal_sha), train_drain_usable_nonempty_fit_count=10,
                    train_nonempty_window_raw_service_fit_count=10, TRAIN_array_estimates=dict(estimates=[]))
    real_sha = p.sha
    def fixture_sha(path):
        return normal_sha if path.name == "normal_logs.jsonl" else real_sha(path)
    def fixture_inputs(system):
        return {}, manifest, [sample] * 10, original, {}
    def fixture_mine(system, audit, manifest, miner):
        miner.add_log_message("fixture train")
        return dict(normal_sha256=normal_sha, counts=dict(rows=1, observed_string=1))
    completed = dict(status="completed", fit=dict(seconds=.01, iterations=1, finite_baseline=True,
                                                baseline_min=.1, baseline_shape=[2]))
    with patch.object(p, "ROOT", root), patch.object(p, "inputs", side_effect=fixture_inputs), (
            patch.object(p, "sha", side_effect=fixture_sha)):
        with patch.object(p, "mine", side_effect=fixture_mine), patch.object(p, "bounded_fit", return_value=completed):
            for system in ("OB", "TT"):
                p.execute(system, p.environment())
        with patch.object(p, "mine", side_effect=AssertionError("Verification mined")), (
                patch.object(p, "bounded_fit", side_effect=AssertionError("Verification fitted"))):
            for system in ("OB", "TT"):
                p.verify(system)
            report_path = root / "OB/report.json"
            report, _ = p.load(report_path)
            report["state_sha256"] = "corrupt"
            with report_path.open("w") as stream:
                json.dump(report, stream)
            try:
                p.verify("OB")
                raise AssertionError("Corrupt final report accepted")
            except AssertionError as exc:
                assert str(exc) != "Corrupt final report accepted"
        try:
            p.execute("OB", p.environment())
            raise AssertionError("Partial/final directory reused")
        except FileExistsError:
            pass
