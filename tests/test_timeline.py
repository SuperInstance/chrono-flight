"""Timeline view acceptance (BRIEF deliverables 2, 4): the run prints
as an ordered timeline with every exhibited behaviour, kills/gaps
render as explicit gaps, the replay-limit statement rides along, and
the CLI end-to-end works on the fixtures."""

import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from importer import REPLAY_LIMIT, audit_agreement, import_run, ledger_entries, render_timeline  # noqa: E402

DEMO = ROOT / "tests" / "fixtures" / "quilt-engine-9752895-demo"
KILL = ROOT / "tests" / "fixtures" / "quilt-engine-9752895-kill"
KILL_OPEN_EXCURSION = "396e366f94c793a6"

OFFSET = re.compile(r"^\s+\+\s*([0-9.]+)s\s")


def rendered(fixture, **kw):
    result = import_run(fixture)
    audit = audit_agreement(
        ledger_entries(result.run.sender_book.lines),
        ledger_entries(result.run.receiver_book.lines),
        sender_name=result.run.sender_book.owner,
        receiver_name=result.run.receiver_book.owner,
    )
    return render_timeline(result, audit=audit, **kw)


class TestTimelineContent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.demo = rendered(DEMO)
        cls.kill = rendered(KILL)

    def test_ordered_by_tick(self):
        for text in (self.demo, self.kill):
            offsets = [
                float(m.group(1))
                for line in text.splitlines()
                if (m := OFFSET.match(line))
            ]
            self.assertEqual(offsets, sorted(offsets))

    def test_demo_shows_every_exhibited_behaviour(self):
        for needle in (
            "crossing",
            "Hold pick 3bfc676e",
            "HoldWatch pick f4c6f8ed",
            "Act(accept_best) pick aa69b1e8",
            "Act(clarify_narrow) pick d0f45a4e",
            "Act(refuse) pick 6fb5840a",
            "disagree   3bfc676e",
            "sender completeness 1.0000 vs receiver 0.6667",
            "session_end",
        ):
            self.assertIn(needle, self.demo)

    def test_kill_shows_gap_and_open_excursion(self):
        self.assertIn("[gap  ] vessel-a: book ends mid-run", self.kill)
        self.assertIn("no session_end", self.kill)
        self.assertIn(f"[open ] seam: open excursion {KILL_OPEN_EXCURSION}", self.kill)
        self.assertIn("HoldWatch pick 396e366f", self.kill)

    def test_kill_never_renders_a_close_for_the_open_excursion(self):
        # Nothing on the timeline claims D was judged: no Act for it,
        # and no Hold naming D as pick (a closing judgment). The only
        # decision naming D is the HoldWatch; the Holds after it carry
        # no pick — a stale pool, not a judgment.
        short = KILL_OPEN_EXCURSION[:8]
        for line in self.kill.splitlines():
            if short not in line:
                continue
            self.assertNotIn("Act(", line)
            self.assertNotIn(f"Hold pick {short}", line)

    def test_replay_limit_statement_present(self):
        for text in (self.demo, self.kill):
            self.assertIn(f"-- {REPLAY_LIMIT}", text)

    def test_audit_section_present_with_counts(self):
        self.assertIn("== agreement audit — recomputed from the two books alone ==", self.demo)
        self.assertIn("agreed:    7", self.demo)
        self.assertIn("agreed:    2", self.kill)

    def test_readings_only_in_all_events_view(self):
        self.assertNotIn("== book readings", self.demo)
        self.assertIn("== book readings", rendered(DEMO, all_events=True))

    def test_gapless_full_run_says_so(self):
        # The full run has one *recorded* open excursion (B) — but no
        # truncation gaps; the gaps section must not claim a kill.
        self.assertNotIn("[gap  ]", self.demo)


class TestCLIEndToEnd(unittest.TestCase):
    def test_cli_on_kill_fixture(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "examples" / "quilt_timeline.py"),
             "--dir", str(KILL)],
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("open excursion 396e366f94c793a6", proc.stdout)
        self.assertIn("agreed:    2", proc.stdout)
        self.assertIn(REPLAY_LIMIT, proc.stdout)


if __name__ == "__main__":
    unittest.main()
