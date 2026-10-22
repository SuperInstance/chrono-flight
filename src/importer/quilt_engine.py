"""Ingest a quilt-engine run directory into chrono-flight's record form.

A quilt-engine demo run directory holds three files at rest (no live
tailing — this module reads files, nothing else):

- ``seam_log.jsonl`` — the seam's event log, written by the receiver
  process hosting the seam's decision point. Lines are JSON events:
  ``crossing`` (transmission id, payload type, sender profile, pick,
  ending, cost, contract), ``decision`` (kind ``hold`` / ``hold_watch`` /
  ``act`` with a response kind, pick, deviation), ``disagreement``
  (both measurements kept verbatim), ``course_adjusted``, and
  ``unreadable_envelope``; each line carries the writer's wall-clock
  ``at``. Engine v0.1 also allows a crossing/decision to record the
  projection a decision consulted (with the horizon used) — carried
  through verbatim when present.
- ``sender_book.jsonl`` / ``receiver_book.jsonl`` — each side's
  sovereign book: ``ledger`` entries (SEND/RECEIVE bookings carrying
  transmission id, peer, payload type, payload hash, ending, cost,
  contract), dated ``reading`` entries (on the reader's *monotonic*
  clock — not comparable to the wall-clock stamps, and marked as such
  here rather than smoothed over), and free-form ``event`` entries
  (session_end, refusal_received, sender_hanging, ...).

Mapping into chrono-flight's record form (see ``recording.py``): every
source line becomes exactly one event on a track — the seam log on the
``seam`` track, each book on its owner's track — with the event's own
timestamp as the tick, a natural magnitude as the velocity/pressure
field where one exists (deviation for decisions, divergence for
disagreements, cost for crossings and bookings; ``None`` otherwise —
no numbers are invented), and the full source line kept in ``detail``.
Nothing is dropped, edited, or reordered; unknown event kinds are
recorded under a ``seam:``/``book:`` intent rather than rejected.

Kills and gaps are marked explicitly, never silently closed: a book
with no ``session_end`` is a truncation gap on that side's track, and
excursions the receiver's own ``session_end`` records as unresolved
are marked open on the seam track. An open excursion is only ever
closed by a recorded decision — a stale-pool Hold (no pick) is not a
judgment and does not close one.

**Replay limit, in plain words: this module and every view over it
replay the record of what happened — the receiver's comparative
judgments (Hold / HoldWatch / Act) are shown as recorded, not
re-derived, and chrono-flight does not re-simulate judgment calls.**

The engine's own version is not written into the run directory (the
only version-ish signal in the files is the seam contract id, e.g.
``beam-quilt/seam-handshake@1.2``); callers stamp the engine commit in
the recording header's ``source`` block from what they know.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .recording import (
    CLOCK_MONO,
    CLOCK_WALL,
    GAP_OPEN,
    GAP_TRUNCATED,
    Gap,
    RecordedEvent,
    RecordingHeader,
)

SEAM_LOG = "seam_log.jsonl"
SENDER_BOOK = "sender_book.jsonl"
RECEIVER_BOOK = "receiver_book.jsonl"

TRACK_SEAM = "seam"

REPLAY_LIMIT = (
    "Replay limit: this replays the record of what happened — the "
    "receiver's comparative judgments (Hold / HoldWatch / Act) are shown "
    "as recorded, not re-derived, and chrono-flight does not re-simulate "
    "judgment calls."
)


def _read_jsonl(path: Path) -> list[tuple[int, dict[str, Any]]]:
    """Parse a JSONL file into (line number, object) pairs, in file
    order. An empty or missing file is an empty list — whether that is
    a gap is decided by the caller, not silently here."""
    if not path.exists():
        return []
    out: list[tuple[int, dict[str, Any]]] = []
    for lineno, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            out.append((lineno, json.loads(line)))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path.name}:{lineno}: not valid JSON ({exc})") from exc
    return out


@dataclass
class Book:
    """One side's book file, parsed and kept verbatim."""

    filename: str
    lines: list[tuple[int, dict[str, Any]]]
    owner: str

    @property
    def ledger(self) -> list[dict[str, Any]]:
        return [d for _, d in self.lines if d.get("kind") == "ledger"]

    @property
    def events(self) -> list[dict[str, Any]]:
        return [d for _, d in self.lines if d.get("kind") == "event"]

    def session_end(self) -> dict[str, Any] | None:
        for d in self.events:
            if d.get("event") == "session_end":
                return d
        return None


@dataclass
class RunDirectory:
    """A quilt-engine run directory parsed at rest."""

    dir: Path
    seam_log: list[tuple[int, dict[str, Any]]]
    sender_book: Book
    receiver_book: Book


def load_run(
    run_dir: str | Path,
    *,
    sender_name: str = "vessel-a",
    receiver_name: str = "vessel-b",
) -> RunDirectory:
    """Parse a run directory. The books do not stamp their owner on
    every line, so each book's track name comes from its own
    ``session_end`` role when it has one, else from the caller's
    declared side names (the demo's vessel-a / vessel-b)."""
    run_dir = Path(run_dir)
    if not (run_dir / SEAM_LOG).exists():
        raise FileNotFoundError(f"{run_dir / SEAM_LOG}: no seam log to import")

    def book(filename: str, default_owner: str) -> Book:
        lines = _read_jsonl(run_dir / filename)
        owner = default_owner
        for d in lines:
            body = d[1]
            if body.get("kind") == "event" and body.get("event") == "session_end":
                role = body.get("role")
                if role:
                    owner = str(role)
                break
        return Book(filename=filename, lines=lines, owner=owner)

    return RunDirectory(
        dir=run_dir,
        seam_log=_read_jsonl(run_dir / SEAM_LOG),
        sender_book=book(SENDER_BOOK, sender_name),
        receiver_book=book(RECEIVER_BOOK, receiver_name),
    )


# ---------------------------------------------------------------- mapping

def _require(d: dict[str, Any], key: str, where: str) -> Any:
    if key not in d:
        raise ValueError(f"{where}: missing required field {key!r}")
    return d[key]


def _seam_event(
    lineno: int, d: dict[str, Any], received_at: float
) -> RecordedEvent:
    where = f"{SEAM_LOG}:{lineno}"
    at = float(_require(d, "at", where))
    ev = d.get("event")
    intent: str
    value: float | None
    if ev == "crossing":
        intent = "crossing"
        value = float(d["cost"]) if isinstance(d.get("cost"), (int, float)) else None
    elif ev == "decision":
        kind = str(_require(d, "kind", where))
        if kind == "act":
            intent = f"decision:act:{d.get('response', '?')}"
        else:
            intent = f"decision:{kind}"
        value = (
            float(d["deviation"]) if isinstance(d.get("deviation"), (int, float)) else None
        )
    elif ev == "disagreement":
        intent = "disagreement"
        value = (
            float(d["divergence"])
            if isinstance(d.get("divergence"), (int, float))
            else None
        )
    elif ev in ("course_adjusted", "unreadable_envelope"):
        intent = str(ev)
        value = None
    else:
        # Unknown seam event: record it, never drop it. Forward
        # compatibility beats rejection for a recorder.
        intent = f"seam:{ev}"
        value = None
    return RecordedEvent(
        tick=at,
        track=TRACK_SEAM,
        intent=intent,
        value=value,
        received_at=received_at,
        clock=CLOCK_WALL,
        detail=dict(d),
        source=where,
    )


def _book_event(
    filename: str, lineno: int, d: dict[str, Any], owner: str, received_at: float
) -> RecordedEvent:
    where = f"{filename}:{lineno}"
    kind = d.get("kind")
    if kind == "ledger":
        side = str(_require(d, "side", where))
        if side not in ("SEND", "RECEIVE"):
            raise ValueError(f"{where}: unknown ledger side {side!r}")
        intent = "send" if side == "SEND" else "receive"
        at = float(_require(d, "at", where))
        value = float(d["cost"]) if isinstance(d.get("cost"), (int, float)) else None
        clock = CLOCK_WALL
    elif kind == "reading":
        intent = "reading"
        at = float(_require(d, "taken_at", where))
        value = None  # the reading's value is a dict (or worse); keep it in detail
        clock = CLOCK_MONO  # the reader's monotonic clock — not wall-comparable
    elif kind == "event":
        intent = f"event:{d.get('event', '?')}"
        at = float(_require(d, "at", where))
        value = None
        clock = CLOCK_WALL
    else:
        intent = f"book:{kind}"
        at = float(_require(d, "at", where))
        value = None
        clock = CLOCK_WALL
    return RecordedEvent(
        tick=at,
        track=owner,
        intent=intent,
        value=value,
        received_at=received_at,
        clock=clock,
        detail=dict(d),
        source=where,
    )


# ---------------------------------------------------------------- gaps

def _last_seam_word(seam_log: list[tuple[int, dict[str, Any]]]) -> str:
    """The seam's last recorded decisions, quoted — not a re-derivation
    of anything. When the literal last decision carries no pick (a
    stale pool, not a judgment), the last pick-bearing decision is
    quoted too, so a kill mid-excursion doesn't read as a close."""
    last: dict[str, Any] | None = None
    last_pick: dict[str, Any] | None = None
    for _, d in seam_log:
        if d.get("event") == "decision":
            if last is None:
                last = d
            if d.get("pick") and last_pick is None:
                last_pick = d

    def desc(d: dict[str, Any] | None) -> str:
        if d is None:
            return "none"
        pick = d.get("pick")
        return f"{d.get('kind')}" + (f" pick {pick}" if pick else " (no pick)")

    if last is None:
        return "no decision on the seam"
    if last.get("pick") or last_pick is None or last_pick is last:
        return f"last seam decision: {desc(last)}"
    return (
        f"last seam decision: {desc(last)}"
        f" (stale pool, not a judgment); last pick-bearing: {desc(last_pick)}"
    )


def _book_gap(book: Book, seam_log: list[tuple[int, dict[str, Any]]]) -> Gap | None:
    """A book that never wrote ``session_end`` is a truncation gap:
    that side was killed or its book was cut — the run does not close
    there, and the recording must not pretend it did."""
    if not book.lines:
        return Gap(
            track=book.owner,
            at_tick=0.0,
            note=f"{book.owner}'s book ({book.filename}) is missing entirely",
            kind=GAP_TRUNCATED,
            detail={"filename": book.filename},
        )
    if book.session_end() is not None:
        return None
    last = book.lines[-1][1]
    at = last.get("at")
    note = (
        f"book ends mid-run — no session_end "
        f"(killed or truncated); {_last_seam_word(seam_log)}"
    )
    if last.get("event") == "sender_hanging":
        note += f"; last send {last.get('last_send')}"
    return Gap(
        track=book.owner,
        at_tick=float(at) if isinstance(at, (int, float)) else 0.0,
        note=note,
        kind=GAP_TRUNCATED,
        detail={"last_line": dict(last)},
    )


def _open_excursion_gaps(receiver_book: Book) -> list[Gap]:
    """Excursions the receiver's own session_end records as unresolved.
    Shown exactly as recorded — the engine keeps a pick whose last
    recorded decision kind was hold_watch listed as unresolved, which
    includes excursions that ended by going stale rather than by a
    judgment; that is the record, and this tool does not amend it."""
    end = receiver_book.session_end()
    if not end:
        return []
    out = []
    for tid in end.get("unresolved_excursions") or []:
        out.append(
            Gap(
                track=TRACK_SEAM,
                at_tick=float(end.get("at", 0.0)),
                note=(
                    f"open excursion {tid}: recorded unresolved at "
                    f"{receiver_book.owner}'s session_end — never closed by a "
                    f"decision; a later no-pick Hold is a stale pool, not a judgment"
                ),
                kind=GAP_OPEN,
                detail={"transmission_id": tid, "session_end": dict(end)},
            )
        )
    return out


# ---------------------------------------------------------------- import

@dataclass
class ImportResult:
    """A run directory normalised into chrono-flight's record form."""

    header: RecordingHeader
    events: list[RecordedEvent]
    gaps: list[Gap]
    run: RunDirectory
    tracks: list[str] = field(default_factory=list)


def import_run(
    run_dir: str | Path,
    *,
    sender_name: str = "vessel-a",
    receiver_name: str = "vessel-b",
    emitter: str | None = None,
    engine: str = "quilt-engine (commit not recorded in the run directory)",
) -> ImportResult:
    """Ingest a quilt-engine run directory: one event per source line,
    in per-file arrival order (seam log, then sender book, then
    receiver book), plus explicit gap markers for kills and recorded
    open excursions."""
    run = load_run(run_dir, sender_name=sender_name, receiver_name=receiver_name)
    received_at = time.time()  # the importer's single receive moment

    events: list[RecordedEvent] = [
        _seam_event(lineno, d, received_at) for lineno, d in run.seam_log
    ]
    for book in (run.sender_book, run.receiver_book):
        events.extend(
            _book_event(book.filename, lineno, d, book.owner, received_at)
            for lineno, d in book.lines
        )

    gaps: list[Gap] = []
    for book in (run.sender_book, run.receiver_book):
        g = _book_gap(book, run.seam_log)
        if g is not None:
            gaps.append(g)
    gaps.extend(_open_excursion_gaps(run.receiver_book))

    contracts = sorted(
        {
            str(d.get("contract"))
            for _, d in run.seam_log + run.sender_book.lines + run.receiver_book.lines
            if d.get("contract")
        }
    )
    tracks = []
    for ev in events:
        if ev.track not in tracks:
            tracks.append(ev.track)
    header = RecordingHeader(
        emitter=emitter or f"quilt-engine:{run.dir.name}",
        start_tick=events[0].tick if events else 0.0,
        ingested_at=received_at,
        source={
            "engine": engine,
            "seam_contracts": contracts,
            "run_dir": str(run.dir),
            "files": {
                SEAM_LOG: len(run.seam_log),
                SENDER_BOOK: len(run.sender_book.lines),
                RECEIVER_BOOK: len(run.receiver_book.lines),
            },
            "clocks": {
                CLOCK_WALL: "the engine's wall-clock 'at' stamps",
                CLOCK_MONO: "book reading 'taken_at' (monotonic) — not wall-comparable",
            },
            "sides": {
                "sender": run.sender_book.owner,
                "receiver": run.receiver_book.owner,
            },
        },
    )
    return ImportResult(
        header=header, events=events, gaps=gaps, run=run, tracks=tracks
    )
