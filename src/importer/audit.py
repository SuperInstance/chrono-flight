"""Agreement audit — the recorder as an independent reader of the ledger.

From the two sovereign books **alone** (never the seam log, never the
engine's own verdicts), recompute which crossings were shared state: a
crossing is *agreed* when one side's book holds a SEND and the other's
holds a RECEIVE for the same transmission id, the same payload hash
**and the same contract version** (beam-quilt SPEC P5 + DESIGN-V03
§6.6: agreement includes the version — v0.1 books carry no version on
either side, which matches and stays agreed). Verdicts:

- **agreed** — such a cross-book pair exists. A crossing the receiver
  honoured under a **superseded citation** lands here too — both sides
  stamped the cited version, so it *is* agreement — with the skew
  reported in the note (the receiver's own ``superseded_citation``
  marking, cross-checked against the fold of its revision records),
  never treated as a discrepancy (DESIGN-V03 §3.1/§3.3: superseded is
  not revoked, and re-judging under the current version would falsify
  the record);
- **skewed** — both sides booked the id and the hash, but every
  cross-book pairing names *different versions*: the books disagree
  about what governed the crossing (a refused revoked/unknown
  citation — the receiver stamped its current, or no version at all).
  A category of its own since v0.3, never averaged into agreed,
  unagreed, or disputed;
- **disputed** — both a SEND and a RECEIVE exist for the id, but no
  agreeing cross-book pair at all (payload hashes differ, or the two
  bookings live in the same book, which is not a crossing between two
  sides);
- **unagreed** — only one side ever booked the id: whatever the other
  side's book says about it, it says nothing.

SETTLE and RECEIVE-DISPUTED bookings ride along in the books without
pairing into anything (v0.2 payload semantics), exactly as in the
engine's own ``agreed_crossings``.

Each book's ``revision`` records (the ex-ante half of the ledger) are
folded with ``version_fold`` — the DESIGN-V03 §4.1 set operation: the
current version is the adopted tip nothing else supersedes, never a
clock — and reported beside the verdicts, so "superseded" in a note is
the audit's own fold of the receiver's book, not the engine's word.

This is a reimplementation from the ledger's spec, not a call into
quilt-engine: the point of the audit is that an outside reader, holding
only the two books, reaches its own counts.

Replay limit, same as everywhere in chrono-flight: this audit reads
what the books record; it does not re-derive either side's judgments.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

# The three P5 verdicts (v0.1). ``skewed`` is v0.3's own category and
# deliberately rides beside them — a separate list on AuditResult and a
# separate line in the render — so v0.1 counts keep their exact shape
# and nothing is averaged anywhere (DESIGN-V03 §3.4).
VERDICTS = ("agreed", "unagreed", "disputed")
SKEWED = "skewed"


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


def revision_entries(
    book_lines: Iterable[dict[str, Any] | tuple[Any, dict[str, Any]]],
) -> list[dict[str, Any]]:
    """The revision records out of one book's parsed lines (the ex-ante
    half of the ledger, v0.3). Accepts (lineno, line-dict) pairs or
    bare line dicts."""
    out: list[dict[str, Any]] = []
    for item in book_lines:
        d = item[1] if isinstance(item, tuple) else item
        if isinstance(d, dict) and d.get("kind") == "revision":
            out.append(d)
    return out


@dataclass
class CrossingVerdict:
    transmission_id: str
    verdict: str  # "agreed" | "unagreed" | "disputed" | "skewed"
    note: str


@dataclass
class AuditResult:
    agreed: list[str] = field(default_factory=list)
    unagreed: list[str] = field(default_factory=list)
    disputed: list[str] = field(default_factory=list)
    skewed: list[str] = field(default_factory=list)  # v0.3: own category
    verdicts: list[CrossingVerdict] = field(default_factory=list)
    # book name -> version_fold of that book's revision records, when
    # the caller passed them (v0.1 books have none; section omitted).
    version_folds: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def counts(self) -> dict[str, int]:
        """The three P5 verdict counts (v0.1 shape). ``skewed`` is not
        folded into any of them — see module docstring."""
        return {v: len(getattr(self, v)) for v in VERDICTS}


def _short(hash_: Any) -> str:
    return hash_[:8] if isinstance(hash_, str) else str(hash_)


def _vers(version: Any) -> str:
    """A version for notes: short hash, or the honest v0.1 case."""
    if version is None:
        return "no version (v0.1 path)"
    return _short(version)


def version_fold(
    revision_records: Iterable[dict[str, Any] | tuple[Any, dict[str, Any]]],
) -> dict[str, Any]:
    """Fold one book's revision records (DESIGN-V03 §4.1).

    The current version is a **set operation, not a timestamp**: among
    the versions this book last booked ``adopted`` and has not revoked,
    the current one is the tip no other adopted, non-revoked version
    supersedes (transitively, stepping over revoked links). More than
    one tip is a **fork** — surfaced, not resolved (§8.2). ``current``
    is ``None`` when the records alone cannot name one (no adoptions,
    or a fork): the seam's pinned base governs then, and a base is not
    a revision record — a book that never revised has an empty fold.

    Positions are booked, never edited: the fold reads the latest
    record per version, in book order.
    """
    latest: dict[str, dict[str, Any]] = {}
    for item in revision_records:
        d = item[1] if isinstance(item, tuple) else item
        if isinstance(d, dict) and d.get("kind") == "revision":
            latest[str(d.get("version"))] = d
    adopted = {v for v, r in latest.items() if r.get("position") == "adopted"}
    revoked = {v for v, r in latest.items() if r.get("position") == "revoked"}
    alive = adopted - revoked

    superseded: set[str] = set()
    for v in alive:
        cur = latest[v].get("supersedes")
        walked: set[str] = set()
        while cur is not None and cur not in walked:
            superseded.add(str(cur))
            walked.add(str(cur))
            rec = latest.get(str(cur))
            cur = rec.get("supersedes") if rec is not None else None

    tips = alive - superseded
    return {
        "positions": {v: latest[v].get("position") for v in sorted(latest)},
        "adopted": sorted(alive),
        "revoked": sorted(revoked),
        "superseded": sorted(superseded),
        "tips": sorted(tips),
        "current": next(iter(tips)) if len(tips) == 1 else None,
        "fork": sorted(tips) if len(tips) > 1 else [],
    }


def audit_agreement(
    sender_ledger: Iterable[dict[str, Any]],
    receiver_ledger: Iterable[dict[str, Any]],
    *,
    sender_name: str = "sender",
    receiver_name: str = "receiver",
    sender_revisions: Iterable[dict[str, Any] | tuple[Any, dict[str, Any]]] | None = None,
    receiver_revisions: Iterable[dict[str, Any] | tuple[Any, dict[str, Any]]] | None = None,
) -> AuditResult:
    """Recompute agreed / unagreed / disputed / skewed crossings from
    the two books' ledger entries alone. Revision records, when
    passed, are only folded and reported (and used to cross-check
    superseded-citation markings) — the verdicts never need them."""
    books: dict[str, list[dict[str, Any]]] = {
        sender_name: list(sender_ledger),
        receiver_name: list(receiver_ledger),
    }
    # id -> book -> set of (side, payload_hash, contract_version) plus
    # the details, for skew markings, keyed alongside.
    seen: dict[str, dict[str, dict[tuple[str, str, Any], dict[str, Any]]]] = {}
    for name, entries in books.items():
        for e in entries:
            tid = e.get("transmission_id")
            side = e.get("side")
            if tid is None or side not in ("SEND", "RECEIVE"):
                continue  # SETTLE / RECEIVE-DISPUTED ride without pairing
            key = (str(side), str(e.get("payload_hash")), e.get("contract_version"))
            slot = seen.setdefault(str(tid), {}).setdefault(name, {})
            slot[key] = e.get("detail") or {}

    result = AuditResult()
    if sender_revisions is not None:
        result.version_folds[sender_name] = version_fold(sender_revisions)
    if receiver_revisions is not None:
        result.version_folds[receiver_name] = version_fold(receiver_revisions)

    for tid in sorted(seen):
        bookings = seen[tid]
        # (hash, version) -> book -> detail, per side
        sends: dict[tuple[str, Any], dict[str, dict[str, Any]]] = {}
        recvs: dict[tuple[str, Any], dict[str, dict[str, Any]]] = {}
        for book, slot in bookings.items():
            for (side, h, v), detail in slot.items():
                tgt = sends if side == "SEND" else recvs
                tgt.setdefault((h, v), {})[book] = detail
        send_hashes = {h for h, _ in sends}
        recv_hashes = {h for h, _ in recvs}
        send_books = {b for m in sends.values() for b in m}
        recv_books = {b for m in recvs.values() for b in m}
        cross_book = bool(send_books) and bool(recv_books) and not (send_books & recv_books)

        def _vk(p: tuple[str, Any]) -> tuple[str, bool, str]:
            return (p[0], p[1] is None, p[1] or "")

        agreeing = sorted(sends.keys() & recvs.keys(), key=_vk) if cross_book else []
        # a skewed pairing: same hash booked SEND and RECEIVE cross-book,
        # but no version pairing matches on that hash
        skewed_hashes = sorted(
            h for h in (send_hashes & recv_hashes)
            if not ({v for hh, v in sends if hh == h}
                    & {v for hh, v in recvs if hh == h})
        ) if cross_book else []

        if agreeing:
            h, v = agreeing[0]
            pair = "/".join(sorted(send_books | recv_books))
            note = (
                f"SEND↔RECEIVE in {pair} on hash {_short(h)} under {_vers(v)}"
            )
            # v0.3: the pairing's RECEIVE side may carry the receiver's
            # own skew markings. Superseded is AGREED (both books stamped
            # the cited version); the skew is reported, never re-judged.
            recv_details = [recvs[(h, v)][b] for b in sorted(recvs[(h, v)])]
            if any(d.get("superseded_citation") for d in recv_details):
                note += (
                    "; honoured under a superseded citation — skew recorded"
                    " by the receiver"
                )
                fold = next(
                    (result.version_folds[b] for b in sorted(recvs[(h, v)])
                     if b in result.version_folds),
                    None,
                )
                if fold is not None:
                    if v in fold["superseded"]:
                        note += " and confirmed by the fold of its revision records"
                    else:
                        note += (
                            ", which its own revision records do not list as"
                            " superseded — reported as recorded"
                        )
            for d in recv_details:
                if d.get("citation_refusal"):
                    note += f"; citation refusal on record: {d['citation_refusal']}"
            verdict = "agreed"
        elif skewed_hashes:
            h = skewed_hashes[0]
            s_vers = sorted(
                {v for hh, v in sends if hh == h}, key=lambda x: (x is None, x or "")
            )
            r_vers = sorted(
                {v for hh, v in recvs if hh == h}, key=lambda x: (x is None, x or "")
            )

            def _applied(x: Any) -> str:
                # in a skew, a None version means the receiver refused the
                # citation and could apply no version at all — not v0.1
                return "no version applied" if x is None else _short(x)

            note = (
                f"SEND↔RECEIVE on hash {_short(h)}, but the books applied "
                f"different versions (SEND cited {_applied(s_vers[0])} vs "
                f"RECEIVE applied {_applied(r_vers[0])})"
            )
            refusals = sorted(
                {
                    str(d.get("citation_refusal"))
                    for (hh, _), m in recvs.items() if hh == h
                    for d in m.values() if d.get("citation_refusal")
                }
            )
            if refusals:
                note += f"; citation refused: {', '.join(refusals)}"
            verdict = SKEWED
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
        f"  skewed:    {len(result.skewed)}",
        "  (SEND↔RECEIVE on transmission id + payload hash + the version",
        "   each side applied; a superseded citation is honoured under the",
        "   cited version — AGREED, with the skew reported; skewed = both",
        "   sides booked, different versions — never averaged; the",
        "   engine's own verdicts are not consulted)",
    ]
    if result.version_folds:
        lines.append("  contract versions — each book's revision records, folded (§4.1):")
        for name, fold in result.version_folds.items():
            if not fold["positions"]:
                lines.append(
                    f"    {name}: no revision records — the seam's pinned"
                    " base governs"
                )
                continue
            current = (
                f"{_short(fold['current'])}" if fold["current"] is not None
                else "— (a fork, or no live adoptions: not decidable from"
                     " the records alone)"
            )
            bits = [f"current {current}"]
            if fold["adopted"]:
                bits.append(f"adopted [{', '.join(_short(v) for v in fold['adopted'])}]")
            if fold["revoked"]:
                bits.append(f"revoked [{', '.join(_short(v) for v in fold['revoked'])}]")
            if fold["superseded"]:
                bits.append(
                    f"superseded [{', '.join(_short(v) for v in fold['superseded'])}]"
                )
            if fold["fork"]:
                bits.append(f"FORK [{', '.join(_short(v) for v in fold['fork'])}]")
            lines.append(f"    {name}: " + "; ".join(bits))
    if result.verdicts:
        lines.append("  per crossing:")
        for v in result.verdicts:
            lines.append(f"    {v.verdict:9s} {v.transmission_id}  {v.note}")
    return "\n".join(lines)
