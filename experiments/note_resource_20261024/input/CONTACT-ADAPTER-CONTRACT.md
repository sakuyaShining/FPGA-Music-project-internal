# Contact identity and complete-layer ownership: implementation oracle

Status: internal interface contract and Python oracle, **not an RTL adapter, physical sensor integration, measured latency or product acceptance**. Base input is642b2df9. D-019 and the existing resource manager define allocation; this document does not introduce another stealing policy.

## Existing source facts

The captured `left_contact_bridge` freezes each frame, tracks seen/blocked contacts and emits `{generation8,contact5}` plus a single returned group. It has one outstanding request. `finger_pitch` supports MULTI_BIND, but a single first-group callback does not bind four layers. The new `note_event_router` needs source-tagged31-bit serials and returns a32-bit group mask, four layer bits and a20-bit layer-to-group map. Neither the old13-bit contact ID nor MIDI pitch may replace that global token.

## Mechanical lifecycle contract

- At accepted contact ON, freeze contact/generation, pitch, caller-provided8-bit velocity, signed glide and the already-resolved enabled layer selection. Assign a new source-global31-bit serial. Source0 and source1 remain equally eligible; this oracle does not allocate resources itself.
- Generation is diagnostic contact metadata, not a delayed-operation lookup key. Every queued OFF, cancellation, completion and movement must retain the captured full token. After256 local generations, the same13-bit legacy ID can recur; an old event must still carry the old token, not be looked up again against the current row.
- A held contact cannot retrigger after its resources are stolen. Retirement removes ownership of all remaining layers but retains the held/seen latch. Only a physical release followed by a new valid contact edge permits another ON.
- A successful allocation confirms every requested eligible layer, each mapped to a distinct group, and the group mask must exactly equal the map union. Preserve the complete response; do not expose only its first group to the expression consumer.
- Movement carries the token and current owned mask to every remaining layer. It does not emit ON or advance age. Natural per-layer completion may shrink this mask; whole-note retirement clears it atomically. OFF stops contact movement, while the resource manager may retain sounding release tails.
- A physical release while its ON transaction is pending becomes matching-token cancellation. A cancellable native ALLOCATED response must not be consumed as final while cancellation is pending; wait for confirmed cancellation/cleanup. Wrong/stale completion must not mutate the pending event or current ownership.
- Serial words may wrap in order before exhausting all unique values of an epoch. They must not repeat a full token within the common reset epoch. The narrowed oracle deliberately exhausts the epoch and requires a reset fence rather than aliasing. A shared backend/router/producer flush is mandatory: token equality alone cannot detect an unsolicited pre-reset replay after a fresh token has been reused.

## Tests and remaining implementation boundary

`contact_contract.py` is a transaction-level oracle. Tests combine it with the existing independent `ResourceModel` for same-pitch two-source admission, complete four-layer ownership, full32-group eviction, held-contact suppression, old OFF/movement after256-generation reuse, cancellation, partial natural finish, wrong response, serial wrap/exhaustion and reset. This is not a ready/valid cycle model or an audio/PCM qualification.

Next RTL work must separately demonstrate stable payload/backpressure, same-cycle cancellation, full map binding/reuse precedence and common reset, then connect the actual captured contact producer and expression endpoint. The score producer needs its own tokenized event/backpressure/overflow adapter; `song_seq` pulses cannot be silently dropped. The existing full-constraint hold-repair failure remains a timing blocker and must accompany later RTL changes and new PnR/STA evidence.

No choices are made here about25/26 physical endpoints, octave changes affecting held notes, pressure/velocity calibration, slot normalization/transposition, editor apply/save semantics, recording scope, J10/GPIO mapping or P-020 fade. Raw motion positions are not converted into a newly invented musical scale. No programming, Flash or manufacture is authorized.
