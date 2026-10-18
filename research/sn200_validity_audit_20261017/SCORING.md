# SN200 DiagMLP 라벨·인덱스·점수 독립 대조

## 판정

**검사 범위 내 문제 미확인 (`notfoundwithinscope`)**: 허용된 세 validation 산출물에서 index·라벨·출력 열 대응 오류를 찾지 못했다. 이는 validation 점수의 독립 재계산이지, 모델의 일반화나 실험 전체의 타당성 판정은 아니다.

## 근거와 대응

- `native_train.py:201–214`는 `model.eval()` 및 `torch.no_grad()`에서 validation 결과를 만들고 logits, labels를 반환한다. `native_train.py:304–312`는 full-validation joint loss가 strict minimum일 때 `parts["validation"]`, root/detection logits, labels를 저장한다. `native_train.py:321–325`의 기존 replay는 네 배열의 equality를 검사한다.
- `native_models.py:105–117`의 label 계약은 `-1`이 normal, `0..11`이 root class다. `native_data.py:125–128,140–146`에서 root는 ordered `SERVICES`의 index이고, 해당 window의 겹치는 fault root로 label을 만든다. 대조한 설정의 `services` 순서는 `config.json:53–66`에 기록되어 있다. metadata의 각 validation fault root index와 event service를 비교했으며 정상 window는 event/provenance가 null인지 확인했다. 불일치 0건.
- 각 `split.json`의 validation index와 NPZ `indices`는 순서까지 정확히 같았다. 각 seed에서 validation 78개, train/test와의 index 교집합 각각 0, logits shape `78×12` 및 `78×2`, label shape `78`이었다. 세 seed split 및 서비스 순서는 동일하다. 라벨은 `-1:13`, 나머지 fault:65였고 세 seed 간 동일했다.
- 각 NPZ SHA-256은 해당 `summary.json`의 `artifact_hashes.validation_predictions.npz`와 일치했다. 기존 `summary.json`은 checkpoint replay가 logits·labels·indices·loss의 bitwise equality였다고 기록한다. 이는 저장된 replay 주장과 hash의 일치 확인이며, 이 감사에서 checkpoint를 열거나 replay를 재실행한 것은 아니다.

## 독립 점수

`native_models.py:120–147` 및 `sn50_verification.py:26–48`과 같은 정의를 NumPy로 독립 적용했다: detection은 `argmax == 1`; fault-only conditional Top-1은 정답 root보다 큰 logit이 없을 때 동률이면 `1 / tie_count` 기대 credit; gated Top-1은 그 credit에 detection 결과를 곱한 fault-only 평균. Detection F1은 TP/FP/FN에서 계산했다. 동률이 있는 정답 root 행은 세 seed 모두 0개였다.

| seed | fault / normal | conditional Top-1 | gated Top-1 | detection F1 | fault Top-1 오답 |
|---:|---:|---:|---:|---:|---:|
| 11 | 65 / 13 | 92.307692% | 89.230769% | 96.923077% (TP=63, FP=2, FN=2) | 5 |
| 23 | 65 / 13 | 98.461538% | 98.461538% | 97.709924% (TP=64, FP=2, FN=1) | 1 |
| 37 | 65 / 13 | 95.384615% | 95.384615% | 100% (TP=65, FP=0, FN=0) | 3 |

seed별 점수의 동일 가중 평균은 conditional Top-1 **95.384615%**다. 이는 `1 - 9/(65×3)`와 같다. logits를 seed 간 합치거나 ensemble로 채점하지 않았다. `sn200_error_windows.json:1818–1830`의 기존 error summary도 DiagMLP fault 평가 195건, root 오답 9건(전체 주석 180 + 부분 주석 15에서 각각 8 + 1), 고유 root-error window 8개를 기록한다. 독립 재계산에서는 오답 총수 및 고유 window 수가 일치한다. 다만 아래 snippet 출력에는 인덱스별 오답 목록을 싣지 않았으므로, 8개 window의 전체 identity는 이 독립 출력만으로 재현·확인했다고 주장하지 않는다.

## 재현 가능한 in-memory 계산

저장 배열 접근은 정확히 아래 세 `validation_predictions.npz`에 한정하며 `allow_pickle=False`를 사용한다. JSON 입력은 해당 seed의 split/config/summary와 안전한 `native_inputs/SN/metadata.json`뿐이다. 연구 모듈·기존 verifier를 import하거나 실행하지 않는다.

```python
from pathlib import Path
import hashlib, json
import numpy as np

base = Path("/home/gnho1236/r2/research/native_reproduction_20261013")
root = base / "calibration200/SN/diagmlp"
meta = json.loads((base / "native_inputs/SN/metadata.json").read_text())
services = meta["services"]
events = {e["event_id"]: e for run in meta["runs"] for e in run["faults"]}

for seed in (11, 23, 37):
    d = root / f"seed_{seed}"
    split = json.loads((d / "split.json").read_text())["indices"]
    config = json.loads((d / "config.json").read_text())
    summary = json.loads((d / "summary.json").read_text())
    p = d / "validation_predictions.npz"
    assert hashlib.sha256(p.read_bytes()).hexdigest() == \
        summary["artifact_hashes"]["validation_predictions.npz"]
    with np.load(p, allow_pickle=False) as z:
        assert set(z.files) == {"indices", "labels", "root_logits", "detection_logits"}
        ix, y, r, g = (z[k].copy() for k in
                       ("indices", "labels", "root_logits", "detection_logits"))
    assert ix.tolist() == split["validation"]
    assert not (set(ix.tolist()) & set(split["train"]))
    assert not (set(ix.tolist()) & set(split["test"]))
    assert (len(ix), r.shape, g.shape, y.shape) == (78, (78, 12), (78, 2), (78,))
    assert config["services"] == services

    for i, label in zip(ix, y):
        w = meta["windows"][int(i)]
        if label == -1:
            assert w["event_id"] is None and w["root_fault_group"] is None
        else:
            hits = [events[eid] for eid in w["event_id"].split(";")]
            assert {int(e["root"]) for e in hits} == {int(label)}
            assert all(services[int(e["root"])] == e["service"] for e in hits)

    faulty = y >= 0
    predicted_fault = np.argmax(g, axis=1) == 1
    credit = []
    for row, truth in zip(r[faulty], y[faulty]):
        true_score = row[int(truth)]
        above = np.count_nonzero(row > true_score)
        ties = np.count_nonzero(row == true_score)
        credit.append(1.0 / ties if above == 0 else 0.0)
    credit = np.asarray(credit)
    tp = int(np.count_nonzero(predicted_fault & faulty))
    fp = int(np.count_nonzero(predicted_fault & ~faulty))
    fn = int(np.count_nonzero(~predicted_fault & faulty))
    f1 = 2 * tp / (2 * tp + fp + fn)
    print(seed, "labels", dict(zip(*np.unique(y, return_counts=True))),
          "conditional/gated", float(credit.mean()),
          float((credit * predicted_fault[faulty]).mean()),
          "F1", f1, "wrong", int(np.count_nonzero(credit < 1)))
```

실제 출력 요약:

```text
11 labels {-1: 13, 0: 4, 1: 9, 2: 5, 3: 6, 4: 3, 5: 5, 6: 10, 8: 9, 9: 5, 10: 1, 11: 8} conditional/gated 0.9230769231 0.8923076923 F1 0.9692307692 wrong 5
23 labels {-1: 13, 0: 4, 1: 9, 2: 5, 3: 6, 4: 3, 5: 5, 6: 10, 8: 9, 9: 5, 10: 1, 11: 8} conditional/gated 0.9846153846 0.9846153846 F1 0.9770992366 wrong 1
37 labels {-1: 13, 0: 4, 1: 9, 2: 5, 3: 6, 4: 3, 5: 5, 6: 10, 8: 9, 9: 5, 10: 1, 11: 8} conditional/gated 0.9538461538 0.9538461538 F1 1.0 wrong 3
```

검사 중 assertion 오류는 없었다. 이 검사는 validation의 수치/메타데이터 대응만 다룬다. 공유 사건·recording에 따른 일반화 한계나 원시 관측값의 정합성은 다시 열람하지 않았으며 판단하지 않는다. test 성능도 평가하지 않았다.
