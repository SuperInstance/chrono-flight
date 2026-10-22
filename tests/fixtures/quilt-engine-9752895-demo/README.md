# Fixture: quilt-engine two-process demo, full run

Frozen capture of one real run of the quilt-engine two-process demo.

- Engine: SuperInstance/quilt-engine @ `9752895f2dacfa4b7c6646e380d63dd80ff786d5` (v0.1)
- Command: `DEMO_TIME_SCALE=0.6 python3 examples/two_process_demo.py --dir <tmp>`
  (orchestrated mode: spawns receiver + sender, then verifies)
- Captured: 2026-10-22, Python 3.12, this machine's clocks. Timestamps are
  one real run — do not regenerate and expect the same ticks or
  transmission ids.

Files (exactly as the demo left them, minus the file-drop `inbox/`,
`responses/` and `done.flag` artifacts):

- `seam_log.jsonl` — the seam's event log, written by the receiver
  (crossings, decisions, disagreement, course_adjusted).
- `sender_book.jsonl` — vessel-a's sovereign book (SEND/RECEIVE ledger
  entries, events).
- `receiver_book.jsonl` — vessel-b's sovereign book (RECEIVE/SEND ledger
  entries, candidate readings, events).

Hand-computed facts (tests assert these):

- Ledger ids: 7 unique transmission ids — 5 sender→receiver crossings
  (A, B, D, E, F) + 2 receiver→sender responses (clarify/narrow question,
  refusal profile). Refreshes reuse the same ids.
- Agreement audit from the two books alone: **7 agreed, 0 unagreed,
  0 disputed** (each id has a SEND in one book and a RECEIVE in the
  other with a matching payload hash).
- Both books end with `session_end` — no kill, no truncation gap.
- The receiver's `session_end` records `unresolved_excursions:
  ["f4c6f8edd3959921"]` (transmission B). Not a kill: the engine keeps
  any pick whose last recorded decision kind was `hold_watch` — B's
  excursion ended by its reading going stale (pool TTL), never by a
  Hold/Act naming it. Shown as recorded; see BRIDGE-REPORT.md.
