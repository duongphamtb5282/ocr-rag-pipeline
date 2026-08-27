# Semantic Document Intelligence Platform

**Upload a document → understand it → answer questions, fill forms, recommend matches — with cost control, guardrails, and observability built in from day one.**

A production-grade LLM solution design that turns unstructured documents (resumes, invoices, product sheets, policies) into **structured profiles**, indexes them into a **semantic vector store**, and serves **grounded Q&A**, **form auto-fill**, and **recommendation-ready matching** — all through a **provider-agnostic multi-LLM gateway**, a **deterministic policy & guardrail layer**, and a **tiered cache** that keeps the bill predictable even as the corpus grows.

---

## Table of Contents

- [Why This Platform](#why-this-platform)
- [Business Content — Resume & Generic Framework](#business-content--resume--generic-framework)
- [System Architecture — Component Diagram](#system-architecture--component-diagram)
- [Ingestion: OCR & Extraction Pipeline](#ingestion-ocr--extraction-pipeline)
- [Indexing: Chunking Strategy, Embeddings & Vector Store](#indexing-chunking-strategy-embeddings--vector-store)
- [Retrieval: Reranking & Self-Reflection](#retrieval-reranking--self-reflection)
- [Semantic Caching — Three Layers](#semantic-caching--three-layers)
- [Scaling for Huge Document Corpora](#scaling-for-huge-document-corpora)
- [Multi-LLM Provider Gateway & Cost Control](#multi-llm-provider-gateway--cost-control)
- [Guardrail & Policy Service](#guardrail--policy-service)
- [Observability](#observability)
- [Setup & Run](#setup--run)
- [API Reference](#api-reference)
- [Recommendation System Roadmap](#recommendation-system-roadmap)

---

## Why This Platform

| Pain point | Platform answer |
|---|---|
| Scanned and messy documents never reach a database cleanly | OCR fallback chain with escalating cost/accuracy — digital PDFs are free and instant, deep OCR only when needed |
| LLM answers drift from the source (hallucination) | Retrieval is reranked, answers are **grounded in a token budget**, and a **faithfulness judge** verifies before the answer ships |
| LLM bills surprise you | Daily / monthly / per-session **hard budgets**, cost-aware routing, write-time dedup, and a 3-layer cache |
| One vendor lock-in | **One active provider at a time** behind a factory — OpenAI, Anthropic, Azure AI, DeepSeek, local models — switch with one environment variable |
| Compliant answers to screening questions | A **separate policy & guardrail service** with its own caching: employer rules are versioned, enforced before *and* after generation |
| Huge document corpora wreck retrieval performance and cost | Structure-aware chunking with a size window, overlap, parent-child pointers, write-time dedup, and a hard context token budget — scale gates with named levers beyond that |

---

## Business Content — Resume & Generic Framework

### Resume: from paper to profile in one pass

The flagship use case is **candidate intelligence**:

```
resume.pdf ──▶ OCR ──▶ structured profile ──▶ embeddings ──▶ vector store
                                                              │
                                        ┌─────────────────────┤
                                        ▼                     ▼
                              Grounded Q&A            Recommendation-ready
                        ("which candidates know   (skills, roles, employers,
                         Python and used it at    tenure, seniority, location
                         a senior level?")        as matchable vectors)
```

What the extraction produces per candidate — **one structured profile**:

- **Candidate info** — name, title, contact, location, links
- **Work history** — role blocks: employer, title, dates, responsibilities
- **Education** — institutions, degrees, specializations
- **Skills & strengths**, **certifications & languages**

Every field carries a **confidence score**, so a human can review before anything is trusted. The same profile is what powers both chat answers and recommendation scoring — one index, two surfaces.

### The generic framework: same pipeline, any document domain

The platform is **schema-driven, not resume-driven**. The extraction schema is the only thing that changes between domains:

| Domain | Input | Structured profile | Serves |
|---|---|---|---|
| Recruiting | Resume / CV | Candidate profile (above) | Candidate Q&A, job-match recommendation |
| E-commerce | Product sheets, catalogs | Product profile (title, attributes, price, specs) | Shopping chat, product recommendation |
| Procurement | Invoices, RFQs, policy documents | Invoice line items, policy rules | Policy Q&A, form auto-fill, compliance |

Swap the schema → the same OCR chain, chunker, embedder, retriever, reranker, and judge keep working. The **recommendation system** is a downstream consumer: it queries the same vector store with a *query profile* (e.g. job description → skill embeddings) and scores candidates by semantic similarity, boosted by employer policy.

---

## System Architecture — Component Diagram

> Two diagrams follow. **Diagram 1** is the main platform; **Diagram 2** shows the guardrail & policy service — designed as its **own deployable with its own caching** so rule enforcement never shares a failure domain with the generation path.

### Diagram 1 — Main platform

```mermaid
flowchart TB
    subgraph Edge["Edge Layer"]
        GW["API Gateway<br/>FastAPI · /api/v1<br/>auth · rate limit · request IDs"]
        AUTH["Tenant Auth<br/>X-Employer-Key"]
    end

    subgraph Orchestration["Orchestration (LangGraph)"]
        CLASS["Classify<br/>doc type + OCR strategy"]
        EXTRACT["Extract<br/>structured profile + confidence"]
        CHAT["Chat Agent<br/>Q&A + multi-turn memory"]
        REVIEW["Human Review<br/>approve / edit"]
    end

    subgraph OCR["OCR & Ingestion"]
        PII["PII Scan<br/>gate before any LLM"]
        CHAIN["OCR Fallback Chain<br/>pdfplumber → tesseract → doctr → llm_vision → Textract*"]
        CHUNK["Chunker v2<br/>structure-aware · window · overlap<br/>parent-child · write-time dedup"]
        EMBED["Embedding Service<br/>bge-m3 (local) / cloud"]
    end

    subgraph Index["Index & Retrieval"]
        VDB[("Vector Store<br/>Qdrant (OSS) · payload filtering")]
        RET["Retriever<br/>top-6 · hard policy filters"]
        RER["Reranker<br/>LLM-as-reranker / cross-encoder"]
        REFL["Self-Reflection<br/>floor-miss → rewrite once → clarify"]
    end

    subgraph Gateway["LLM Gateway (provider-agnostic)"]
        FACT["Provider Factory<br/>ONE active provider"]
        ROUTE["Cost-Aware Router<br/>vision · chat · extract · embed"]
        BUD["Budget Controller<br/>daily · monthly · per-session"]
        CB["Circuit Breakers"]
        TOK["Token Budget<br/>chars/4 estimate — identical across providers"]
    end

    subgraph Cache["Semantic Cache (3-layer)"]
        C1["Embedding cache<br/>content-addressed"]
        C2["Retrieval cache<br/>policy-keyed"]
        C3["Answer cache<br/>policy-versioned"]
    end

    subgraph Data["Data Layer"]
        RULES[("MongoDB · ocr_rules<br/>policies (versioned)")]
        DB[("Postgres / SQLite<br/>sessions · chat memory · audit")]
        REDIS[(Redis)]
    end

    subgraph Providers["LLM Providers"]
        P1["OpenAI"]
        P2["Anthropic"]
        P3["Azure AI"]
        P4["DeepSeek"]
        P5["Local · Ollama (qwen · bge-m3)"]
    end

    subgraph Guardrail["Guardrail & Policy Service (separate — see Diagram 2)"]
        POLAPI["Policy API"]
    end

    subgraph Obs["Observability"]
        M["/metrics · /healthz · /readyz"]
        LOG["request-scoped structured logs"]
    end

    GW --> AUTH --> CLASS
    CLASS --> CHAIN --> PII --> EXTRACT
    EXTRACT --> CHUNK --> EMBED --> VDB
    VDB --> RET --> RER --> CHAT
    RET -. "hard policy filter" .-> POLAPI
    CHAT --> REFL
    CHAT --> TOK --> FACT --> ROUTE
    FACT --> P1 & P2 & P3 & P4 & P5
    ROUTE --> BUD --> CB
    GW --> C1 & C2 & C3
    C3 --> VDB
    CHAT --> REVIEW
    GW --> RULES & DB & REDIS
    CHAT -. "policy refilter + faithfulness judge" .-> POLAPI
    GW --> M & LOG

    classDef data fill:#f5f5f5,stroke:#666,stroke-dasharray:4
    classDef cache fill:#eef7ff,stroke:#4a90d9
    class RULES,DB,REDIS,VDB data
    class C1,C2,C3 cache
```

### Diagram 2 — Guardrail & Policy Service (independent deployable, own caching)

```mermaid
flowchart TB
    subgraph Edge["Callers"]
        PLATFORM["Main platform<br/>(chat · retrieval · ingest)"]
        ADMIN["Admin console / HR teams"]
    end

    subgraph Service["Guardrail & Policy Service"]
        GPI["Policy API<br/>rules CRUD · evaluate · refilter"]
        GCACHE["Policy Cache (Redis)<br/>active version + compiled rules<br/>TTL-bounded, invalidation on publish"]
        ENG["Policy Engine<br/>deterministic rules — verifiable verdicts"]
        SOFT["Soft-rule LLM judge<br/>optional, provider via same gateway"]
        GUARDS["Guardrails<br/>input guard · PII scan · output filter<br/>prefill safety · abuse detector"]
        AUDIT["Immutable Audit Log<br/>who · what · when · version"]
        COST["Cost Ledger<br/>per-tenant spend · budget alerts"]
    end

    subgraph Storage["Policy Storage"]
        RULES[("MongoDB · ocr_rules<br/>policies — immutable versions<br/>hard_filters · soft_boosts · answer_rules")]
    end

    subgraph Obs["Observability"]
        METR["policy metrics<br/>pass rate · refilter rate · cache hit"]
    end

    PLATFORM --> GPI
    ADMIN --> GPI
    GPI --> GCACHE
    GCACHE --> RULES
    GPI --> ENG
    ENG --> SOFT
    ENG --> GUARDS
    GPI --> AUDIT --> COST
    GPI --> METR
    GUARDS --> PLATFORM

    classDef data fill:#f5f5f5,stroke:#666,stroke-dasharray:4
    class RULES data
```

**Why a separate service:** the policy decision is the *compliance guarantee* of the whole platform. It runs before retrieval (hard filters), after generation (output refilter), and inside the guardrails — so it gets its own API, its own versioned rule store, its own cache (active-version + compiled rules), and its own audit trail. If the policy service is down, the platform **fails closed** — no unfiltered answers.

---

## Ingestion: OCR & Extraction Pipeline

1. **Upload** — input guards validate existence, size (20 MB), magic bytes, MIME, and hash every document (abuse tracking + dedup key).
2. **Classify** — the first agent decides the document type and picks the OCR strategy (`auto | tesseract | doctr | llm_vision | pdfplumber`).
3. **OCR fallback chain** — escalating cost/accuracy until one succeeds:

   | Backend | Best for | Cost |
   |---|---|---|
   | `pdfplumber` | Digital PDFs (embedded text) | Free, instant |
   | `tesseract` | Scanned print | Free, local |
   | `doctr` | Layout-aware deep OCR | Free, heavier (torch) |
   | `llm_vision` | Last resort — visual reasoning | Expensive, rare |
   | AWS Textract (planned) | High-accuracy escalation tier | Gated by budget |

   Optional **PaddleX OCR service mode** (Docker profile `ocr`, port 8080) for PP-OCRv5-grade accuracy at scale. Every backend returns the same contract — `{text, layout_blocks, confidence, engine, page_count}` — so the pipeline never cares which engine produced the text.
4. **PII gate** — documents **never reach an LLM** before the PII scanner checks them.
5. **Extract** — the second agent converts OCR text into the domain's structured profile; every field carries a confidence score for the human review step.
6. **Human review** — the web UI shows extracted values + confidence; a human approves or edits before anything is trusted downstream.
7. **Audit & index** — immutable audit log, telemetry, cost accounting, then vector indexing.

---

## Indexing: Chunking Strategy, Embeddings & Vector Store

### The chunking strategy — structure-aware first, token guard second

Token-count chunking is **never** the primary strategy. Boundaries come from the document's semantic units (each role block, each education institution, each skills section — one chunk per claim). On top of that:

- **Size window** — a unit over 400 tokens sub-splits **on sentence boundaries** into ≤ 400-token windows, so no fact straddles a cut.
- **Overlap** — 10% overlap (40 tokens) between windows catches facts that fall across a boundary.
- **Parent-child pointers** — every child carries its parent unit's text in the payload; a short child that would answer a question gets its full parent attached at answer time, so the LLM sees the complete role block, not a fragment.
- **Write-time dedup** — before embedding, the indexer probes `(candidate, text_hash)`; re-uploading the same resume skips **every** chunk embed. Change one line → only the changed text embeds.
- **Versioned payloads** — schema bumps invalidate stale caches and rebuilds are incremental, not full re-embeds.

### Embeddings & the vector store

- **Embeddings** — bge-m3 (1024-dim, multilingual) locally, or the cloud provider's embed model; the gateway falls back automatically when the active chat provider has no embedding endpoint (e.g. Anthropic → OpenAI/Azure).
- **Vector store** — Qdrant OSS by default (persistent volume, `:6333`); pgvector and an in-memory backend are drop-in switches via one environment variable, behind a common interface.
- **Payload filtering** — hard policy rules (employer filters, skills/location/role constraints) are applied as vector-store payload filters *before* semantic search, so candidates excluded by policy never enter the ranking.

---

## Retrieval: Reranking & Self-Reflection

### Two-stage retrieval: recall first, precision second

1. **Retrieve** top-6 candidate chunks with hard policy filters applied in-store.
2. **Rerank** to top-3 — LLM-as-reranker on the cloud tier, cross-encoder locally, or off — with the employer's **soft boosts** (preferred skills, seniority) applied during ranking. Context shrinks by half, precision rises, and the Fortran-style hallucination failure mode is structurally removed: the answer LLM only ever sees what the reranker says is relevant.

### Grounded answers with a hard token budget

The prompt's `Candidate data` section is assembled under **`CHAT_CONTEXT_MAX_TOKENS` (1500 default)** — the assembler walks reranked sources in order, truncates a long chunk to its remaining share, and stops at the cap. Tokens — not chunk count — are the cost unit, and the estimate is a **provider-agnostic heuristic**, so the budget means the same thing on DeepSeek, OpenAI, Azure, or local models. Set `0` for unlimited (legacy parity).

### Self-reflection loop — the system notices its own failures

A poor or ambiguous question is not a dead end. The platform watches two signals:

- **Retrieval floor miss** — semantic score below 0.35 → no data.
- **Faithfulness judge fails** — the judge (same active provider, JSON format) says the draft isn't supported by the retrieved text.

On either signal, if the question has **domain anchors** (skills, locations, roles), the system rewrites the query once (one small LLM call), re-searches, re-answers, re-judges — and returns the rewritten query with the answer. If there are no anchors (pure pronouns), it replies with a **clarification** ("add a skill, a location…"). Bounded: at most one rewrite, inside the request timeout; the local tier clarifies only. Every shipped answer is **judge-verified**; if verification fails after one corrective regeneration, the platform says so instead of guessing.

---

## Semantic Caching — Three Layers

Each layer kills a different measured cost:

| Layer | Key | Kills |
|---|---|---|
| **Embedding cache** | content address (text hash) | re-indexes re-embedding everything — re-upload of the same resume costs ~0 |
| **Retrieval cache** | employer + policy version + query | repeated searches paying full pipeline |
| **Answer cache** | employer + policy version + question | repeated questions paying generation — cache hits cost ~0 and are verified-equivalent by construction |

Cache parity is enforced by test (a cache hit is byte-compatible with a fresh run — including policy checks). Redis is the shared store for multi-instance deployments; an in-memory fallback keeps single-node runs cache-active with zero infrastructure.

---

## Scaling for Huge Document Corpora

Huge corpora attack two budgets at once — **retriever performance** (vector scan grows with N, semantic noise rises) and **tokens** (every chunk is embedded at ingestion; every chat call pays the retrieved text). The platform answers with a **layered, gated, reversible control stack**:

| Layer | Lever | Status |
|---|---|---|
| L1 | **Context token budget** (1500 default) — prompt cost is bounded per call, ~40–75% input-token cut on long documents | Live |
| L2 | **Chunker v2** — short children embed cheaper, retrieve sharper; parent carried only when it adds value | Live |
| L3 | **Write-time dedup** — re-upload / re-index of unchanged text costs ~0 embeddings | Live |
| L4 | **Embedding cache** (content-addressed) — re-index runs near $0 | Live |
| L5 | **Payload index on the dedup hash** — the hot existence probe becomes an indexed lookup | Scale gate 1 |
| L6 | **Quantization + compaction** — smaller vectors, cheaper scan | Scale gate 2 |
| L7 | **Partitioning / sharding** — multi-node Qdrant or sharded pgvector once a single node's budget is crossed | Scale gate 3 |

Each scale gate is armed by **metrics, not guesswork** (retriever p95, recall on the golden set, store size), and each is reversible. Today a single node comfortably holds 10k+ documents with ~7 chunks each (~70k points).

---

## Multi-LLM Provider Gateway & Cost Control

### One active provider, zero code changes

Every LLM call — chat, extraction, classification, reranking, judging, vision, embeddings — goes through the gateway:

- **Provider factory** — exactly **one** provider is active at a time, selected by `LLM_PROVIDER`. Switching is a one-line environment change: `openai` · `anthropic` · `azure` (deployment-name mapped) · `deepseek` · `bedrock` (reserved) · `google` (reserved) · `local` (Ollama — qwen chat + bge-m3 embeddings, the zero-cost AI tier).
- **Automatic failover** — on outage or budget exhaustion the router can switch providers at runtime; still only one is ever served.
- **Embedding fallback** — providers without embeddings (Anthropic, DeepSeek) automatically delegate to a configured embed-capable provider; vector search never breaks.
- **Consistent semantics** — token budgets, chunk windows, dedup hashes and judge prompts are **provider-agnostic by design**: the same settings produce the same behavior on any provider. No provider-specific branch exists in the budget path.

### Cost control as a first-class citizen

| Control | Default | Effect |
|---|---|---|
| `LLM_DAILY_BUDGET_USD` | 25 | daily ceiling — soft downgrade at 80%, hard stop at 100% |
| `LLM_MONTHLY_BUDGET_USD` | 500 | hard monthly ceiling; further LLM spend blocks |
| `LLM_MAX_PER_SESSION_USD` | 0.15 | caps a single runaway session |
| Cost-aware router | — | cheapest capable model per route (vision / extraction / classification / chat) |
| Circuit breakers | — | per-provider failure isolation with auto-recovery |
| 3-layer cache + dedup | on | the biggest lever of all: don't pay for work already done |

Every call records tokens / cost / latency, and cache savings are tracked — you can see what the cache saved you, not just what you spent.

---

## Guardrail & Policy Service

A separate deployable (Diagram 2 above) — **its own API, its own versioned rule store, its own cache, its own audit trail**.

### Policy store — MongoDB, every environment

Rules live in MongoDB (`ocr_rules` database) — the same managed service in dev, staging and production (local container in dev; Atlas / Cosmos in prod). Each policy is an **immutable versioned document**: `hard_filters` (mandatory exclusions), `soft_boosts` (preferences), `answer_rules` (how to phrase answers). Publishing a new version is an audit event and invalidates the policy cache.

### Enforcement — before, during, and after

1. **Before retrieval** — hard filters become vector-store payload filters; excluded candidates never enter ranking.
2. **During generation** — the active policy version is stamped into the answer context, and the answer cache is policy-version-keyed so a policy change can never serve a stale-compliant answer.
3. **After generation** — a deterministic, source-anchored **output refilter** re-evaluates every cited candidate against the rules (~ms, no LLM). This is the compliance guarantee: the answer complies with the *question's* policy, not just the retrieval filters. If the refilter fails, the answer is regenerated once with correction; a second failure returns a policy refusal — never an unverified answer.

### Guardrail modules (same service)

Input guard · PII scanner (before any LLM) · output filter (injection/undesired content) · prefill safety (blocks dangerous auto-fill values) · abuse detector (rate limits) · audit logger (immutable) · data retention (GDPR right-to-deletion).

**Caching:** the active policy version + compiled rule set are cached in Redis with TTL bounds and invalidation-on-publish — rule evaluation is a cache hit in the hot path, and the policy service never re-reads MongoDB per chat request.

---

## Observability

| Surface | What you get |
|---|---|
| **Health & readiness** | `/healthz` (liveness) and `/readyz` (vector store + cache + policy connectivity — the platform fails closed when policy is unreachable) |
| **Metrics** | `/metrics` in Prometheus text format: chat p95 latency, retrieval recall, rerank precision, cache hit rates, policy pass/refilter rates, budget utilization |
| **Structured logs** | every request carries a `request_id`; the full chat trace — search → rerank → assemble → answer → judge — is one correlated line |
| **Cost telemetry** | per-call tokens/cost/latency records per provider, per tenant; cache savings reported |
| **Evaluation harness** | golden-set offline eval (retrieval recall, faithfulness rate, policy compliance) + online monitor — correctness is measured, not assumed |

---

## Setup & Run

### Prerequisites

- **Python 3.11**
- **Tesseract OCR** — `brew install tesseract` (macOS) / `apt install tesseract-ocr` (Debian)
- **Docker** (for the AI stack / policy store — optional for a pure in-memory run)
- One LLM provider key (or none, if using the local Ollama tier)

### 1 — Install

```bash
git clone <repo-url> ocr-rag-pipeline
cd ocr-rag-pipeline

# Virtualenv + package
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Optional extras
pip install -e ".[doctr]"    # DocTR deep-OCR backend (pulls torch)
pip install -e ".[aws]"      # AWS Bedrock / Textract tier (planned)

# Browser for the auto-fill workflow (optional)
playwright install chromium
```

### 2 — Configure

```bash
cp .env.example .env
```

Pick **one** provider (the factory serves exactly one at a time):

```bash
# Cloud: OpenAI, Anthropic, Azure AI, or DeepSeek
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-...            # your key, never committed

# Local AI tier (zero API cost): Ollama + Qdrant via the local compose
LLM_PROVIDER=local                 # or keep cloud and set EMBEDDING_SOURCE=auto
VECTOR_DB_TYPE=qdrant
VECTOR_DB_URL=http://localhost:6333
POLICY_STORE_TYPE=mongodb          # MongoDB policy store — all environments
MONGO_URL=mongodb://admin:password123@localhost:27017/ocr_rules?authSource=admin
```

Budgets, cache, chunking, and the context token budget are all env-visible: `LLM_DAILY_BUDGET_USD`, `LLM_MONTHLY_BUDGET_USD`, `CHAT_CONTEXT_MAX_TOKENS`, `CHUNK_MAX_TOKENS`, `CHUNK_OVERLAP_TOKENS`, `REDIS_URL`, … — every variable is documented in `.env.example`.

### 3 — Start the data & AI stack

```bash
# Full platform stack: app + Redis + Qdrant + MongoDB policy store
docker compose up -d --build
# Redis + Qdrant are behind profiles; to include them:
docker compose --profile with-redis --profile with-vectordb up -d

# Local AI tier (Qdrant + Ollama with qwen3:4b and bge-m3 warm-up)
docker compose -f docker-compose.local.yml up -d
# + PaddleX OCR serving, if you want it:
docker compose -f docker-compose.local.yml --profile ocr up -d
```

### 4 — Run the app

```bash
uvicorn app.main:app --reload --port 8000
```

Open **http://localhost:8000** — upload a resume, watch it classify → OCR → extract → index, then chat with it.

### 5 — Smoke test

```bash
curl -s http://localhost:8000/api/v1/health

# Upload a resume
curl -s -X POST http://localhost:8000/api/v1/sessions \
  -H "Content-Type: multipart/form-data" \
  -F "file=@samples/resume.pdf"

# Ask a grounded question (with an employer policy key if configured)
curl -s -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-Employer-Key: <tenant-key>" \
  -d '{"session_id":"<session>","message":"Which candidates know Python?"}'
```

Verify in the app log:

- `Grounded context: N est. tokens (budget 1500, 3 sources)` — the token budget is active
- `dedup skipped 5/5 chunks` — re-uploading the same resume costs zero embeddings
- `policy_refilter: PASS` — every answer complied with the employer policy

### 6 — Tests

```bash
.venv/bin/python -m pytest -q        # 286 tests — hermetic: never touches live services
```

---

## API Reference

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/v1/health` | Health check |
| `POST` | `/api/v1/sessions` | Upload a document (multipart) |
| `GET` | `/api/v1/sessions` | List sessions |
| `GET` | `/api/v1/sessions/{id}` | Session details |
| `GET` | `/api/v1/sessions/{id}/review` | Human review data |
| `POST` | `/api/v1/sessions/{id}/review` | Submit review |
| `POST` | `/api/v1/sessions/{id}/process` | Run the pipeline |
| `POST` | `/api/v1/sessions/{id}/cancel` | Cancel a session |
| `DELETE` | `/api/v1/sessions/{id}` | Delete (GDPR) |
| `POST` | `/api/v1/chat` | Grounded candidate Q&A |
| `GET` | `/api/v1/search` | Semantic search across documents |
| `GET` | `/api/v1/policies` | Policy service — list versions |
| `POST` | `/api/v1/policies` | Publish a policy version (audited) |
| `GET` | `/api/v1/healthz` / `/api/v1/readyz` | Liveness / readiness |
| `GET` | `/api/v1/metrics` | Prometheus metrics |

---

## Recommendation System Roadmap

The framework is built to feed a recommendation engine, not just answer questions:

1. **Profile vectors today** — every candidate profile is already a set of typed, policy-filtered, reranked vectors in the store.
2. **Query profiles next** — a job description (or a product brief) is parsed by the *same* pipeline into a query profile, then matched by cosine similarity with skill/role/seniority boosts from the policy service.
3. **Feedback loop** — human review accept/reject signals and chat follow-ups become labeled training data for tuned embeddings or a dedicated ranker.
4. **Hybrid retrieval** — sparse + dense fusion at the scale gates for long-tail skill names and acronyms.

Nothing about the ingestion, indexing, or guardrail layers changes for any of this — the recommendation system is another consumer of the same semantic backbone.

---

*Built with FastAPI · LangGraph · Qdrant · MongoDB · Redis · Ollama · Playwright. Provider-agnostic, cost-aware, guardrailed by design.*
