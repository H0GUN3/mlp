# RCA guarded schema/input cost audit

Frozen split SHA256 `1644bb875d061884b8dff37203b07761bd5f11ae3f3e9ed7f8f44687eb3142e5`; Python3.10/PyArrow19.
TRAIN108 telemetry; validation36 schema/footer-time/service IDs only. Final36 case files not opened.
Input feasibility only: no templates, Hawkes extraction, feature/model training, new candidates or graph adoption.
**Labels:** publisher nominal normal `<inject_time`, faulty `>=inject_time`; not verified physical activation or fault duration.

## Export and cost coverage
|System|normal original rows|profile samples|TRAIN windows|nonempty raw service fits|canonical N|observed TRAIN N|
|---|---:|---:|---:|---:|---:|---:|
|OB|4771132|10|7732|69254|15|15|
|TT|6669330|10|7776|165983|69|69|

JSONL order: case, raw service (null first), timestamp, original source row; no deduplication/string cleaning/null replacement.
Clipping uses own inclusive metric range and strictly pre-injection timestamps. Missing/outside rows and boundary/tail-window events are counted per case.
Profiles retain every source event, fixed10s half-open bounds, both nominal periods, beginning/middle/end and smallest/largest counts. Selection uses counts/time only.

## Evidence-backed schema issues
- **OB TRAIN:** metric rows 77377; family-column counts `{'cpu': 594, 'mem': 596, 'diskio': 360, 'socket': 596, 'workload': 594, 'error': 144, 'latency-50': 540, 'latency-90': 540}`; absent fields 1236, null cells 19257 (unknown rows 0), constant fields 837. Missing error fields are unknown, never zero errors.
- **OB services:** real unknown TRAIN `[]`, validation `[]`; logs-only TRAIN `[]`. All raw IDs, proxy sightings and unmerged alias hypotheses are retained in manifests.
- **OB log placement:** `{'nominal_normal': 4771132, 'nominal_faulty': 4468819}`.
- **TT TRAIN:** metric rows 77814; family-column counts `{'cpu': 3672, 'mem': 3674, 'diskio': 3618, 'socket': 3674, 'workload': 1482, 'error': 477, 'latency-50': 1482, 'latency-90': 1482}`; absent fields 9831, null cells 134079 (unknown rows 0), constant fields 2217. Missing error fields are unknown, never zero errors.
- **TT services:** real unknown TRAIN `[]`, validation `[]`; logs-only TRAIN `[]`. All raw IDs, proxy sightings and unmerged alias hypotheses are retained in manifests.
- **TT log placement:** `{'nominal_normal': 6669330, 'nominal_faulty': 6264579}`.
- Exact exclusions remain BlackHoleCluster, PassthroughCluster, InboundPassthroughClusterIpv4/Ipv6. Cost exports do not drop these or unknown IDs.
- TRAIN startTime/startTimeMillis rowwise coordinate agreement is recorded; us/ms start coordinates are supported by scale/epoch comparison. RCA duration is int64 without unit metadata: microseconds remains an assumption, not certified provenance. Native Jaeger conversion is evidence for native data only.
- Arrays use W×N×10×8 metric float32, W×N×10×2 trace float32, W×N×E log float64. Exact byte coefficients for current/observed N and explicitly validation-derived estimates are in manifests; E/solver cost remain unknown until later TRAIN-only profiling.

## Verification and provenance
144 final-open and 3 validation-value requests rejected before disk access; clipping, Unicode/null preservation and row-completeness self-checks passed. All exported rows round-trip unchanged; per-case source-row/order hashes, full footer fields and bounded case/partition/file ledger are in JSON.
Preimplementation probe: six TRAIN footer opens recorded separately. Initial bounded old-features read exposed TRAIN/validation vectors; none influenced sampling or decisions, and no final features existed there. Exporter uses metadata header only.
Outputs below record SHA256 and bytes; JSON self hash is recorded in successful monitor OUTPUT_HASH output.

- `rca_schema_audit.py` (49807 bytes): `82769686a92620dcfe83d4264c3870ece8493c96c655b04237b71e9db1ea709b`
- `normal_logs.jsonl` (675279381 bytes): `43bae57dbbb3237441f923c09626b65bfa8b043471f2f3ce799ff12e8c55a66d`
- `profile_windows.json` (201601 bytes): `5290ad161c2cd7d204e7bd40cd77e58ddcd439ab58c49adbcc5b3d0263920a22`
- `manifest.json` (11658 bytes): `8fce150ef6ae02c9150c22c159135a04a9658fcf6ab8bd393427887d435ab873`
- `normal_logs.jsonl` (3329121536 bytes): `f9d87228518b7e7119913c1aa34681f520be616a27099f4e726727fa5628e6a4`
- `profile_windows.json` (835017 bytes): `f97c3ecb5ac0d8d5eb549534dda1784f4b342a2146dbd01e9d94c3ffb875fc73`
- `manifest.json` (21015 bytes): `f0ca1afc3cb4ae0b34c8e646f9cb64c694a8d6eccb999c3b4066d83a3463c7d6`
