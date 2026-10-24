# Real four-slot note partial renderer candidate

This incremental candidate replaces the external testbench partial provider in the previous audio probe. `note_resource_instrument_probe` accepts logical note/configuration requests, snapshots the note and four-slot configuration, generates actual partial payloads in RTL, then drives the shared32-group coordinator and real512-partial TDM/envelope core. It does not replace the captured `fpga/current` checkpoint or the original producer workspace.

## Implemented boundary

- Real `instrument_table` two-bank/full16-word commit interface, selected-bank snapshots and all four slots, including custom88-bit partial/envelope definitions.
- Captured note/preset/brightness/slot-velocity tables and legacy spectrum, pad-mask, strike-curve and independent-envelope payload math; explicit glide field passes through.
- One locked note context through admission/cancellation; held query responses retain token/ticket/layer/partial identity under backpressure. Concurrent configuration commit takes precedence over a new note, preventing mixed definitions during one admission.
- `vel_shape_scaled` fixes inherited signed-delta width overflow for non-default velocity scales. The captured original and ROM remain unchanged. See `VELOCITY-SOURCE.json`; this is arithmetic correction, not new calibration or default timbre.
- Existing real-audio PREPARE/PUBLISH/RETIRE/FINISH transaction protocol remains unchanged. D-019 source-neutral, tail-first whole-note allocation is retained. Immediate RETIRE is still experimental; proposed0.5ms fade has not been approved.

## Reproduce in fresh directories

Run with Python and Icarus/vvp (`FPGA_IVERILOG`/`FPGA_VVP` or PATH); outputs must not already exist or be inside the repository:

```powershell
python experiments/note_resource_20261024/audio/renderer/verify_renderer.py --fault-checks --output D:/FPGA-Project/review/my-renderer
python experiments/note_resource_20261024/audio/renderer/verify_velocity.py --output D:/FPGA-Project/review/my-velocity
python experiments/note_resource_20261024/audio/renderer/verify_instrument.py --output D:/FPGA-Project/review/my-instrument
python experiments/note_resource_20261024/audio/renderer/synthesize_instrument.py --output D:/FPGA-Project/review/my-instrument-synthesis
python -m unittest discover -s experiments/note_resource_20261024/audio/renderer/tests -v
```

The synthesis command uses an installed Gowin tool and runs synthesis only, not PnR/STA/programming. Exact source/tool hashes, commands and compressed traces are bound by `project/versions/note-partial-renderer-20261024.json` and its review directory.

## Evidence and limits

- Final renderer02: independent integer oracle checks16384 partial vectors in each of the captured-ROM and distinct-slot diagnostic fixtures. Four faults (wrong slot, velocity disabled, live tilt leaking into a snapshot, old signed widths) are detected at amplitude mismatch, not compilation/timeouts. Diagnostic ROM changes exist only in the exported negative/control fixture, not product ROM.
- Actual renderer-to-audio02:546 logical requests,5136 accepted payloads independently checked,4080 PCM frames/4049 nonzero,551 publications and6 whole-note retirements. Default-scale trace is exactly equal before/after the width correction. Logical note and config stimuli remain synthetic; PCM equality here is a regression comparison, not an independent complete PCM oracle.
- Velocity regression:2097152 vectors over1024 ROM addresses,256 base amplitudes and8 scales;524288 default0/256 cases exactly match original,218790 non-default corrections. Before-fix renderer01/reference and synthesis01 are historical reproduction, not acceptance of the old overflow.
- Same-source integrated instrument synthesis is recorded separately. A smaller logical-input core does not prove complete-device fit. No candidate PnR, valid STA, bitstream or board acceptance exists for this RTL.

Still missing: physical finger edge/move and score/live source routing, auto-release scheduling for strike modes, automatic reuse-derived glide, ongoing-note refresh, final transpose/normalization/edit application semantics, full PCM/transient/listening acceptance, J10/84-node scan integration, standalone editing/nonvolatile/file recording and complete product top/PnR/STA. Snapshot isolation is an admission transaction contract, not approval of final edit/ongoing-note policy. No download, Flash operation, PCB interface change or manufacturing release is authorized.
