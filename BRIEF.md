# BUILD BRIEF — chrono-flight: read a quilt-engine seam log

Repos: SuperInstance/chrono-flight (the fleet flight recorder; work
here) and SuperInstance/quilt-engine (read-only reference, @ 9752895).
Work in a fresh clone of chrono-flight.

## Background

quilt-engine v0/v0.1 writes, per demo run, a seam log (seam_log.jsonl,
written by the receiver process) plus two sovereign books
(sender_book.jsonl / receiver_book.jsonl). Each seam-log line is a JSON
event: decisions (hold / hold_watch / act with response kind), picks,
deviations, timestamps; v0.1 also records decisions that consulted a
projection, with the horizon used. chrono-flight's charter is the
fleet's flight recorder: ingest what happened, replay it, and state its
own limit honestly — a replay shows what happened; it does NOT promise
deterministic re-simulation of judgment calls.

## Build

1. **Importer.** A chrono-flight module that ingests a quilt-engine run
   directory (seam_log.jsonl + both books) and normalises it into
   chrono-flight's own event/record form (follow chrono-flight's
   existing conventions — read its README/ARCHITECTURE/SPEC first and
   match them; if its record form has a spec, the importer targets the
   spec, not an invention).
2. **Timeline view.** A CLI or example that prints the run as an
   ordered timeline: crossings, decisions with their kind
   (Hold/HoldWatch/Act + response), disagreements, kills/gaps visible
   as gaps (a side's book ending mid-excursion reads as an open
   excursion, never silently closed).
3. **Agreement audit.** From the two books alone, recompute which
   crossings were agreed (SEND↔RECEIVE on id + payload hash) and report
   agreed / unagreed / disputed counts — the recorder as an independent
   reader of the ledger, not a consumer of the engine's own verdicts.
4. **Replay-limit statement.** The timeline output and the module
   docstring both carry chrono-flight's standing limit in plain words:
   this replays the record of what happened; the receiver's comparative
   judgments are shown as recorded, not re-derived.
5. **Fixture + tests.** Generate a real fixture by running the
   quilt-engine demo (clone it, run examples/two_process_demo.py into a
   temp dir, capture the three files as a test fixture with a README
   noting the engine commit). Tests: importer round-trip on the
   fixture; agreement audit matches hand-computed counts for the
   fixture; a truncated-book fixture (kill case) shows the open
   excursion as open. Keep chrono-flight's existing tests green.

## Non-goals

No changes to quilt-engine. No live tailing/streaming — files at rest
only. No new dependencies beyond what chrono-flight already uses.

## Report

Leave BRIDGE-REPORT.md in the chrono-flight repo root: what was built,
how a run directory maps into chrono-flight's record form, test counts
(paste the tail), and any place the engine's log format was ambiguous.
Do NOT push to GitHub; leave the work committed on a local branch named
engine-bridge.
