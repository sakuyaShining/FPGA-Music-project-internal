# Immutable frame-format source and tokenized contact transport

Status: implemented frame-format source plus command ledger, **not analog scanning, a complete finger-pitch consumer, score/audio integration or a final instrument**. Base82d37271. Original producer/current files remain unchanged.

`contact_frame_source` accepts the captured bridge's contact/invalid bitmaps,9-bit per-contact positions, caller-resolved note map, sequence/calibration marker, resolved8-bit velocity/glide/layer selection. It freezes the entire accepted frame. Later changes on those input pins cannot change queued commands. DefaultNF26 follows the captured prototype parameter; it does not decide25/26 physical endpoints, a panel note map, pressure calibration or a new pitch scale.

`note_frame_transport` connects that source to `note_contact_adapter`. ON snapshots issue a source-global token; queued release/movement retains that full token sampled from the current row, never a generation-only lookup. Anchor pulses expose accepted ON contact/position for a future full-layer expression consumer. The returned full allocation map and motion group/layer masks are preserved; no first-group reduction is introduced. The actual finger consumer still has to bind the confirmed groups and receive allocator reuse/publication notifications.

## Lifecycle and fault boundary

- Normal held motion does not generate another ON. Resource retirement removes ownership but does not clear physical seen state or retrigger a held contact. Only a real release rearms a new edge.
- Release can reach the ledger while an ON is still awaiting admission. The matching cancellation stays tokenized; the backend must confirm cancellation rather than leave an unconsumable ALLOCATED response. The test server implements that withdrawal/confirmation contract, but remains a stub, not the real manager.
- Invalid frames preserve the earlier contact while below the configured consecutive-bad threshold, then force release/quarantine. Calibration, sequence discontinuity or stale-frame watchdog force release and block held contacts until a valid physical release.32-bit sequence wrap is continuous;8-bit contact generation wrap does not reuse global tokens.
- LINK_TIMEOUT covers both a stalled ON/release command and an accepted transaction until its completion reply is consumed; it never drops or rewrites the unresolved request. This retains the original REPLY-wait diagnostic, not merely input-ready stalls. A stale-frame recovery is serviced after the frozen current frame/command completes. No worst-case physical latency is signed off, particularly with an unresponsive downstream.
- Zero resolved layer selection cannot issue the ledger's invalid zero-layer ON or deadlock a frame. The source records admission_error and seen state without admission, and requires release before another edge. This is an invalid-admission transport safeguard, not approval of an editor/all-slots-off user workflow or changes to in-flight notes.
- Source, ledger, router, backend and eventual expression consumer require one common reset fence. Original sensor/fault/watchdog policy is retained at this boundary, not replaced with a happy-path pulse adapter.

## Verification boundary

Independent frame-semantic traces coverNF4/four layers and defaultNF26/single layers, plus event/reply backpressure. Deliberate corruption of external fields after frame acceptance tests whole-frame freezing. Tests include retirement while held, bad-frame quarantine, calibration, sequence gaps and wrap, watchdog, zero-layer liveness, generation wrap and physical release during delayed admission. Boundary observations verify timely release/quarantine, rather than only eventual ON/OFF counts. Five designated mutants detect mutable-frame position, held retrigger, ignored sequence gaps, missing watchdog recovery and missing accepted-transaction timeout. Compile errors, timeouts and incomplete traces cannot substitute for those counterexamples.

The frame path's new full-constraint scan-shell PnR again exits0xC0000005 at routing80%, with no STA. Its fixed diagnostic pins/27MHz envelope are not the PCB interface. Retain the actual source/tool/report identities and failed timing; do not download the diagnostic image or replay old17-case crash experiments. No original golden data or current product source was changed.

Next connect the full-layer finger consumer and actual allocator/renderer, then the score source/backpressure/automatic OFF and complete device top. Octave-in-flight, normalization/transposition, edit/apply/save, recording scope and screen/GPIO remain separate pending decisions. D-019 is unchanged and P-020 remains unapproved. No programming, Flash, CAD or manufacturing operation is authorized.
