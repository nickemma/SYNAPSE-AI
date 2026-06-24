# API.md — SYNAPSE-AI

**Complete API Reference**

**Last Updated:** June 24, 2026  
**Protocol:** gRPC + Protocol Buffers  
**Authentication:** mTLS (mutual TLS)

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Ingestion API](#ingestion-api)
4. [Consent API](#consent-api)
5. [Inference API](#inference-api)
6. [Audit API](#audit-api)
7. [Admin API](#admin-api)
8. [Error Codes](#error-codes)
9. [Examples](#examples)

---

## Overview

SYNAPSE-AI provides four main gRPC services:

| Service | Purpose | Authentication | Audience |
| --- | --- | --- | --- |
| **IngestService** | Stream EEG samples | Device mTLS cert | Edge devices |
| **ConsentService** | Manage consent grants | Subject mTLS cert | Subjects, platforms |
| **InferenceService** | Run inference requests | Requester mTLS cert | Models, researchers |
| **AuditService** | Query audit trail | Requester mTLS cert | Auditors, subjects |
| **AdminService** | Platform management | Admin mTLS cert | Operators |

**Base Endpoint:** `synapse-gateway.default:8443` (or your deployment)

---

## Authentication

All services require **mutual TLS (mTLS)** authentication.

### Client Certificates

Every client must present an X.509 certificate issued by the SYNAPSE-AI CA.

```bash
# Example: Create a client certificate
openssl req -new -x509 -keyout client-key.pem -out client.pem -days 365 \
  -subj "/CN=research-lab-01/O=SYNAPSE-AI/C=NG"
```

### mTLS Handshake

```bash
# Call a gRPC service with client cert
grpcurl -cacert ca.pem \
  -cert client.pem \
  -key client-key.pem \
  synapse-gateway:8443 \
  synapse.v1.InferenceService.Infer
```

### Identity Extraction

The server extracts the client's identity from the mTLS certificate CN (Common Name):

```
Client Cert: CN=research-lab-01, O=SYNAPSE-AI, C=NG
Server reads: requester_id = "research-lab-01"

Inference Request: { model: "mental-state-classifier@v2.3", ... }
Server logs: "research-lab-01" made inference request
```

---

## Ingestion API

### Service: IngestService

**Purpose:** Stream EEG samples from edge devices to secure storage

**Proto Definition:**

```protobuf
syntax = "proto3";
package synapse.v1;

service IngestService {
  rpc StreamSamples(stream EEGSample) returns (stream IngestAck);
}

message EEGSample {
  string device_id = 1;
  // subject_id is populated by gateway from mTLS cert
  int64 timestamp_ms = 2;  // milliseconds since epoch
  map<string, float> channels = 3;  // e.g., { "fp1": 4.2, "fp2": 3.8 }
  int32 sample_rate_hz = 4;  // 250 Hz typical
  bytes device_signature = 5;  // ECDSA(sample_payload)
  bytes encrypted_payload = 6;  // AES-256-GCM(sample)
  bytes nonce = 7;  // 12-byte GCM nonce
  bytes auth_tag = 8;  // 16-byte GCM authentication tag
  int32 version = 9;  // Schema version (currently 1)
}

message IngestAck {
  string sample_id = 1;
  bool accepted = 2;
  string error_message = 3;  // if accepted=false
  int64 received_at_unix_ms = 4;
}
```

### Usage: Python Example

```python
import grpc
from synapse_v1 import ingest_pb2, ingest_pb2_grpc

# Load client cert
with open('client.pem', 'rb') as f:
    client_cert = f.read()
with open('client-key.pem', 'rb') as f:
    client_key = f.read()
with open('ca.pem', 'rb') as f:
    ca_cert = f.read()

# Create mTLS credentials
creds = grpc.ssl_channel_credentials(
    root_certificates=ca_cert,
    private_key=client_key,
    certificate_chain=client_cert
)

# Create channel
channel = grpc.secure_channel(
    'synapse-gateway:8443',
    creds
)

# Create stub
stub = ingest_pb2_grpc.IngestServiceStub(channel)

# Prepare sample
sample = ingest_pb2.EEGSample(
    device_id='device-01',
    timestamp_ms=int(time.time() * 1000),
    channels={
        'fp1': 4.2,
        'fp2': 3.8,
        'f3': 2.1,
    },
    sample_rate_hz=250,
    device_signature=b'...',  # ECDSA signature
    encrypted_payload=b'...',  # AES-256-GCM ciphertext
    nonce=b'...',  # 12 bytes
    auth_tag=b'...',  # 16 bytes
    version=1
)

# Stream samples
def sample_generator():
    for i in range(100):
        yield sample

responses = stub.StreamSamples(sample_generator())
for ack in responses:
    print(f"Sample {ack.sample_id}: accepted={ack.accepted}")
    if not ack.accepted:
        print(f"  Error: {ack.error_message}")
```

### Errors

```
INVALID_ARGUMENT: Malformed sample (missing channels, bad timestamp)
UNAUTHENTICATED: Device cert not presented or invalid
PERMISSION_DENIED: Subject not enrolled
RESOURCE_EXHAUSTED: Gateway rate limit exceeded
```

---

## Consent API

### Service: ConsentService

**Purpose:** Create, list, and revoke consent grants

**Proto Definition:**

```protobuf
service ConsentService {
  rpc CreateGrant(CreateGrantRequest) returns (CreateGrantResponse);
  rpc ListGrants(ListGrantsRequest) returns (ListGrantsResponse);
  rpc GetGrant(GetGrantRequest) returns (GrantRecord);
  rpc RevokeGrant(RevokeGrantRequest) returns (RevokeGrantResponse);
  rpc VerifyConsent(VerifyConsentRequest) returns (VerifyConsentResponse);
}

message CreateGrantRequest {
  string subject_id = 1;
  string model_id = 2;  // e.g., "mental-state-classifier@v2.3"
  string purpose = 3;  // e.g., "attention/fatigue research"
  repeated string scope = 4;  // ["inference"] or ["training"] or both
  int32 ttl_days = 5;  // Time-to-live, e.g., 30 days
  string context = 6;  // Optional: "Enrolled in Study X, cohort A"
}

message CreateGrantResponse {
  string grant_id = 1;
  string status = 2;  // "PENDING" or "ACTIVE"
  int64 created_at_unix_ms = 3;
  int64 expires_at_unix_ms = 4;
}

message ListGrantsRequest {
  string subject_id = 1;
  bool active_only = 2;  // If true, only return active grants
}

message ListGrantsResponse {
  repeated GrantRecord grants = 1;
}

message GrantRecord {
  string grant_id = 1;
  string subject_id = 2;
  string model_id = 3;
  string purpose = 4;
  repeated string scope = 5;
  int64 created_at_unix_ms = 6;
  int64 expires_at_unix_ms = 7;
  string status = 8;  // "PENDING", "ACTIVE", "EXPIRED", "REVOKED"
  string context = 9;
  int64 revoked_at_unix_ms = 10;
  string revocation_reason = 11;
}

message RevokeGrantRequest {
  string subject_id = 1;
  string grant_id = 2;
  string reason = 3;  // Optional: "subject-initiated", "manual-admin", etc.
}

message RevokeGrantResponse {
  string status = 1;  // "REVOKED"
  int64 revoked_at_unix_ms = 2;
}

message VerifyConsentRequest {
  string subject_id = 1;
  string model_id = 2;
  string purpose = 3;
  string scope = 4;  // "inference" or "training"
}

message VerifyConsentResponse {
  string status = 1;  // "ACTIVE", "DENIED", "EXPIRED", "REVOKED", "BUDGET_EXHAUSTED"
  string reason = 2;  // Human-readable reason
  bool allowed = 3;  // true if status == "ACTIVE"
}
```

### Usage: Go Example

```go
package main

import (
    "context"
    "fmt"
    pb "synapse/v1"
    "google.golang.org/grpc"
    "google.golang.org/grpc/credentials"
)

func main() {
    // Load client cert
    creds, _ := credentials.NewClientTLSFromFile("ca.pem", "synapse-gateway")
    conn, _ := grpc.Dial(":8443", grpc.WithTransportCredentials(creds))
    defer conn.Close()

    client := pb.NewConsentServiceClient(conn)
    ctx := context.Background()

    // Create a grant
    createResp, _ := client.CreateGrant(ctx, &pb.CreateGrantRequest{
        SubjectId: "subj-7f3a",
        ModelId:   "mental-state-classifier@v2.3",
        Purpose:   "attention/fatigue research",
        Scope:     []string{"inference"},
        TtlDays:   30,
        Context:   "Enrolled in Attention Study, cohort A",
    })

    fmt.Printf("Grant created: %s (status: %s)\n", 
        createResp.GrantId, createResp.Status)

    // List grants
    listResp, _ := client.ListGrants(ctx, &pb.ListGrantsRequest{
        SubjectId:  "subj-7f3a",
        ActiveOnly: true,
    })

    for _, grant := range listResp.Grants {
        fmt.Printf("  - %s: %s (expires %d)\n",
            grant.GrantId, grant.Status, grant.ExpiresAtUnixMs)
    }

    // Verify consent
    verifyResp, _ := client.VerifyConsent(ctx, &pb.VerifyConsentRequest{
        SubjectId: "subj-7f3a",
        ModelId:   "mental-state-classifier@v2.3",
        Purpose:   "attention/fatigue research",
        Scope:     "inference",
    })

    fmt.Printf("Consent verified: %v (status: %s)\n",
        verifyResp.Allowed, verifyResp.Status)
}
```

### Errors

```
INVALID_ARGUMENT: Model not found, invalid TTL
NOT_FOUND: Subject not enrolled, grant not found
ALREADY_EXISTS: Grant already exists (duplicate)
PERMISSION_DENIED: Subject cannot manage grants (wrong identity)
FAILED_PRECONDITION: Grant already revoked
```

---

## Inference API

### Service: InferenceService

**Purpose:** Run inference requests (gated by consent & DP budget)

**Proto Definition:**

```protobuf
service InferenceService {
  rpc Infer(InferenceRequest) returns (InferenceResponse);
  rpc BatchInfer(BatchInferenceRequest) returns (BatchInferenceResponse);
}

message InferenceRequest {
  string subject_id = 1;
  string model_id = 2;  // e.g., "mental-state-classifier@v2.3"
  string purpose = 3;  // Must match an active grant's purpose
  // requester_id is populated by gateway from mTLS cert
}

message InferenceResponse {
  map<string, double> prediction = 1;  // e.g., {"attention": 0.71, "fatigue": 0.18}
  string consent_status = 2;  // "ACTIVE", "DENIED", "EXPIRED", "REVOKED", "BUDGET_EXHAUSTED"
  string consent_reason = 3;  // Human-readable reason if denied
  double epsilon_spent = 4;  // DP epsilon spent on this request
  double epsilon_remaining = 5;  // DP epsilon remaining for subject
  string audit_hash = 6;  // SHA256 hash of prediction provenance record
  bool served = 7;  // false if consent/budget check failed
  string error_message = 8;  // Error details if not served
  int32 latency_ms = 9;  // Request processing time
}

message BatchInferenceRequest {
  string subject_id = 1;
  string model_id = 2;
  string purpose = 3;
  int32 batch_size = 4;  // Number of samples to infer on
}

message BatchInferenceResponse {
  repeated InferenceResponse responses = 1;
  double total_epsilon_spent = 2;
  double average_latency_ms = 3;
}
```

### Usage: gRPCurl Example

```bash
# Single inference
grpcurl -d '{
  "subject_id": "subj-7f3a",
  "model_id": "mental-state-classifier@v2.3",
  "purpose": "attention/fatigue research"
}' \
  -cacert ca.pem \
  -cert client.pem \
  -key client-key.pem \
  synapse-gateway:8443 \
  synapse.v1.InferenceService.Infer

# Output:
# {
#   "prediction": {
#     "attention": 0.71,
#     "fatigue": 0.18,
#     "stress": 0.11
#   },
#   "consentStatus": "ACTIVE",
#   "epsilonSpent": 0.1,
#   "epsilonRemaining": 0.9,
#   "auditHash": "sha256:...",
#   "served": true,
#   "latencyMs": 45
# }
```

### Inline Response (Compact)

If you want just the prediction without consent/audit metadata:

```protobuf
message SimpleInferenceRequest {
  string subject_id = 1;
  string model_id = 2;
  string purpose = 3;
  bool include_provenance = 4;  // Default: false
}

message SimpleInferenceResponse {
  map<string, double> prediction = 1;
}
```

### Errors

```
UNAUTHENTICATED: Requester cert not presented
PERMISSION_DENIED: Requester not authorized
NOT_FOUND: Subject or model not found
FAILED_PRECONDITION: Consent not active, DP budget exhausted
RESOURCE_EXHAUSTED: Model queue full, try later
INTERNAL: Model inference error
```

---

## Audit API

### Service: AuditService

**Purpose:** Query prediction history and consent ledger

**Proto Definition:**

```protobuf
service AuditService {
  rpc GetPrediction(GetPredictionRequest) returns (PredictionRecord);
  rpc ListPredictions(ListPredictionsRequest) returns (stream PredictionRecord);
  rpc GetConsentLedger(GetConsentLedgerRequest) returns (stream ConsentLedgerEntry);
  rpc VerifyAuditIntegrity(VerifyAuditIntegrityRequest) returns (VerifyAuditIntegrityResponse);
}

message GetPredictionRequest {
  string prediction_id = 1;
}

message ListPredictionsRequest {
  string subject_id = 1;
  int64 start_time_unix_ms = 2;  // Optional: filter by time range
  int64 end_time_unix_ms = 3;
  string model_id = 4;  // Optional: filter by model
  int32 limit = 5;  // Default: 100, max: 10000
}

message PredictionRecord {
  string prediction_id = 1;
  string subject_id = 2;
  string model_id = 3;
  map<string, double> prediction = 4;
  int64 timestamp_unix_ms = 5;
  string requester_id = 6;
  string consent_grant_id = 7;
  string consent_status = 8;
  double epsilon_spent = 9;
  string audit_hash = 10;
  string previous_audit_hash = 11;
}

message GetConsentLedgerRequest {
  string subject_id = 1;
}

message ConsentLedgerEntry {
  string entry_id = 1;
  string type = 2;  // "grant" or "revocation"
  string grant_id = 3;
  string model_id = 4;
  string purpose = 5;
  int64 created_at_unix_ms = 6;
  int64 expires_at_unix_ms = 7;
  int64 revoked_at_unix_ms = 8;
  string audit_hash = 9;
  string previous_audit_hash = 10;
}

message VerifyAuditIntegrityRequest {
  // Empty; verifies entire audit trail
}

message VerifyAuditIntegrityResponse {
  bool valid = 1;
  int32 num_entries = 2;
  string root_hash = 3;
  string last_verified_at = 4;
  repeated string errors = 5;  // If valid=false
}
```

### Usage: Auditor Example

```bash
# Get audit trail for a subject
grpcurl -d '{
  "subject_id": "subj-7f3a",
  "limit": 100
}' \
  -cacert ca.pem \
  -cert auditor.pem \
  -key auditor-key.pem \
  synapse-gateway:8443 \
  synapse.v1.AuditService.ListPredictions

# Verify integrity of entire audit trail
grpcurl -d '{}' \
  -cacert ca.pem \
  -cert auditor.pem \
  -key auditor-key.pem \
  synapse-gateway:8443 \
  synapse.v1.AuditService.VerifyAuditIntegrity

# Output:
# {
#   "valid": true,
#   "numEntries": 2847,
#   "rootHash": "sha256:...",
#   "lastVerifiedAt": "2026-06-24T10:00:00Z",
#   "errors": []
# }
```

### Errors

```
PERMISSION_DENIED: Requester not an auditor
NOT_FOUND: Subject or prediction not found
INVALID_ARGUMENT: Bad time range
FAILED_PRECONDITION: Audit trail integrity check failed
```

---

## Admin API

### Service: AdminService

**Purpose:** Platform administration (operator-only)

**Proto Definition:**

```protobuf
service AdminService {
  rpc CreateSubject(CreateSubjectRequest) returns (CreateSubjectResponse);
  rpc DeployModel(DeployModelRequest) returns (DeployModelResponse);
  rpc RotateKeys(RotateKeysRequest) returns (RotateKeysResponse);
  rpc GetSystemStatus(GetSystemStatusRequest) returns (GetSystemStatusResponse);
}

message CreateSubjectRequest {
  string subject_name = 1;
  string email = 2;
  string phone = 3;
}

message CreateSubjectResponse {
  string subject_id = 1;
  string enrollment_token = 2;  // For edge app provisioning
  int64 token_expires_at_unix_ms = 3;
}

message DeployModelRequest {
  string model_id = 1;
  string version = 2;
  bytes model_weights = 3;  // Serialized model
  string training_dataset = 4;
  double training_epsilon = 5;
}

message DeployModelResponse {
  bool success = 1;
  string message = 2;
}

message RotateKeysRequest {
  string subject_id = 1;  // Optional: if empty, rotate all subjects
}

message RotateKeysResponse {
  int32 subjects_rotated = 1;
}

message GetSystemStatusRequest {}

message GetSystemStatusResponse {
  string status = 1;  // "healthy", "degraded", "unhealthy"
  repeated ServiceStatus services = 2;
  int64 uptime_seconds = 3;
}

message ServiceStatus {
  string name = 1;
  string status = 2;
  int64 latency_ms = 3;
  int64 error_count = 4;
}
```

### Usage: Operator Example

```bash
# Create a subject
grpcurl -d '{
  "subject_name": "Jane Doe",
  "email": "jane@example.com",
  "phone": "+234-xxx-xxxx"
}' \
  -cacert ca.pem \
  -cert admin.pem \
  -key admin-key.pem \
  synapse-gateway:8443 \
  synapse.v1.AdminService.CreateSubject

# Output:
# {
#   "subjectId": "subj-7f3a9b2c",
#   "enrollmentToken": "provisioning-abc123def456",
#   "tokenExpiresAtUnixMs": 1719312000000
# }
```

### Errors

```
PERMISSION_DENIED: Only admins can call these methods
ALREADY_EXISTS: Subject/model already exists
RESOURCE_EXHAUSTED: Too many subjects/models
INTERNAL: System error
```

---

## Error Codes

SYNAPSE-AI uses standard gRPC error codes:

| Code | Meaning | Typical Cause |
| --- | --- | --- |
| `OK` (0) | Success | N/A |
| `CANCELLED` (1) | Request cancelled | Client cancelled |
| `UNKNOWN` (2) | Unknown error | Server bug |
| `INVALID_ARGUMENT` (3) | Bad input | Malformed request |
| `DEADLINE_EXCEEDED` (4) | Request timed out | Slow response |
| `NOT_FOUND` (5) | Resource not found | Subject/grant not found |
| `ALREADY_EXISTS` (6) | Resource exists | Duplicate grant |
| `PERMISSION_DENIED` (7) | No authorization | Wrong mTLS cert |
| `RESOURCE_EXHAUSTED` (8) | Capacity exceeded | Rate limit, budget exhausted |
| `FAILED_PRECONDITION` (9) | Invalid state | Consent expired, grant revoked |
| `ABORTED` (10) | Transaction aborted | Retry-able transient error |
| `INTERNAL` (13) | Server error | Server bug, out of memory |
| `UNAVAILABLE` (14) | Service unavailable | Dependency down |
| `UNAUTHENTICATED` (16) | Auth required | mTLS cert missing/invalid |

### Error Response Format

```json
{
  "code": 7,
  "message": "PERMISSION_DENIED: Requester identity not authorized",
  "details": [
    {
      "code": "PERMISSION_DENIED",
      "message": "Requester mTLS cert CN 'unknown-lab' not in allowlist",
      "metadata": {
        "requester_id": "unknown-lab",
        "required_role": "researcher"
      }
    }
  ]
}
```

---

## Examples

### End-to-End Flow

**1. Subject Enrolls**
```
Admin: CreateSubject(name="Jane", email="jane@example.com")
  → Returns: subject_id="subj-7f3a", enrollment_token="prov-abc"

Jane: Opens edge app, enters enrollment_token
  → App gets device cert, stores in secure storage

Gateway: Verifies device cert on first connection
  → Returns: ready_to_ingest
```

**2. Grant Consent**
```
Jane (via web): CreateGrant(
  model="mental-state-classifier@v2.3",
  purpose="attention/fatigue research",
  ttl_days=30
)
  → Returns: grant_id="g-001", status="ACTIVE"

Jane: Receives email confirmation
```

**3. Stream EEG**
```
Edge App: StreamSamples(sample_1, sample_2, ...)
  → Each sample: signed + encrypted

Gateway: VerifySignature, verify mTLS cert
  → All good, forward to storage

Storage: Append encrypted sample to WAL
  → Durability guaranteed via fsync
```

**4. Request Inference**
```
Researcher: Infer(
  subject_id="subj-7f3a",
  model_id="mental-state-classifier@v2.3",
  purpose="attention/fatigue research"
)
  → Gateway: VerifyConsent(subj-7f3a, model-v2.3, purpose)
  → Result: ACTIVE ✓
  
  → PrivacyBudget.Check(subj-7f3a)
  → Result: epsilon_remaining=0.9 ✓
  
  → Storage.Fetch(subj-7f3a) → encrypted samples
  → Decrypt (using subject key)
  → Preprocess & run model
  → Add DP noise
  → Log to audit
  → Return: {"attention": 0.71, ...} + provenance
```

**5. Subject Revokes Consent**
```
Jane: RevokeGrant(grant_id="g-001")
  → Revocation appended to ledger

Researcher (60s later): Infer(...)
  → Gateway: VerifyConsent(...)
  → Ledger: Grant has revocation → REVOKED
  → Return: PERMISSION_DENIED
```

---

## Rate Limits

| Endpoint | Limit | Window |
| --- | --- | --- |
| `IngestService.StreamSamples` | 10,000 samples/sec per device | 1 second |
| `ConsentService.CreateGrant` | 100 grants/sec per subject | 1 minute |
| `InferenceService.Infer` | 1,000 inferences/sec per model | 1 second |
| `AuditService.ListPredictions` | 100 queries/sec per requester | 1 minute |

If a limit is exceeded, the server returns `RESOURCE_EXHAUSTED`.

---

## Backwards Compatibility

**API Versioning:** Current version is `v1`

- Breaking changes (next major version): Will bump to `v2`
- Non-breaking changes: Backwards compatible
- Example: Adding a new optional field to a request is safe
- Example: Removing a required field is a breaking change

---

**For more details, see:**
- [DESIGN_DOC.md](DESIGN_DOC.md) — API schema details
- [ARCHITECTURE.md](ARCHITECTURE.md) — System design
- [Examples](https://github.com/nickemma/synapse-ai/tree/main/examples) — Runnable examples
