# chrono-flight src/ — planned layout

Language not yet chosen; components are defined by ARCHITECTURE.md, not by a stack. No code beyond stubs yet.

- `recorder/` — append-only capture of the live event stream.
- `store/` — recording files: full-fidelity ring buffer; downmixing on read (v1+).
- `playback/` — scrub / mute / solo / quantize views over a recording; branch export (later).
- `shell/` — chrono-shell piano-roll UI over the playback API (terminal first).

Build order and acceptance criteria: ../BUILD-BRIEF.md.
