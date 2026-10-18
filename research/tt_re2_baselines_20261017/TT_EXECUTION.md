# TT 기준선 실행 영수증

2026-10-17. 동결 TT_PROTOCOL.md와 입력/모델 source를 유지했다.
완료 모델은 Eadro/DiagMLP × seed11/23/37의6개이며,각50epoch/650update다.
validation은선택자료이며최종시험성능이아니다.

## 실행 전

mon_HP14VG6XRCKJ527N의실제exit0:
6개focusedtests OK, owned-projectPyright0errors/0warnings/0informations,
TT_INPUT_PASS4069 27. TT_INPUT_CHECK.json에허용입력/분할/source해시가있다.
앞선검사에서는numpy.int64 JSON직렬화실패가있었고,
TT_INPUT_CHECK.failed.partial및원래모니터에보존했다. 학습전실패다.
native단일파일LSP의환경import해석차이는숨기거나억제하지않았다.

## 중단·복구

최초3monitor는기본시간제한으로exit1(timed_out).
pgrep으로해당학습프로세스가종료됐음을확인했다.
Eadro11은45epoch,23은47epoch까지만완료되어optimizer상태없이이어학습하지않고,
모든부분산출물을interrupted_attempts아래hash동일하게보존한뒤동일seed로재시작했다.
Eadro37은50epoch와best/last/history가이미완성되어학습을반복하지않았다.
그가중치의후처리/재추론만복구했다. DiagMLP3실행은각최초실행이다.

총학습시작8회중완료6회/중단2회이며,중단을추가독립seed로세지않는다.
동결tt_runner.py/test/TT_PROTOCOL/native sources는복구때도수정하지않았다.
recover_tt.py는부분산출물보존과seed37후처리만담당한다.

## 실제 성공 종료 기록

절대경로 실행기와기존.venv-eadro/Python3.8환경,
OMP/MKL/OPENBLAS2threads, bytecode off, Python assertions enabled.
복구모니터는timeout_ms1800000을명시했다.

| seed | monitor / parent session | 실제 결과 |
|---|---|---|
| 11 | mon_PFD1H8N5ABR0DP7J / bash_22 | completed exit_code0; TT_INTERRUPTION_ARCHIVED11 45; TT_FIT_PASS eadro11 50; TT_FIT_PASS diagmlp11 50 |
| 23 | mon_FP88Z2C4WD8FM7KP / bash_21 | completed exit_code0; TT_INTERRUPTION_ARCHIVED23 47; TT_FIT_PASS eadro23 50; TT_FIT_PASS diagmlp23 50 |
| 37 | mon_5H31W46VJWB97P28 / bash_20 | completed exit_code0; TT_RECOVERED_POSTPROCESS eadro37 50; TT_FIT_PASS diagmlp37 50 |

주담당이모든완료session의bash_output을읽어위exit/sentinel을확인했다.
완료run별summary에는선택/최종checkpoint의TRAIN/validation예측4개의
새모델재추론bitwise일치기록이있다.

독립NumPy채점·선택규칙·해시·중단epochprefix대조는verify_tt.py의
별도TT_RESULTS.json/PASS와실제종료기록을요구한다.
학습성공만으로그독립검증이끝났다고주장하지않는다.

원래TT시험1744행과미배정1행은접근하지않았다.
seed37의시간은epoch별기록합이며checkpointIO시간을빠뜨리므로,
실행시간비교로효율우위를주장하지않는다.
