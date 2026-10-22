"""Agreement audit — the recorder as an independent reader of the ledger.

From the two sovereign books **alone** (never the seam log, never the
engine's own verdicts), recompute which crossings were shared state: a
crossing is *agreed* when one side's book holds a SEND and the other's
holds a RECEIVE for the same transmission id **and** the same payload
hash (beam-quilt SPEC P5: shared state is agreement only). Verdicts:

- **agreed** — such a cross-book pair exists;
- **disputed** — both a SEND and a RECEIVE exist for the id, but no
  agreeing cross-book pair (payload hashes differ, or the two bookings
  live in the same book, which is not a crossing between two sides);
- **unagreed** — only one side ever booked the id: whatever the other
  side's book says about it, it says nothing.

This is a reimplementation from the ledger's spec, not a call into
quilt-engine: the point of the audit is that an outside reader, holding
only the two books, reaches its own counts.

Replay limit, same as everywhere in chrono-flight: this audit reads
what the books record; it does not re-derive either side's judgments.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

VERDICTS = ("agreed", "unagreed", "disputed")


def ledger_entries(
    book_lines: Iterable[dict[str, Any] | tuple[Any, dict[str, Any]]],
) -> list[dict[str, Any]]:
    """The ledger bookings out of one book's parsed lines. Accepts the
    book's (lineno, line-dict) pairs or bare line dicts."""
    out: list[dict[str, Any]] = []
    for item in book_lines:
        d = item[1] if isinstance(item, tuple) else item
        if isinstance(d, dict) and d.get("kind") == "ledger":
            out.append(d)
    return out


@dataclass
class CrossingVerdict:
    transmission_id: str
    verdict: str  # "agreed" | "unagreed" | "disputed"
    note: str


@dataclass
class AuditResult:
    agreed: list[str] = field(default_factory=list)
    unagreed: list[str] = field(default_factory=list)
    disputed: list[str] = field(default_factory=list)
    verdicts: list[CrossingVerdict] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        return {v: len(getattr(self, v)) for v in VERDICTS}


def _short(hash_: str) -> str:
    return hash_[:8] if isinstance(hash_, str) else str(hash_)


def audit_agreement(
    sender_ledger: Iterable[dict[str, Any]],
    receiver_ledger: Iterable[dict[str, Any]],
    *,
    sender_name: str = "sender",
    receiver_name: str = "receiver",
) -> AuditResult:
    """Recompute agreed / unagreed / disputed crossings from the two
    books' ledger entries alone."""
    books: dict[str, list[dict[str, Any]]] = {
        sender_name: list(sender_ledger),
        receiver_name: list(receiver_ledger),
    }
    # id -> book -> set of (side, payload_hash)
    seen: dict[str, dict[str, set[tuple[str, str]]]] = {}
    for name, entries in books.items():
        for e in entries:
            tid = e.get("transmission_id")
            side = e.get("side")
            ph = e.get("payload_hash")
            if tid is None or side is None:
                continue  # not a crossing booking; the books' other kinds aren't ledger
            seen.setdefault(str(tid), {}).setdefault(name, set()).add((str(side), str(ph)))

    result = AuditResult()
    for tid in sorted(seen):
        bookings = seen[tid]
        send_books = {b for b, pairs in bookings.items() if any(s == "SEND" for s, _ in pairs)}
        recv_books = {b for b, pairs in bookings.items() if any(s == "RECEIVE" for s, _ in pairs)}
        send_hashes = {h for pairs in bookings.values() for s, h in pairs if s == "SEND"}
        recv_hashes = {h for pairs in bookings.values() for s, h in pairs if s == "RECEIVE"}
        agreeing = sorted(send_hashes & recv_hashes)
        cross_book = bool(send_books) and bool(recv_books) and not (send_books & recv_books)

        if agreeing and cross_book:
            verdict = "agreed"
            pair = "/".join(sorted(send_books | recv_books))
            note = f"SEND↔RECEIVE in {pair} on hash {_short(agreeing[0])}"
        elif send_hashes and recv_hashes:
            verdict = "disputed"
            note = (
                f"both sides booked, no agreeing cross-book pair "
                f"(SEND hashes {sorted(_short(h) for h in send_hashes)} vs "
                f"RECEIVE hashes {sorted(_short(h) for h in recv_hashes)}"
                + (", bookings share a book" if not cross_book else "")
                + ")"
            )
        elif send_hashes:
            verdict = "unagreed"
            note = f"SEND in {sorted(send_books)} but no RECEIVE anywhere"
        else:
            verdict = "unagreed"
            note = f"RECEIVE in {sorted(recv_books)} but no SEND anywhere"
        getattr(result, verdict).append(tid)
        result.verdicts.append(CrossingVerdict(tid, verdict, note))
    return result


def render_audit(result: AuditResult) -> str:
    """The audit as plain lines, for the timeline CLI and reports."""
    c = result.counts
    lines = [
        "== agreement audit — recomputed from the two books alone ==",
        f"  agreed:    {c['agreed']}",
        f"  unagreed:  {c['unagreed']}",
        f"  disputed:  {c['disputed']}",
        "  (SEND↔RECEIVE on transmission id + payload hash; the engine's own",
        "   verdicts are not consulted)",
    ]
    if result.verdicts:
        lines.append("  per crossing:")
        for v in result.verdicts:
            lines.append(f"    {v.verdict:9s} {v.transmission_id}  {v.note}")
    return "\n".join(lines)
