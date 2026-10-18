"""Persist synthetic reference checks and verify exact upstream source blobs."""
import hashlib
import json

import torch

from mlp_readiness import OUT, save_new
from mlp_reference import self_check


def main():
    blobs = {
        "eadro_model.py": "cdc188dcdcb972e7d6a7b200f549600e10ee7aaa",
        "eadro_corrected_model.py": "d0cf0560a4a2ad0f5d9814f7d6118fc6d989bbbc",
    }
    for name, expected in blobs.items():
        raw = (OUT / name).read_bytes()
        actual = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        assert actual == expected, f"Upstream source drift: {name}"
    torch.set_num_threads(2)
    result = self_check()
    result["verified_git_blobs"] = blobs
    assert len(result["adapted"]) == 4
    assert all(row["forward_backward"] == "passed" for row in result["adapted"])
    assert result["original_main"]["status"] == "blocked_upstream"
    assert result["corrected_main"]["status"] == "passed"
    path = OUT / "model_checks.json"
    if path.exists():
        assert json.loads(path.read_text()) == result, "Stored model checks differ"
    else:
        save_new(path, result)
    print("MODEL_CHECK_PASS adapted=4 corrected_full=passed original_full=blocked_upstream", flush=True)


if __name__ == "__main__":
    main()
