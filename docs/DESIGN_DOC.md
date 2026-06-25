# DESIGN DOCUMENT — SYNAPSE-AI

**Last Updated:** June 24, 2026  
**Status:** Pre-Implementation  
**Audience:** Engineers, architects, security reviewers, Neuroscience research team

> **Scope:** this document specifies the two pieces being built first — the **append-only ledger** and the **consent engine**. The harder subsystems (differential privacy, federated learning) are described at the end as **Future Work**, so the design intent is captured without pretending they're implemented.

---

## Part 1 — Append-Only Ledger (prototyped ✅)
 
### Purpose
A tamper-evident record of events. Today it backs consent grants/revocations; later it also backs the audit trail. Same primitive, two uses.
 
### Record shape
Each ledger entry wraps a record plus its chain links:
 
```json
{
  "record": { "action": "grant", "subject": "subj-7f3a", "model": "attention-classifier", "purpose": "research" },
  "previous_hash": "sha256 of the entry before this one",
  "hash": "sha256 of (this record + previous_hash)"
}
```
 
### The hash
```
hash = SHA256( json(record, sorted_keys) + previous_hash )
```
`sorted_keys` guarantees identical records hash identically. The first entry's `previous_hash` is the genesis value (64 zeros).
 
### Verification
Walk the chain from genesis. For each entry: (1) its `previous_hash` must equal the prior entry's `hash`, and (2) recomputing its hash from its contents must match the stored `hash`. Any mismatch = tampering, with the index where it broke.
 
Reference implementation: `examples/ledger.py`.
 
### Why append-only
You cannot edit or delete — only append. A correction is a *new* record (e.g. a revocation appended after a grant), never an overwrite. This is what makes the history tamper-evident and auditable. (Tradeoff discussed in TRADEOFFS.md.)
 
---
 
## Part 2 — Consent Engine (in progress 🚧)
 
### Purpose
The reference monitor. Every inference request is checked here first; deny-by-default. This is the heart of SYNAPSE-AI.
 
### Grant model
A grant authorises a *specific model*, for a *specific purpose*, for a *bounded time*:
 
```json
{
  "grant_id": "g-001",
  "subject": "subj-7f3a",
  "model": "attention-classifier@v1",
  "purpose": "research",
  "scope": ["inference"],
  "granted_at": "2026-06-24T09:00:00Z",
  "expires_at": "2026-07-24T09:00:00Z",
  "status": "active"
}
```
 
Both grants and revocations are appended to the ledger from Part 1, so consent history is tamper-evident.
 
### The check (deny-by-default)
Pseudocode for the core decision — the single most important logic in the project:
 
```
function verify_consent(subject, model, purpose):
    grant = ledger.latest_grant(subject, model, purpose)
 
    if grant is None:           return DENIED        # no grant exists
    if now() <  grant.starts:   return NOT_YET_ACTIVE
    if now() >= grant.expires:  return EXPIRED
    if ledger.has_revocation_after(grant):  return REVOKED
 
    return ACTIVE               # only path that allows access
```
 
Notice: every branch except one returns a denial. Access is the exception, not the default.
 
### State machine
```
PENDING ──(starts_at reached)──▶ ACTIVE ──(expires)──▶ EXPIRED
                                   │
                              (revoked) ──▶ REVOKED
```
EXPIRED and REVOKED are terminal — no inference. Re-granting creates a *new* grant; the old record stays in the ledger forever.
 
### Revocation
A revocation is an appended ledger record pointing at a grant. Because the check always consults the latest ledger state, a revocation takes effect on the very next request — no "eventually consistent" window in the prototype design.
 
---
 
## Future Work (design intent, not yet built 📋)
 
These are captured so contributors understand the destination — but they are **roadmap, not reality.**
 
### Identity & encryption 📋
Device and requester identity (mTLS in the long run; toy signing first), encryption of stored records at rest, per-subject key isolation. Begins at concept level — *never* by hand-rolling crypto.
 
### Differential privacy 📋
A per-subject ε budget bounding leakage across inferences and training; spent budget denies further use. This is research-grade and the easiest place to get privacy subtly wrong — hence late on the roadmap.
 
### Federated learning 📋
Train locally per node; only privacy-protected gradient updates leave the node; aggregate centrally. "Bring the model to the data." Hardest subsystem; furthest out.
 
### Provenance records 📋
Self-describing predictions (model version, authorising grant, requester, timestamp) written to a tamper-evident trail — reusing the Part 1 ledger directly.
 
---
 
## Build Order
 
1. ✅ Ledger + verification (done — prototype)
2. 🚧 Consent grants + deny-by-default check (current)
3. 📋 Revocation + expiry edge cases
4. 📋 Consent-gated inference over a toy model
5. 📋 Provenance trail (reuses #1)
6. 📋 Identity/encryption, then DP, then federated (frontier)
 
---

**Status:** Ready for engineering review and detailed implementation planning.
