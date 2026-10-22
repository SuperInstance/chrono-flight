# Fixture: quilt-engine two-process demo, sender killed mid-excursion

Frozen capture of one real run of the quilt-engine two-process demo in
its kill configuration (`DEMO_SENDER_HANG=1`, as used by the engine's own
`tests/test_demo.py::TestKillMidRun`).

- Engine: SuperInstance/quilt-engine @ `9752895f2dacfa4b7c6646e380d63dd80ff786d5` (v0.1)
- Roles run by hand (no orchestrator, so the sender is really killed):

      DEMO_TIME_SCALE=0.6 python3 examples/two_process_demo.py \
          --role receiver --dir <tmp> --until 1.6 &
      sleep 0.3
      DEMO_TIME_SCALE=0.6 DEMO_SENDER_HANG=1 \
          python3 examples/two_process_demo.py --role sender --dir <tmp> &
      # after both A and D have crossed (2 RECEIVEs in the receiver book):
      kill <sender pid>; wait

- Captured: 2026-10-22, Python 3.12. One real run; ticks and ids are
  frozen and will not reproduce.

What happened:

1. Sender (vessel-a) sends A (telemetry, inside the band → Hold, with a
   disagreement record) and D (course-proposal, merit 0.97 — an
   excursion), logs `sender_hanging`, and is killed. Its book ends
   there: **no `session_end`** — the book is truncated mid-run.
2. D's excursion is open at the seam (`hold_watch`); D's reading then
   goes stale (pool TTL), so the seam's next decision is `hold` with
   pick `null` — the pool is empty, **not** a judgment closing D.
3. The receiver (vessel-b) runs to its `--until`, ends cleanly, and its
   `session_end` records `unresolved_excursions: ["396e366f94c793a6"]`
   (transmission D).

Hand-computed facts (tests assert these):

- Ledger ids: 2 unique transmission ids (A, D), both sender→receiver.
- Agreement audit from the two books alone: **2 agreed, 0 unagreed,
  0 disputed**.
- The sender book has no `session_end` → the importer must mark a
  truncation gap on vessel-a's track, and excursion D must appear as
  **open** in the timeline — never silently closed by the stale-pool
  Hold that follows it.
