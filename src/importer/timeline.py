"""Ordered timeline view over an imported run.

Prints the run as one ordered timeline — crossings, decisions with
their kind (Hold / HoldWatch / Act + response), disagreements — with
kills and truncation gaps rendered as explicit gaps: a side's book
ending mid-excursion reads as an open excursion, never silently closed.

v0.3 runs also show their contract-versioning story: revision
**crossings** (a ``contract/revision`` proposal at the seam, the
citations each crossing carries), **adoption points** (each book's
``revision`` records — proposed / adopted / refused / withdrawn /
revoked — on the adopting side's track), and the **skew** events (a
crossing honoured under a superseded citation; a citation refused with
a version divergence). All shown as recorded, never re-judged.

Ordering: events on the engine's wall clock merge by tick (ties keep
arrival order). Book readings are stamped on each reader's *monotonic*
clock, which is not comparable to wall time; they are shown in their
own per-track section in book order, never interleaved into the
wall-clock timeline — clock disagreement stays visible instead of
being smoothed over. Revision records are stamped ``proposed_at`` on
the same wall clock and merge into the timeline.

Replay limit: the timeline output carries chrono-flight's standing
limit in plain words — this replays the record of what happened; the
receiver's comparative judgments (Hold / HoldWatch / Act) are shown as
recorded, not re-derived.
"""

from __future__ import annotations

from typing import Any

from .audit import AuditResult, render_audit
from .quilt_engine import REPLAY_LIMIT, ImportResult
from .recording import GAP_OPEN, RecordedEvent

# Intents shown on the main timeline by default. Ledger bookings
# (send/receive, one line per refresh — dozens on a real run) and
# monotonic readings are shown only with all_events=True; the recording
# holds them regardless.
_DEFAULT_PREFIXES = ("crossing", "decision:", "disagreement", "course_adjusted",
                     "unreadable_envelope", "seam:", "event:",
                     "revision_received", "superseded_citation",
                     "version_divergence", "revision:")


def _short(tid: Any) -> str:
    s = str(tid)
    return s if len(s) <= 8 else s[:8] + "…"


def _decision_text(ev: RecordedEvent) -> str:
    d = ev.detail
    kind = str(d.get("kind"))
    label = {"hold": "Hold", "hold_watch": "HoldWatch"}.get(kind, kind)
    if kind == "act":
        label = f"Act({d.get('response', '?')})"
    pick = d.get("pick")
    pick_text = f"pick {_short(pick)}" if pick else "no pick — pool empty"
    text = f"{label} {pick_text}"
    if isinstance(d.get("deviation"), (int, float)):
        text += f" deviation {float(d['deviation']):.2f}"
    text += _projection_text(d.get("projection"))
    return text


def _projection_text(p: Any) -> str:
    """v0.1: the projection a decision consulted, as recorded (the
    two-process demo's seam log does not write one; JevPair runs do)."""
    if not isinstance(p, dict):
        return ""
    if p.get("refused"):
        return f" [projection refused: {p.get('reason', '?')}]"
    if p.get("value") is not None:
        used = "used" if p.get("used") else "recorded"
        return (
            f" [projection {used}: value {float(p['value']):.3f}, "
            f"horizon {float(p.get('horizon', 0)):.2f}s "
            f"≤ cap {float(p.get('max_horizon', 0)):.2f}s]"
        )
    return " [projection recorded]"


def _version(v: Any) -> str:
    """A version hash for display, with the honest none-cases named."""
    if v is None:
        return "—"
    return _short(v)


def _crossing_text(ev: RecordedEvent) -> str:
    d = ev.detail
    text = f"{_short(d.get('transmission_id'))} {d.get('payload_type', '?')}"
    facts = []
    if d.get("ending"):
        facts.append(str(d["ending"]))
    if isinstance(d.get("cost"), (int, float)):
        facts.append(f"cost {float(d['cost']):.1f}")
    if facts:
        text += f" ({', '.join(facts)})"
    # v0.3: the citation pair the crossing carried — the version the
    # sender cited and the version the receiver applied (a superseded
    # citation is honoured under the cited one; the flag says the
    # receiver knows it has moved past it).
    if "cited_version" in d or "applied_version" in d:
        text += (
            f" [cites {_version(d.get('cited_version'))}"
            f" → applied {_version(d.get('applied_version'))}"
            + ("; superseded citation" if d.get("superseded_citation") else "")
            + "]"
        )
    return text


def _revision_received_text(ev: RecordedEvent) -> str:
    """A revision proposal crossing the seam (the crossing itself; the
    receiver's position on it is its own book's record)."""
    d = ev.detail
    label = f" {d['label']}" if d.get("label") else ""
    text = (
        f"proposal {_short(d.get('transmission_id'))}{label}:"
        f" {_short(d.get('version'))} supersedes {_version(d.get('supersedes'))}"
        f" — receiver position {d.get('position', '?')}"
        f" (cites {_version(d.get('cited_version'))}"
        f" → applied {_version(d.get('applied_version'))}"
        + (f"; {d['reason']}" if d.get("reason") else "")
        + ")"
    )
    return text


def _superseded_citation_text(ev: RecordedEvent) -> str:
    d = ev.detail
    return (
        f"{_short(d.get('transmission_id'))} honoured under cited"
        f" {_version(d.get('cited_version'))}"
        f" (receiver current {_version(d.get('receiver_current'))})"
        " — never re-judged"
    )


def _version_divergence_text(ev: RecordedEvent) -> str:
    d = ev.detail
    return (
        f"{_short(d.get('transmission_id'))} citation refused:"
        f" {d.get('citation_refusal', '?')}"
        f" (cites {_version(d.get('cited_version'))},"
        f" applied {_version(d.get('applied_version'))})"
    )


def _revision_record_text(ev: RecordedEvent) -> str:
    """A book's own position on a version — the adoption points."""
    d = ev.detail
    position = ev.intent.split(":", 1)[1]
    label = f" {d['label']}" if d.get("label") else ""
    text = (
        f"{position}{label}: {_short(d.get('version'))}"
        f" supersedes {_version(d.get('supersedes'))}"
    )
    if d.get("proposed_by"):
        text += f", by {d['proposed_by']}"
    if d.get("reason"):
        text += f" — {d['reason']}"
    if d.get("related_crossing"):
        text += f" (crossing {_short(d['related_crossing'])})"
    return text


def _disagreement_text(ev: RecordedEvent) -> str:
    d = ev.detail
    sp = d.get("sender_profile") or {}
    rm = d.get("receiver_measurement") or {}
    text = f"{_short(d.get('transmission_id'))}"
    if isinstance(d.get("divergence"), (int, float)):
        text += f" divergence {float(d['divergence']):.4f}"
    if "completeness" in sp and "completeness" in rm:
        text += (
            f" — sender completeness {float(sp['completeness']):.4f}"
            f" vs receiver {float(rm['completeness']):.4f}"
        )
    return text


def _booking_text(ev: RecordedEvent) -> str:
    d = ev.detail
    arrow = {"send": "→", "receive": "←"}.get(ev.intent)
    if arrow is not None:
        text = (
            f"{ev.intent} {_short(d.get('transmission_id'))} {d.get('payload_type', '?')} "
            f"{arrow} {d.get('peer', '?')}"
        )
    elif ev.intent == "settle":
        text = (
            f"settle {_short(d.get('transmission_id'))} {d.get('payload_type', '?')} "
            f"— settlement stands under the version stamped at booking"
        )
    else:  # receive-disputed: the receiver's own measurement is the record
        det = d.get("detail") if isinstance(d.get("detail"), dict) else {}
        text = (
            f"receive-disputed {_short(d.get('transmission_id'))} "
            f"{d.get('payload_type', '?')} (declared "
            f"{_short(det.get('declared_hash'))}, computed "
            f"{_short(d.get('payload_hash'))})"
        )
    if d.get("contract_version") is not None:
        text += f" [under {_short(d.get('contract_version'))}]"
    return text


def _event_text(ev: RecordedEvent) -> str:
    d = ev.detail
    name = str(d.get("event", "?"))
    extras = []
    if name == "session_end":
        unresolved = d.get("unresolved_excursions")
        if unresolved:
            extras.append(
                "unresolved: " + ", ".join(_short(t) for t in unresolved)
            )
        received = d.get("received")
        if isinstance(received, list):
            extras.append(f"received {len(received)}")
    elif name == "sender_hanging":
        extras.append(f"last send {_short(d.get('last_send'))}")
    elif name == "adoption_ack_received":
        # v0.3: the third booking of the adoption cycle landed — only
        # now does this book adopt (the revision governs when both
        # books hold it).
        extras.append(
            f"version {_short(d.get('version'))} {d.get('position')};"
            f" sender now on {_short(d.get('sender_now_on'))}"
        )
    elif name == "revision_position_booked":
        extras.append(
            f"version {_short(d.get('version'))} {d.get('position')};"
            f" receiver now on {_short(d.get('receiver_now_on'))}"
        )
    if extras:
        return f"{name} ({'; '.join(extras)})"
    return name


def _event_line(ev: RecordedEvent) -> str:
    intent = ev.intent
    if intent == "crossing":
        body = _crossing_text(ev)
    elif intent.startswith("decision:"):
        body = _decision_text(ev)
    elif intent == "disagreement":
        body = _disagreement_text(ev)
    elif intent == "course_adjusted":
        body = f"course adjusted to pick {_short(ev.detail.get('pick'))}"
    elif intent == "unreadable_envelope":
        body = f"unreadable envelope {ev.detail.get('file', '?')}"
    elif intent == "revision_received":
        body = _revision_received_text(ev)
    elif intent in ("superseded_citation", "version_divergence"):
        body = (
            _superseded_citation_text(ev) if intent == "superseded_citation"
            else _version_divergence_text(ev)
        )
    elif intent.startswith("revision:"):
        body = _revision_record_text(ev)
    elif intent in ("send", "receive", "settle", "receive-disputed"):
        body = _booking_text(ev)
    elif intent.startswith("event:"):
        body = _event_text(ev)
    else:  # seam:<unknown> / book:<unknown> / reading
        body = intent
    return body


def render_timeline(
    result: ImportResult,
    *,
    audit: AuditResult | None = None,
    all_events: bool = False,
) -> str:
    """Render an imported run as an ordered timeline string."""
    wall = [ev for ev in result.events if ev.clock == "wall"]
    mono = [ev for ev in result.events if ev.clock != "wall"]

    def wanted(ev: RecordedEvent) -> bool:
        return all_events or ev.intent.startswith(_DEFAULT_PREFIXES)

    t0 = min((ev.tick for ev in wall), default=0.0)
    lines: list[str] = []
    lines.append(
        f"== chrono-flight timeline: {result.header.source.get('run_dir', '?')} =="
    )
    lines.append(
        f"   tracks: {', '.join(result.tracks)}"
        f"  (seam log + both books; engine: {result.header.source.get('engine', '?')})"
    )
    lines.append("")
    ordered = sorted(
        enumerate(wall), key=lambda pair: (pair[1].tick, pair[0])
    )
    for _, ev in ordered:
        if not wanted(ev):
            continue
        category = {
            "crossing": "crossing",
            "disagreement": "disagree",
            "course_adjusted": "adjust",
            "unreadable_envelope": "unreadable",
            "send": "send",
            "receive": "receive",
            "settle": "settle",
            "receive-disputed": "disputed",
            "revision_received": "revision",
            "superseded_citation": "skew",
            "version_divergence": "diverge",
        }.get(ev.intent) or ev.intent.split(":")[0]
        lines.append(
            f"  +{ev.tick - t0:7.3f}s  {ev.track:<12s} {category:<10s} "
            f"{_event_line(ev)}"
        )

    if all_events and mono:
        lines.append("")
        lines.append(
            "== book readings (each reader's monotonic clock — shown in book"
        )
        lines.append(
            "   order, not merged into the wall-clock timeline above) =="
        )
        for ev in mono:
            v = ev.detail.get("value") or {}
            lines.append(
                f"  {ev.track:<12s} reading {_short(v.get('transmission_id'))} "
                f"{v.get('type', '?')} @{ev.tick:.3f}"
            )

    lines.append("")
    lines.append("== gaps — never silently closed ==")
    if result.gaps:
        for gap in result.gaps:
            tag = "open " if gap.kind == GAP_OPEN else "gap  "
            lines.append(f"  [{tag}] {gap.track}: {gap.note}")
    else:
        lines.append("  none: both books closed with session_end; no recorded"
                     " unresolved excursions")
    if audit is not None:
        lines.append("")
        lines.append(render_audit(audit))

    versioning = result.header.source.get("versioning") or {}
    unmapped = {
        kind: fields
        for kind, fields in (versioning.get("detail_only_fields") or {}).items()
        if fields
    }
    if unmapped:
        lines.append("")
        lines.append(
            "== v0.3 record kinds — fields the record form cannot hold =="
        )
        lines.append(
            "  (kept verbatim in each event's detail; named here, never"
            " silently dropped)"
        )
        for kind, fields in unmapped.items():
            lines.append(f"    {kind}: {', '.join(fields)}")

    lines.append("")
    lines.append(f"-- {REPLAY_LIMIT}")
    return "\n".join(lines)
