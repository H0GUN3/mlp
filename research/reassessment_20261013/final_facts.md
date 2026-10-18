# Final factual review

**Verdict: PASS**

No factual blocker found in `다섯질문_답변.md`. PASS is limited to the claims checked below; it does not establish paper reproduction or the unknowns the draft already labels.

| Claim checked | Finding / evidence |
|---|---|
| DiagMLP original SN 80.2%, TT 98.5%; local 96.3%, 81.5% | Verified against the public arXiv **v2** Table IV (SN and TT rows, DiagMLP Top-1) and local `research/mlp_prerequisites/verification.json` `comparison[]` (`diagmlp_common`, 18 validation cases, 3 seeds). The primary manuscript is https://arxiv.org/html/2501.02766v2, Table IV; the proceedings PDF was not checked. Draft correctly distinguishes systems and protocols and calls the local result an adaptation, not reproduction. |
| Eadro HR@1 = .982 | Verified in the primary paper’s §V-F, reported average HR@1; https://arxiv.org/html/2302.05092v1, §V-F. It is not the local adapted model’s score. |
| BARO size and Avg@5 meaning | Primary BARO §4.1 specifies 100 injection cases per system across Online Boutique, Sock Shop, Train Ticket (4 fault types × 5 targets × 5 repeats), hence 300 total. §4.2.2/Table 3 defines Avg@k as the average of AC@1 through AC@k; Train Ticket Avg@5 is .81. Thus it is neither AC@5 alone nor a single Top-5 hit rate. https://arxiv.org/html/2405.09330v1, §§4.1–4.2.2, Table 3. |
| Local RE2 split and coverage | `split.json` plus `adequacy.md`: 180 cases = 60 distinct system/root/fault scenarios × 3 repetitions; per system 54/18/18 cases and 18/6/6 scenarios across train/validation/test; five root services and six faults. Counts are metadata only; no final-test raw, feature, or prediction data were opened. |
| ops-lite metadata/sample | Correct root-relative files: `evidence/ops-lite-summary.json` reports 455 labels and 30 samples; `evidence/ops-lite-sample-audit.json` records ten normal/abnormal traces, logs, metrics, histogram, and sum files per sampled case (300 decoded files); `ops-lite-sample.json` lists 30 names. A bounded search of `data/ops-lite/manifest.jsonl` matched all 30 names. Whether this local subset is the official OpenRCA 500-case release remains **unknown**, not asserted as equivalent. |
| Repeated validation error | Saved local validation evidence and `adequacy.md` identify the single case `re2tt_ts-train-service_delay_2`: across seeds 11, 23, and 37, the predicted root is `ts-travel-service` instead of `ts-train-service`. This is one case repeated across seeds—not all three delay repetitions. The draft states that distinction correctly. |

Checked primary-paper sections/tables and the named local metadata/results reports. No final-test data were opened; no model training, package installation, author contact, or dataset download was performed.
