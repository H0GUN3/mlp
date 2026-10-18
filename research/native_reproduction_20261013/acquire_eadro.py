"""Acquire pinned Eadro archives and validate them without changing older data."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import sys
import zipfile

BASE = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
DATA = BASE / "data/eadro_native"
sys.path.insert(0, str(BASE / "scripts"))
from acquire import request

RECORD = "https://zenodo.org/api/records/7615394"
EXPECTED = {
    "SN Dataset.zip": (78753809, "4c523faf64770b1e9a709cdd610e07c4"),
    "TT Dataset.zip": (48923113, "2d77861e4a025781e598d51866fd6f4e"),
}


def hashes(path):
    md5, sha = hashlib.md5(), hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            md5.update(chunk)
            sha.update(chunk)
    return md5.hexdigest(), sha.hexdigest()


def safe_path(name):
    path = PurePosixPath(name.replace("\\", "/"))
    if not path.parts or path.is_absolute() or ".." in path.parts or ":" in path.parts[0]:
        raise ValueError(f"Unsafe archive member: {name}")
    return path


def main():
    assert str(safe_path("SN/a.json")) == "SN/a.json"
    for name in ("../escape", "/absolute", "C:\\escape", "SN/../../escape"):
        try:
            safe_path(name)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Unsafe path accepted: {name}")
    DATA.mkdir(parents=True, exist_ok=True)
    with request(RECORD) as response:
        metadata = json.load(response)
    assert int(metadata["id"]) == 7615394
    files = {row["key"]: row for row in metadata["files"]}
    reports = []
    for name, (size, checksum) in EXPECTED.items():
        row = files[name]
        assert row["size"] == size and row["checksum"] == "md5:" + checksum
        archive = DATA / name
        if not archive.exists():
            partial = archive.with_suffix(".zip.partial")
            with request(row["links"]["self"]) as response, partial.open("wb") as output:
                shutil.copyfileobj(response, output, length=1024 * 1024)
            assert partial.stat().st_size == size
            assert hashes(partial)[0] == checksum
            partial.rename(archive)
        md5, sha = hashes(archive)
        assert archive.stat().st_size == size and md5 == checksum
        extracted = DATA / name.removesuffix(".zip").replace(" ", "_")
        entries = []
        with zipfile.ZipFile(archive) as source:
            assert sum(info.file_size for info in source.infolist()) < 10 * 1024**3
            assert source.testzip() is None, "Archive CRC failure"
            for info in source.infolist():
                relative = safe_path(info.filename)
                if stat.S_ISLNK(info.external_attr >> 16):
                    raise ValueError("Symlink in archive")
                target = extracted.joinpath(*relative.parts)
                assert target.resolve().is_relative_to(extracted.resolve())
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    assert target.stat().st_size == info.file_size, "Existing extracted file differs"
                    with target.open("rb") as stream:
                        import zlib
                        crc = 0
                        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                            crc = zlib.crc32(chunk, crc)
                    assert crc == info.CRC, "Existing extracted file CRC differs"
                else:
                    with source.open(info) as incoming, target.open("xb") as output:
                        shutil.copyfileobj(incoming, output, length=1024 * 1024)
                entries.append({"path": str(target.relative_to(BASE)), "bytes": info.file_size,
                                "crc32": info.CRC})
        reports.append({"name": name, "bytes": size, "publisher_md5": md5, "sha256": sha,
                        "source": row["links"]["self"], "files": entries,
                        "uncompressed_bytes": sum(r["bytes"] for r in entries)})
        print(f"ARCHIVE_PASS {name} files={len(entries)} extracted_bytes={reports[-1]['uncompressed_bytes']}",
              flush=True)
    report = {"record": RECORD, "doi": metadata.get("doi"), "archives": reports}
    destination = OUT / "acquisition.json"
    if destination.exists():
        assert json.loads(destination.read_text()) == report
    else:
        with destination.open("x") as output:
            json.dump(report, output, indent=2)
    print("ACQUISITION_COMPLETE archives=2 publisher_hashes=passed", flush=True)


if __name__ == "__main__":
    main()
