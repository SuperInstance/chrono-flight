"""Importer acceptance (BRIEF deliverables 1, 4, 5): a quilt-engine run
directory normalises into chrono-flight's record form faithfully — one
event per source line, in order, unedited — round-trips through a
recording file, and marks kills/open excursions as explicit gaps,
never silently closed."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from importer import (  # noqa: E402
    GAP_OPEN,
    GAP_TRUNCATED,
    import_run,
    read_recording,
    write_recording,
)

DEMO = ROOT / "tests" / "fixtures" / "quilt-engine-9752895-demo"
KILL = ROOT / "tests" / "fixtures" / "quilt-engine-9752895-kill"

# Hand-read from the fixture files (see the fixture READMEs).
DEMO_SOURCE_LINES = {"seam_log.jsonl": 20, "sender_book.jsonl": 35,
                     "receiver_book.jsonl": 63}
KILL_OPEN_EXCURSION = "396e366f94c793a6"   # transmission D in the kill run
DEMO_OPEN_EXCURSION = "f4c6f8edd3959921"   # transmission B in the full run


class TestFaithfulImport(unittest.TestCase):
    """Every source line becomes exactly one event; nothing is added,
    edited, or reordered."""

    @classmethod
    def setUpClass(cls):
        cls.result = import_run(DEMO, engine="SuperInstance/quilt-engine@9752895")

    def test_event_count_matches_source_lines_exactly(self):
        self.assertEqual(len(self.result.events), sum(DEMO_SOURCE_LINES.values()))
        self.assertEqual(self.result.header.source["files"], DEMO_SOURCE_LINES)

    def test_per_source_order_preserved(self):
        for filename in DEMO_SOURCE_LINES:
            linenos = [
                int(ev.source.split(":")[1])
                for ev in self.result.events
                if ev.source.startswith(filename + ":")
            ]
            self.assertEqual(
                linenos, sorted(linenos),
                f"{filename}: events left the file's order",
            )

    def test_source_lines_kept_verbatim_in_detail(self):
        for filename in DEMO_SOURCE_LINES:
            originals = [
                json.loads(l)
                for l in (DEMO / filename).read_text().splitlines() if l.strip()
            ]
            details = [
                ev.detail for ev in self.result.events
                if ev.source.startswith(filename + ":")
            ]
            self.assertEqual(details, originals, filename)

    def test_tensor_form_and_tracks(self):
        tracks = set()
        for ev in self.result.events:
            t = ev.tensor()
            self.assertIsInstance(t, list)
            self.assertEqual(len(t), 4)
            self.assertEqual(t[0], ev.tick)
            self.assertEqual(t[1], ev.track)
            self.assertEqual(t[2], ev.intent)
            self.assertEqual(t[3], ev.value)
            tracks.add(ev.track)
        self.assertEqual(tracks, {"seam", "vessel-a", "vessel-b"})

    def test_readings_are_the_only_monotonic_events(self):
        for ev in self.result.events:
            if ev.detail.get("kind") == "reading":
                self.assertEqual(ev.clock, "mono")
                self.assertEqual(ev.intent, "reading")
            else:
                self.assertEqual(ev.clock, "wall")

    def test_decision_intents_carry_kind_and_response(self):
        intents = {ev.intent for ev in self.result.events
                   if ev.intent.startswith("decision:")}
        self.assertIn("decision:hold", intents)
        self.assertIn("decision:hold_watch", intents)
        self.assertEqual(
            {i for i in intents if i.startswith("decision:act:")},
            {"decision:act:accept_best", "decision:act:clarify_narrow",
             "decision:act:refuse"},
        )


class TestRecordingRoundTrip(unittest.TestCase):
    """The recording file is the record form: write it, read it back,
    get the same events back."""

    @classmethod
    def setUpClass(cls):
        cls.result = import_run(DEMO)

    def test_round_trip_preserves_everything(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "recording.jsonl"
            write_recording(path, self.result.header, self.result.events,
                            self.result.gaps)
            header, events, gaps = read_recording(path)
        self.assertEqual(header.emitter, self.result.header.emitter)
        self.assertEqual(header.format, self.result.header.format)
        self.assertEqual(header.start_tick, self.result.header.start_tick)
        self.assertEqual(header.source["files"], DEMO_SOURCE_LINES)
        self.assertEqual(
            [ev.to_record() for ev in events],
            [ev.to_record() for ev in self.result.events],
        )
        self.assertEqual([g.to_record() for g in gaps],
                         [g.to_record() for g in self.result.gaps])


class TestGapsNeverSilentlyClosed(unittest.TestCase):
    """Kills and open excursions are explicit gap markers."""

    def test_full_run_no_truncation_one_recorded_open_excursion(self):
        result = import_run(DEMO)
        truncated = [g for g in result.gaps if g.kind == GAP_TRUNCATED]
        opened = [g for g in result.gaps if g.kind == GAP_OPEN]
        self.assertEqual(truncated, [])  # both books closed with session_end
        # The receiver's session_end records B's excursion unresolved
        # (it ended by going stale, never by a judgment) — shown as
        # recorded, exactly one open marker.
        self.assertEqual(len(opened), 1)
        self.assertEqual(opened[0].detail["transmission_id"], DEMO_OPEN_EXCURSION)

    def test_kill_case_sender_book_is_a_gap_and_excursion_is_open(self):
        result = import_run(KILL)
        truncated = [g for g in result.gaps if g.kind == GAP_TRUNCATED]
        opened = [g for g in result.gaps if g.kind == GAP_OPEN]
        self.assertEqual(len(truncated), 1)
        self.assertEqual(truncated[0].track, "vessel-a")
        self.assertIn("no session_end", truncated[0].note)
        self.assertEqual(len(opened), 1)
        self.assertEqual(opened[0].detail["transmission_id"], KILL_OPEN_EXCURSION)

    def test_kill_case_excursion_never_silently_closed(self):
        # The excursion stays open: no recorded decision ever closes D.
        # The HoldWatch named it; after it, only no-pick Holds (a stale
        # pool) exist — none of which is a judgment about D.
        result = import_run(KILL)
        about_d = [
            ev for ev in result.events
            if ev.intent.startswith("decision:")
            and ev.detail.get("pick") == KILL_OPEN_EXCURSION
        ]
        self.assertTrue(about_d)
        self.assertTrue(
            all(ev.detail["kind"] == "hold_watch" for ev in about_d)
        )

    def test_missing_book_is_a_gap(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            (td / "seam_log.jsonl").write_text(
                '{"at": 1.0, "event": "decision", "kind": "hold", "pick": null}\n'
            )
            result = import_run(td)
        missing = [g for g in result.gaps if g.kind == GAP_TRUNCATED]
        self.assertEqual(len(missing), 2)  # both books absent
        self.assertTrue(all("missing entirely" in g.note for g in missing))

    def test_missing_seam_log_refuses_to_import(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(FileNotFoundError):
                import_run(td)

    def test_malformed_line_names_file_and_line(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            (td / "seam_log.jsonl").write_text(
                '{"at": 1.0, "event": "decision"}\nnot json\n'
            )
            with self.assertRaises(ValueError) as ctx:
                import_run(td)
            self.assertIn("seam_log.jsonl:2", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
