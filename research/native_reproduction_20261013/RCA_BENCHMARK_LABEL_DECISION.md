# RCA benchmark labels versus independently verified physical intervals

The [pinned publisher card](https://huggingface.co/datasets/phamquiluan/RCAEval/blob/afeacb11bcc94dadfd1c8f483ee4377b2b8b614e/README.md)
explicitly states:

> `inject_time.txt` splits each case into a normal period (before) and a faulty period (after).

Its example likewise uses `< inject_time` and `>= inject_time`. The inventory
names the case service as the ground-truth root.

This is a usable **benchmark annotation convention**. Missing independent
activation/termination measurements do not make that published convention
nonexistent. An encoder-preserving native-method port can be compared against
other methods on these same nominal labels, provided the convention, missing
interval verification and domain changes are disclosed.

The distinction in `rca_native_label_contract.md` remains important:

* **Verified:** what the distributor defines as normal/faulty and root service.
* **Not independently verified:** when the injected fault actually became active,
  whether it persisted for the full post-boundary recording, and recovery timing.
* **Not justified:** presenting these labels as independently observed physical
  intervals, or calling this an exact reproduction of the Eadro experiment.

Do not impose a hidden requirement for physical activation measurements on
RCAEval while accepting another dataset's nominal injection records without
equivalent physical verification. Nor should a new label interpretation be
silently chosen from high-anomaly segments.

## Subsequent port boundary

If proceeding after native calibration, freeze full 10-second windows within
each case and wholly on one side of its supplied boundary. Use the publisher's
nominal labels, preserve joint detection/localization loss and native modality
encoders, and explicitly name the result a **native-method RCAEval port under
benchmark labels**, not an author checkpoint or exact paper-score reproduction.

Keep current train108/validation36/final36 groups unchanged and final36 sealed.
Fit learned templates and shared transformations on training information only.
The source-like stateless case normalization is specified in
`RCA_NORMALIZATION_SCOPE.md`; it assumes the full case is supplied for offline
diagnosis, not ten-second early prediction. Freeze channel/missingness,
candidate identity, topology and per-case aggregation rules before training;
none may be chosen after examining whether delay_2 becomes correct.

This decision permits a properly qualified comparison; it does not report that
the port was implemented, that the old error persists, or that a proposal helps.
Unrelated Eadro errors still do not establish persistence of the RCA incident.
