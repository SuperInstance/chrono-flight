# chrono-flight — build brief (v0)

**For the agent who builds this:** you need this brief, `ARCHITECTURE.md`,
and the chrono-tensor event format. You do not need the ideation
conversations; the need-to-knows are extracted here. Blinders on.

## The build

Three pieces, in order:

1. **Record.** A recorder process that consumes a chrono-tensor event
   stream and appends it, unmodified and in order, to a recording file
   with a header (emitter id, start tick, format version). Source stream
   for v0: **the quilt-engine two-process demo** — two patches exchanging
   envelopes through a Jev pair is the smallest real fleet there is, and
   its run is the first thing worth being able to re-examine.
2. **Play back.** A playback view over the recording file supporting:
   scrub to an arbitrary tick, per-track **mute**, per-track **solo**, and
   a state-at-tick readout (each track's latest event at or before the
   playhead). Terminal UI is acceptable and preferred for v0.
3. **Prove it.** An automated check that the recording is faithful:
   replaying the demo with recording on produces a file whose event
   sequence matches the demo's own emitted sequence exactly, and whose
   playback state-at-tick matches a hand-computed expectation at three
   chosen ticks (start, mid-incident, end).

## Acceptance criteria

- Recording the quilt-engine demo run yields a file containing every
  emitted event, in emitted order, with no additions except the header
  and explicit gap markers (none expected in v0).
- Scrubbing to the tick just before the demo's known deadband event shows
  the sender's transmission as the latest event on its track; scrubbing
  one tick past it shows the receiver's clarification outcome.
- Muting the receiver's track leaves the sender's track and all state-at-
  tick readouts for it unchanged.
- Soloing the receiver's track shows only its events.
- Killing the recorder mid-run and restarting it produces a recording
  with an explicit gap marker — never a silently truncated file that
  looks complete.
- No code path in the v0 tree writes to, signals, or otherwise touches a
  live fleet. (Checked by review: the recorder only reads its input; the
  player only reads files.)

## Non-goals (do not build these)

- **No live control.** v0 cannot pause, steer, mute-in-real-life, or
  inject into a running fleet. Recorder first; **conductor never by
  default** — live control is a different tool and a different decision,
  and if it is ever proposed it starts as its own repo and its own
  argument.
- **No re-simulation.** No "press play and watch the alternate timeline."
  The recorder shows what happened (see "The replay limit" in
  ARCHITECTURE.md). Branch export is not in v0.
- **No downmixing in v0.** Full fidelity only; retention policy and
  compaction are v1 design work.
- **No auditory diagnostics.** Parked as speculative in ARCHITECTURE.md.
- **No format invention.** If the demo's stream doesn't fit the
  chrono-tensor format, the finding goes to the chrono-tensor repo — this
  tool does not grow a private format.
