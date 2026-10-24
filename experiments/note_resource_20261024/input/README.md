# Tagged score/live input router candidate

## Frame-format source increment

`rtl/contact_frame_source.v` and `rtl/note_frame_transport.v` now connect the captured immutable-frame interface format to the tokenized command ledger. See `FRAME-SOURCE-CONTRACT.md` and `project/versions/note-frame-source-20261024.json`. Default26-contact and four-layer small-interface traces, backpressure, quarantine/watchdog and release-during-admission cancellation are tested against independent frame semantics. This is still not analog scanning or the full-layer finger/score/real-audio path; allocator replies remain stubs. New full-constraint diagnostic PnR also fails at routing80% with0xC0000005/no STA.

```powershell
python experiments/note_resource_20261024/input/verify_frames.py --fault-checks --output D:/FPGA-Project/review/my-frame-source
python experiments/note_resource_20261024/input/build_frames.py --output D:/FPGA-Project/review/my-frame-unit-timing
```

`note_duet_probe` adds two equal logical ready/valid input ports ahead of the real four-slot renderer/resource/TDM candidate. This is an input transport stage, not the completed physical contact/score-file adapter or full instrument. Original current checkpoints and producer roots remain unchanged.

## Contract

- Live tokens are `{0, serial31}`, score tokens `{1, serial31}`. Sources provide a new monotonically advancing serial for each ON, preserve that serial for its OFF, and do not reuse a full token in one reset epoch. The manager's half-range serial ordering remains applicable. A MIDI pitch,13-bit old contact ID or group number is not an adequate replacement token.
- Both pending sources alternate on accepted requests. Initial deterministic tie phase is live, then the other source gets the next tie; it is not a persistent priority. No score/live resource reservation, layer reduction or weighted stealing is added.
- One entire request is registered, including token, note,8-bit velocity, signed glide and full layer mask. The selected producer holds valid/payload until ready. No upstream acceptance occurs during the outstanding transaction, and downstream stalls cannot change the registered request.
- Responses route only to the matching token's source; wrong/stale token responses are not consumed and set a sticky protocol error. Both consumer valid flags can never be high together. Response payload is a shared bus and must only be used with the corresponding valid signal.
- The native backend cancellation protocol is preserved: an unaccepted ALLOCATED response may be withdrawn and later replaced by CANCELLED while retirement completes. This bridge does not promise that such cancellable responses form an immutable mailbox. It does not consume a response before its selected caller is ready.
- A matching ON cancellation received while the router is waiting for configuration/backend admission is retained until completion and forwarded with its original token. Same-cycle input acceptance/cancel is included in the latch logic. Nonmatching/stale cancels must not target the queued note; one shared cancel port still needs an upstream source adapter contract.
- Reset must flush router, backend and source adapters together. Token equality alone cannot distinguish an unsolicited replay of a previously completed response with the same token; backend response ordering/one outstanding transaction and the common reset fence are required.

## Actual upstream audit

The captured `tdm_top_owned` already contains per-source `event_hold` queues and round-robin arbitration. The old `song_seq` comment saying its events are selected instead of external playing does **not** describe that current top. However, `event_hold` only carries on/pitch/4-bit velocity, not instance tokens or a four-layer completion map. `left_contact_bridge` uses13-bit IDs and a single returned group; `finger_pitch` can support MULTI_BIND but still needs confirmed per-layer ownership. Those interfaces cannot be connected blindly to this new candidate.

Pending: source adapters must create/retain global source serials, handle ON/OFF and contact generations without aliases, stop stolen-held contacts from re-triggering, fan confirmed layer maps into expression ownership, and make pulse-producing `song_seq` backpressure/overflow explicit. Physical scanner mapping,25/26 endpoints, octave-in-flight behavior, score-file/pause semantics and right-hand/edit application rules are not chosen here.

The next contact interface is specified in `CONTACT-ADAPTER-CONTRACT.md` with a transaction oracle in `contact_contract.py`. Eleven tests combine it with the independent shared-resource model; separate isolated variants detect legacy13-bit token alias after256generations, stolen-held retrigger and first-layer-only movement in their designated assertions. This is **not an implemented RTL/physical source adapter** or a new PCM/timing qualification. Both the initial CRLF-verifier rejection and the corrected complete replay are retained in `project/reviews/20261024-contact-contract-intake/`. Score pulse transport, RTL handshake/cancel races, complete-layer expression fanout and actual scanner integration remain next work.

```powershell
python experiments/note_resource_20261024/input/verify_contact_contract.py --output D:/FPGA-Project/review/my-contact-contract
```

## Reproduce

The next bounded increment is `rtl/note_contact_adapter.v`: an implemented ready/valid contact-command ledger with frozen replies and pulse-based full-layer motion, verified against the earlier transaction oracle. It does **not** yet replace/connect the captured immutable-frame producer or `finger_pitch`, and uses stub allocation replies in these tests. See `project/versions/note-contact-transport-20261024.json` for exact inputs/results and the retained failures. The new standalone full-constraint diagnostic also reaches routing80% then exits0xC0000005; no STA is available. Do not download its scan-shell image or describe this as actual scanner/score/whole-instrument integration.

```powershell
python experiments/note_resource_20261024/input/verify_contact_rtl.py --fault-checks --output D:/FPGA-Project/review/my-contact-rtl
python experiments/note_resource_20261024/input/build_contact.py --output D:/FPGA-Project/review/my-contact-unit-timing
```

```powershell
python experiments/note_resource_20261024/input/verify.py --fault-checks --output D:/FPGA-Project/review/my-input-router
python experiments/note_resource_20261024/input/verify_audio.py --output D:/FPGA-Project/review/my-duet-audio
python experiments/note_resource_20261024/input/verify_audio.py --fault-check --output D:/FPGA-Project/review/my-queued-cancel-counterexample
python experiments/note_resource_20261024/input/build.py --mode integrated --output D:/FPGA-Project/review/my-duet-synthesis
python experiments/note_resource_20261024/input/build.py --mode timing --output D:/FPGA-Project/review/my-unit-router-timing
python -m unittest discover -s experiments/note_resource_20261024/input/tests -v
```

All outputs must be fresh and outside the repo; Icarus/vvp and Gowin paths can use the same environment variables as the renderer candidate. Timing mode generates a **non-product diagnostic** image in a scan-register shell. Its fixed pins and27MHz I/O envelope are not the PCB contract. NEVER download this image.

Evidence is bound by `project/versions/note-input-router-20261024.json`. Router01 checks24000 cycles,1713 accepted inputs/1708 responses,1709 simultaneous-source choices,314 wrong-token response cycles,4901 downstream and5832 response-stall cycles,6 reset episodes and one31-bit serial wrap per source;3 designated routing/payload faults are detected. Duet audio06 adds queued-admission cancellation to the earlier stress:547 logical requests,5136 independently checked actual loads,4080PCMframes,551 publications and6 retirements. Its sources are still logical stimuli, not physical scanning or a score file. A separate disabled-cancel-latch mutant fails the explicit cancellation assertion, not timeout/compile failure. After whitespace-only bench cleanup,06 and fault02 rerun against the exact cleaned source;05/fault01 evidence remains unchanged.

Final integrated synthesis03 succeeds; full-device fit and timing remain unqualified. Timing01/02 failed parsing the diagnostic wrapper; timing03 and04 reached route80% then the tool exited3221225477 (0xC0000005), including a different fixed-pin/four-bit shell attempt. No routed timing report exists, so **PnR/STA failed/incomplete**, not passed. Integrated synthesis02 completed its vendor run but was rejected because the build helper changed mid-run; final03 reran with unchanged inputs. Full independent PCM/transient/listening tests, complete product top/PnR/STA, physical input latency, J10/editor/nonvolatile/recording files and the unanswered P-020 fade rule remain open. No programming, Flash, CAD or manufacturing operation was performed.

## Router crash diagnosis supplement

See `project/reviews/20261024-router-crash-diagnosis/summary.json` and `diagnostic-evidence.zip` for the frozen case inputs, tool hashes, logs, constraints and timing reports. Seventeen PnR diagnostic cases retain seven completed routes, nine access violations and one explicitly inconclusive supervisor-aborted case. They are not seventeen successful timing qualifications.

The original router completes with clock-only, clock plus uncertainty, output-only, maximum-input-only or controls-only constraints. Minimum-delay coverage on the four scan-data inputs reproduces the access violation. With **all original constraints retained**, disabling automatic hold correction completes routing but reports **hold -1.402ns**, so this is a counterexample to treating route completion or an `.fs` as acceptance, not a proposed product configuration. Both original failures and later crashes identify `gowin.dll` offset0x1c9f10 in the observed Windows application events; the internal defect mechanism remains unproven.

Registering every shell input together is verified against a one-cycle-delayed original over24000 cycles, including6217loads/17908shifts/6226captures/1466three-way overlaps. A deliberately unaligned load fails the designated state check atcycle58. That shell still crashes under full constraints, as do explicit bus-bit spelling and alternate place/route strategy; none is adopted as a fix. The minimal eight-register full-constraint control completes routing. The separate minimal clock-only run wrote completed console output but never signalled its process handle; its waiting supervisor was explicitly stopped and its `aborted.json` is retained, without a PASS.

```powershell
python experiments/note_resource_20261024/input/diagnose_timing.py --logic router --constraints input-min --input-ports data --output D:/FPGA-Project/review/my-data-hold-reproducer
python experiments/note_resource_20261024/input/diagnose_timing.py --logic router --constraints full --hold-correction off --output D:/FPGA-Project/review/my-negative-hold-counterexample
python experiments/note_resource_20261024/input/verify_timing_shell.py --output D:/FPGA-Project/review/my-shell-alignment
```

Every run requires a fresh non-system-drive directory; exports, vendor temporary files and logs remain there. Reduced constraints are deliberately incomplete and cannot qualify STA. No production RTL, existing pin constraints, product rules, original golden data or other owner's sources were changed. Next investigate an evidence-backed full-constraint hold-repair workaround or a separately installed qualified tool version; do not remove minimum-delay checks, disable repair and hide the resulting violation, or blindly rerun the same crash. Physical contact/score adapters and the complete-device timing target remain pending.
