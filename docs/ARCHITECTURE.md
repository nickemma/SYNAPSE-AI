# ARCHITECTURE — SYNAPSE-AI

> **Status legend:** ✅ prototyped · 🚧 in progress · 📋 future work (roadmap, not built)

**System Architecture Overview**

**Last Updated:** June 24, 2026  
**Status:** In Development

This document describes the *target* architecture and is honest about what exists today. Most of it is future work; that's expected for an early-stage learning project. The point of writing it down now is to think clearly about the design before building — which is itself the secure-by-design discipline this project is practising.
---

## The Core Idea
 
The governance layer is the system. A model is a consumer that must pass the same gates as a human. The data path is a one-way gauntlet:
 
```
EEG signal → Encrypt → Store → Consent check → Privacy check → Inference → Provenance record
   📋          📋        ✅         🚧             📋            📋          📋
```
 
If any gate denies, the model never sees the data. Today only the storage gate (as a tamper-evident ledger) is prototyped, and the consent gate is being built next.
 
---
 
## Layers
 
### 1. Encrypted Ingestion 📋
**Goal:** neural samples are signed and encrypted on the device, before they ever travel. The platform never sees plaintext.
**Concepts in play:** edge cryptography, device identity, encryption in transit.
**Status:** not built. Will start at concept level (toy signing/encryption) rather than production mTLS.
 
### 2. Append-Only Storage ✅ (prototype)
**Goal:** an append-only, tamper-evident log. No in-place edits; any alteration is detectable.
**Concepts in play:** hash chaining, integrity, audit logging — the atom of a blockchain.
**Status:** prototyped in `examples/ledger.py`. Records chain by committing to the previous hash; `verify()` walks the chain and catches tampering. This is the foundation everything else builds on.
 
### 3. Consent Verification 🚧 (in progress)
**Goal:** every inference is checked against the consent ledger *before* the model runs. No active grant → denied. This is a **reference monitor**: every access mediated, nothing bypasses, deny-by-default.
**Concepts in play:** access control, least privilege, default-deny.
**Status:** design drafted (see DESIGN_DOC.md). The deny-by-default check is the current milestone — the most important single thing in the whole project.
 
### 4. Privacy Layer 📋
**Goal:** a per-subject differential-privacy budget bounds how much any individual can be inferred from model outputs. Spent budget denies further use.
**Concepts in play:** differential privacy, bounded leakage.
**Status:** future work. This is the research frontier and is intentionally last — it only makes sense once layers 2–3 are solid, and it's the easiest place to get privacy subtly wrong.
 
### 5. ML Inference 📋
**Goal:** the model runs only after consent + privacy gates pass, on a toy or public-dataset model first.
**Status:** future work. Will begin with a trivial classifier, not federated learning.
 
### 6. Provenance & Audit 📋
**Goal:** every prediction is self-describing — model version, authorising grant, requester, timestamp — and written to a tamper-evident trail (same hash-chain technique as the ledger).
**Status:** future work, but reuses the Layer 2 prototype directly.
 
---
 
## Why This Order
 
The build order is the *learning* order, bottom-up:
 
1. **Tamper-evidence** (Layer 2) — the integrity primitive everything reuses.
2. **Deny-by-default** (Layer 3) — the access-control core.
3. **Identity & encryption** (Layer 1) — applied crypto, once you know what you're protecting.
4. **Differential privacy / federated learning** (Layers 4–5) — the frontier, last.
Each layer is a concept the Software Systems & Cybersecurity curriculum leans on, built a year before the coursework so the ideas are already familiar.
 
---
 
## Federated Training (Future Vision)
 
The eventual ambition: training runs *beside* the inference path, not through it. A model is shipped to each node, trains locally on data that never moves, and only privacy-protected gradient updates return to be aggregated — "bring the model to the data." This is genuinely hard and genuinely research-grade, which is why it sits at the far end of the roadmap rather than in the current build.
