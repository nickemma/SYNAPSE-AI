# CONTRIBUTING — SYNAPSE-AI

**How to Contribute to SYNAPSE-AI**

**Last Updated:** June 24, 2026

Thanks for looking at SYNAPSE-AI. This is an early-stage learning/capstone project, so contributing right now means working on small, real, well-scoped pieces — not a giant codebase.

---

## Before You Start
 
Read these three, in order — they're short:
 
1. [README.md](README.md) — what this is, and honestly what works today
2. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — the design and per-layer status
3. [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md) — what we defend and what we don't
The golden rule: **if a doc describes something as done and it isn't, that's a bug — fix the doc or flag it.** We'd rather under-claim than over-claim.

---

## Where Things Actually Are
 
- ✅ `examples/ledger.py` — the hash-chained ledger prototype. This is the live part.
- 🚧 Consent engine — being built. Deny-by-default check is the current milestone.
- 📋 Everything else — roadmap. See the README.

---

## Good First Contributions
 
Right now the best entry points are around the ledger and consent check:
 
- **Extend the ledger tests** — try the "cover your tracks" and "break the link" attacks described in the challenges at the bottom of `ledger.py`. Document what breaks and why.
- **Help build the consent check** — implement `verify_consent` from `docs/DESIGN_DOC.md` against the ledger, with deny-by-default.
- **Edge cases** — expiry, revocation-after-grant, re-granting. Write the test that proves each is handled.
- **Neuro/neurotech input** — challenge or refine the arousal/valence mental-state framing in the README. Open an issue; this is genuinely wanted.
- **Doc honesty** — find any over-claim and fix it.

---

## How to Contribute
 
1. Comment on an issue to claim it (or open one).
2. Branch: `feat/...`, `fix/...`, `docs/...`.
3. Keep changes small and readable — readability beats cleverness here, since this is a learning project.
4. If you change behaviour, update the relevant doc *and its status marker*.
5. Open a PR describing what you did and why.

---

## Code Style
 
- Python, standard library where possible (low setup bar is a feature).
- Clear names over clever ones. Comments explain *why*, not *what*.
- Every security-relevant function gets a test that tries to break it.

---

## Code of Conduct
 
Be respectful, be constructive, assume good faith. Harassment or discrimination isn't tolerated. This is a space for people to learn — including the maintainer.

---

## Recognition

Contributors are recognized in:
1. Commit history (GitHub shows your profile)
2. Release notes (if significant)
3. Contributors page (coming soon)

Thank you for contributing! 🙏

---

## Questions?

- **General:** Open an issue with the `question` label
- **Design:** Discuss in an issue before implementing

---

**Happy contributing! We're excited to have you on the team.**
