# INSTALL.md — SYNAPSE-AI

**Installation & Configuration Guide**

**Last Updated:** June 24, 2026  
**Status:** Pre-Release

---

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Prerequisites](#prerequisites)
3. [Local Development Setup](#local-development-setup)
4. [Docker Compose Quick Start](#docker-compose-quick-start)
5. [Kubernetes Production Deployment](#kubernetes-production-deployment)
6. [Configuration Reference](#configuration-reference)
7. [Troubleshooting](#troubleshooting)

---

## System Requirements

### For Local Development

- **OS:** Linux (Ubuntu 22.04 LTS recommended) or macOS (Intel/Apple Silicon)
- **CPU:** 4 cores minimum (8 cores recommended for multi-node federated learning)
- **RAM:** 8 GB minimum (16 GB recommended)
- **Storage:** 100 GB SSD (for storing neural signal samples)
- **Network:** Stable internet connection with mTLS support

### For Production

- **Kubernetes:** 1.24+ (managed K8s on AWS EKS, GCP GKE, or self-hosted)
- **Nodes:** 3+ nodes (for redundancy and federated learning)
- **CPU:** 2 cores per pod; total 6+ cores
- **RAM:** 4 GB per pod; total 12+ GB
- **Storage:** PersistentVolumes with 100+ GB capacity
- **Database:** PostgreSQL 13+ or compatible (managed RDS, CloudSQL)
- **KMS:** AWS KMS or similar key management service

---

## Prerequisites

### Required Software

```bash
# Go 1.25+
wget https://go.dev/dl/go1.25.linux-amd64.tar.gz
tar -C /usr/local -xzf go1.25.linux-amd64.tar.gz
export PATH=$PATH:/usr/local/go/bin

# Rust 1.87+
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env

# Python 3.12+
sudo apt-get install python3.12 python3.12-venv

# Docker & docker-compose
sudo apt-get install docker.io docker-compose

# protoc (Protocol Buffers compiler)
sudo apt-get install protobuf-compiler

# kubectl (for Kubernetes deployments)
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
```

### Optional Tools

```bash
# Helm (for Kubernetes package management)
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# k9s (terminal UI for Kubernetes)
curl https://github.com/derailed/k9s/releases/download/v0.27.4/k9s_Linux_amd64.tar.gz -L -o k9s.tar.gz
tar -xzf k9s.tar.gz && sudo mv k9s /usr/local/bin/

# grpcurl (gRPC CLI tool)
go install github.com/fullstorydev/grpcurl/cmd/grpcurl@latest
```

### AWS CLI & Credentials (for Production)

```bash
# AWS CLI v2
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Configure credentials
aws configure
# Enter:
# AWS Access Key ID: [your-key]
# AWS Secret Access Key: [your-secret]
# Default region: us-west-2
# Default output format: json
```

---

## Local Development Setup

### 1. Clone the Repository

```bash
git clone https://github.com/nickemma/synapse-ai.git
cd synapse-ai

# Verify Go, Rust, Python versions
go version       # expect 1.25+
rustc --version  # expect 1.87+
python3 --version # expect 3.12+
```

### 2. Build the Binary

```bash
make build
# Compiles:
# - Gateway (Go)
# - Storage service (Rust)
# - Inference service (Go)
# - FL Orchestrator (Python)
# - CLI tools (Go)

# Output: ./bin/synapse-*
```

### 3. Generate Certificates for mTLS

```bash
# Create CA
mkdir -p ./certs
openssl genrsa -out ./certs/ca-key.pem 4096
openssl req -new -x509 -days 3650 -key ./certs/ca-key.pem \
  -out ./certs/ca.pem \
  -subj "/CN=synapse-ai-ca/O=SYNAPSE-AI/C=NG"

# Create server cert (gateway)
openssl genrsa -out ./certs/server-key.pem 4096
openssl req -new -key ./certs/server-key.pem \
  -out ./certs/server.csr \
  -subj "/CN=synapse-gateway/O=SYNAPSE-AI/C=NG"
openssl x509 -req -in ./certs/server.csr \
  -CA ./certs/ca.pem -CAkey ./certs/ca-key.pem \
  -CAcreateserial -out ./certs/server.pem \
  -days 365 -sha256

# Create client cert (for testing)
openssl genrsa -out ./certs/client-key.pem 4096
openssl req -new -key ./certs/client-key.pem \
  -out ./certs/client.csr \
  -subj "/CN=test-client/O=SYNAPSE-AI/C=NG"
openssl x509 -req -in ./certs/client.csr \
  -CA ./certs/ca.pem -CAkey ./certs/ca-key.pem \
  -CAcreateserial -out ./certs/client.pem \
  -days 365 -sha256

# Copy to docker-compose volume
mkdir -p ./config/certs
cp ./certs/*.pem ./config/certs/
```

### 4. Set Environment Variables

```bash
export SYNAPSE_GATEWAY_PORT=8443
export SYNAPSE_STORAGE_DIR=./data/storage
export SYNAPSE_MTLS_CA=./certs/ca.pem
export SYNAPSE_MTLS_SERVER_CERT=./certs/server.pem
export SYNAPSE_MTLS_SERVER_KEY=./certs/server-key.pem
export SYNAPSE_CONSENT_DENY_BY_DEFAULT=true
export SYNAPSE_DP_EPSILON_PER_SUBJECT=1.0
export SYNAPSE_DP_DELTA=1e-5
```

### 5. Start Services

```bash
# Terminal 1: Storage service
./bin/synapse-storage

# Terminal 2: Gateway
./bin/synapse-gateway

# Terminal 3: Inference service
./bin/synapse-inference

# Terminal 4: FL Orchestrator
cd ml/orchestrator && python3 -m orchestrator
```

### 6. Verify Installation

```bash
./bin/synapse-cli health --gateway localhost:8443
# Expected: Status: healthy
```

---

## Docker Compose Quick Start

**Fastest way to get a local cluster running.**

```bash
# Start all services (gateway + storage + inference + FL)
docker-compose up -d

# Verify services are running
docker-compose ps
# All should be "Up"

# View logs
docker-compose logs -f synapse-gateway

# Run end-to-end test
./scripts/e2e-test.sh
# Should complete in <30 seconds

# Stop services
docker-compose down
```

### Customization

Edit `docker-compose.yml` to change:
- Ports (SYNAPSE_GATEWAY_PORT, etc.)
- Storage location (SYNAPSE_STORAGE_DIR)
- Replica count (services → scale)
- Environment variables (services → environment)

---

## Kubernetes Production Deployment

### 1. Create Namespace & Secrets

```bash
kubectl create namespace synapse-ai
kubectl config set-context --current --namespace=synapse-ai

# Create mTLS secrets
kubectl create secret tls synapse-gateway-tls \
  --cert=./certs/server.pem \
  --key=./certs/server-key.pem

kubectl create secret generic synapse-ca \
  --from-file=ca.pem=./certs/ca.pem

# Create KMS credentials
kubectl create secret generic synapse-kms \
  --from-literal=AWS_ACCESS_KEY_ID=<your-key> \
  --from-literal=AWS_SECRET_ACCESS_KEY=<your-secret> \
  --from-literal=AWS_REGION=us-west-2
```

### 2. Deploy Using Helm

```bash
# Add SYNAPSE-AI Helm repo (future; not yet published)
helm repo add synapse-ai https://charts.synapse-ai.io
helm repo update

# Install
helm install synapse-ai synapse-ai/synapse-ai \
  --namespace synapse-ai \
  --values ./helm-values-production.yaml

# Verify deployment
kubectl get pods -n synapse-ai
# All pods should be Running
```

### 3. Alternative: Deploy Using Kubectl

```bash
# Apply manifests
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/storage.yaml
kubectl apply -f k8s/gateway.yaml
kubectl apply -f k8s/inference.yaml
kubectl apply -f k8s/fl-orchestrator.yaml

# Verify
kubectl get all -n synapse-ai
```

### 4. Expose Gateway Service

```bash
# Create LoadBalancer service (AWS, GCP, Azure)
kubectl expose deployment synapse-gateway \
  --type=LoadBalancer \
  --port=8443 \
  --target-port=8443

# Get external IP
kubectl get svc synapse-gateway -n synapse-ai
# Copy the EXTERNAL-IP

# Verify connectivity
curl -k --cacert ./certs/ca.pem \
  https://<EXTERNAL-IP>:8443/health
```

### 5. Configure Ingress (Optional)

```bash
# Install Ingress controller (e.g., nginx-ingress)
helm install nginx-ingress ingress-nginx/ingress-nginx \
  --namespace ingress-nginx --create-namespace

# Create Ingress resource
kubectl apply -f k8s/ingress.yaml

# Verify
kubectl get ingress -n synapse-ai
```

---

## Configuration Reference

### Environment Variables

```bash
# Gateway
SYNAPSE_GATEWAY_PORT=8443
SYNAPSE_GATEWAY_WORKERS=10
SYNAPSE_MTLS_CA=/etc/synapse/ca.pem
SYNAPSE_MTLS_SERVER_CERT=/etc/synapse/server.pem
SYNAPSE_MTLS_SERVER_KEY=/etc/synapse/server-key.pem
SYNAPSE_MTLS_REQUIRE_CLIENT_CERT=true

# Storage
SYNAPSE_STORAGE_DIR=/var/lib/synapse
SYNAPSE_STORAGE_HOST=localhost
SYNAPSE_STORAGE_PORT=9090
SYNAPSE_WAL_SYNC_INTERVAL_MS=100
SYNAPSE_WAL_ENCRYPTION_KEY=<32-byte-hex-key>  # Generated on first run

# Consent Engine
SYNAPSE_CONSENT_DENY_BY_DEFAULT=true
SYNAPSE_CONSENT_LEDGER_PATH=/var/lib/synapse/ledger
SYNAPSE_CONSENT_CACHE_TTL_SECONDS=60

# Privacy
SYNAPSE_DP_EPSILON_PER_SUBJECT=1.0
SYNAPSE_DP_DELTA=1e-5
SYNAPSE_DP_CLIP_NORM=1.0

# Federated Learning
SYNAPSE_FL_MIN_NODES=3
SYNAPSE_FL_NODE_TIMEOUT_SECONDS=3600
SYNAPSE_FL_AGGREGATION=secure-avg
SYNAPSE_FL_GRADIENT_COMPRESSION=none  # or "quantize"

# Audit & Observability
SYNAPSE_AUDIT_HASH_CHAIN=true
SYNAPSE_AUDIT_LEDGER_PATH=/var/lib/synapse/audit
SYNAPSE_METRICS_PORT=9090
SYNAPSE_LOGGING_LEVEL=info  # debug, info, warn, error

# Database (Postgres)
SYNAPSE_DATABASE_URL=postgres://user:pass@localhost:5432/synapse_db
SYNAPSE_DATABASE_POOL_SIZE=20

# KMS (AWS)
AWS_REGION=us-west-2
AWS_KMS_KEY_ID=arn:aws:kms:us-west-2:123456789:key/...
AWS_ACCESS_KEY_ID=<key>
AWS_SECRET_ACCESS_KEY=<secret>
```

### Config File (YAML)

Alternatively, create `synapse-config.yaml`:

```yaml
gateway:
  port: 8443
  workers: 10
  tls:
    ca_path: /etc/synapse/ca.pem
    cert_path: /etc/synapse/server.pem
    key_path: /etc/synapse/server-key.pem
    require_client_cert: true

storage:
  dir: /var/lib/synapse
  host: localhost
  port: 9090
  wal:
    sync_interval_ms: 100
    encryption_key: <32-byte-hex>

consent:
  deny_by_default: true
  ledger_path: /var/lib/synapse/ledger
  cache_ttl_seconds: 60

privacy:
  epsilon_per_subject: 1.0
  delta: 1e-5
  clip_norm: 1.0

federated_learning:
  min_nodes: 3
  node_timeout_seconds: 3600
  aggregation: secure-avg

audit:
  hash_chain: true
  ledger_path: /var/lib/synapse/audit

observability:
  metrics_port: 9090
  logging_level: info
```

Load with:
```bash
./bin/synapse-gateway --config synapse-config.yaml
```

---

## Troubleshooting

### Problem: `connection refused` on localhost:8443

**Diagnosis:**
```bash
netstat -tuln | grep 8443
# Should show a listening socket
```

**Solution:**
```bash
# Check gateway logs
docker-compose logs synapse-gateway | grep ERROR

# Verify port is not in use
lsof -i :8443

# If in use, kill the process or use a different port
export SYNAPSE_GATEWAY_PORT=8444
docker-compose up -d
```

### Problem: mTLS certificate verification failed

**Diagnosis:**
```bash
# Test mTLS handshake
openssl s_client -connect localhost:8443 \
  -cert ./certs/client.pem \
  -key ./certs/client-key.pem \
  -CAfile ./certs/ca.pem
```

**Solution:**
```bash
# Verify certificates are signed by CA
openssl verify -CAfile ./certs/ca.pem ./certs/server.pem
openssl verify -CAfile ./certs/ca.pem ./certs/client.pem

# If verification fails, regenerate certs:
rm ./certs/*
# Then re-run "Generate Certificates for mTLS" section above
```

### Problem: `permission denied` on /var/lib/synapse

**Diagnosis:**
```bash
ls -la /var/lib/synapse
# Check owner and permissions
```

**Solution:**
```bash
# Change owner to the synapse user (if running as a service)
sudo chown -R synapse:synapse /var/lib/synapse

# Or, run docker-compose with elevated privileges
sudo docker-compose up -d
```

### Problem: Database connection failed

**Diagnosis:**
```bash
psql -h localhost -U synapse_user -d synapse_db -c "SELECT 1;"
# Should return 1
```

**Solution:**
```bash
# Check PostgreSQL is running
docker-compose logs postgres

# Verify credentials in SYNAPSE_DATABASE_URL
echo $SYNAPSE_DATABASE_URL

# If using local Postgres, ensure it's started:
sudo systemctl start postgresql
```

### Problem: Out of Memory (OOM) errors

**Diagnosis:**
```bash
docker stats
# Check memory usage of each container
```

**Solution:**
```bash
# Increase memory limits in docker-compose.yml:
services:
  synapse-storage:
    mem_limit: 4g  # increase from 2g

# Or, on Kubernetes:
kubectl set resources deployment synapse-storage \
  --limits=memory=4Gi --requests=memory=2Gi
```

---

## Post-Installation

### 1. Enroll Your First Subject

```bash
./bin/synapse-admin subject create \
  --subject-name "Test Subject" \
  --email test@example.com

# Output: enrollment_token: ...
```

### 2. Grant Consent for a Model

```bash
./bin/synapse-cli consent create \
  --subject <subject-id> \
  --model mental-state-classifier@v2.3 \
  --purpose "research" \
  --ttl 30

# Output: grant_id: ...
```

### 3. Run Your First Inference

```bash
./bin/synapse-cli infer \
  --subject <subject-id> \
  --model mental-state-classifier@v2.3 \
  --input samples/eeg-public-sample.edf

# Output: prediction with provenance
```

### 4. Verify Audit Trail

```bash
./bin/synapse-cli audit show --prediction <prediction-id>
# Should show full provenance record
```

---

## Next Steps

- [ ] Review [THREAT_MODEL.md](THREAT_MODEL.md)
- [ ] Review [DESIGN_DOC.md](DESIGN_DOC.md)
- [ ] Review [RUNBOOK.md](RUNBOOK.md)
- [ ] Configure monitoring (Prometheus + Grafana)
- [ ] Set up backups (to S3 or similar)
- [ ] Set up CI/CD pipeline
- [ ] Plan capacity & scaling

---

**Need help?** Open an issue on GitHub or contact support@synapse-ai.io
