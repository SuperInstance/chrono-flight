# chrono-flight src/ — planned layout

Components are defined by ARCHITECTURE.md, not by a stack. Python 3 (stdlib only), matching the programme's other repos.

- `recorder/` — append-only capture of the live event stream (stub).
- `store/` — recording files: full-fidelity ring buffer; downmixing on read (v1+) (stub).
- `playback/` — scrub / mute / solo / quantize views over a recording; branch export (later) (stub).
- `shell/` — chrono-shell piano-roll UI over the playback API (terminal first) (stub).
- `importer/` — built: ingest other systems' run artifacts at rest into the record form. First target: quilt-engine run directories (`seam_log.jsonl` + both books), with a timeline view, a books-only agreement audit, and explicit kill/open-excursion gap markers.

Build order and acceptance criteria: ../BUILD-BRIEF.md; the importer's build: ../BRIEF.md, reported in ../BRIDGE-REPORT.md.
