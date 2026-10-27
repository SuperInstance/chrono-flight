# BRIDGE-V03-REPORT — chrono-flight bridge upgrade for quilt-engine v0.3 runs

Built on branch **`bridge-v03`** (fresh clone of `main` @ `0a8843b`;
local; not pushed), per `BRIEF.md`. quilt-engine was read only, at
`a54bb51d70e6c9ab3f2bdaf2b29683eaf30bc0b5` (v0.3); its suite (85
tests) was re-run at that commit before the fixture was frozen and
stays green. The bridge's suite went 30 → 62 tests, all green, with
the 30 v0.1 tests untouched.

## What changed

- **`src/importer/quilt_engine.py`** — the importer carries v0.3's
  record kinds without loss. Before this change a v0.3 run directory
  could not be imported at all: `revision` records have no `at` field
  (the old unknown-kind path required one), and v0.2's `SETTLE` /
  `RECEIVE-DISPUTED` ledger sides were rejected as unknown. Now:
  - `kind: "revision"` lines map one-for-one to events, intent
    `revision:<position>` (proposed / adopted / refused / withdrawn /
    revoked), tick `proposed_at` (wall clock — that is the record's
    own time; the engine writes no `at` on it).
  - Ledger sides `SETTLE` / `RECEIVE-DISPUTED` ride with intents
    `settle` / `receive-disputed` (still never pairing in the audit —
    engine parity).
  - Seam events `revision_received`, `superseded_citation`,
    `version_divergence` are first-class intents (previously they
    would have been recorded as `seam:<name>` unknowns — still
    lossless, but unnamed).
  - The recording header gains a `versioning` block:
    `seam_citations` (per contract id, versions the sources show
    cited / applied), `revision_records` (positions booked, both
    books), `skew_markings` (counted where they live — the books'
    ledger details and the seam's own events are two records of the
    same skew), and `detail_only_fields`.
  - **Fields the record form cannot hold are named, not dropped.**
    The chrono-tensor event `[tick, track, intent, value]` has no
    slot for a version citation, a chain link, or a statement. The
    importer computes, per record kind, the source fields that ride
    only in `detail` (`detail_only_fields`, from the actual data —
    `revision` names `statement`, `supersedes`, `owner_consent`, …;
    `ledger` names `contract_id`, `contract_version`, …). The
    timeline prints the inventory; every one of those fields is kept
    byte-verbatim in the event's `detail` (test-asserted against the
    fixture files).
- **`src/importer/audit.py`** — v0.3 semantics, still derived from
  the two books alone (see decisions below). New: the `skewed`
  category, skew reporting on agreed superseded citations, and
  `version_fold` (the DESIGN-V03 §4.1 set-operation fold over each
  book's revision records, reported beside the verdicts and used to
  cross-check superseded markings). `revision_entries` exported
  alongside `ledger_entries`.
- **`src/importer/timeline.py`** — revision crossings (the
  `contract/revision` proposal at the seam, each crossing's citation
  pair `[cites H → applied H]`), adoption points (each book's
  `revision:` records on its own track — the receiver's `adopted`
  visibly precedes the sender's, which adopts only on the ack), skew
  events, and the fields-not-held section. Book events
  `adoption_ack_received` / `revision_position_booked` render their
  version/position facts.
- **`examples/quilt_timeline.py`** — passes each book's revision
  records into the audit (fold + cross-check); `--engine` stamps the
  header as before.
- **`tests/fixtures/quilt-engine-a54bb51-versioning/`** — the frozen
  v0.3 run (provenance below), beside the v0.1 fixtures.
- **`tests/test_v03.py`** — 32 new tests (the 30 v0.1 tests are
  untouched): fixture import completeness, superseded-citation audit
  verdict, skewed category in audit output, revision entries on the
  timeline, synthetic v0.3 verdict rules, recording round-trip, CLI
  end-to-end.

The **replay-limit statement is unchanged in force and in bytes** —
same string, still printed with every timeline output, still carried
in the importer docstring. The audit's version fold reads records; it
does not re-derive anyone's judgments.

## Fixture provenance

`tests/fixtures/quilt-engine-a54bb51-versioning/` is one real run of
the v0.3 two-process demo's versioning scenario, frozen exactly as the
demo left it (minus `inbox/`, `responses/`, `done.flag`):

- Engine: `SuperInstance/quilt-engine` @
  `a54bb51d70e6c9ab3f2bdaf2b29683eaf30bc0b5` (v0.3), suite re-run at
  that commit: 85 tests green.
- Command: `DEMO_TIME_SCALE=0.6 python3 examples/two_process_demo.py
  --dir <tmp> --scenario versioning` (orchestrated mode; the run
  passed the demo's own `VERSIONING OK` acceptance, which checks the
  adoption cycle, the in-flight/stale honoured citations, the refused
  unknown citation, the standing v1 settlement, and the skewed
  category via the engine's own `agreed_crossings`).
- Captured 2026-10-27, Python 3.12. One real run — do not regenerate
  and expect the same ticks or transmission ids.
- Hand-computed facts (asserted by the new tests, cross-checked
  against the engine's own `agreed_crossings` during development):
  10 unique transmission ids; audit **9 agreed / 1 skewed / 0
  unagreed / 0 disputed**; the skewed crossing is the unknown-version
  probe `eaa98b9350332e70`; crossings `a2eb687ff37ecce4` (in flight
  across adoption) and `29ab3643d191f31a` (stale v1 citation) are
  agreed under H1 with the receiver's `superseded_citation` marking;
  both books' folds end on H2 (`834a0af5…`) with H1 (`7f8c6f77…`)
  superseded.

## Audit-semantics decisions

Each decision is pinned by the engine's own tests where one exists;
none of this consults the seam log or the engine's verdicts.

1. **Agreement includes the version** (DESIGN-V03 §6.6). A crossing is
   agreed when a SEND in one book pairs with a RECEIVE in the other
   on the same transmission id, payload hash **and contract version**
   (v0.1 books carry no version on either side — `None` matches
   `None`, so the 7/2 agreed counts of the v0.1 fixtures are
   unchanged). Pinned by `test_versioning.py::
   test_matching_versions_still_agree` and
   `test_v01_unversioned_crossings_still_agree`.
2. **A superseded citation is AGREED, with the skew reported** — both
   books stamped the cited version, so honouring it *is* the
   agreement; the receiver's `detail.superseded_citation` marking is
   quoted in the note and cross-checked against the audit's own fold
   of the receiver's revision records (confirmation noted; a marking
   the fold does not back is reported as recorded, not amended).
   Pinned by `test_in_flight_honoured_under_cited_version` (engine
   asserts the crossing is agreed, `skewed == []`, flag set).
3. **Skewed is its own category**: both sides booked the id and the
   hash, but every cross-book pairing names different versions (a
   refused revoked/unknown citation — the receiver stamped its
   current, or `None`). Pinned by
   `test_unknown_citation_refused_and_statement_requested`,
   `test_revoked_citation_refused_under_receiver_current`, and
   `test_mismatched_versions_are_skewed_not_unagreed`.
4. **`skewed` is not folded into `counts`.** The audit's `counts`
   property keeps its exact v0.1 shape (`agreed` / `unagreed` /
   `disputed`) — the 30 existing tests assert that dict — and
   `skewed` rides as its own list and its own rendered line. Nothing
   is averaged anywhere (§3.4), including into our own counts.
5. **Disputed (chrono-flight's own category) is kept, and the
   precedence is agreed > skewed > disputed > unagreed.** The
   engine's `agreed_crossings` has three categories and folds
   hash-mismatch into unagreed; the bridge's pre-existing `disputed`
   (both sides booked, hashes differ, or bookings share a book) is
   older and richer, so it stands. A hash mismatch under matching
   versions stays disputed, not skewed
   (`test_hash_mismatch_still_disputed_under_v03_rules`).
6. **SETTLE / RECEIVE-DISPUTED never pair**, exactly as the engine
   documents ("only SEND/RECEIVE pairings classify a crossing").
7. **The fold is the §4.1 set operation, and its limits are
   stated.** `current` is the adopted tip nothing else supersedes —
   never a clock; a fork surfaces as a fork with `current = None`.
   From the books alone the pinned base version is not recoverable as
   a *record* (the engine's `contract_state` takes it as exogenous
   input), so a book with no live adoptions renders "the seam's
   pinned base governs" rather than inventing one. Revocation is
   version-local (a revoked tip falls back; descendants stand), per
   `test_revocation_is_version_local` and
   `test_current_is_a_set_operation_not_a_clock`.

## Where v0.3 was ambiguous, and what I did about it

Honest findings, each handled explicitly rather than smoothed over:

1. **Revision records carry no `at`.** The books' `RevisionEntry`
   writes `proposed_at` (wall clock) and nothing else time-shaped.
   The importer takes `proposed_at` as the tick and says so in the
   header inventory; the recording never claims it is the engine's
   booking-stamp `at` that other records carry.
2. **What "applied" means on a SEND.** DESIGN-V03 §6.2: the SEND books
   the version *the sender* applied — which is also what it cited. The
   header's `seam_citations.applied` set therefore includes versions
   the sender applied on its own SENDs (in the fixture, the
   never-crossed third hash appears in both `cited` and `applied`
   because the *sender* sent under it). That is the design's wording,
   not a bug here, but a reader of the summary should know a SEND
   speaks only for its own side.
3. **The skew flag is noisy during the adoption window** (DESIGN-V03
   §3.2, stated by the design itself): the in-flight crossing V3 is
   flagged `superseded_citation` even though the seam was bilaterally
   still on v1 when it was sent — the receiver had already adopted.
   The engine's test pins exactly this (`skewed == []`, flag set), so
   the bridge reports the marking as recorded and does not second-guess
   it.
4. **v0.2 seam events (`payload_received`, `payload_disputed`) stay
   unnamed.** They appear in the versioning fixture (the V0 probe) and
   are carried verbatim under `seam:` intents, visible on the
   timeline, in detail without loss — but they are v0.2's kinds, not
   in this brief's list, so they got no first-class intent. Named in
   the header inventory as `seam/payload_received` fields.
5. **A referee audit exists one commit after the pinned engine
   commit** (`91a1b41`, "CC1 referee audit" — smuggled-rulings
   findings about v0.3's behavior: refused versions govern,
   re-adoption erases revocations, etc.). It changes no code the books
   write. The fixture is from `a54bb51` as the brief pins; the bridge
   reads only what the books record, so none of those findings require
   a different reading here — noted because an auditor of this bridge
   may meet them.
6. **The engine's `agreed_crossings` does not distinguish chrono-
   flight's `disputed`.** See decision 5 — the difference is
   documented rather than reconciled, and the fixture's hand-computed
   facts agree with the engine on everything the engine does categorise
   (agreed 9, skewed 1, unagreed 0).

## Tests

    python3 -m unittest discover -s tests

Tail of the run on `bridge-v03`:

    ..............................................................
    --------------------------------------------------------------------
    Ran 62 tests in 0.283s

    OK

30 pre-existing (v0.1) tests untouched and green; 32 new in
`tests/test_v03.py`: fixture import completeness (one event per source
line, detail verbatim, revision records, v0.2 sides, header summaries,
named un-holdable fields, recording round-trip), audit on the fixture
(hand-computed counts, superseded-citation verdicts with
fold-confirmed skew, skewed category, rendered output), synthetic
v0.3 verdict rules (skew, revoked refusal, unversioned agreement,
hash-mismatch-still-disputed, SETTLE non-pairing, fold/fork), timeline
(revision crossing, adoption points, receiver-before-sender adoption
order, skew events, citation display, un-holdable-fields section,
replay limit), and the CLI end-to-end.

## Non-goals honored

No changes to quilt-engine (local clone at `a54bb51`, working tree
clean). Files at rest only. Stdlib only. Not pushed.
