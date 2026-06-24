# SECURITY.md — SYNAPSE-AI

**Security Policy & Responsible Disclosure**

**Last Updated:** June 24, 2026  
**Status:** Active

---

## Table of Contents

1. [Security Policy](#security-policy)
2. [Vulnerability Reporting](#vulnerability-reporting)
3. [Responsible Disclosure Timeline](#responsible-disclosure-timeline)
4. [Security Updates](#security-updates)
5. [Compliance & Standards](#compliance--standards)
6. [Security Contacts](#security-contacts)

---

## Security Policy

### Our Commitment

SYNAPSE-AI is built from first principles with security as a core architectural concern. We take security seriously because the data we handle—neural signals—is the closest thing to a direct brain readout. Protecting this data is both a technical obligation and an ethical one.

**We commit to:**
- Transparent communication about security issues
- Timely patching of vulnerabilities
- No "security through obscurity"
- Regular third-party security audits
- Open-source security review (future; not yet open-source)

### What We Protect

| Asset | How | Threat |
| --- | --- | --- |
| Neural signals | Encrypted at edge + AES-256-GCM at rest | Unauthorized access |
| Consent ledger | Append-only + hash chain | Tampering with consent decisions |
| Privacy budgets | Ledger-backed + immutable | Privacy leakage beyond ε bounds |
| Subject identity | mTLS + access controls | De-anonymization |
| Model weights | Version-locked + signed | Unauthorized model updates |

### What We Don't Protect

- **Regulatory enforcement:** We can't stop a researcher from violating their use agreement
- **Adversarial inputs:** We don't defend against adversarial EEG samples designed to fool the model
- **Physical security:** We can't protect against a stolen device
- **Quantum attacks:** We don't use post-quantum cryptography (yet)
- **Compromised devices:** We can't help if your device is owned by malware

---

## Vulnerability Reporting

### **Do NOT**

- ❌ Post the vulnerability publicly on GitHub, Twitter, or in a PR
- ❌ Contact us via public channels (Slack, Twitter, email lists)
- ❌ Disclose the vulnerability to other researchers without permission
- ❌ Exploit the vulnerability beyond proof-of-concept

### **Do**

- ✅ Email us at **security@synapse-ai.io** with a detailed description
- ✅ Include steps to reproduce (if applicable)
- ✅ Include your contact information and PGP key (if you have one)
- ✅ Give us time to patch before you disclose publicly
- ✅ Be respectful and constructive in your communication

### Reporting Template

Email to **security@synapse-ai.io**:

```
Subject: [SECURITY] Vulnerability in SYNAPSE-AI

Description:
[Describe the vulnerability in detail]

Component:
[e.g., "Consent Engine", "Storage Layer", "mTLS"]

Steps to Reproduce:
1. [Step 1]
2. [Step 2]
...

Impact:
[What can an attacker do? How severe?]

Suggested Fix (optional):
[If you have ideas, share them]

Timeline Preference:
[90 days is standard; let us know if you prefer shorter/longer]

Your Contact:
Name: [Your name]
Email: [Your email]
PGP Key: [Paste or link to your PGP key, if you have one]
```

---

## Responsible Disclosure Timeline

We follow a **90-day responsible disclosure timeline**:

| Day | Action |
| --- | --- |
| Day 0 | You report the vulnerability to security@synapse-ai.io |
| Day 1 | We acknowledge receipt and assign a ticket number |
| Day 7 | We confirm the vulnerability and outline our patch plan |
| Day 30 | We release a patch (target; may be shorter for critical issues) |
| Day 45 | We draft a security advisory |
| Day 60 | We publish the advisory (with your permission) |
| Day 90 | You may disclose the vulnerability publicly if we haven't |

### Critical Vulnerabilities

If we determine the vulnerability is **critical** (e.g., consent bypass, data exfiltration), we may:
- Expedite patching (target: 7-14 days)
- Request a shorter disclosure timeline (30-45 days)
- Issue a CVE immediately upon patch release

### Non-Critical Vulnerabilities

If the vulnerability is **non-critical** (e.g., logging, side-channel), we follow the 90-day timeline or longer if you prefer.

---

## Security Updates

### Release Cycle

- **Regular releases:** Every 2 weeks (minor features, bug fixes)
- **Security releases:** As-needed, on an expedited schedule
- **LTS versions:** Every 6 months (3-year support window)

### How to Stay Updated

1. **Watch for announcements:**
   - GitHub releases: https://github.com/nickemma/synapse-ai/releases
   - Security mailing list: security-updates@synapse-ai.io (subscribe via website)
   - Twitter: @synapse_ai_sec

2. **Check your version:**
   ```bash
   ./bin/synapse-gateway --version
   # Output: synapse-gateway version v1.0.0 (build hash: abc123)
   ```

3. **Upgrade procedure:**
   ```bash
   # For Docker Compose
   docker-compose pull
   docker-compose up -d --force-recreate
   
   # For Kubernetes
   kubectl set image deployment/synapse-gateway \
     synapse-gateway=synapse/synapse-gateway:v1.0.1
   ```

### End-of-Life Timeline

| Version | Release | End-of-Life | Security Patches |
| --- | --- | --- | --- |
| v1.0 (LTS) | 2026-07-01 | 2029-07-01 | Until EOL |
| v1.1 | 2026-09-01 | 2026-12-01 | 3 months |
| v2.0 (LTS) | 2027-01-01 | 2030-01-01 | Until EOL |

---

## Compliance & Standards

### Standards We Adhere To

- **OWASP Top 10:** Assessed against current Top 10 vulnerabilities
- **CWE:** Avoid CWE-listed weakness classes
- **NIST Cybersecurity Framework:** Follow CSF guidelines for cryptography, access control, audit
- **ISO/IEC 27001:** Comply with information security management standards
- **GDPR:** Data protection and privacy controls (consent-based, right-to-revoke)
- **HIPAA:** Not currently in scope, but architecture supports HIPAA-like requirements

### Security Audits

- **Frequency:** Annual third-party security audit
- **Scope:** Code review, penetration testing, threat modeling
- **Public Report:** Published on our website (with redactions for critical issues)

### Cryptography

- **Encryption at rest:** AES-256-GCM (authenticated)
- **Encryption in transit:** TLS 1.3 (mTLS)
- **Signing:** ECDSA P-256 (FIPS 186-4)
- **Hashing:** SHA-256 (tamper-evidence)
- **Key derivation:** PBKDF2 (password-based keys)

**Note:** We do not use weak cryptography (MD5, SHA-1, DES, RC4). All cryptographic libraries are battle-tested (libsodium, OpenSSL, rustcrypto).

---

## Vulnerability Categories & Severity

### Critical

**Definition:** Affects the core security properties of the platform.

**Examples:**
- Consent bypass (serve inference without active grant)
- Key disclosure (encryption keys leaked)
- Ledger tampering (modify consent records without detection)
- Authentication bypass (impersonate a user/service)

**Response:** Patch within 7-14 days; emergency release if needed

### High

**Definition:** Reduces privacy or audit guarantees.

**Examples:**
- Side-channel leaks (infer consent status via timing)
- Partial data exfiltration (read a subset of subjects' data)
- Differential privacy budget not enforced
- Audit trail gaps (predictions not logged)

**Response:** Patch within 30 days

### Medium

**Definition:** Limits functionality or user trust.

**Examples:**
- Denial of service (crash the gateway)
- Information disclosure (non-sensitive logging)
- Revocation delayed >1 minute
- Federated round failure without recovery

**Response:** Patch within 60 days

### Low

**Definition:** Cosmetic or edge-case issues.

**Examples:**
- Unclear error messages
- Non-critical logging typos
- Minor documentation inaccuracies
- Unused dependencies

**Response:** Patch in next regular release

---

## Bug Bounty Program (Future)

We're currently evaluating a bug bounty program to incentivize security research. Details to come.

**Rough guidelines (not finalized):**
- Critical: $5,000–$10,000
- High: $1,000–$5,000
- Medium: $500–$1,000
- Low: $100–$500

---

## Third-Party Dependencies

### Dependency Updates

- **Automated scanning:** Dependabot monitors dependencies 24/7
- **Patch cadence:** Security patches applied within 1 week
- **Major updates:** Evaluated and tested before deployment

### Supply Chain Security

- **Signed commits:** All commits are GPG-signed
- **Verified releases:** Tags are signed with our release key
- **Minimal dependencies:** We use only well-maintained, widely-used libraries
- **License compliance:** All dependencies use compatible open-source licenses (MIT, Apache, BSD)

### Vendoring

For production, we recommend vendoring dependencies (check them into version control) to reduce supply chain risk:

```bash
go mod vendor
cargo vendor
pip freeze > requirements.lock
```

---

## Security Incident Response

### If We Discover a Vulnerability

1. **Immediate (Day 0):**
   - Triage and assign severity
   - Create a private security issue (not public)
   - Notify the team

2. **Short-term (Days 1-7):**
   - Develop and test a fix
   - Plan roll-out strategy
   - Determine disclosure timeline

3. **Medium-term (Days 8-30):**
   - Release patched version
   - Notify customers
   - Publish security advisory (if appropriate)

4. **Long-term (Day 31+):**
   - Post-mortem: why did this happen?
   - Improve testing / monitoring to catch similar issues
   - Update documentation

### If You Report a Vulnerability

We'll keep you informed at each step:
- Day 1: Confirmation of receipt
- Day 7: Vulnerability assessment + fix plan
- Day 30: Patch released (or explanation if delayed)
- Day 60: Public advisory (with your permission)

---

## Security Contacts

### For Security Issues

**Email:** security@synapse-ai.io  
**Response time:** <24 hours (even on weekends)  
**PGP Key:** [To be published on website]

### For Other Questions

**General inquiries:** info@synapse-ai.io  
**Support:** support@synapse-ai.io  
**GitHub Issues:** https://github.com/nickemma/synapse-ai/issues

---

## Disclaimer

**As written in the LICENSE:**

SYNAPSE-AI is provided "as is" without warranty. While we strive for security and correctness, no software is perfect. Use at your own risk.

This system is designed for **research and non-medical purposes**. It is not a diagnostic tool and should not be used to make medical decisions.

---

## Changelog

### Version History

| Version | Date | Changes |
| --- | --- | --- |
| v0.1 | 2026-06-24 | Initial pre-release; security policy drafted |
| [Future] | TBD | [Future releases] |

---

## Additional Reading

- [THREAT_MODEL.md](THREAT_MODEL.md) — Detailed threat analysis
- [DESIGN_DOC.md](DESIGN_DOC.md) — Security architecture decisions
- [RUNBOOK.md](RUNBOOK.md) — Operational security procedures
- [OWASP Top 10](https://owasp.org/www-project-top-ten/) — Common web vulnerabilities
- [CWE Top 25](https://cwe.mitre.org/top25/) — Common software weaknesses

---

**Last reviewed:** June 24, 2026  
**Next review:** December 24, 2026 (6 months)  
**Responsible party:** Security Team
