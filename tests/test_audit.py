"""Agreement audit acceptance (BRIEF deliverable 3): from the two
books alone, recomputed counts match the hand-computed expectations
for both fixtures, and the verdict rules hold on synthetic ledgers.
The audit never sees the seam log or the engine's own verdicts."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from importer import audit_agreement, import_run, ledger_entries  # noqa: E402

DEMO = ROOT / "tests" / "fixtures" / "quilt-engine-9752895-demo"
KILL = ROOT / "tests" / "fixtures" / "quilt-engine-9752895-kill"


def books(fixture):
    run = import_run(fixture)
    return (
        ledger_entries(run.run.sender_book.lines),
        ledger_entries(run.run.receiver_book.lines),
    )


class TestFixtureCounts(unittest.TestCase):
    def test_demo_fixture_matches_hand_computed_counts(self):
        sender, receiver = books(DEMO)
        result = audit_agreement(sender, receiver)
        # Hand-computed from the fixture (see its README): five
        # sender→receiver crossings (A, B, D, E, F) + two responses
        # (clarify question, refusal profile); refreshes reuse ids.
        self.assertEqual(result.counts, {"agreed": 7, "unagreed": 0, "disputed": 0})
        self.assertEqual(
            set(result.agreed),
            {
                "3bfc676e1f05996d",  # A telemetry
                "f4c6f8edd3959921",  # B course-proposal (transient excursion)
                "aa69b1e8fec26394",  # D course-proposal -> accept_best
                "d0f45a4ea99520e6",  # E course-proposal -> clarify_narrow
                "6fb5840a96187cb8",  # F course-proposal -> refuse
                "18b3b2853530e202",  # response: clarify/narrow question
                "37f5a8c7ab974acf",  # response: refusal profile
            },
        )

    def test_kill_fixture_matches_hand_computed_counts(self):
        sender, receiver = books(KILL)
        result = audit_agreement(sender, receiver)
        # Hand-computed: A and D both crossed and both sides booked them
        # with matching hashes before the sender was killed.
        self.assertEqual(result.counts, {"agreed": 2, "unagreed": 0, "disputed": 0})
        self.assertEqual(
            set(result.agreed),
            {"9c6608ce36d3d36e", "396e366f94c793a6"},
        )


def ledger(side, tid, ph, peer="peer"):
    return {"kind": "ledger", "side": side, "transmission_id": tid,
            "payload_hash": ph, "peer": peer}


class TestVerdictRules(unittest.TestCase):
    """Synthetic ledgers pin the three verdicts down independently of
    any real run."""

    def setUp(self):
        self.h1 = "a" * 64
        self.h2 = "b" * 64

    def test_send_without_receive_is_unagreed(self):
        result = audit_agreement([ledger("SEND", "t1", self.h1)], [])
        self.assertEqual(result.counts, {"agreed": 0, "unagreed": 1, "disputed": 0})
        self.assertIn("no RECEIVE anywhere", result.verdicts[0].note)

    def test_receive_without_send_is_unagreed(self):
        result = audit_agreement([], [ledger("RECEIVE", "t1", self.h1)])
        self.assertEqual(result.counts, {"agreed": 0, "unagreed": 1, "disputed": 0})
        self.assertIn("no SEND anywhere", result.verdicts[0].note)

    def test_hash_mismatch_is_disputed(self):
        result = audit_agreement(
            [ledger("SEND", "t1", self.h1)], [ledger("RECEIVE", "t1", self.h2)]
        )
        self.assertEqual(result.counts, {"agreed": 0, "unagreed": 0, "disputed": 1})
        self.assertIn("no agreeing cross-book pair", result.verdicts[0].note)

    def test_both_bookings_in_one_book_is_disputed(self):
        # A crossing needs two sides; SEND and RECEIVE inside one book
        # is a ledger anomaly, not shared state.
        one_book = [ledger("SEND", "t1", self.h1), ledger("RECEIVE", "t1", self.h1)]
        result = audit_agreement(one_book, [])
        self.assertEqual(result.counts, {"agreed": 0, "unagreed": 0, "disputed": 1})

    def test_matching_cross_book_pair_is_agreed(self):
        result = audit_agreement(
            [ledger("SEND", "t1", self.h1)], [ledger("RECEIVE", "t1", self.h1)]
        )
        self.assertEqual(result.counts, {"agreed": 1, "unagreed": 0, "disputed": 0})

    def test_reverse_direction_is_agreed_too(self):
        # Responses cross receiver→sender: SEND in the receiver's book.
        result = audit_agreement(
            [ledger("RECEIVE", "t1", self.h1)], [ledger("SEND", "t1", self.h1)]
        )
        self.assertEqual(result.counts, {"agreed": 1, "unagreed": 0, "disputed": 0})


if __name__ == "__main__":
    unittest.main()
