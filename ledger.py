"""
A minimal hash-chained consent ledger — the seed of SYNAPSE-AI.

Run it:   python3 ledger.py

It builds a 3-entry consent ledger, verifies the chain is intact,
then secretly tampers with a record and shows the tampering is caught.

The lesson: we don't *prevent* the edit. We make it impossible to hide.
That distinction — detect, not prevent — is at the heart of audit logs,
blockchains, certificate transparency, and Git itself.
"""

import hashlib
import json


def hash_record(record, previous_hash):
    """Fingerprint a record together with the hash of the record before it.

    sort_keys=True matters: it guarantees the SAME record always serialises
    to the SAME string, so the hash is stable. Without it, dict ordering
    could change the fingerprint for identical data.
    """
    payload = json.dumps(record, sort_keys=True) + previous_hash
    return hashlib.sha256(payload.encode()).hexdigest()


def build_ledger(entries):
    """Chain a list of records: each entry stores the previous entry's hash."""
    ledger = []
    prev = "0" * 64  # genesis: nothing precedes the first record
    for e in entries:
        h = hash_record(e, prev)
        ledger.append({"record": e, "previous_hash": prev, "hash": h})
        prev = h
    return ledger


def verify(ledger):
    """Walk the chain and check every link. Returns a human-readable result."""
    prev = "0" * 64
    for i, entry in enumerate(ledger):
        # 1. Does this entry point back to the one before it?
        if entry["previous_hash"] != prev:
            return f"BROKEN at #{i}: previous-link doesn't match"
        # 2. Recompute the hash from scratch — does it match what's stored?
        recomputed = hash_record(entry["record"], entry["previous_hash"])
        if recomputed != entry["hash"]:
            return f"BROKEN at #{i}: contents were altered"
        prev = entry["hash"]
    return "OK - chain intact, nothing has been tampered with"


if __name__ == "__main__":
    entries = [
        {"action": "grant",  "subject": "subj-7f3a", "model": "attention-classifier", "purpose": "research"},
        {"action": "grant",  "subject": "subj-7f3a", "model": "fatigue-classifier",   "purpose": "research"},
        {"action": "revoke", "subject": "subj-7f3a", "model": "attention-classifier", "purpose": "research"},
    ]

    ledger = build_ledger(entries)
    print("Fresh ledger:      ", verify(ledger))

    # ATTACK: quietly turn the revoke back into a grant (un-revoke consent).
    ledger[2]["record"]["action"] = "grant"
    print("After secret edit: ", verify(ledger))

    # CHALLENGE 1: make the attacker smarter — also recompute the edited
    #   record's OWN hash to cover their tracks:
    #       ledger[2]["hash"] = hash_record(ledger[2]["record"], ledger[2]["previous_hash"])
    #   Run verify() again. It STILL breaks — but where, and why?
    #
    # CHALLENGE 2: now also fix the previous_hash link. How far does the
    #   attacker have to go to fully forge the chain? (That effort IS the
    #   security property.)
