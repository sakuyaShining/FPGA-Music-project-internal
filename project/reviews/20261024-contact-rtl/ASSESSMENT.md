# Contact command transport RTL: bounded implementation review

## Functional increment and acceptance limit

The new `note_contact_adapter` implements the previously reviewed contact transaction contract, not a new allocation policy. It freezes accepted ON payload and source-global serial, retains complete layer ownership, suppresses held retrigger after whole-note retirement, rejects stale operations and handles cancellation during send/wait and on the allocation-response clock. Motion carries all surviving groups without generating another ON. An old tail completion cannot restore ownership into a newly reused contact row; retirement/release wins over old motion. Completion replies are immutable under consumer backpressure.

Final replay05 compares7521 cycles across source0/source1 with31-bit wrap and narrowed3-bit epoch exhaustion. Independent lifecycle operations come from the committed ContactLedger, not RTL state readback. Five mutated RTL sources fail their designated fields: global token, held retrigger, all-layer movement, allocation/cancel race and old-tail/new-ON ownership. Wrong response tokens/code7, incomplete/duplicate maps, natural completion plus allocation, release plus movement, output stalls and common reset are included. The five unit tests from the initial increment plus a diagnostic-wrapper port test bring the full local suites to97 tests.

This is a **command-level RTL endpoint with stub allocator responses**. The actual immutable-frame bridge, per-layer finger consumer, score pulse transport, real renderer/PCM path and complete top have not been connected to this endpoint. No physical endpoint count, pressure calibration, octave-in-flight behavior, normalization/transposition, editor/save, recording or screen/GPIO rule is selected here. D-019 remains unchanged; P-020 remains unapproved. The endpoint must not be presented as the finished sensor path or as an integrated product.

## Original failures and timing evidence

- Replay01 generated invalid Verilog parameter names because placeholder replacement also touched `.SOURCE`/`.INITIAL_SERIAL`; compilation failed and no mutant qualified. Original script and exported benches are retained.
- Replay02 passed all candidates, but the legacy-token mutant first changed non-designated readiness before event_token. The run correctly remained FAIL. The repaired verifier records first overall and first designated differences separately, and never accepts short/unknown traces or compile/timeout failures as targeted counterexamples.
- Replay03 passed;04 added distinct-map and additional completion/movement races;05 binds the final contract documentation. All original inputs/results/logs and compressed traces remain in the archive and original D directories.
- Full-constraint standalone diagnostic timing01 completed synthesis and reached routing80%, then the actual process23560 exited0xC0000005. Windows event1000 matches that PID, gowin.dll and offset0x1c9f10. No STA exists. The result is FAIL_OR_INCOMPLETE_TIMING, not fit/STA success and not a proven internal vendor defect mechanism.
- The build completed with an unchanged source guard. Later fixture additions changed the reference generator file, but both the final RTL and regenerated diagnostic wrapper still match the original build byte-for-byte; original generator/source hashes remain recorded. No failure is cleared and the same crash is not blindly rerun. A separately qualified tool/workaround remains needed.

The scan shell's fixed pins and27MHz timing envelope are diagnostic only, not a PCB interface. No image was programmed, Flash written, CAD modified or manufacturing released. Product/current sources remain unchanged.

## New hardware handoff: observed progression, failed closure

The registered06df construction-state changed from the a3a258/49issues13nets620vias checkpoint to an owner-reported951ce88a/42issues12nets/227components649vias. It now points to a separate D:/codex-deliverables handoff root, registered explicitly as a fourth active producer. Exact current owner thread and a recoverable current native CAD archive are not verified here. These observations do not overwrite the old captured native ZIP or pretend it contains951.

The current-next document reports an ADDR2 repair and completed native DRC/reopen, but marks native_stage_pass=false and manufacturing=false/physicalUNMEASURED. Its all_current_jobs_terminal=false is stale relative to the separate full-review-state: that job is terminal with AssertionError, citing ADDR2/Inner16 closed-set copper differences (about0.003612/0.003606mm2). These are conflicting stage/status observations, not a passing whole-board review. No geometry job, CAD replay, native apply, DRC or ownership takeover was performed by this session. The original owner must resolve and hand back complete source-bound evidence.

Reviewing and capturing these changed handoff documents renews only their actual source observation/classification. It does not qualify a board, inherit prior PASS or make all local CAD state visible to GitHub. A later change to these live inputs still requires another observation and review. PR4 remains an unmerged candidate; actual main is the only published authority.

## Entry identity gate

The first full-content check rejected the new PRODUCT-SPEC/WORK-PLAN paragraphs because their separate reviewed-design fingerprints had not yet been updated. Its original FAIL log is retained. The bounded endpoint and still-failed hardware/timing scope were then explicitly added to DESIGN-CURRENT, design-state and the state/handoff registries, with a new contact-command-endpoint candidate identity and reviewed document hashes. Old recoverable checkpoints and the latest integrated router profile remain separate. This is not a source snapshot replacement or a hash-only product acceptance.
