# Hardware tiers

SOVEREIGN is designed to deploy at four tiers, from a developer laptop to a
multi-GPU enterprise server. The application code is identical across tiers
— only `configs/models.yaml` and `configs/<env>.yaml` change.

## Tier 1 — Developer machine

| Item | Value |
|---|---|
| CPU | Any modern x86_64 / ARM64, 4+ cores |
| RAM | 8 GB minimum, 16 GB recommended |
| GPU | None required |
| Disk | 20 GB |
| OS | Linux / macOS / WSL2 |

**Use case:** local development, CI, smoke tests.

**Model stack:** `MockBackend` for all 5 capabilities. No real inference.
The entire pipeline (ingestion → RAG → agents → deliverables) runs end-to-end
on recorded fixtures.

**Config:** `configs/dev.yaml` + `configs/models.yaml` (default mock backends).

**What works:** everything except actually intelligent model output. The
point of Tier 1 is to exercise the *plumbing* — config, logging, audit,
retrieval mechanics, agent routing, deliverable rendering — without burning
GPU cycles.

## Tier 2 — Single GPU workstation

| Item | Value |
|---|---|
| CPU | 8+ cores |
| RAM | 32 GB |
| GPU | 1× NVIDIA, 24 GB VRAM (RTX 4090, A10, L40S) |
| Disk | 500 GB SSD |

**Use case:** small team pilot, single-user production.

**Recommended models:**

| Capability | Model | VRAM | Quant | Context | License |
|---|---|---|---|---|---|
| Text LLM | Qwen2.5-7B-Instruct | ~6 GB (AWQ 4-bit) | AWQ | 32k | Apache 2.0 |
| Vision LLM | Qwen2-VL-7B-Instruct | ~8 GB (AWQ 4-bit) | AWQ | 32k | Apache 2.0 (with notice) |
| Embedding | BAAI/bge-m3 | ~2 GB (FP16) | FP16 | 8k | MIT |
| Reranker | BAAI/bge-reranker-v2-m3 | ~2 GB (FP16) | FP16 | 8k | MIT |
| OCR | Tesseract 5.x | CPU | n/a | n/a | Apache 2.0 |

Inference server: **vLLM** with AWQ quantization for the LLMs.

## Tier 3 — Enterprise GPU server

| Item | Value |
|---|---|
| CPU | 32+ cores |
| RAM | 128 GB |
| GPU | 2–4× NVIDIA, 80 GB VRAM each (A100, H100) |
| Disk | 4 TB NVMe |

**Use case:** department-wide deployment, 10–50 concurrent users.

**Recommended models:**

| Capability | Model | VRAM | Quant | Context |
|---|---|---|---|---|
| Text LLM | Qwen2.5-32B-Instruct | ~20 GB (AWQ 4-bit) | AWQ | 64k |
| Vision LLM | Qwen2-VL-72B-Instruct | ~40 GB (AWQ 4-bit) | AWQ | 32k |
| Embedding | BAAI/bge-m3 | ~2 GB | FP16 | 8k |
| Reranker | BAAI/bge-reranker-v2-m3 | ~2 GB | FP16 | 8k |
| OCR | Surya (layout-aware) | ~4 GB | FP16 | n/a |

Inference server: **vLLM** with tensor parallelism across GPUs.

## Tier 4 — Multi-GPU on-prem infrastructure

| Item | Value |
|---|---|
| CPU | 64+ cores |
| RAM | 256+ GB |
| GPU | 8+× NVIDIA H100 80GB |
| Disk | 10+ TB NVMe + tape backup |

**Use case:** enterprise-wide deployment, 100+ concurrent users, multi-team.

**Recommended models:** Tier 3 set + dedicated OCR/vision nodes; horizontal
scaling via vLLM with Ray backend. Qdrant server mode in a 3-node cluster.

## Notes on quantization

- **AWQ 4-bit** is the recommended quantization for production — negligible
  quality loss vs FP16, ~4× VRAM reduction.
- **GPTQ** is an alternative but slightly slower inference.
- **GGUF** is used when running on Ollama (Tier 2 fallback).
- Always benchmark on your own workload before committing to a quant.

## Notes on context length

Industrial documents are long. The 9-stage RAG pipeline is designed so the
LLM never sees the full document — only the reranked top-k chunks (typically
5–10 chunks × ~500 tokens = 2.5k–5k tokens of context). This means a 32k
context model is sufficient for almost all RAG use cases; long-context
models (128k+) are only needed for full-document summarization or
cross-document reasoning.
