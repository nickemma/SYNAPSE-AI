# SYNAPSE-AI — Consent-Governed Neural Data & Privacy-Preserving ML

![Status](https://img.shields.io/badge/status-In%20development-orange)
![Go Version](https://img.shields.io/badge/go-1.25-blue)
![Rust Version](https://img.shields.io/badge/rust-1.87-orange)
![Python Version](https://img.shields.io/badge/python-3.12-blue)
![License](https://img.shields.io/badge/license-APACHE-green)
[![CI](https://github.com/nickemma/meridian/workflows/CI/badge.svg)](https://github.com/nickemma/synapse-ai/actions)


**A consent-governed platform for sensitive neural data — where an AI model *must obey the same consent, encryption, and audit rules as any human user.***

*Encrypted at the edge. Stored append-only. Analysed only under active consent and differential privacy. Models trained via federated learning — the model travels to the data, never the reverse. Every prediction carries its own provenance.*

[What is SYNAPSE-AI?](#what-is-synapse-ai) • [Architecture](#architecture) • [The Pillars](#the-five-pillars) • [Quick Start](#quick-start) • [Threat Model](docs/THREAT_MODEL.md) • [Roadmap](#roadmap)

> ⚠️ **Honest status:** This is an early-stage learning and capstone project, not a production system. The **vision** below describes where it's headed. The **Current Status** section tells you exactly what actually runs today (spoiler: the tamper-evident ledger, and not much else yet). Everything past that is on the **Roadmap** — real goals, not finished features. If you're a contributor, start at [What Works Today](#what-works-today).

---

## The Idea, In One Sentence
 
Most "AI + sensitive data" systems treat the model as a privileged insider that can reach into the data whenever it likes. SYNAPSE-AI inverts that: **the consent and governance layer *is* the system, and the model is just another consumer that has to ask permission — exactly like a human would.**
 
The data in question is neural signals (EEG). You can't rotate a brain the way you rotate a password, so the rule is non-negotiable: an inference request faces the same checks as a person reading a record — *who are you, whose data, do you have active consent for this purpose, and will this be recorded?* If any check fails, the model never sees the data.

---

## Why This Project Exists
 
This is a capstone-style learning project building toward a Master's in **Software Systems & Cybersecurity**. Its purpose is to make core secure-by-design concepts concrete by building them, not just reading about them:
 
- **Tamper-evidence & append-only logs** (the hash-chained ledger)
- **Deny-by-default access control** (the consent engine — a reference monitor)
- **Applied cryptography** (identity, encryption at rest, signing)
- **Privacy-preserving ML** (differential privacy, federated learning) — the research frontier
It's deliberately scoped so that **others can contribute**, especially people from neuroscience and neurotech who care about the mental-state modelling but not the systems plumbing.

---

## The Neuro Side (For Neurotech Contributors)
 
The platform's example task is **passive mental-state estimation from EEG** — non-medical, non-diagnostic. Rather than treating mental states as a bag of independent yes/no flags (which produces self-contradicting outputs like "highly relaxed AND highly stressed"), SYNAPSE-AI frames them on **two underlying dimensions** drawn from affective-state research:
 
- **Arousal** — calm ←→ activated. *Relaxed* sits low; *Stress* and *High workload* sit high.
- **Valence / task-engagement** — disengaged ←→ engaged. *Fatigue* sits low; *Attention* and *Engagement* sit high.
The six states people usually ask about are then **points in that 2D space** rather than six separate classifiers:

| State | Arousal | Engagement |
| --- | --- | --- |
| Relaxed | low | mid |
| Fatigue | low | low |
| Attention | mid–high | high |
| Engagement | mid | high |
| Stress | high | mid–low |
| High workload | high | high |
 
This is a modelling *choice*, not settled science — and it's exactly the kind of thing a neurotech contributor might refine, challenge, or replace. Discussion welcome in issues.
 
> **Important scope line:** this is a research/wellness signal, **not** a medical device and **not** a diagnostic tool. It estimates rough mental states from public EEG datasets. It does not detect, diagnose, or treat any condition.

---

## What Works Today
 
Being honest about the build state:
 
- ✅ **Hash-chained ledger (prototype).** Append-only records where each entry commits to the previous one; tampering is detectable by re-verifying the chain. This is the seed of the consent ledger.
- 🚧 **Consent engine.** Design drafted; implementation in progress. The deny-by-default check is the next real milestone.
- ❌ Everything else below is **not built yet** — it's roadmap.
If a doc in this repo describes something as though it already runs and it's not in the ✅ list above, treat that as *intended design*, not reality. We're actively fixing any doc that over-claims.

---

## Architecture (Target Design)
 
The intended data path is a one-way gauntlet — nothing reaches a model without clearing every gate. *This is the design goal; only the storage/ledger pieces are prototyped so far.*
 
```
        EEG / Neural Signal (edge device)
                    │
                    ▼
        Encrypted Ingestion      ── signed + encrypted at the edge        [roadmap]
                    │
                    ▼
        Append-Only Storage      ── tamper-evident log                    [prototype ✅]
                    │
                    ▼
        Consent Verification     ── active grant required (deny-by-default) [in progress 🚧]
                    │
                    ▼
        Privacy Layer            ── differential-privacy budget check       [roadmap]
                    │
                    ▼
        ML Inference             ── model runs only if all gates passed     [roadmap]
                    │
                    ▼
        Provenance Record        ── prediction logged with full context     [roadmap]
```
 
See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detail on each layer and its status.

---

## The Five Pillars (Vision)
 
The full system is organised around five pillars. Today only Pillar 1's storage/ledger piece is prototyped; the rest are the roadmap.
 
1. **Secure Ingestion & Storage** — edge encryption + append-only tamper-evident log *(ledger prototyped ✅)*
2. **Consent & Governance Engine** — deny-by-default, scoped grants, immediate revocation, hash-chained consent ledger *(in progress 🚧)*
3. **Privacy-Preserving ML** — federated learning + differential privacy *(roadmap)*
4. **Provenance & Audit** — self-describing predictions, tamper-evident trail *(roadmap)*
5. **Observability & Security** — metrics, dashboards, chaos/consent-bypass tests *(roadmap)*

---

---

## Roadmap
 
Ordered so each step builds on the last (this mirrors the learning sequence behind the project):
 
- [x] Hash-chained append-only ledger (tamper-evidence prototype)
- [ ] **Consent engine: deny-by-default check against the ledger** ← current focus
- [ ] Scoped, time-bounded grants + immediate revocation
- [ ] Identity & encryption: signing, encryption at rest (concept-level first)
- [ ] Consent-gated inference path over a toy/public model
- [ ] Prediction provenance records linked to the authorising grant
- [ ] Differential-privacy budget tracking *(research frontier)*
- [ ] Federated learning across nodes *(research frontier)*
- [ ] Public EEG dataset integration + reproducible mental-state demo
- [ ] Chaos + consent-bypass test suite

---

---

## Tech Stack (Intended)
 
| Layer | Technology | Status |
| --- | --- | --- |
| Ledger / storage | Python (prototype) → Rust (later) | prototype in Python ✅ |
| Consent engine / gateway | Go | planned |
| Privacy-preserving ML | Python | roadmap |
| Inter-service API | gRPC + Protobuf | roadmap |
 
*(The stack is a target. The current prototype is plain Python with the standard library — deliberately, so contributors can read it without setup.)*

---

## Getting Started (Contributors)
 
Right now "getting started" means running the ledger prototype and trying to break it — that's the live part of the project.
 
```bash
git clone https://github.com/nickemma/synapse-ai.git
cd synapse-ai
python3 examples/ledger.py        # builds a tiny consent ledger, then tampers with it
```
 
You'll see the chain verify as intact, then break the moment a record is altered. Good first issues live around extending that: covering-tracks attacks, breaking the link, the genesis-block edge case.
 
See [CONTRIBUTING.md](CONTRIBUTING.md) for how to get involved, and [docs/](docs/) for design and threat-model thinking.

---

## Documentation
 
| Doc | What it's for |
| --- | --- |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design + honest per-layer status |
| [DESIGN_DOC.md](docs/DESIGN_DOC.md) | Consent engine & storage design; rest as future work |
| [THREAT_MODEL.md](docs/THREAT_MODEL.md) | Threats for what's built now; broader threats as future work |
| [TRADEOFFS.md](docs/TRADEOFFS.md) | Why the architecture is shaped this way |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute |
 
---

## Author

**[@nickemma](https://github.com/nickemma)** — building secure-by-design systems from first principles, one commit at a time.

💼 *Contributions welcome — especially from neuroscience/neurotech folks interested in the mental-state modelling.*

<div align="center">
<a href="https://www.linkedin.com/in/techieemma/"><img src="https://img.shields.io/badge/linkedin-%23f78a38.svg?style=for-the-badge&logo=linkedin&logoColor=white" alt="Linkedin"></a>
<a href="https://twitter.com/techieemma"><img src="https://img.shields.io/badge/Twitter-%23f78a38.svg?style=for-the-badge&logo=Twitter&logoColor=white" alt="Twitter"></a>
<a href="https://github.com/nickemma/"><img src="https://img.shields.io/badge/github-%23f78a38.svg?style=for-the-badge&logo=github&logoColor=white" alt="Github"></a>
<a href="https://techieemma.medium.com/"><img src="https://img.shields.io/badge/Medium-%23f78a38.svg?style=for-the-badge&logo=Medium&logoColor=white" alt="Medium"></a>
<a href="mailto:nicholasemmanuel321@gmail.com"><img src="https://img.shields.io/badge/Gmail-f78a38?style=for-the-badge&logo=gmail&logoColor=white" alt="Gmail"></a>
</div>

---

**Building Systems, Building Faith — One Commit at a Time**

[⬆ Back to Top](#synapse-ai--consent-governed-neural-data--privacy-preserving-ml)
