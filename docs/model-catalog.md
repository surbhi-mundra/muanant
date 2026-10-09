# Model catalog

This document lists recommended models for each capability, organized by
hardware tier. The catalog is *advisory* — the actual backend wiring is in
`configs/models.yaml`, and the ModelGateway makes any swap a config change.

> **Critical:** SOVEREIGN is model-agnostic. The development model used to
> build SOVEREIGN has no special status inside the system. Any open-weight
> model that satisfies the protocol interface can be used.

## Text LLM

| Model | Size | VRAM (4-bit) | Context | License | Notes |
|---|---|---|---|---|---|
| Qwen2.5-7B-Instruct | 7B | 6 GB | 32k | Apache 2.0 | Best small-model quality |
| Qwen2.5-14B-Instruct | 14B | 10 GB | 32k | Apache 2.0 | Solid mid-tier |
| Qwen2.5-32B-Instruct | 32B | 20 GB | 64k | Apache 2.0 | Tier 3 sweet spot |
| Qwen2.5-72B-Instruct | 72B | 40 GB | 64k | Apache 2.0 | Tier 3+ reasoning |
| Llama-3.1-8B-Instruct | 8B | 6 GB | 128k | Llama 3.1 | Long context |
| Llama-3.3-70B-Instruct | 70B | 40 GB | 128k | Llama 3.3 | Tier 3+ alternative |
| Mistral-Small-24B-Instruct | 24B | 14 GB | 32k | Apache 2.0 | Good efficiency |
| DeepSeek-V2-Lite-Instruct | 16B | 10 GB | 32k | DeepSeek License | MoE |

**Recommendation:** Qwen2.5 family for new deployments — strong multi-turn
tool-calling support, permissive license, well-supported by vLLM.

## Vision LLM

| Model | Size | VRAM (4-bit) | Context | License | Notes |
|---|---|---|---|---|---|
| Qwen2-VL-7B-Instruct | 7B | 8 GB | 32k | Apache 2.0 (with notice) | Best small VLM |
| Qwen2-VL-72B-Instruct | 72B | 40 GB | 32k | Apache 2.0 (with notice) | Tier 3+ |
| Llama-3.2-11B-Vision-Instruct | 11B | 8 GB | 128k | Llama 3.2 | Solid alternative |
| InternVL2-26B | 26B | 16 GB | 8k | MIT | Good OCR/diagram |

**Recommendation:** Qwen2-VL for engineering drawings and inspection images
— strong on document-style imagery.

## Embedding model

| Model | Dim | VRAM | Context | License | Notes |
|---|---|---|---|---|---|
| BAAI/bge-m3 | 1024 | 2 GB | 8k | MIT | Multi-lingual, strong |
| BAAI/bge-large-en-v1.5 | 1024 | 1.5 GB | 0.5k | MIT | English-only |
| sentence-transformers/all-MiniLM-L6-v2 | 384 | 0.5 GB | 0.5k | Apache 2.0 | Fast, lightweight |
| nomic-embed-text-v1.5 | 768 | 1 GB | 8k | Apache 2.0 | Long context |

**Recommendation:** `bge-m3` — best quality per VRAM, multi-lingual,
well-supported by `sentence-transformers` and the TEI server.

## Reranker

| Model | VRAM | License | Notes |
|---|---|---|---|
| BAAI/bge-reranker-v2-m3 | 2 GB | MIT | Best general-purpose |
| BAAI/bge-reranker-large | 1.5 GB | MIT | Slightly faster |
| jina-reranker-v2-base-multilingual | 1 GB | CC BY-NC 4.0 | Non-commercial |

**Recommendation:** `bge-reranker-v2-m3` — permissive license, strong quality.

## OCR

| Engine | GPU required? | License | Notes |
|---|---|---|---|
| Tesseract 5.x | No | Apache 2.0 | Baseline; CPU-friendly |
| Surya OCR | Optional | GPL-3.0 | Layout-aware, strong on tables |
| PaddleOCR | Optional | Apache 2.0 | Multi-lingual, very fast on GPU |
| docTR | Optional | Apache 2.0 | Good for document layout |

**Recommendation:** Tesseract for Tier 1–2 (CPU-friendly, present in dev
sandbox). Surya or PaddleOCR for Tier 2+ when layout-aware OCR matters
(engineering drawings, multi-column reports).

## Inference servers

| Server | Strengths | License |
|---|---|---|
| vLLM | Best throughput, multimodal, PagedAttention | Apache 2.0 |
| Ollama | Easiest ops, GGUF support | MIT |
| TGI (HuggingFace) | Solid, simpler than vLLM | Apache 2.0 |
| Text Embeddings Inference (TEI) | Dedicated to embeddings/reranking | Apache 2.0 |
| LMDeploy | Strong on internLM family | Apache 2.0 |

**Recommendation:** vLLM for LLM/VLM serving, TEI for embeddings/reranking.
Ollama as a Tier-2 fallback where ops simplicity matters more than throughput.

## License compliance checklist

Before adding a model to the catalog:

- [ ] License permits commercial use (Apache 2.0, MIT, or permissive custom)
- [ ] Model weights are downloadable without gated access (or accept gated)
- [ ] Acceptable use policy is compatible with industrial use case
- [ ] Quantization is available in a supported format (AWQ / GPTQ / GGUF)
- [ ] vLLM (or chosen server) supports the model architecture
- [ ] VRAM requirement fits at least one tier
- [ ] Documented context length is sufficient for the RAG workload
