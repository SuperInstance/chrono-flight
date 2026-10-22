"""chrono-flight's record form — the recording file and its events.

A recording is an append-only JSONL file (ARCHITECTURE.md §1–2, v0:
full fidelity only):

- one **header** record first — emitter id, start tick, format version
  (BUILD-BRIEF deliverable 1) — plus where the recording came from;
- **event** records after that, one per captured event, in arrival
  order. Each carries the event itself in the chrono-tensor form
  ``[time/tick, channel/agent, intent, velocity/pressure]``, alongside
  the recorder's own receive-timestamp, the clock domain of the tick
  (imported runs mix the engine's wall-clock stamps with monotonic
  reading stamps — the two are not comparable, and the recording says
  which is which instead of smoothing it over), a ``detail`` dict of
  the source's own fields, and a ``source`` reference (file:line) back
  to where the event was captured;
- **gap** records marking explicit holes — a killed or truncated
  source, an excursion a side left open — so a recording that ends
  mid-story says so instead of looking complete (BUILD-BRIEF
  acceptance: never a silently truncated file that looks complete).

Nothing is added beyond these three record kinds, and nothing captured
is edited, filtered, or reordered: a recording that can be argued with
is worthless.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

RECORDING_FORMAT = "chrono-flight/recording-1"

# Clock domains a tick may live in. Imported quilt-engine runs carry
# both: seam/ledger/event stamps are the engine's wall clock; book
# readings stamp `taken_at` on the reader's monotonic clock.
CLOCK_WALL = "wall"
CLOCK_MONO = "mono"

# Gap kinds: `gap` = a source stopped producing (killed/truncated/
# missing); `open` = an excursion the record itself says was never
# closed. Both are explicit markers; neither is inferred from silence.
GAP_TRUNCATED = "gap"
GAP_OPEN = "open"


@dataclass
class RecordedEvent:
    """One captured event in chrono-flight's record form."""

    tick: float
    track: str
    intent: str
    value: float | None  # velocity/pressure; None when no number exists
    received_at: float  # this recorder's own receive-timestamp
    clock: str = CLOCK_WALL
    detail: dict[str, Any] = field(default_factory=dict)
    source: str = ""  # e.g. "seam_log.jsonl:12"

    def tensor(self) -> list[Any]:
        """The chrono-tensor event form: [time/tick, channel/agent,
        intent, velocity/pressure]."""
        return [self.tick, self.track, self.intent, self.value]

    def to_record(self) -> dict[str, Any]:
        return {
            "record": "event",
            "event": self.tensor(),
            "received_at": self.received_at,
            "clock": self.clock,
            "detail": self.detail,
            "source": self.source,
        }

    @classmethod
    def from_record(cls, d: dict[str, Any]) -> "RecordedEvent":
        if d.get("record") != "event" or "event" not in d:
            raise ValueError(f"not an event record: {d!r:.120}")
        tick, track, intent, value = d["event"]
        return cls(
            tick=tick,
            track=track,
            intent=intent,
            value=value,
            received_at=d["received_at"],
            clock=d.get("clock", CLOCK_WALL),
            detail=d.get("detail", {}),
            source=d.get("source", ""),
        )


@dataclass
class Gap:
    """An explicit hole in the record (never silent)."""

    track: str
    at_tick: float
    note: str
    kind: str = GAP_TRUNCATED  # GAP_TRUNCATED | GAP_OPEN
    clock: str = CLOCK_WALL
    detail: dict[str, Any] = field(default_factory=dict)
    source: str = ""

    def to_record(self) -> dict[str, Any]:
        return {
            "record": "gap",
            "kind": self.kind,
            "track": self.track,
            "at_tick": self.at_tick,
            "clock": self.clock,
            "note": self.note,
            "detail": self.detail,
            "source": self.source,
        }

    @classmethod
    def from_record(cls, d: dict[str, Any]) -> "Gap":
        if d.get("record") != "gap":
            raise ValueError(f"not a gap record: {d!r:.120}")
        return cls(
            track=d["track"],
            at_tick=d["at_tick"],
            note=d["note"],
            kind=d.get("kind", GAP_TRUNCATED),
            clock=d.get("clock", CLOCK_WALL),
            detail=d.get("detail", {}),
            source=d.get("source", ""),
        )


@dataclass
class RecordingHeader:
    """The recording's first line: emitter id, start tick, format
    version (BUILD-BRIEF deliverable 1), plus provenance of the
    capture."""

    emitter: str
    start_tick: float
    format: str = RECORDING_FORMAT
    source: dict[str, Any] = field(default_factory=dict)
    ingested_at: float | None = None

    def to_record(self) -> dict[str, Any]:
        return {
            "record": "header",
            "format": self.format,
            "emitter": self.emitter,
            "start_tick": self.start_tick,
            "ingested_at": self.ingested_at,
            "source": self.source,
        }

    @classmethod
    def from_record(cls, d: dict[str, Any]) -> "RecordingHeader":
        if d.get("record") != "header":
            raise ValueError(f"not a header record: {d!r:.120}")
        return cls(
            emitter=d["emitter"],
            start_tick=d["start_tick"],
            format=d.get("format", RECORDING_FORMAT),
            source=d.get("source", {}),
            ingested_at=d.get("ingested_at"),
        )


def write_recording(
    path: str | Path,
    header: RecordingHeader,
    events: list[RecordedEvent],
    gaps: list[Gap],
) -> None:
    """Write a recording file: header, then events in arrival order,
    then gap markers."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(header.to_record(), sort_keys=True) + "\n")
        for ev in events:
            fh.write(json.dumps(ev.to_record(), sort_keys=True) + "\n")
        for gap in gaps:
            fh.write(json.dumps(gap.to_record(), sort_keys=True) + "\n")


def read_recording(
    path: str | Path,
) -> tuple[RecordingHeader, list[RecordedEvent], list[Gap]]:
    """Read a recording file back. The first record must be the
    header; anything that is not a header/event/gap record raises — a
    recording with unknown records in it is somebody else's format."""
    header: RecordingHeader | None = None
    events: list[RecordedEvent] = []
    gaps: list[Gap] = []
    for lineno, line in enumerate(
        Path(path).read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        d = json.loads(line)
        kind = d.get("record")
        if header is None:
            if kind != "header":
                raise ValueError(
                    f"{path}:{lineno}: first record is {kind!r}, not a header"
                )
            header = RecordingHeader.from_record(d)
        elif kind == "header":
            raise ValueError(f"{path}:{lineno}: a second header record")
        elif kind == "event":
            events.append(RecordedEvent.from_record(d))
        elif kind == "gap":
            gaps.append(Gap.from_record(d))
        else:
            raise ValueError(f"{path}:{lineno}: unknown record kind {kind!r}")
    if header is None:
        raise ValueError(f"{path}: no header record")
    return header, events, gaps
