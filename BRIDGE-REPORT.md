# BRIDGE-REPORT — reading a quilt-engine seam log

Built on branch **`engine-bridge`** (local; not pushed), per `BRIEF.md`.
quilt-engine was read only, at `9752895f2dacfa4b7c6646e380d63dd80ff786d5`
(v0.1); its suite (42 tests) was re-run after the work and stays green.

## What was built

chrono-flight's first code: `src/importer/` (Python 3, stdlib only —
no new dependencies), plus a CLI and frozen fixtures.

- **`src/importer/recording.py`** — chrono-flight's record form: an
  append-only JSONL recording of `header` (emitter id, start tick,
  format version — BUILD-BRIEF deliverable 1), `event`, and `gap`
  records. Each event carries the chrono-tensor form
  `[time/tick, channel/agent, intent, velocity/pressure]`, the
  recorder's receive-timestamp, the tick's clock domain, the source
  line verbatim in `detail`, and a `file:line` reference.
- **`src/importer/quilt_engine.py`** — the importer: ingests a run
  directory (`seam_log.jsonl` + `sender_book.jsonl` +
  `receiver_book.jsonl`, files at rest) into that record form. The
  module docstring carries the replay-limit statement.
- **`src/importer/audit.py`** — the agreement audit: recomputes
  agreed / unagreed / disputed crossings from the two books alone
  (SEND↔RECEIVE on transmission id + payload hash), an independent
  reimplementation of the ledger check that never consults the seam
  log or the engine's own verdicts.
- **`src/importer/timeline.py`** — the ordered timeline view:
  crossings, decisions with kind and response (Hold / HoldWatch /
  Act(…)), disagreements, and an explicit gaps section. The replay
  limit is printed with every timeline.
- **`examples/quilt_timeline.py`** — the CLI:

      python3 examples/quilt_timeline.py --dir RUN
      python3 examples/quilt_timeline.py --dir RUN --record out.jsonl --all

- **`tests/fixtures/quilt-engine-9752895-demo/`** and
  **`tests/fixtures/quilt-engine-9752895-kill/`** — frozen captures of
  real demo runs (commands and engine commit in each README): the full
  run, and the `DEMO_SENDER_HANG=1` run with the sender killed
  mid-excursion.
- **`tests/`** — 30 tests (importer faithfulness + recording
  round-trip + gap rules, audit hand-counts + synthetic verdict rules,
  timeline content + ordering + CLI end-to-end).

## How a run directory maps into the record form

One event per source line, in per-file arrival order (seam log, then
sender book, then receiver book). Nothing is dropped, edited, or
reordered; unknown event kinds are recorded (under `seam:`/`book:`
intents), never rejected.

| Source | Track | Tick | Intent | velocity/pressure |
|---|---|---|---|---|
| seam `crossing` | `seam` | `at` (wall) | `crossing` | cost |
| seam `decision` | `seam` | `at` (wall) | `decision:hold` / `decision:hold_watch` / `decision:act:<response>` | deviation |
| seam `disagreement` | `seam` | `at` (wall) | `disagreement` | divergence |
| seam `course_adjusted`, `unreadable_envelope`, unknown | `seam` | `at` (wall) | as-is / `seam:<x>` | none |
| book `ledger` | book owner | `at` (wall) | `send` / `receive` | cost |
| book `reading` | book owner | `taken_at` (**mono**) | `reading` | none (value is a dict; kept in detail) |
| book `event` | book owner | `at` (wall) | `event:<name>` | none |

- **Book owner (track name)** comes from the book's own `session_end`
  `role` when present; a killed side never writes one, so the
  importer then falls back to caller-declared side names (defaults:
  the demo's `vessel-a` / `vessel-b`).
- **Numbers are never invented**: the velocity/pressure field is a
  natural magnitude where one exists (deviation, divergence, cost) and
  `null` otherwise.
- **Gaps are explicit markers**, never silence: a book with no
  `session_end` is a truncation gap on that side's track (quoting the
  seam's last recorded decisions); each excursion the receiver's own
  `session_end` lists as unresolved is an open-excursion marker on the
  seam track. A missing book file is a gap. A later `hold` with no
  pick is a stale pool — it is not a judgment and closes nothing.
- **Header `source` block** records the engine label (see
  ambiguities), the seam contract ids found, the run dir, per-file
  line counts, the clock legend, and the resolved side names.

**Replay limit, carried in the importer docstring and every timeline
output:** this replays the record of what happened — the receiver's
comparative judgments (Hold / HoldWatch / Act) are shown as recorded,
not re-derived, and chrono-flight does not re-simulate judgment calls.

## Tests

    python3 -m unittest discover -s tests

Tail:

    ..............................
    --------------------------------------------------------------------
    Ran 30 tests in 0.134s

    OK

Hand-computed expectations the audit tests assert (cross-checked
against the engine's own `agreed_crossings` during development): full
demo 7 agreed / 0 unagreed / 0 disputed (5 crossings A,B,D,E,F + 2
responses; refreshes reuse ids); kill run 2 / 0 / 0. The kill fixture
asserts the sender's truncation gap and that excursion D
(`396e366f94c793a6`) appears as open — with the invariant that no
timeline line renders a closing judgment (`Act(` or `Hold pick D`)
for it.

## Where the engine's log format was ambiguous

Honest findings, none blocking; each is handled explicitly rather than
smoothed over:

1. **Books don't name their owner per line.** A book's ledger entries
   carry only the *peer*. The owner is recoverable from
   `session_end.role` — which a killed side never writes. The
   importer takes it from `session_end` when present, else from
   caller-declared side names.
2. **Two clock domains in one book.** Ledger `at` and event `at` are
   wall clock (`time.time()`); readings' `taken_at` is monotonic
   (`time.monotonic()`). They are not comparable, so the recording
   marks each event's clock and the timeline never merges monotonic
   readings into the wall-clock ordering (they get their own
   per-track section, in book order). Clock disagreement stays
   visible.
3. **The engine's version is not in the run directory.** The only
   version-ish signal is the seam contract id
   (`beam-quilt/seam-handshake@1.2`) on crossings and ledger entries.
   The recording header stamps the engine label from caller
   knowledge; the fixture READMEs pin the commit.
4. **v0.1 projection records are demo-path-invisible.** The brief's
   background says v0.1 records decisions that consulted a projection
   with the horizon used; that is true of the `JevPair` in-process
   path (crossing events carry `expected_course` + `projection`), but
   the two-process demo's receiver is not wired to a course-cell log,
   so its seam log contains none. The importer carries such fields
   verbatim in `detail` and the timeline annotates them (adopted /
   refused, with horizon and cap) when present — no fixture exercises
   this yet.
5. **"Unresolved" includes stale-ended excursions.** The receiver's
   `session_end.unresolved_excursions` lists any pick whose last
   recorded decision kind was `hold_watch` — including excursions
   that ended by the pool going stale rather than by a judgment. In
   the *full* demo run that list still contains B
   (`f4c6f8edd3959921`), which the demo narrative calls resolved.
   chrono-flight shows the list as recorded (one open marker in the
   full-run timeline) and does not amend the engine's accounting.
6. **A `hold` with `pick: null` is not a close.** It means the pool is
   empty (candidates pruned stale). It would be easy — and wrong — to
   read the final no-pick Hold in the kill run as the excursion
   closing; the timeline labels it "no pick — pool empty" and the
   gaps section carries the real state.
7. **The demo's own count comment is loose.** `two_process_demo.py`
   says "A-F + 2 responses = 8" agreed crossings while checking only
   `>= 6`; the ledger actually holds 7 unique ids (A,B,D,E,F + 2
   responses). Hand count and the engine's `agreed_crossings` agree
   on 7.
8. **Startup artifact.** The seam log's first line is typically a
   `decision hold pick null` written before any envelope arrives (the
   receiver's initial empty-pool tick). It is recorded like any other
   event; timeline readers should not read it as a judgment about
   anything.

## Non-goals honored

No changes to quilt-engine (clone left clean at `9752895`). Files at
rest only — the importer reads finished run directories, no tailing,
and no code path touches a live fleet. No new dependencies (stdlib
only, matching the programme's repos).
