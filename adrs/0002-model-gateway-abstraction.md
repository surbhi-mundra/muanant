# 0002. Model Gateway abstraction

Date: 2026-10-09
Status: Accepted

## Context

SOVEREIGN's mandate is to be a model-agnostic on-premise AI workbench.
Organizations must be able to swap the underlying LLM, vision model,
embedding model, reranker, and OCR engine without rewriting application
code. The choice of model depends on hardware tier, license constraints,
language requirements, and evolving open-weight model quality — none of
which are stable enough to hard-code.

Additionally: **the development model used to build SOVEREIGN has no
special status inside the system.** This is a hard requirement from the
project owner. There must be no code path that references a specific model
family (GLM, Llama, Qwen, etc.) by name.

The dev sandbox is a 2-vCPU / 4 GB / no-GPU box. Real model inference is
impossible here, but the entire pipeline must be exercisable end-to-end
for development and CI. This demands a backend that runs without GPU and
without multi-GB model downloads.

## Options considered

### Option A — Direct calls to model libraries in each agent
Each agent imports `transformers` / `vllm` / `sentence_transformers`
directly and instantiates the model it needs.

- Pros: simplest; no abstraction layer.
- Cons: changing the model means editing every agent. Testing without a
  GPU is impossible. The dev sandbox can't run anything. Hard-codes model
  names — violates the mandate.

### Option B — String-based model registry
A central dict maps `"llm"` → some callable. Agents call
`registry["llm"](...)`.

- Pros: slightly better than A — one place to change model names.
- Cons: no type safety; the registry callable can have any signature, so
  agents still couple to a specific call shape. Hard to mock. No protocol
  enforcement.

### Option C — ModelGateway with Protocol interfaces + adapter registry
Define Python `Protocol`s for each capability (`TextLLM`, `VisionLLM`,
`EmbeddingModel`, `Reranker`, `OCR`). A `ModelGateway` factory reads
`configs/models.yaml` and constructs the right adapter per capability.
Agents and capabilities depend only on the Protocols. Adapters register
themselves in a registry. A `MockBackend` provides a CPU-only, zero-dep
reference implementation for dev/CI.

- Pros: type-safe; `isinstance(x, TextLLM)` runtime check; trivially
  mockable; swap-by-YAML; dev sandbox runs everything; the contract is
  explicit and self-documenting.
- Cons: more code upfront (5 protocols + schemas + gateway + registry);
  Protocol evolution requires back-compat consideration.

### Option D — LangChain / LlamaIndex model abstractions
Use an existing framework's model abstraction layer.

- Pros: less code to write.
- Cons: couples SOVEREIGN to that framework's API and its evolution; the
  framework may not abstract all 5 capabilities (e.g., OCR is rarely
  covered); framework abstractions are often leaky and constrain backend
  choices.

## Decision

Adopt **Option C — ModelGateway with Protocol interfaces + adapter registry.**

Concretely:
- `sovereign/models/schemas.py` defines 5 Protocols + their request/response
  dataclasses.
- `sovereign/models/backends/__init__.py` is the adapter registry.
- `sovereign/models/backends/mock.py` is the reference implementation
  (`MockTextLLM`, `MockVisionLLM`, `MockEmbeddingModel`, `MockReranker`,
  `MockOCR`) used by dev/CI.
- `sovereign/models/gateway.py` is the `ModelGateway` factory that reads
  `configs/models.yaml` and constructs the right adapters lazily.
- Real adapters (`vllm.py`, `ollama.py`, `sentence_transformers.py`,
  `tesseract.py`, `surya.py`, etc.) are added in later phases as the
  relevant subsystems need them. They register themselves on import.
- Agents and capabilities receive a `ModelGateway` via FastAPI DI and ask
  for capabilities via `gateway.text`, `gateway.vision`, etc.

## Reason

Option C is the only option that satisfies all three constraints:

1. **Model-agnosticism**: agents depend on Protocols, not adapters. Swap
   is a YAML edit, not a code edit.
2. **Dev-sandbox runnable**: the `MockBackend` runs the entire pipeline on
   CPU with zero ML deps. CI runs the same tests as prod.
3. **Type-safe**: `isinstance(gateway.text, TextLLM)` runtime check catches
   misconfigured backends at startup, not at first call.

Option D was tempting (less code) but rejected because it would couple
SOVEREIGN to a framework's evolution and would not cover all 5
capabilities uniformly.

## Consequences

- Positive: any model satisfying the Protocol can be dropped in. The dev
  sandbox runs everything. Backend misconfiguration fails fast at startup
  via `/readyz`.
- Positive: the Protocol surface is small (5 interfaces) and stable — new
  backends don't change it.
- Negative: adding a new capability (e.g., `SpeechToText`) requires
  extending the Protocol surface and updating all backends. Mitigation:
  only add capabilities when truly needed; use `options: dict` for
  backend-specific extras rather than proliferating Protocol methods.
- Negative: Protocol evolution requires back-compat. Mitigation: prefer
  adding fields with defaults over removing/renaming; version the gateway
  config schema if a breaking change is unavoidable.
- Neutral: real adapters import heavy deps (torch, transformers, vllm).
  These are in optional-dependency groups in `pyproject.toml`, not the
  default install.

## References

- [PEP 544 — Protocols](https://peps.python.org/pep-0544/)
- `sovereign/models/schemas.py` — the 5 Protocols
- `sovereign/models/gateway.py` — the factory
- `configs/models.yaml` — the wiring
- `docs/model-catalog.md` — recommended models per tier
