# CONTRIBUTING.md — SYNAPSE-AI

**How to Contribute to SYNAPSE-AI**

**Last Updated:** June 24, 2026

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Development Workflow](#development-workflow)
3. [Code Standards](#code-standards)
4. [Testing Requirements](#testing-requirements)
5. [Commit Messages](#commit-messages)
6. [Pull Request Process](#pull-request-process)
7. [Contributor License Agreement](#contributor-license-agreement)
8. [Code of Conduct](#code-of-conduct)

---

## Getting Started

### Prerequisites

- [ ] Read [THREAT_MODEL.md](THREAT_MODEL.md) — understand the security model
- [ ] Read [DESIGN_DOC.md](DESIGN_DOC.md) — understand the architecture
- [ ] Read [TRADEOFFS.md](TRADEOFFS.md) — understand why certain choices were made
- [ ] Install development tools (Go 1.25+, Rust 1.87+, Python 3.12+)
- [ ] Clone the repo: `git clone https://github.com/nickemma/synapse-ai.git`

### Setting Up Your Development Environment

```bash
cd synapse-ai

# Install pre-commit hooks (for linting & formatting)
pip install pre-commit
pre-commit install

# Build locally
make build

# Run tests
make test

# Verify everything works
./scripts/e2e-test.sh
```

---

## Development Workflow

### 1. Pick an Issue

Look for issues labeled:
- `good-first-issue` — beginner-friendly
- `help-wanted` — actively seeking help
- `security` — security-related (must discuss before starting)

**Before starting work, comment on the issue:** "I'd like to work on this."

### 2. Create a Feature Branch

```bash
git checkout -b feat/add-consent-cache-ttl
# Branch naming: feat/*, fix/*, docs/*, chore/*, security/*
```

### 3. Make Changes

Follow the code standards (see below). Make frequent, logical commits.

```bash
# Make changes to files
git add <files>
git commit -m "Add consent cache TTL configuration"
```

### 4. Test Locally

```bash
# Run unit tests
make test

# Run integration tests
make test-integration

# Run end-to-end tests
./scripts/e2e-test.sh

# Check code style
make lint

# Check security issues
make security-audit
```

### 5. Push & Create a Pull Request

```bash
git push origin feat/add-consent-cache-ttl

# Go to GitHub and create a PR
# Fill in the PR template
```

### 6. Respond to Feedback

Reviewers will suggest changes. Update your branch and push again:

```bash
git add <files>
git commit -m "Address PR feedback: clarify cache TTL logic"
git push origin feat/add-consent-cache-ttl
```

### 7. Merge

Once approved, a maintainer will merge your PR. Congratulations! 🎉

---

## Code Standards

### Go

**Style Guide:** Follow [Effective Go](https://golang.org/doc/effective_go)

```go
// Bad: unclear names, missing docs
func verifyConsent(s string, m string) (bool, error) {
    // ...
}

// Good: clear names, documented
// VerifyConsent checks if a subject has active consent for a model.
// Returns true if consent is active, false otherwise.
func VerifyConsent(subjectID, modelID string) (bool, error) {
    // ...
}
```

**Rules:**
- Exported functions must have doc comments
- Use descriptive variable names (not `s`, `m`, `x`)
- Error handling: check and return errors early
- No bare `panic()`; use explicit error returns
- Use `fmt.Errorf` for errors with context

**Tools:**
```bash
# Format code
gofmt -s -w .
# or: go fmt ./...

# Lint code
golangci-lint run ./...

# Vet for common mistakes
go vet ./...
```

### Rust

**Style Guide:** Follow [Rust API Guidelines](https://rust-lang.github.io/api-guidelines/)

```rust
// Bad: unclear names
fn vc(s: &str, m: &str) -> Result<bool> {
    // ...
}

// Good: clear names, documented
/// Verifies if a subject has active consent for a model.
/// Returns Ok(true) if consent is active, Ok(false) otherwise.
pub fn verify_consent(subject_id: &str, model_id: &str) -> Result<bool> {
    // ...
}
```

**Rules:**
- Public items must have doc comments
- Use snake_case for functions/variables, CamelCase for types
- Prefer `Result<T>` over `Option<T>` for fallible operations
- No unwrap() in production code
- Use clippy suggestions: `cargo clippy --all-targets --all-features`

**Tools:**
```bash
# Format code
cargo fmt

# Lint code
cargo clippy --all-targets --all-features

# Check for security issues
cargo audit
```

### Python

**Style Guide:** Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/)

```python
# Bad: unclear names, missing docstrings
def verify_consent(s, m):
    return True

# Good: clear names, documented
def verify_consent(subject_id: str, model_id: str) -> bool:
    """
    Verify if a subject has active consent for a model.

    Args:
        subject_id: The subject's ID.
        model_id: The model's ID.

    Returns:
        True if consent is active, False otherwise.
    """
    # ...
    return True
```

**Rules:**
- Use type hints on function signatures
- Public functions must have docstrings (Google style)
- No bare `except:`; specify the exception type
- Use f-strings for string formatting
- Follow Black formatting rules

**Tools:**
```bash
# Format code
black .

# Lint code
pylint ml/

# Type checking
mypy ml/

# Check security issues
bandit -r ml/
```

---

## Testing Requirements

### Unit Tests

Every module must have unit tests. Aim for >80% code coverage.

**Go:**
```go
// In consent_test.go
func TestVerifyConsent(t *testing.T) {
    tests := []struct {
        name      string
        subjectID string
        modelID   string
        want      bool
        wantErr   bool
    }{
        {
            name:      "active consent",
            subjectID: "subj-123",
            modelID:   "model-1",
            want:      true,
            wantErr:   false,
        },
        {
            name:      "no consent",
            subjectID: "subj-456",
            modelID:   "model-1",
            want:      false,
            wantErr:   false,
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            got, err := VerifyConsent(tt.subjectID, tt.modelID)
            if (err != nil) != tt.wantErr {
                t.Errorf("VerifyConsent() error = %v, wantErr %v", err, tt.wantErr)
            }
            if got != tt.want {
                t.Errorf("VerifyConsent() = %v, want %v", got, tt.want)
            }
        })
    }
}
```

**Python:**
```python
# In test_consent.py
import pytest
from consent import verify_consent

def test_verify_consent_active():
    """Test that active consent is verified correctly."""
    result = verify_consent("subj-123", "model-1")
    assert result is True

def test_verify_consent_no_consent():
    """Test that missing consent is detected."""
    result = verify_consent("subj-456", "model-1")
    assert result is False

def test_verify_consent_invalid_subject():
    """Test that invalid subject ID raises an error."""
    with pytest.raises(ValueError):
        verify_consent("invalid!", "model-1")
```

**Run tests:**
```bash
make test          # All tests
make test-unit     # Unit tests only
make test-race     # Race condition detector (Go)
```

### Integration Tests

Test components working together (e.g., consent engine + storage).

**Example:**
```bash
# In tests/integration/
# Setup: create a temporary storage + consent ledger
# Test: grant consent, revoke, verify, repeat
make test-integration
```

### Chaos Tests

For critical paths (consent verification, federated aggregation), test failure scenarios.

**Example:**
```python
# tests/chaos/consent_bypass_test.py
def test_inference_without_consent_denied():
    """Attempt to infer without active consent."""
    # Should be denied, every time
    assert not infer(subject_id, model_id)

def test_inference_with_revoked_consent_denied():
    """Attempt to infer after revoking consent."""
    # Grant, revoke, then attempt
    grant_consent(...)
    revoke_consent(...)
    assert not infer(subject_id, model_id)
```

**Run chaos tests:**
```bash
make test-chaos
```

---

## Commit Messages

**Format:**
```
<type>(<scope>): <subject>

<body>

<footer>
```

**Example:**
```
feat(consent): add cache TTL configuration

Add a configurable TTL for consent cache. Reduces ledger load
during high inference traffic while maintaining revocation latency.

Implements #123
Refs DESIGN_DOC.md section "Consent Verification Performance"
```

**Types:**
- `feat` — new feature
- `fix` — bug fix
- `docs` — documentation
- `style` — code formatting (no logic change)
- `refactor` — code refactoring (no logic change)
- `perf` — performance improvement
- `test` — test additions
- `chore` — dependency updates, CI config
- `security` — security fix (even if small)

**Scope:**
- `consent` — consent engine
- `storage` — storage layer
- `gateway` — gateway service
- `inference` — inference service
- `federated-learning` or `fl` — federated learning
- `audit` — audit trail
- etc.

**Rules:**
- Keep the subject line <50 characters
- Use imperative mood ("add", not "adds" or "added")
- Reference issues: "Fixes #123" or "Refs #456"
- Sign commits: `git commit -S` (GPG signature)

---

## Pull Request Process

### Before You Push

1. **Verify tests pass:**
   ```bash
   make test
   make lint
   make security-audit
   ```

2. **Update documentation** if you change behavior

3. **Write a clear PR description:**
   ```markdown
   ## Description
   Add a configurable TTL for consent cache to reduce ledger load.

   ## Related Issues
   Fixes #123

   ## Testing
   - [x] Unit tests added
   - [x] Integration tests pass
   - [x] End-to-end tests pass

   ## Checklist
   - [x] Code follows style guide
   - [x] Commit messages follow format
   - [x] Tests added/updated
   - [x] Documentation updated
   - [x] No breaking changes
   ```

### During Code Review

- Be respectful and constructive
- Respond to feedback within 24 hours
- Update code, then re-request review
- Squash commits if requested (but typically leave history intact)

### After Approval

A maintainer will merge your PR. No need to do anything.

---

## Contributor License Agreement

By contributing to SYNAPSE-AI, you agree to:

1. **License your contributions** under the same license as the project (Apache 2.0)
2. **Own the code** (or have permission from your employer)
3. **Not include third-party code** without proper licensing
4. **Not contribute to break security** (as per our threat model)

---

## Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inclusive environment for all contributors, regardless of:
- Age, body size, disability, ethnicity, gender identity, level of experience, nationality, personal appearance, race, religion, sexual identity, sexual orientation, or socioeconomic status

### Our Standards

**Acceptable behavior:**
- Respectful disagreement
- Constructive feedback
- Inclusive language
- Patience and empathy

**Unacceptable behavior:**
- Harassment or discrimination
- Violent threats or language
- Trolling or insulting comments
- Unwanted sexual attention
- Doxxing or privacy violations

### Reporting

If you experience or witness unacceptable behavior, report it to **conduct@synapse-ai.io**.

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
- **Security:** See [SECURITY.md](SECURITY.md)
- **Design:** Discuss in an issue before implementing

---

**Happy contributing! We're excited to have you on the team.**
