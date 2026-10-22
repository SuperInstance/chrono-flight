"""chrono-flight importer — ingest other systems' run artifacts into
chrono-flight's record form.

First target: quilt-engine run directories (``seam_log.jsonl`` + the
two sovereign books). See ``quilt_engine`` (the importer),
``recording`` (the record form), ``timeline`` (the ordered view),
``audit`` (the books-only agreement audit).

Files at rest only — no live tailing, no code path into a live fleet.
"""

from .audit import AuditResult, audit_agreement, ledger_entries, render_audit
from .quilt_engine import REPLAY_LIMIT, ImportResult, import_run, load_run
from .recording import (
    GAP_OPEN,
    GAP_TRUNCATED,
    Gap,
    RecordedEvent,
    RecordingHeader,
    read_recording,
    write_recording,
)
from .timeline import render_timeline

__all__ = [
    "REPLAY_LIMIT",
    "AuditResult",
    "ImportResult",
    "GAP_OPEN",
    "GAP_TRUNCATED",
    "Gap",
    "RecordedEvent",
    "RecordingHeader",
    "audit_agreement",
    "import_run",
    "ledger_entries",
    "load_run",
    "read_recording",
    "render_audit",
    "render_timeline",
    "write_recording",
]
