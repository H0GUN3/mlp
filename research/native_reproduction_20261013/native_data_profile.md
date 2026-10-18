# Native Eadro data profile

## Scope and execution evidence

Raw access was limited to authorized `data/eadro_native/SN_Dataset/SN Dataset` and `TT_Dataset/TT Dataset` trees. No RCAEval raw access, installs, downloads, extraction, mutation, preprocessing, training, or split selection occurred.

`native_data_profile.py` ran under `.venv-eadro`: Python 3.8.20, NumPy 1.21.5, pandas 1.4.2, tick 0.7.0.1, torch 1.12.1+cpu, DGL 0.9.1. Synthetic parser checks and the full monitored run exited **0**; source diagnostics were clean. Additional summary consistency assertions passed. The 174,333-byte JSON contains counts, schemas, source paths, and time ranges—not raw telemetry. Every metric cell/log timestamp was checked; spans were streamed for full counts/time ranges, with structural schemas sampled from the first 64 traces/spans per session.

Rerun, without writing or extracting data:

```sh
.venv-eadro/bin/python -B research/native_reproduction_20261013/native_data_profile.py
```

Output is progress plus `PROFILE_PAYLOAD` (base64/gzip JSON). The checked JSON was saved with `apply_patch`.

## Actual observations, not paper-imposed counts

| Quantity | SN | TT |
|---|---:|---:|
| `data/` fault-record JSONs / recording folders | 4 / 4 | 9 / 9 |
| Fault events per record | 9 | 9 |
| **Annotated fault events** | **36** | **81** |
| Unique injected roots / root–fault conditions | 12 / 36 | 27 / 81 |
| Occurrences per root–fault condition | exactly 1 | exactly 1 |
| Events per type (`cpu_load`, `network_delay`, `network_loss`) | 12 each | 27 each |
| Injection duration | 120 s each | 600 s each |
| Additional no-fault-collection recordings | 3 | 3 |
| Distinct recording sessions including these | 7 | 12 |
| Available metadata JSONs including no-fault | 7 | 11 |

Thus this acquired SN corpus establishes **36, not 72**, annotated injections; archive duplication does not double them. These are injections, not independent window counts. There are no repeated annotated root–fault conditions in this release.

Fault-record durations (`end-start`) are SN 1,410.266–1,412.998 s and TT 6,460.375–6,461.776 s. Annotated no-fault recordings last SN 1,441.232–1,441.305 s and TT 8,106.691–8,106.962 s. TT's third no-fault-collection recording has no metadata JSON; its filename spans 8,107 s. Do not invent an annotation for it.

## Inner archives: duplicates versus additional sessions

All regular members were read without extraction. SHA-256 compared each all-data member with its corresponding loose file, including fault metadata:

| Archive | Regular members / contents | Result |
|---|---|---|
| `SN-all.tgz` | 60: 4 records, 4 logs, 4 spans, 48 metric CSVs | **60/60 byte-identical**, no additions |
| `TT-all.txz` | 270: 9 records, 9 logs, 9 spans, 243 metric CSVs | **270/270 byte-identical**, no additions |
| SN no-fault `.tar.xz` ×3 | 14 each: logs, spans, 12 CSVs | three additional dated sessions |
| TT no-fault archives ×3 | 29 each: logs, spans, 27 CSVs | three additional dated sessions |

SN additions are `2022-04-20T182405`, `2022-04-21T105249`, `2022-04-21T153302`. TT additions are `2022-04-20T134450` inside `TT-no-fault.txz`, and `2022-04-21T105158`, `2022-04-21T153246` inside individually named archives. No no-fault archive contains fault metadata; corresponding JSONs are alongside archives, except the missing TT April-20 record.

These add recording paths/time intervals, not additional annotated faults. This does **not** establish uniqueness of every underlying trace ID across sessions.

## Correspondence and implementation contracts

`datasets.{SN,TT}.record_to_folder_correspondence` in JSON records **every** original record path, matching folder, and source parser index. Removing `.fault-` from each metadata basename gives the corresponding session basename; independently sorted record/folder indices agree for all 4 SN and 9 TT records. No unmatched metadata was found.

Examples:

- `data/SN.fault-2022-04-17T181245D2022-04-17T183616.json` → `data/SN.2022-04-17T181245D2022-04-17T183616`.
- `data/TT.fault-2022-04-17T212101D2022-04-17T230842.json` → `data/TT.2022-04-17T212101D2022-04-17T230842`.

Each session's `source_paths` identifies `logs.json`, `spans.json`, and `metrics/{service}.csv`; archive sources use `archive!member` notation. Preserve these provenance links rather than relying solely on numeric indices.

- Metadata: object with floating-second `start/end`, `faults` list; fault `name/fault` strings, `start` float seconds, `duration` integer seconds. SN container names map by removing `socialnetwork-`/`-1` (nginx special case); TT uses the underscore-delimited service component. All roots match the original `Info` service list.
- Metrics: header `timestamp` followed by `cpu_usage_system,cpu_usage_total,cpu_usage_user,memory_usage,memory_working_set,rx_bytes,tx_bytes`; pandas parsed timestamp `int64`, all metrics `float64`.
- Logs: service-keyed object of string lists, not parsed templates or an `event` column.
- Traces: top-level list of Jaeger objects; `processes` maps process IDs to `serviceName`, and `spans` contains string IDs/process references plus integer-microsecond `startTime/duration`. `warnings` can be null or list.

## Quality and alignment findings

All **19 recordings** contain logs, spans, and all expected metric CSVs/log service keys. Across **408 CSVs / 2,346,330 metric rows**, no missing/extra columns, NaN/non-numeric/infinite cells, duplicate/nonintegral timestamps, backwards steps, or non-1-second steps were found. Service time ranges agree within each recording. TT has constant columns: 126 service-recordings each for `memory_usage` and `memory_working_set`, 60 for `tx_bytes`; constant is not missing.

All 94,319 SN and 124,571 TT log lines match/parse using the upstream timestamp formats. Nevertheless 7–8 SN and 12–14 TT services have empty log lists per recording. SN spans cover all 12 services; TT recordings omit spans for 8–14 of its 27 services. File presence is not per-service signal completeness. Counts are SN 87,984 traces / 1,438,191 spans; TT 28,648 / 290,941. No unknown service or unresolved process reference was observed.

**Offset comparison only:** filenames/text timestamps are UTC-coordinate wallclocks, not asserted timezone truth. Against [the pinned fork](https://github.com/FeiGSSS/Eadro/tree/7d69281a80adce60067aa858729746fc6a362f53/codes/preprocess) functions `parse_raw_records.py:process_raw_records`, `parse_raw_metrics.py:process_metrics`, `parse_raw_traces.py:parse_spans`, and `parse_raw_logs.py:extract_unix_timestamp`:

- `int(record start/end)+16h` exactly matches every available filename endpoint.
- `metric timestamp+16h` covers filename start through **end−1 s** in every recording.
- `span startTime/1e6+8h` brings recent spans near filename intervals, but files also contain **historical out-of-interval spans**: SN April-21 starts as early as −58,057.217 s; TT fault recordings as early as −165,820.828 s. TT April-18 `150729` ends 2,736.790 s early. Whole-file trace ranges cannot be assumed confined to their recording.
- Upstream log parsing applies **no shift**: observed log ranges sit approximately **8h before** filename/source-shifted metric intervals. Adding 8h is recorded as an observational comparison only; it is not an adopted correction. Source behavior would miss these logs in shifted recording windows.

No offsets were selected by accuracy, and no issues were silently repaired. Chronological trace provenance, the missing TT no-fault annotation, and these time-coordinate mismatches remain parent implementation decisions. This profile establishes corpus counts/schema issues, **not successful preprocessing or model reproduction**.
