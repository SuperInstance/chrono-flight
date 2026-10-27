# Fixture: quilt-engine two-process demo, versioning scenario (v0.3)

Frozen capture of one real run of the quilt-engine v0.3 two-process
demo's versioning scenario (DESIGN-V03: contract versioning).

- Engine: SuperInstance/quilt-engine @ `a54bb51d70e6c9ab3f2bdaf2b29683eaf30bc0b5` (v0.3)
- Command: `DEMO_TIME_SCALE=0.6 python3 examples/two_process_demo.py
  --dir <tmp> --scenario versioning` (orchestrated mode: spawns
  receiver + sender, then verifies — the run passed the demo's own
  `VERSIONING OK` acceptance)
- Captured: 2026-10-27, Python 3.12, this machine's clocks. Timestamps
  are one real run — do not regenerate and expect the same ticks or
  transmission ids.

Files (exactly as the demo left them, minus the file-drop `inbox/`,
`responses/` and `done.flag` artifacts):

- `seam_log.jsonl` — the seam's event log, written by the receiver.
  v0.3 adds `revision_received`, `superseded_citation`, and
  `version_divergence` events; `crossing`/`payload_received` events
  carry the citation pair (`cited_version` → `applied_version`).
- `sender_book.jsonl` — vessel-a's sovereign book. v0.3 adds
  `kind: "revision"` records (the ex-ante half of the ledger:
  `proposed` → `adopted` for H2) and ledger citations
  (`contract_id` + `contract_version`, the version this side applied).
- `receiver_book.jsonl` — vessel-b's sovereign book: its `adopted`
  revision record, versioned ledger entries (RECEIVEs stamped with the
  version applied — including two honoured superseded citations and
  one refused unknown citation stamped `null`), candidate readings,
  events.

Hand-computed facts (tests assert these; cross-checked against the
engine's own `agreed_crossings` at a54bb51 during development):

- 10 unique transmission ids: V0 payload offer (settled under v1) +
  its receipt, V1 clean v1 probe, the `contract/revision` proposal,
  V3 in-flight probe, the `contract/adoption-ack`, V4 clean v2 probe,
  V5 stale-v1 probe, V6 unknown-version probe, and the
  `version-probe/unknown/narrow` statement request that crossed back.
- Versions: H1 = `7f8c6f778ec9b7a2…` (sha256 of the pinned v1
  handshake statement), H2 = `834a0af5162926e8…` (its revision,
  label "v2"), and a third hash that never crossed (`7f612159…`).
- Agreement audit from the two books alone (v0.3 semantics: agreement
  includes the version): **9 agreed, 1 skewed, 0 unagreed, 0
  disputed**. The skewed crossing is `eaa98b9350332e70` (V6: sender
  cited a statement the receiver never held — refused
  `citation_refusal: "statement not held"`, RECEIVE stamped `null`).
- Two crossings are AGREED under H1 with the receiver's
  `superseded_citation: true` marking on its RECEIVE:
  `a2eb687ff37ecce4` (V3, in flight across the adoption boundary) and
  `29ab3643d191f31a` (V5, stale v1 citation after adoption) — honoured
  under the cited version, never re-judged.
- Both books end with `session_end` — no kill, no truncation gap; no
  recorded unresolved excursions (the version-probe crossings sit
  inside the band; the seam holds them, it never acts on them).
- Adoption is skewed by construction: the receiver books `adopted`
  before the sender (its record sits earlier in wall time); the
  sender books `proposed` → (ack received) → `adopted`.
