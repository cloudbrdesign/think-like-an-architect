# ADR-006 — Deletion as a derived-state obligation, with evidence

**Status:** accepted (2026-09-16) · **Answers:** DQ-E

## Context
Incident 3: documents deleted in the records system were gone from answers but still present in derived stores weeks
later, and nobody could say where derived copies lived. The decision records that deletion is a derived-state problem, not
an index operation, and that the derived-copy surface is derived from the selected architecture rather than assumed from
a list. Backups expire through retention; restore-and-redelete is not the normal mechanism.

## Decision
1. **Two-phase deletion.** *Unretrievability first:* from the next request, deleted content is not served (ADR-002's
   pending set plus the authority check). *Physical removal second:* within the obligation window.
2. **The actual derived-copy graph.** Implementation first establishes which derived copies genuinely exist in the chosen
   design, and deletion is then proven across exactly those. No store may exist outside the graph, and no fictional store
   is added to make a demonstration look larger. The graph is re-derived whenever the architecture changes.
3. **A content-free deletion ledger** records, per deletion: the record identifier and version, the authoritative
   deletion time, each derived store, the completion time and the outcome — never content.
4. **Backups are governed by retention**, with their own expiry, and the ledger records which retained backups still
   contain the record and when they expire.
5. **Deletion completeness is reconciled:** the ledger is periodically checked against the inventory, so a store that
   silently keeps content is discovered (FX-4 as a validation theme).

## Alternatives considered
| Alternative | Why not |
|---|---|
| Delete index entries and call it done | Incident 3 |
| Restore-and-redelete backups as routine | Ruled out: expensive, risky, and it re-introduces deleted content to do so |
| Rely on a full rebuild to drop deleted content | Too slow for an obligation window, and it hides the defect |
| Track deletions in operational logs only | Logs are not evidence of completion, and content-free evidence is required (SEC-005) |

## Consequences
- **Good:** obligations become demonstrable (CMP-001, CMP-002, DATA-004); "where does content live?" has a maintained
  answer.
- **Cost:** every new derived store carries an obligation, which constrains future designs — deliberately.
- **Open:** the obligation window's interaction with backup retention is a policy position, recorded, not legal advice.
