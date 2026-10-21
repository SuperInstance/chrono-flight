# Foundations application — chrono-flight

What beam-quilt's verified foundations (beam-quilt `FOUNDATIONS.md`, Lane A
pull list) mean for this repo specifically. Tags: **SETTLED / PROPOSED /
SPECULATIVE**. Headline first: the foundations *strengthen* this repo's
central refusal — the replay limit is not a local caveat, it is the
position the prior-art survey independently arrived at.

## ADAPT here

### ADAPT — Chronicle Queue named tailers + mmap append-only cycles (Apache-2.0) → `src/playback/`, `src/store/`
- **Replaces:** per-view, anonymous playback cursors. Named, persistent,
  read-without-consume tailers are exactly "each sovereign reader keeps
  its own scrub position": an operator's playhead survives sessions, and
  two operators scrubbing one recording never disturb each other.
  Cycle-rolling is the retention seam where downmix/archive hooks in.
- **Rebuild the semantics; do not vendor the Java original.** The
  recorder's append-only capture (ARCHITECTURE §1) is unchanged —
  tailers govern reading, never writing.
- Tag: **PROPOSED** (playback verbs themselves stay SETTLED; persistence
  and naming of cursors is the new design content).

### ADAPT — Temporal's position-matched replay discipline (docs; platform not run) → `src/playback/` branch export
- **Replaces:** the undesigned part of "re-voice / branch" (ARCHITECTURE
  §3 marks branch export **plausible**, format undesigned). The discipline
  supplies the design rule: a branched prefix is positionally checkable —
  every event carries its position, any re-derivation is matched
  position-by-position, and drift is reported as a positional mismatch,
  never smoothed over. Model calls in the recording are activities:
  recorded, never re-executed.
- This is the replay limit expressed as a mechanism. It does not soften
  the limit; it is how the limit is enforced if branch export is built.
- Tag: **PROPOSED**.

### STUDY patterns — WinDbg TTD (→ `src/shell/`) and rr's honesty bar (→ all docs)
- TTD's ring-recording mode, keyframe index, and Timelines lanes are the
  UI precedent for the chrono-shell: precedent, not a dependency.
  **PROPOSED** as design reference.
- rr's cost-up-front documentation style is the honesty bar the replay
  limit section already follows; keep following it in every future claim
  this repo makes. **SETTLED** as a writing rule.

### ADAPT (supporting) — LTTng rotation/snapshot semantics (docs CC BY 4.0) → `src/store/`
- Rotation/chunk archives and snapshot mode are the reference semantics
  for extracting a downmixed stem from a live ring — the store's
  "compact on retention" step. The primary adaptation lives in
  chrono-tensor; here it informs only the extraction behaviour.
  Tag: **PROPOSED**.

## BUILD OUR OWN

- **The recorder as assembled.** Every mechanic exists somewhere (Lane A
  §4); an owner-consented, fleet-wide flight recorder whose playback
  makes no re-execution promise has never been assembled. The assembly —
  consent boundaries, per-patch logs into one multi-track stream,
  faithful navigation — is this repo's contribution. Foundations-verified:
  no surveyed system (EventStoreDB/Kurrent, Axon (rejected), rr, TTD,
  Undo (rejected)) is this tool.

## Open decisions — NOT settled by the foundations

### Deadband semantics (Casey's ruling: clarify vs abstain as fourth outcome)
The recorder is ruling-agnostic by design — it records whatever outcomes
occur and interprets none. Exactly one surface is ruling-sensitive:
- **`src/store/` downmix aggregates.** ARCHITECTURE §2 lists "decision
  tallies" among the per-track aggregates. If abstain becomes a
  producible seam outcome, the tally gains a category, and recordings
  downmixed across the ruling change are not tally-comparable unless the
  category set is recorded in the recording header (it already declares
  bucket size and retention horizon — the category set belongs beside
  them). Under clarify-only, tallies stay three-way. No code anticipates
  either branch; the header field is the only preparation warranted.

### State model (continuum-runtime's open decision: stored vs trajectory-only)
- **Stored state (SPEC P4/P5 as written):** this repo's emitter
  assumptions hold — patches keep logs, runtimes emit them, the recorder
  captures them. Nothing changes here.
- **Trajectory-only (would require a beam-quilt SPEC amendment first):**
  there would be no P5 patch logs for continuum-runtime runs to record,
  and §1's recorder would have only the live stream — no per-patch record
  to align against. The README relation map's "Emitters" row and
  ARCHITECTURE §2's two-tier store assumptions would both need
  re-examination. Recorded here so the dependency is visible; nothing in
  this repo is designed for that branch, and nothing should be until the
  ruling and the SPEC amendment exist.

## Conflicts found against the verified foundations

1. **Cross-repo tension — when downmixing happens.** chrono-tensor
   ARCHITECTURE §3/§4 has the oldest segment downmixed *at ring-buffer
   wrap, before release*; this repo's ARCHITECTURE §2 says downmixing
   happens "on read/retention, never on capture," as a storage policy
   applied later, with v0 possibly full-fidelity only. These are
   reconcilable (wrap-time *is* retention-time) only if "the ring buffer"
   means the same store in both documents — as written, a builder could
   implement two different compaction points. Flagged for the two repos'
   maintainers to align in words; the foundations' rule that survives
   either reading: never on capture, always declared, always marked as
   summarized (chrono-tensor D4).
2. **BUILD-BRIEF.md wording — "replaying the demo with recording on."**
   Loose use of "replaying" for what is recording + playback. The replay
   limit (ARCHITECTURE, SETTLED) governs the term in this repo; flagged
   so the brief's phrasing is never cited as a re-execution feature.
3. No refuted factual claims (sub-millisecond, rigid-graph, OPAL lineage,
   global optimality) occur anywhere in this repo — verified in the
   foundations pass; nothing to correct.
