# chrono-flight — architecture

Confidence marks: **settled** = plain engineering or a direct consequence
of the chrono-tensor format; **plausible** = a reasonable design choice,
untested; **speculative** = from the source conversations, no evidence yet.
Speculative components are documented so they aren't rediscovered as if
new — and are fenced off the v0 path.

## Components

### 1. Recorder — `src/recorder/`

Append-only capture of the live event stream.

- Subscribes to a fleet's chrono-tensor stream (file tail, socket, or a
  runtime's stream output) and writes events in arrival order, with the
  recorder's own receive-timestamp alongside each event's stream tick, so
  clock disagreement between emitters is itself visible in the recording.
- Never edits, filters, reorders, or interprets. A recording that can be
  argued with is worthless; this component's whole job is to be boring.
- Handles emitter disconnect/reconnect as recorded events, so gaps in a
  recording are explicit, never silent.

Confidence: **settled**. Append-only capture is the one part of this
design with no open questions.

### 2. Store — ring buffer + downmixing on read — `src/store/`

Two-tier storage, following the temporal-compaction idea in the
chrono-tensor ideation:

- **Recent history at full fidelity.** A ring buffer holds the newest
  stretch of the stream event-for-event. This is what an operator scrubs
  through during and just after an incident.
- **Older history downmixed.** As events age out of the ring, they are
  compacted into lower-resolution summaries — per-track aggregates
  (counts, rates, extrema, decision tallies) over time buckets — the way
  audio stems are bussed down: the shape of what happened survives, the
  individual transients don't.
- **Downmixing happens on read/retention, never on capture.** The
  recorder (above) always writes full fidelity; compaction is a storage
  policy applied later, and the bucket size and retention horizon are
  configuration, declared in the recording's header — because a downmixed
  stretch can answer "were refusals rising?" but not "what exactly did
  patch A send at tick 4412?", and the operator must be able to see which
  kind of answer they're getting.

Confidence: **plausible**. Downmixing is lossy summarisation with a good
name; the policy details (bucket sizes, which aggregates) are undesigned
and are v1+ work. v0 may ship full-fidelity only.

### 3. Playback engine — `src/playback/`

Reads a recording and serves a navigable view of it. The verbs, taken from
the multi-track material in `gemini22.md`:

- **Scrub** — move the playhead to any tick; the view shows every track's
  state as of that tick (each track's most recent event at or before it).
- **Mute** — hide a track (one agent, one channel) from the view, to see
  the rest of the fleet's shape without it.
- **Solo** — the inverse: show one track only.
- **Quantize (view)** — snap the displayed timeline to a coarser time grid
  to see pattern over jitter. A display operation only; the recording is
  untouched.
- **Re-voice / branch** — export a *copy* of a prefix of the recording
  with a chosen event altered or a track removed, as the input stream for
  a **new** run elsewhere. See the replay limit below: this prepares a
  what-if; it does not resume the past.

All playback operations are non-destructive and operate on views or
copies. There is no code path from playback into a live fleet.

Confidence: **settled** for scrub/mute/solo/quantize (they are queries
over an append-only log). **Plausible** for branch export (format details
for a re-runnable prefix are undesigned).

### 4. Interface — the chrono-shell — `src/shell/`

The piano-roll UI from the chrono-tensor ideation is **this tool's
interface**, not a separate product: tracks as rows, time as the
horizontal axis, event intensity as block height/brightness, a draggable
playhead, mute/solo toggles per track. First form: a terminal UI; a web
view can follow the same playback API.

*One-tool-one-repo note:* the shell lives here while it is only a view
over recordings. If it ever grows live-session features of its own, it
splits into its own repo at that point — it does not grow them inside
chrono-flight.

Confidence: **plausible** (the shape is well precedented by every DAW and
trace viewer; nothing here is invented, which is the point).

### 5. Auditory diagnostics — speculative extra

The ideation proposes mapping track health to sound so an operator can
*hear* a fleet degrade. Marked **speculative**: no mapping from event
patterns to audio parameters has been designed, let alone tested, and a
bad mapping is worse than none (it trains false intuition). Parked here
so the idea is on record; it is not in any build brief and should not be
built on spec.

## The replay limit — read this before promising anything

The source material repeatedly promises "time-travel debugging": scrub
back, mute the faulty agent, re-voice, press play, watch the alternate
timeline. **That promise is not kept by this tool, and must not be made
on its behalf.**

- An LLM-based node's output depends on sampling, model version, and
  context that a stream recording does not fully capture. Re-running a
  recorded prefix through live nodes will, in general, **diverge** — and
  the divergence itself would be unrecorded, unlabelled guesswork wearing
  the recording's authority.
- chrono-flight therefore guarantees only: **a faithful record, and
  faithful navigation of it.** What happened, in order, per track, with
  gaps marked.
- Re-simulation ("what would have happened if…") is a *separate,
  unproven* feature belonging to the runtimes, not the recorder. If it is
  ever built, its outputs must be labelled as simulations, never merged
  into a recording.

Confidence: **settled** — this is a property of the recorded systems, not
a limitation a better recorder removes.
