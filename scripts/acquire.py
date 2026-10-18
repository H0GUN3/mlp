"""Download pinned public data; verify publisher hashes before keeping bytes."""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import random
import re
import time
import urllib.parse
import urllib.request
import urllib.error

BASE = Path(__file__).resolve().parents[1]
REPOS = {
    "rcaeval": ("phamquiluan/RCAEval", "afeacb11bcc94dadfd1c8f483ee4377b2b8b614e"),
    "ops-lite": ("anon-ops/ops-lite", "581eba39d0bfd2d397eded6cd7cbe3303255521a"),
}


def request(url):
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "RCA-data-verification/1.0"}),
        timeout=120,
    )


def index(repo, revision):
    url = f"https://huggingface.co/api/datasets/{repo}/tree/{revision}?recursive=true&limit=1000"
    entries = []
    while url:
        with request(url) as response:
            entries.extend(json.load(response))
            links = response.headers.get("Link", "")
        match = re.search(r'<([^>]+)>;\s*rel="next"', links)
        url = match.group(1) if match else None
    return [entry for entry in entries if entry["type"] == "file"]


def check(path, entry):
    if not path.exists() or path.stat().st_size != entry["size"]:
        return None
    sha = hashlib.sha256()
    git = hashlib.sha1(f"blob {entry['size']}\0".encode())
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            sha.update(chunk)
            git.update(chunk)
    expected = entry.get("lfs", {}).get("oid")
    valid = sha.hexdigest() == expected if expected else git.hexdigest() == entry["oid"]
    return sha.hexdigest() if valid else None


def download(key, entry):
    repo, revision = REPOS[key]
    relative = Path(entry["path"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"Unsafe path: {relative}")
    target = BASE / "data" / key / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    digest = check(target, entry)
    url = f"https://huggingface.co/datasets/{repo}/resolve/{revision}/{urllib.parse.quote(entry['path'])}"
    if digest is None:
        partial = target.with_name(target.name + ".partial")
        for attempt in range(4):
            try:
                with request(url) as response, partial.open("wb") as output:
                    while chunk := response.read(1024 * 1024):
                        output.write(chunk)
                digest = check(partial, entry)
                if digest is None:
                    raise ValueError(f"Publisher hash/size mismatch: {entry['path']}")
                partial.replace(target)
                break
            except Exception as error:
                if attempt == 3:
                    raise
                delay = 2 ** attempt
                if isinstance(error, urllib.error.HTTPError) and error.code == 429:
                    retry = error.headers.get("Retry-After", "")
                    reset = re.search(r"(?:^|;)t=(\d+)", error.headers.get("RateLimit", ""))
                    delay = int(retry) if retry.isdigit() else (int(reset.group(1)) + 1 if reset else 301)
                time.sleep(delay)
    return {"path": str(target.relative_to(BASE)), "bytes": entry["size"],
            "sha256": digest, "publisher_hash": entry.get("lfs", {}).get("oid", entry["oid"]),
            "publisher_hash_type": "sha256" if "lfs" in entry else "git-blob-sha1",
            "url": url, "verified": True}


def run(key):
    output = BASE / "evidence"
    output.mkdir(exist_ok=True)
    repo, revision = REPOS[key]
    tree_path = output / f"{key}-tree.json"
    cached = json.loads(tree_path.read_text()) if tree_path.exists() else {}
    tree = cached["entries"] if cached.get("revision") == revision and cached.get("repo") == repo else index(repo, revision)
    tree_path.write_text(json.dumps({"repo": repo, "revision": revision, "entries": tree}, indent=2))
    previous = output / f"{key}-downloads.json"
    if previous.exists():
        (output / f"{key}-downloads-before-retry-{time.time_ns()}.json").write_bytes(previous.read_bytes())
    print(f"INDEX {key} files={len(tree)} bytes={sum(x['size'] for x in tree)}", flush=True)
    if key == "rcaeval":
        selected = [entry for entry in tree if entry["path"] in ("README.md", "cases.parquet")
                    or entry["path"].startswith(("re2ob_", "re2tt_"))]
    else:
        manifest = next(entry for entry in tree if entry["path"] == "manifest.jsonl")
        download(key, manifest)
        records = [json.loads(line) for line in
                   (BASE / "data" / key / "manifest.jsonl").read_text().splitlines()]
        rng = random.Random(42)
        sample = []
        for system in sorted({record["system"] for record in records}):
            eligible = sorted(record["name"] for record in records
                              if record["system"] == system
                              and record["n_required_faults"] == 1
                              and record["process_applicable"])
            sample.extend(rng.sample(eligible, min(10, len(eligible))))
        (output / "ops-lite-sample.json").write_text(json.dumps(
            {"seed": 42, "criteria": "10 per system; one required fault and process_applicable",
             "cases": sorted(sample)}, indent=2))
        sample = set(sample)
        selected = [entry for entry in tree if entry["path"] in ("README.md", "manifest.jsonl")
                    or (entry["path"].startswith("cases/") and
                        (entry["path"].endswith(".json") or entry["path"].split("/")[1] in sample))]
    print(f"SELECTED {key} files={len(selected)} bytes={sum(x['size'] for x in selected)}", flush=True)
    succeeded, failed = [], []
    started = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(download, key, entry): entry["path"] for entry in selected}
        for future in concurrent.futures.as_completed(futures):
            try:
                succeeded.append(future.result())
            except Exception as error:
                failed.append({"path": futures[future], "error": repr(error)})
                print(f"FAILED {key} {futures[future]} {error!r}", flush=True)
            completed = len(succeeded) + len(failed)
            if completed % 100 == 0:
                print(f"PROGRESS {key} {completed}/{len(selected)}", flush=True)
    report = {"repo": repo, "revision": revision, "seconds": time.monotonic() - started,
              "files": sorted(succeeded, key=lambda item: item["path"]), "failed": failed}
    (output / f"{key}-downloads.json").write_text(json.dumps(report, indent=2))
    print(f"COMPLETE {key} verified={len(succeeded)} failed={len(failed)} "
          f"bytes={sum(item['bytes'] for item in succeeded)} seconds={report['seconds']:.1f}", flush=True)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", choices=REPOS)
    run(parser.parse_args().dataset)
