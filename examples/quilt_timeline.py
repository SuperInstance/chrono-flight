"""Print a quilt-engine run directory as a chrono-flight timeline.

The CLI form of the bridge deliverables: ordered timeline (crossings,
decisions with kind and response, disagreements), explicit gaps
(kills, open excursions), the agreement audit recomputed from the two
books alone, and the replay-limit statement. Optionally writes the
run as a chrono-flight recording file.

    python3 examples/quilt_timeline.py --dir tests/fixtures/quilt-engine-9752895-demo
    python3 examples/quilt_timeline.py --dir RUN --record out.jsonl --all
    python3 examples/quilt_timeline.py --dir RUN --no-audit

Files at rest only: this reads a finished run directory; it does not
tail a live one and has no path into a running fleet.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from importer import (  # noqa: E402
    audit_agreement,
    import_run,
    ledger_entries,
    render_timeline,
    write_recording,
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dir", required=True, help="quilt-engine run directory")
    ap.add_argument(
        "--record", metavar="OUT.jsonl", default=None,
        help="also write the run as a chrono-flight recording file",
    )
    ap.add_argument(
        "--all", action="store_true",
        help="include every book booking and reading (default: seam events,"
             " book events, and gaps)",
    )
    ap.add_argument(
        "--no-audit", action="store_true",
        help="skip the books-only agreement audit",
    )
    ap.add_argument(
        "--engine", default="quilt-engine (commit not recorded in the run directory)",
        help="engine label/commit stamped into the recording header",
    )
    args = ap.parse_args()

    result = import_run(args.dir, engine=args.engine)
    audit = None
    if not args.no_audit:
        audit = audit_agreement(
            ledger_entries(result.run.sender_book.lines),
            ledger_entries(result.run.receiver_book.lines),
            sender_name=result.run.sender_book.owner,
            receiver_name=result.run.receiver_book.owner,
            sender_revisions=result.run.sender_book.lines,
            receiver_revisions=result.run.receiver_book.lines,
        )
    print(render_timeline(result, audit=audit, all_events=args.all))
    if args.record:
        write_recording(args.record, result.header, result.events, result.gaps)
        print(f"\nrecording written: {args.record}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
