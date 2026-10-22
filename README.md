# chrono-flight

**A black-box flight recorder for agent fleets: it captures a fleet's
chrono-tensor event stream and plays it back — rewind, mute a track, solo a
track, branch the view — so an incident can be re-examined instead of
guessed at.**

## Who it's for

Operators of multi-agent fleets — the person who gets asked "why did the
fleet do that at 03:12?" and today has to answer from scattered,
incomparably-timestamped logs across machines. If your fleet already emits
(or can be made to emit) a time-ordered, multi-track event stream, this
tool is the recorder and the playback deck for it.

## What it consumes

The **chrono-tensor event format** — `[time/tick, channel/agent,
intent, velocity/pressure]` — owned by the `chrono-tensor` repo
(https://github.com/SuperInstance/chrono-tensor). chrono-flight does not
define the format and does not interpret the events' semantics; it records
them faithfully and lets a human navigate them. Fleets built on
`quilt-engine` or `continuum-runtime` emit this format on their seams,
which is what makes them recordable.

## Status

**First component built: the engine bridge.** `src/importer/` ingests a
finished quilt-engine run directory (seam log + both sovereign books)
into chrono-flight's record form, prints it as an ordered timeline
with explicit kill/open-excursion gaps, recomputes crossing agreement
from the two books alone, and can write a recording file — see
`BRIDGE-REPORT.md` and `examples/quilt_timeline.py`. The live recorder
and playback deck remain design-only; confidence is annotated per
component in `ARCHITECTURE.md` — the recorder and playback core are
ordinary, buildable engineering; the speculative extras are marked as
speculative and are not on the v0 path (see `BUILD-BRIEF.md`).

One limit is stated up front because everything else depends on it:
**chrono-flight shows what happened. It does not promise to re-run it.**
Deterministic replay of LLM-based nodes is not a feature of this tool —
see ARCHITECTURE.md, "The replay limit."

## Relation map

| Role | Repo |
|---|---|
| **Event format** this tool records | `chrono-tensor` |
| **Spec** for what the recorded events mean at a seam | `beam-quilt` |
| **Emitters** whose runs get recorded | `quilt-engine`, `continuum-runtime` |
| **This repo** — one tool, one job: record and play back | `chrono-flight` |

This repo exists separately, rather than as a feature inside a runtime,
on Casey's standing rule: one tool, one repo. A recorder that only
observes also stays honest — it has no reason to grow control features
(see the non-goals in BUILD-BRIEF.md).

## Layout

- `ARCHITECTURE.md` — recorder, storage/downmixing, playback engine, the
  chrono-shell interface, and the replay limit, with confidence marks.
- `BUILD-BRIEF.md` — the v0 build and its acceptance criteria.
- `BRIEF.md` / `BRIDGE-REPORT.md` — the engine-bridge build and its report.
- `src/` — component layout; `src/importer/` is built, the rest are stubs.
- `examples/`, `tests/` — the timeline CLI and the suite (with frozen
  quilt-engine run fixtures under `tests/fixtures/`).

## Source material

Extracted from `chrono-tensor/docs/ideation/gemini1.md` (chrono-flight as
the "killer app": the autonomous-system black box, the chrono-shell
piano-roll interface, the ops cockpit, temporal downmixing) and
`beam-quilt/docs/proposed/gemini22.md` (the playback verbs — scrub, mute,
solo, quantize — worked out on multi-track timelines). Those files are raw
conversation exports containing repeated iterations; this repo is the
distilled, buildable residue.
