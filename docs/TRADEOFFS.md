# TRADEOFFS — SYNAPSE-AI

**Purpose:** Document the conscious design choices made in SYNAPSE-AI, their costs, and why we chose them anyway.

**Last Updated:** June 24, 2026

Every design choice gives something up. This doc records the decisions that actually matter for what's being built now, and *why* — so the reasoning is defensible, not just asserted. (Decisions about subsystems that don't exist yet are deliberately omitted; they'll be added when those parts are built.)

---

## 1. Append-only ledger vs. an editable database
 
**Chosen:** append-only. No edits, no deletes — corrections are new appended records.
 
**Gain:** tamper-evidence. With a hash chain, any silent alteration is detectable. The history is trustworthy.
 
**Give up:** convenience. Fixing a mistake means appending a correction, not editing in place. Storage only grows. Queries must account for "latest state" rather than reading one mutable row. A future "right to be forgotten" becomes genuinely hard (you can mark data inaccessible, but the record of *that* stays).
 
**Why anyway:** the entire value proposition is trust in the consent record. An editable store is exactly where silent tampering hides. Worth the inconvenience.
 
---
 
## 2. Deny-by-default vs. allow-by-default
 
**Chosen:** deny-by-default. Access is refused unless an active grant explicitly permits it.
 
**Gain:** safety. A missing, expired, or revoked grant — or any unanticipated state — results in *no access*. Failures fail closed.
 
**Give up:** friction. Nothing works until consent is correctly set up. More "access denied" moments during development.
 
**Why anyway:** this is the most important principle in access control. For brain data the cost of wrongly allowing access dwarfs the cost of wrongly denying it. Fail closed, always.
 
---
 
## 3. Synchronous consent check vs. cached decisions
 
**Chosen (design):** check current ledger state on each request rather than trusting a cache.
 
**Gain:** revocation is honoured immediately — the next request after a revocation is denied.
 
**Give up:** performance. A live check per request is slower than a cached "yes." At scale this would need careful caching with correct invalidation.
 
**Why anyway:** at prototype scale performance is irrelevant, and immediate revocation is a core promise. Optimisation is a *later* problem and explicitly noted as future work — premature caching is where revocation bugs are born.
 
---
 
## 4. Build Python prototype vs. start in the "real" stack (Go/Rust)
 
**Chosen:** plain Python, standard library, for the prototype.
 
**Gain:** anyone can read and run it with zero setup. The *concepts* (hash chaining, deny-by-default) are visible without fighting toolchains. Lowers the bar for neuro/contributor involvement.
 
**Give up:** it's not the performant production stack the vision describes.
 
**Why anyway:** the goal right now is *understanding and contribution*, not throughput. Rewriting hot paths in Rust/Go is a deliberate later step, once the design is proven in something readable.
 
---
 
## 5. Scope to non-medical mental states vs. anything diagnostic
 
**Chosen:** non-medical, non-diagnostic passive states only (attention, fatigue, etc.), framed on an arousal/engagement model.
 
**Gain:** stays clear of medical-device regulation and clinical liability. Lets the project focus on the *systems and security* learning, which is the actual point.
 
**Give up:** the flashier "detects condition X" claims — and some perceived impact.
 
**Why anyway:** it's a software-systems-and-security capstone, not a medical product. Diagnostic scope would add enormous regulatory weight for no learning benefit. Honest scoping is itself good engineering.
 
---
 
## A note on what's missing here
 
You won't find tradeoffs for differential privacy, federated aggregation, or key management in this doc yet — because those aren't built. Adding tradeoff analysis for systems that don't exist is how the *original* version of these docs drifted into fiction. Each section here will get a sibling when its subsystem actually ships.

---

## Feedback & Revisions

**This document is not final.** If you think a tradeoff is wrong, or if you have evidence that an alternative is better, open an issue and we'll reconsider.

Tradeoffs are decisions; decisions can be revisited.
