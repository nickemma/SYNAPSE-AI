# THREAT MODEL — SYNAPSE-AI

**Last Updated:** June 24, 2026  
**Status:** In Development  
**Scope:** Neural data governance, consent-gated inference, federated learning with differential privacy

> **Scope:** this threat model covers **what exists or is being built now** — the append-only ledger and the consent engine. Threats against subsystems that don't exist yet (encryption, differential privacy, federated learning) are listed at the end as **Future Threats** so the analysis grows with the system. A focused threat model you can defend beats a sprawling one you can't.
 
A good threat model names *what you're defending*, *who the adversary is*, *what stops them*, and — honestly — *what you are NOT defending against*. That last part is the mark of secure-by-design thinking.

---

## What We're Protecting (Today)
 
| Asset | Why it matters |
| --- | --- |
| **Consent ledger** | The record of who authorised what. If it can be silently altered, every guarantee collapses. |
| **Consent decisions** | The deny-by-default check must not be bypassable. |
 
That's it for now. We're not yet storing real neural data or running models, so those aren't live assets yet (they're in Future Threats).
 
---
 
## Threats In Scope
 
### T1 — Silent tampering with the ledger
**Attack:** someone with storage access edits a record — e.g. flips a `revoke` back to a `grant` to re-enable access a subject withdrew.
**Defense:** hash chaining. Each record commits to the previous one; altering any record breaks verification at that index. We don't *prevent* the edit — we make it *undeniable*. (Demonstrated live in `examples/ledger.py`.)
**Residual risk:** an attacker who can rewrite the *entire* chain from the edit point onward could re-forge it. Mitigated in future by publishing the ledger's latest hash somewhere external (so a wholesale rewrite is detectable). For now, documented honestly as a known limitation.
 
### T2 — Consent-check bypass
**Attack:** craft an inference request that reaches the model without an active grant.
**Defense:** deny-by-default. The check returns a denial on every path except an active, unexpired, unrevoked grant. There is no "default allow" branch. Every access is mediated (reference-monitor property).
**Residual risk:** the property only holds if *all* access goes through the check. A future code path that reads data without calling `verify_consent` would break it — so this becomes a code-review and test invariant.
 
### T3 — Stale/expired grant treated as valid
**Attack:** rely on a grant that has expired or been revoked.
**Defense:** the check evaluates expiry and looks for a later revocation on every call; it reads current ledger state rather than a cached "yes."
**Residual risk:** clock skew between systems. Noted for when this becomes distributed.
 
---
 
## Explicitly NOT Defended Against (Out of Scope, Honestly)
 
- **A compromised host.** If an attacker fully owns the machine, they can do anything before hashing happens. Host security is assumed, not solved here.
- **Stolen credentials / insider with legitimate access.** Tamper-evidence catches *changes*, not authorised misuse.
- **Anything requiring crypto we haven't built** — encryption at rest, network interception, device spoofing. Those are Future Threats, below.
- **Regulatory / legal compulsion.** Out of scope for a learning project.
Saying these out loud is deliberate. A threat model that claims to defend everything is defending nothing.
 
---
 
## Future Threats (as subsystems get built 📋)
 
These map to roadmap features and are captured now so the model grows with the code — **not** claims of current protection.
 
- **Spoofed devices / requesters** → mitigated later by identity (signing, eventually mTLS).
- **Data interception in transit / at rest** → mitigated later by encryption.
- **Model inversion / membership inference** (reconstructing or detecting a subject from model outputs) → mitigated later by differential privacy. This is the big one for neural data and is intentionally a *future* problem because it's where privacy is hardest to get right.
- **Malicious federated node** sending poisoned gradients → mitigated later by gradient clipping, DP aggregation, anomaly detection.
- **Forged provenance records** → mitigated later by reusing the hash-chain technique for the audit trail.
---
 
## Threat Model Review Cadence
 
Revisit this document each time a roadmap item ships — move the relevant Future Threat into scope, with its real defense and its real residual risk. The threat model should always describe the system as it *actually is*, never as it's imagined to be.

---

**Last reviewed:** [Date]  
**Next review:** [Date + 6 months]  
**Reviewer:** Security team + external auditor
