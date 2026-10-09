# SOVEREIGN — Deployment Guide

## Tier 1: Developer Machine (dev)

### Prerequisites
- Python 3.11+
- `uv` (or pip)
- Tesseract OCR (`apt install tesseract-ocr` on Linux)
- qpdf (`apt install qpdf`)
- Node.js 22+ + npm (for the workbench)

### Quick Start

```bash
# 1. Install backend deps
make install

# 2. Run migrations (creates SQLite DB)
make migrate

# 3. Start the API
make run

# 4. In another terminal, start the workbench
cd workbench
npm install
npm run dev
```

The API is at http://127.0.0.1:8000, the workbench at http://127.0.0.1:3000.

### Using Docker (dev)

```bash
docker compose -f infra/compose/docker-compose.dev.yml up -d
```

## Tier 2: Single GPU Workstation

### Prerequisites
- NVIDIA GPU (24GB VRAM: RTX 4090, A10, L40S)
- NVIDIA drivers + CUDA
- Docker + NVIDIA Container Toolkit

### Deployment

```bash
# 1. Edit configs/models.yaml to use real model backends
#    (vLLM for LLM/Vision, sentence-transformers for embeddings)

# 2. Set the JWT secret
export SOVEREIGN_JWT_SECRET=$(openssl rand -hex 32)

# 3. Start all services
docker compose -f infra/compose/docker-compose.yml up -d

# 4. Run migrations
docker compose exec api python -m alembic upgrade head

# 5. Verify
curl http://localhost:8000/healthz
curl http://localhost:8000/readyz
```

### Model Configuration

Edit `configs/models.yaml` to switch from mock to real backends:

```yaml
text:
  backend: vllm.text
  model_name: Qwen/Qwen2.5-7B-Instruct
  server_url: http://127.0.0.1:8001
  quantization: awq

vision:
  backend: vllm.vision
  model_name: Qwen/Qwen2-VL-7B-Instruct
  server_url: http://127.0.0.1:8002

embedding:
  backend: sentence_transformers.embedding
  model_name: BAAI/bge-m3
  dim: 1024

reranker:
  backend: cross_encoder.reranker
  model_name: BAAI/bge-reranker-v2-m3

ocr:
  backend: tesseract.ocr
  model_name: tesseract-5.x
```

### Starting vLLM Servers

```bash
# Text LLM
vllm serve Qwen/Qwen2.5-7B-Instruct \
  --quantization awq \
  --port 8001 \
  --max-model-len 32768

# Vision LLM
vllm serve Qwen/Qwen2-VL-7B-Instruct \
  --quantization awq \
  --port 8002 \
  --max-model-len 32768
```

## Tier 3: Enterprise GPU Server

### Prerequisites
- 2-4× NVIDIA A100/H100 (80GB VRAM each)
- Kubernetes cluster with NVIDIA GPU operator
- Load balancer + TLS certificate

### Deployment

```bash
# 1. Create namespace + secrets
kubectl create namespace sovereign
kubectl create secret generic sovereign-db-secret \
  --from-literal=password=$(openssl rand -hex 16) \
  -n sovereign
kubectl create secret generic sovereign-api-secret \
  --from-literal=jwt-secret=$(openssl rand -hex 32) \
  -n sovereign

# 2. Build and push images
docker build -t sovereign-api:latest -f infra/docker/Dockerfile .
docker build -t sovereign-workbench:latest -f infra/docker/Dockerfile.workbench .
docker push sovereign-api:latest
docker push sovereign-workbench:latest

# 3. Deploy
kubectl apply -f infra/k8s/deployment.yaml

# 4. Wait for rollout
kubectl rollout status deployment/sovereign-api -n sovereign
kubectl rollout status deployment/sovereign-workbench -n sovereign

# 5. Check health
kubectl exec -it deployment/sovereign-api -n sovereign -- \
  curl http://localhost:8000/readyz
```

## Tier 4: Multi-GPU On-Prem Infrastructure

For Tier 4, use the same Kubernetes manifests but:
- Scale the API deployment to 4+ replicas
- Use GPU node taints/tolerations to schedule on GPU nodes
- Deploy vLLM with tensor parallelism across multiple GPUs
- Use a Qdrant cluster (3+ nodes) instead of a single instance
- Configure Postgres with streaming replication
- Add a CDN/cache layer for the workbench

## Security Checklist (Prod)

- [ ] Change `SOVEREIGN_JWT_SECRET` to a random 32+ byte string
- [ ] Change the PostgreSQL password
- [ ] Set `SOVEREIGN_ENV=prod` (disables `/docs` and OpenAPI)
- [ ] Set `EGRESS_ENABLED=false` (default)
- [ ] Configure TLS for the API and workbench
- [ ] Set up OIDC (Keycloak/Authentik) for authentication
- [ ] Configure Postgres RLS policies for project isolation
- [ ] Enable disk encryption (LUKS) for the object store volume
- [ ] Set up the audit chain verification cron job
- [ ] Configure backup for PostgreSQL + Qdrant + object store

## Backup

```bash
# PostgreSQL
pg_dump -U sovereign sovereign > backup_$(date +%Y%m%d).sql

# Qdrant
curl http://localhost:6333/collections | jq '.result.collections[].name' | \
  xargs -I{} curl -X POST http://localhost:6333/collections/{}/snapshots

# Object store
tar czf objects_$(date +%Y%m%d).tar.gz /var/lib/sovereign/objects/
```

## Monitoring

- **Health**: `GET /healthz` (liveness), `GET /readyz` (readiness)
- **Metrics**: structured JSON logs (stdout), OTEL traces (Phase 11 stubs → real exporter)
- **Audit**: `scripts/verify_audit_chain.py` (run as cron job)

## Troubleshooting

### API won't start
- Check `DATABASE_URL` is reachable
- Check `QDRANT_URL` is reachable (or empty for embedded mode)
- Check `configs/models.yaml` exists and is valid
- Run `make migrate` to ensure DB schema is up to date

### OCR not working
- Verify tesseract is installed: `tesseract --version`
- Check `pytesseract` is installed: `pip install pytesseract`
- Check the image is a valid PNG/JPEG/WEBP

### RAG returns "insufficient evidence"
- Check the knowledge base has indexed documents: `GET /kb/stats`
- Try re-indexing: `POST /documents/{id}/index`
- Check the query is relevant to uploaded documents
- With the MockBackend, the LLM can't generate grounded answers — use a real LLM for meaningful results

### Performance
- Use vLLM with AWQ quantization for best throughput
- Increase `evidence_top_k` in RAG config for more context (at the cost of latency)
- Use Qdrant server mode (not embedded) for >100k vectors
- Scale the API horizontally for concurrent users
