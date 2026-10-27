"""v0.3 bridge-upgrade acceptance (BUILD-BRIEF: bridge upgrade for
quilt-engine v0.3 runs): the a54bb51 fixture imports completely (every
new record kind carried, nothing silently dropped), the audit applies
v0.3 semantics — a superseded citation is AGREED with the skew
reported, skewed bookings are a category of their own — and the
timeline shows revision crossings and adoption points. The 30 v0.1
tests keep their own file unchanged."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from importer import (  # noqa: E402
    REPLAY_LIMIT,
    audit_agreement,
    import_run,
    ledger_entries,
    read_recording,
    render_audit,
    render_timeline,
    revision_entries,
    version_fold,
    write_recording,
)

V03 = ROOT / "tests" / "fixtures" / "quilt-engine-a54bb51-versioning"

# Hand-read from the fixture files (see the fixture README): the three
# contract versions and the transmission ids the scenario mints.
H1 = "7f8c6f778ec9b7a2c8e2e3835c87296e587bd8f9a5f7589038b1f1aa2133ea1c"
H2 = "834a0af5162926e8ef9cbabe9da49b1c8ee29c158a9f91e2b3a61a0134498fdc"
NEVER = "7f6121595699e8755e1cf393d99bc40ecb86b2b309ebff493e4b7f9df889a8b6"
PROPOSAL = "5420a9ec18aad8b3"      # the contract/revision crossing
IN_FLIGHT = "a2eb687ff37ecce4"     # crossing in flight across adoption
STALE_V1 = "29ab3643d191f31a"      # stale v1 citation after adoption
UNKNOWN = "eaa98b9350332e70"       # citation of a statement never crossed

V03_SOURCE_LINES = {"seam_log.jsonl": 21, "sender_book.jsonl": 16,
                    "receiver_book.jsonl": 19}


def v03_run():
    return import_run(V03, engine="SuperInstance/quilt-engine@a54bb51")


def v03_audit(run):
    return audit_agreement(
        ledger_entries(run.run.sender_book.lines),
        ledger_entries(run.run.receiver_book.lines),
        sender_name=run.run.sender_book.owner,
        receiver_name=run.run.receiver_book.owner,
        sender_revisions=run.run.sender_book.lines,
        receiver_revisions=run.run.receiver_book.lines,
    )


class TestV03FixtureImport(unittest.TestCase):
    """The a54bb51 run directory imports with nothing lost: every
    source line one event, detail verbatim, revision records and
    version citations carried, the un-holdable fields named."""

    @classmethod
    def setUpClass(cls):
        cls.result = v03_run()

    def test_every_source_line_is_exactly_one_event(self):
        self.assertEqual(
            len(self.result.events), sum(V03_SOURCE_LINES.values())
        )
        self.assertEqual(self.result.header.source["files"], V03_SOURCE_LINES)

    def test_source_lines_kept_verbatim_in_detail(self):
        for filename in V03_SOURCE_LINES:
            originals = [
                json.loads(l)
                for l in (V03 / filename).read_text().splitlines() if l.strip()
            ]
            details = [
                ev.detail for ev in self.result.events
                if ev.source.startswith(filename + ":")
            ]
            self.assertEqual(details, originals, filename)

    def test_revision_records_carried_as_events(self):
        revs = [ev for ev in self.result.events if ev.intent.startswith("revision:")]
        # three records in per-file arrival order: the sender's book
        # (proposed -> adopted) then the receiver's (adopted)
        self.assertEqual(
            [ev.intent for ev in revs],
            ["revision:proposed", "revision:adopted", "revision:adopted"],
        )
        self.assertEqual(
            [ev.track for ev in revs], ["vessel-a", "vessel-a", "vessel-b"]
        )
        for ev in revs:  # tick is the record's own proposed_at, wall clock
            self.assertEqual(ev.tick, ev.detail["proposed_at"])
            self.assertEqual(ev.clock, "wall")
        self.assertEqual(len(revision_entries(self.result.run.sender_book.lines)), 2)
        self.assertEqual(len(revision_entries(self.result.run.receiver_book.lines)), 1)

    def test_v02_ledger_sides_carried(self):
        intents = [ev.intent for ev in self.result.events]
        # v0.2 payload path: the V0 offer settles on both sides
        self.assertEqual(intents.count("settle"), 2)
        self.assertEqual(intents.count("send"), 10)
        self.assertEqual(intents.count("receive"), 10)

    def test_readings_still_the_only_monotonic_events(self):
        for ev in self.result.events:
            if ev.detail.get("kind") == "reading":
                self.assertEqual(ev.clock, "mono")
            else:
                self.assertEqual(ev.clock, "wall")

    def test_version_citations_summarised_in_header(self):
        cit = self.result.header.source["versioning"]["seam_citations"]
        self.assertIn("beam-quilt/seam-handshake", cit)
        self.assertEqual(
            cit["beam-quilt/seam-handshake"]["cited"], [NEVER, H1, H2]
        )
        self.assertEqual(
            cit["beam-quilt/seam-handshake"]["applied"], [NEVER, H1, H2]
        )

    def test_skew_markings_counted_where_they_live(self):
        skew = self.result.header.source["versioning"]["skew_markings"]
        self.assertEqual(
            skew["book_ledger_detail"],
            {"citation_refusal": 1, "superseded_citation": 2},
        )
        self.assertEqual(
            skew["seam_events"],
            {"superseded_citation": 2, "version_divergence": 1},
        )

    def test_fields_the_record_form_cannot_hold_are_named(self):
        named = self.result.header.source["versioning"]["detail_only_fields"]
        # the revision record: only position + proposed_at get first-class
        # slots; the statement bytes, the chain link, the consent seam
        # and the rest are named, not silently dropped
        for field in ("statement", "supersedes", "owner_consent", "version"):
            self.assertIn(field, named["revision"])
        for field in ("contract_id", "contract_version"):
            self.assertIn(field, named["ledger"])
        for field in ("cited_version", "applied_version", "superseded_citation"):
            self.assertIn(field, named["seam/crossing"])

    def test_recording_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "recording.jsonl"
            write_recording(
                path, self.result.header, self.result.events, self.result.gaps
            )
            _, events, gaps = read_recording(path)
        self.assertEqual(
            [ev.to_record() for ev in events],
            [ev.to_record() for ev in self.result.events],
        )
        self.assertEqual(
            [g.to_record() for g in gaps], [g.to_record() for g in self.result.gaps]
        )


class TestV03AuditOnFixture(unittest.TestCase):
    """The books-only audit under v0.3 semantics, hand-computed from
    the fixture (cross-checked during development against the engine's
    own agreed_crossings at a54bb51: same three-way counts, same
    skewed id)."""

    @classmethod
    def setUpClass(cls):
        cls.imported = v03_run()
        cls.audit = v03_audit(cls.imported)

    def test_hand_computed_counts(self):
        self.assertEqual(
            self.audit.counts, {"agreed": 9, "unagreed": 0, "disputed": 0}
        )
        self.assertEqual(self.audit.skewed, [UNKNOWN])

    def test_superseded_citations_are_agreed_with_the_skew_reported(self):
        for tid in (IN_FLIGHT, STALE_V1):
            self.assertIn(tid, self.audit.agreed)
            note = next(
                v.note for v in self.audit.verdicts if v.transmission_id == tid
            )
            self.assertIn("superseded citation", note)
            self.assertIn(f"under {H1[:8]}", note)
            # the audit's own fold of the receiver's records confirms it
            self.assertIn("confirmed by the fold", note)

    def test_superseded_is_never_a_discrepancy(self):
        for tid in (IN_FLIGHT, STALE_V1):
            self.assertNotIn(tid, self.audit.disputed)
            self.assertNotIn(tid, self.audit.skewed)
            self.assertNotIn(tid, self.audit.unagreed)

    def test_unknown_citation_is_skewed_not_unagreed(self):
        self.assertNotIn(UNKNOWN, self.audit.agreed)
        self.assertNotIn(UNKNOWN, self.audit.unagreed)
        note = next(
            v.note for v in self.audit.verdicts if v.transmission_id == UNKNOWN
        )
        self.assertIn("different versions", note)
        self.assertIn("statement not held", note)

    def test_both_folds_end_on_v2_with_v1_superseded(self):
        for name in ("vessel-a", "vessel-b"):
            fold = self.audit.version_folds[name]
            self.assertEqual(fold["current"], H2)
            self.assertEqual(fold["superseded"], [H1])
            self.assertEqual(fold["fork"], [])

    def test_rendered_audit_names_the_skewed_category(self):
        text = render_audit(self.audit)
        self.assertIn("skewed:    1", text)
        self.assertIn(f"current {H2[:8]}", text)
        self.assertIn(f"superseded [{H1[:8]}]", text)


class TestV03AuditSemantics(unittest.TestCase):
    """Synthetic ledgers pin the v0.3 verdict rules independently of
    any real run."""

    def setUp(self):
        self.h1 = "a" * 64
        self.h2 = "b" * 64
        self.ph = "f" * 64

    def ledger(self, side, tid, version=None, detail=None, ph=None):
        return {"kind": "ledger", "side": side, "transmission_id": tid,
                "payload_hash": ph or self.ph, "peer": "peer",
                "contract_version": version, "detail": detail or {}}

    def revision(self, version, position, supersedes=None):
        return {"kind": "revision", "version": version,
                "position": position, "supersedes": supersedes}

    def test_superseded_citation_is_agreed_skew_reported(self):
        result = audit_agreement(
            [self.ledger("SEND", "t1", version=self.h1)],
            [self.ledger("RECEIVE", "t1", version=self.h1,
                         detail={"superseded_citation": True})],
            receiver_revisions=[self.revision(self.h2, "adopted", self.h1)],
        )
        self.assertEqual(result.counts, {"agreed": 1, "unagreed": 0, "disputed": 0})
        self.assertEqual(result.skewed, [])
        self.assertIn("superseded citation", result.verdicts[0].note)
        self.assertIn("confirmed by the fold", result.verdicts[0].note)

    def test_flag_without_fold_backing_is_reported_as_recorded(self):
        # the receiver marked the citation superseded but its own records
        # don't list the version: shown as recorded, not re-judged
        result = audit_agreement(
            [self.ledger("SEND", "t1", version=self.h1)],
            [self.ledger("RECEIVE", "t1", version=self.h1,
                         detail={"superseded_citation": True})],
            receiver_revisions=[],
        )
        self.assertIn("reported as recorded", result.verdicts[0].note)

    def test_version_mismatch_is_skewed(self):
        result = audit_agreement(
            [self.ledger("SEND", "t1", version=self.h1)],
            [self.ledger("RECEIVE", "t1", version=None,
                         detail={"citation_refusal": "statement not held"})],
        )
        self.assertEqual(result.counts, {"agreed": 0, "unagreed": 0, "disputed": 0})
        self.assertEqual(result.skewed, ["t1"])
        self.assertIn("statement not held", result.verdicts[0].note)

    def test_revoked_refusal_books_receiver_current_and_is_skewed(self):
        result = audit_agreement(
            [self.ledger("SEND", "t1", version=self.h1)],
            [self.ledger("RECEIVE", "t1", version=self.h2,
                         detail={"citation_refusal": "revoked"})],
        )
        self.assertEqual(result.skewed, ["t1"])
        self.assertIn("revoked", result.verdicts[0].note)

    def test_unversioned_v01_pair_still_agrees(self):
        result = audit_agreement(
            [self.ledger("SEND", "t1")], [self.ledger("RECEIVE", "t1")]
        )
        self.assertEqual(result.counts, {"agreed": 1, "unagreed": 0, "disputed": 0})
        self.assertEqual(result.skewed, [])

    def test_hash_mismatch_still_disputed_under_v03_rules(self):
        result = audit_agreement(
            [self.ledger("SEND", "t1", version=self.h1, ph="1" * 64)],
            [self.ledger("RECEIVE", "t1", version=self.h1, ph="2" * 64)],
        )
        self.assertEqual(result.counts, {"agreed": 0, "unagreed": 0, "disputed": 1})
        self.assertEqual(result.skewed, [])

    def test_settle_and_disputed_bookings_never_pair(self):
        # SETTLE / RECEIVE-DISPUTED ride along; only SEND/RECEIVE pair
        one = [self.ledger("SEND", "t1", version=self.h1),
               {"kind": "ledger", "side": "SETTLE", "transmission_id": "t1",
                "payload_hash": self.ph, "peer": "peer",
                "contract_version": self.h1}]
        other = [self.ledger("RECEIVE", "t1", version=self.h1)]
        result = audit_agreement(one, other)
        self.assertEqual(result.counts, {"agreed": 1, "unagreed": 0, "disputed": 0})

    def test_fold_current_is_a_set_operation_and_forks_surface(self):
        h3 = "c" * 64
        # H1 <- H2 <- H3 adopted: H3 current, H1 and H2 superseded
        fold = version_fold([
            self.revision(self.h2, "adopted", self.h1),
            self.revision(h3, "adopted", self.h2),
        ])
        self.assertEqual(fold["current"], h3)
        self.assertEqual(fold["superseded"], [self.h1, self.h2])
        # two adopted successors of one predecessor: a fork, unresolved
        forked = version_fold([
            self.revision(self.h2, "adopted", self.h1),
            self.revision(h3, "adopted", self.h1),
        ])
        self.assertEqual(forked["current"], None)
        self.assertEqual(forked["fork"], sorted([self.h2, h3]))


class TestV03Timeline(unittest.TestCase):
    """The timeline shows the revision crossing, the adoption points
    (receiver before sender — adoption is skewed by construction), the
    skew events, and the named un-holdable fields."""

    @classmethod
    def setUpClass(cls):
        cls.imported = v03_run()
        cls.text = render_timeline(cls.imported, audit=v03_audit(cls.imported))

    def _offset(self, needle):
        for line in self.text.splitlines():
            if needle in line and line.lstrip().startswith("+"):
                return float(line.split("+")[1].split("s")[0])
        self.fail(f"no timeline line matches {needle!r}")

    def test_revision_crossing_shown(self):
        self.assertIn(f"proposal {PROPOSAL[:8]}", self.text)
        self.assertIn("supersedes", self.text)

    def test_adoption_points_shown_on_both_tracks(self):
        self.assertIn(f"proposed v2: {H2[:8]}", self.text)
        self.assertEqual(self.text.count(f"adopted v2: {H2[:8]}"), 2)

    def test_receiver_adopts_before_sender(self):
        # DESIGN-V03 §2.4: local adoption is local; the receiver's
        # record precedes the sender's, which adopts only on the ack
        self.assertLess(
            self._offset("vessel-b     revision   adopted"),
            self._offset("vessel-a     revision   adopted"),
        )

    def test_skew_events_shown(self):
        self.assertIn(f"{IN_FLIGHT[:8]}… honoured under cited {H1[:8]}…", self.text)
        self.assertIn(f"{STALE_V1[:8]}… honoured under cited {H1[:8]}…", self.text)
        self.assertIn(f"{UNKNOWN[:8]}… citation refused: statement not held", self.text)

    def test_crossings_carry_their_citations(self):
        self.assertIn(f"[cites {H1[:8]}", self.text)
        self.assertIn("superseded citation]", self.text)

    def test_audit_section_with_skewed_count_and_folds(self):
        self.assertIn("== agreement audit", self.text)
        self.assertIn("skewed:    1", self.text)
        self.assertIn(f"current {H2[:8]}", self.text)

    def test_unholdable_fields_named_not_dropped(self):
        self.assertIn(
            "== v0.3 record kinds — fields the record form cannot hold ==",
            self.text,
        )
        self.assertIn("owner_consent", self.text)  # §8.1 seam, kept verbatim

    def test_replay_limit_unchanged_and_present(self):
        self.assertIn(f"-- {REPLAY_LIMIT}", self.text)


class TestV03CLIEndToEnd(unittest.TestCase):
    def test_cli_on_v03_fixture(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "examples" / "quilt_timeline.py"),
             "--dir", str(V03),
             "--engine", "SuperInstance/quilt-engine@a54bb51"],
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("skewed:    1", proc.stdout)
        self.assertIn(f"adopted v2: {H2[:8]}", proc.stdout)
        self.assertIn(REPLAY_LIMIT, proc.stdout)


if __name__ == "__main__":
    unittest.main()
