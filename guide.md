# Run the OCR Form-Fill App with DeepSeek (V4-Flash)

Practical guide to run the OCR form-fill pipeline with **DeepSeek as the LLM provider** — the cheapest verified configuration under the $500/mo ceiling (ADR-0003).

> **Status:** DeepSeek integration is designed (ADR-0006, Proposed) and the adapter is pending `/build`. Appendix A contains the exact copy-paste wiring (4 small files) so this guide is runnable today. Once `/build` lands the adapter, skip Appendix A and go straight to §5.
>
> **Read first:** `docs/adr/0006-deepseek-llm-provider.md` · `docs/architecture/deepseek-integration.md` · `docs/trade-offs/deepseek-integration-trade-offs.md`

---

## 1. What you get

| Layer | DeepSeek model | Role |
|---|---|---|
| Classification / mapping | `deepseek-v4-flash` | default for all chat routes |
| Field extraction (quality route) | `deepseek-v4-flash` (V4-Pro is a later tuning decision, D-8) | works Flash-only from day one |
| Vision OCR (last resort) | `deepseek-v4-flash-vision-exp` | **experimental — off by default** (`DEEPSEEK_VISION_ENABLED=false`); Claude vision stays the stable tier |
| Embeddings (vector search / semantic mapping) | — | DeepSeek has **no embeddings endpoint**; the gateway falls back to OpenAI/Azure automatically (the same mechanism `anthropic` uses — zero work) |

**Development posture:** V4-Flash-only is a valid development configuration from commit one. Dev traffic costs ~$0.0002–0.001/doc — iteration is effectively free under the ceiling.

## 2. Prerequisites

- **Python 3.11** (`>=3.11,<3.12` — project constraint)
- **Tesseract** — `brew install tesseract` (macOS) / `apt install tesseract-ocr` (Debian). If the binary isn't on `PATH`, set `OCR_TESSERACT_CMD` in `.env`
- **DeepSeek API key** — create at [platform.deepseek.com](https://platform.deepseek.com) and top up (pay-as-you-go; there is **no free API tier** — the free tier is a consumer chatbot, not an API)
- Optional: Redis (`redis-server` or Docker) for the L3 cache, Playwright for auto-fill (`playwright install chromium`)

## 3. Install

```bash
cd ocr-rag-pipeline
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Optional extras: `pip install -e ".[aws]"` (Textract/Bedrock — not needed for DeepSeek), `pip install -e ".[doctr]"` (deep-OCR, pulls torch).

## 4. Wire DeepSeek into the gateway (one time — pending /build)

The adapter doesn't exist in the repo yet. Apply **Appendix A** (4 files, ~60 lines total), then continue. If `/build` has already landed it, skip this step.

## 5. Configure `.env`

```bash
cp .env.example .env
```

Set the DeepSeek block (keep everything else as-is):

```dotenv
# LLM provider selection — exactly ONE active at a time (factory)
LLM_PROVIDER=deepseek

# DeepSeek (ADR-0006)
DEEPSEEK_API_KEY=sk-xxxx                # REQUIRED — from platform.deepseek.com
DEEPSEEK_BASE_URL=https://api.deepseek.com   # default; change only if proxied
DEEPSEEK_VISION_ENABLED=false           # experimental vision-exp — OFF by default (TO-7)
DEEPSEEK_PII_POLICY=block-sensitive     # TO-9 default: gate PII-bearing docs off the direct API
```

> **PII note (TO-9):** `DEEPSEEK_PII_POLICY` is part of the ADR-0006 design; its enforcement hook lands with `/build`. Until then, keep sensitive documents off the DeepSeek direct API manually — the API is China-hosted with training-by-default and no DPA. The pipeline's PII scan + human review still run before anything is filled.

Budget caps (already the defaults, ADR-0003): `LLM_DAILY_BUDGET_USD=25` · `LLM_MONTHLY_BUDGET_USD=500` · `LLM_MAX_PER_SESSION_USD=0.15`.

## 6. Run

```bash
uvicorn app.main:app --reload --port 8000
```

Open **http://localhost:8000** — upload a document and walk the review flow.

Optional services (multi-instance cache / persistent vectors):

```bash
redis-server &                                  # or: docker compose up redis
# .env: REDIS_URL=redis://localhost:6379/0
# .env: VECTOR_DB_TYPE=memory        # default; qdrant / pgvector for persistence
```

Or the whole stack via Docker:

```bash
docker compose up --build
```

## 7. Verify DeepSeek is actually serving

1. **Gateway status endpoint:**

   ```bash
   curl -H "X-Admin-Key: $ADMIN_API_KEY" http://localhost:8000/api/v1/admin/gateway/status
   ```

   Expect: `deepseek` → `enabled: true`, models listed (`deepseek-v4-flash`, `deepseek-v4-pro`, `deepseek-v4-flash-vision-exp`), circuit breaker `closed`.

2. **Startup log line:** `Factory instantiated adapter: deepseek` (the factory logs this once per provider).

3. **Health check:** `curl http://localhost:8000/api/v1/health` → 200.

4. **Cost accounting:** after a few docs, telemetry records `deepseek-*` tokens with non-zero cost (if it shows $0 — see Troubleshooting → "provider silently costs $0").

5. **Embeddings still work:** search a processed doc via `GET /api/v1/search?q=...` — the factory falls back to OpenAI/Azure for vectors; DeepSeek serves chat only.

## 8. The two early checks (`[VERIFY]`, ADR-0006)

Run these once, on day one:

1. **Function-calling parity** — the LangGraph agents use tools; DeepSeek must return tool calls. Smoke test with the raw OpenAI-compatible client:

   ```bash
   python - <<'EOF'
   import asyncio
   from openai import AsyncOpenAI
   from app.config import settings

   async def main():
       client = AsyncOpenAI(api_key=settings.DEEPSEEK_API_KEY, base_url=settings.DEEPSEEK_BASE_URL)
       resp = await client.chat.completions.create(
           model="deepseek-v4-flash",
           messages=[{"role": "user", "content": "What is 2+2? Use the calculator tool."}],
           tools=[{"type": "function", "function": {
               "name": "calculator", "description": "Add two numbers",
               "parameters": {"type": "object", "properties": {"a": {"type": "number"}, "b": {"type": "number"}}, "required": ["a", "b"]}}}],
       )
       print(resp.choices[0].message.tool_calls)   # expect a tool_call for calculator
   asyncio.run(main())
   EOF
   ```

   If `tool_calls` is `None`, the LangGraph agents will silently lose tool use — file it before building agent workflows.

2. **Telemetry cost rows exist** — the provider silently costs $0 without them:

   ```bash
   python -c "from app.gateway.telemetry import COST_PER_1K_TOKENS; print(COST_PER_1K_TOKENS['deepseek'])"
   ```

   Expect the three models with non-zero in/out rates (Appendix A step 4).

## 9. Day-to-day flows

| Action | Endpoint |
|---|---|
| Upload a document | `POST /api/v1/sessions` (multipart) |
| Run the pipeline | `POST /api/v1/sessions/{id}/process` |
| Human review | `GET/POST /api/v1/sessions/{id}/review` |
| Semantic search | `GET /api/v1/search?q=...` |
| Cancel / delete (GDPR) | `POST /api/v1/sessions/{id}/cancel` · `DELETE /api/v1/sessions/{id}` |

The pipeline is unchanged by the provider swap: upload → input guards → classify (DeepSeek) → OCR chain → PII scan → extract (DeepSeek) → map (DeepSeek + OpenAI embeddings) → human review → auto-fill → audit → index.

## 10. Tests

```bash
pytest tests/ -v
```

Unit tests cover guardrails, budget, gateway cache, PII scanner, vector backends, validation tools. Add a `tests/test_deepseek_adapter.py` smoke test (invoke → `{content, usage}` shape) once the adapter lands.

## 11. Cost expectations

| | Baseline (Haiku/Sonnet) | With DeepSeek |
|---|---|---|
| LLM spend / mo | ≈ $250 | **≈ $120–130** `[ASSUMPTION]` |
| Total run-rate / mo | ≈ $360–420 | **≈ $250–285** vs $500 ceiling |

- Per document (classification + extraction + mapping): **~$0.002–0.006** at Flash rates — effectively free for development and small-scale use.
- Automatic context caching (stable prompt prefixes ≥1K tokens) cuts input cost ~80–98% further — no config needed.
- Caps are hard-enforced by the budget controller: daily $25, monthly $500, per-session $0.15.

## 12. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `Provider 'deepseek' selected but not configured` warning | `DEEPSEEK_API_KEY` missing/empty in `.env` — the factory's `available` check failed |
| `401 invalid_api_key` | Wrong or expired key; regenerate at platform.deepseek.com |
| `400 ... model not found` | **Legacy names retired 2026-07-24** — `deepseek-chat`/`deepseek-reasoner` no longer resolve. Use `deepseek-v4-flash` / `deepseek-v4-pro` / `deepseek-v4-flash-vision-exp` only |
| Telemetry shows $0 cost for DeepSeek calls | Missing `COST_PER_1K_TOKENS["deepseek"]` rows (Appendix A step 4) |
| `NotImplementedError: embed()` | Expected — DeepSeek has no embeddings; keep `supports_embedding = False` so the factory falls back to OpenAI/Azure |
| Vision call returns `400 "This model does not support image"` | Images only on `deepseek-v4-flash-vision-exp`, in **user** messages only; keep `DEEPSEEK_VISION_ENABLED=false` unless you accept the experimental tier (TO-7) |
| Circuit breaker OPEN (5 failures / 60 s) | Check key, quota balance, and peak-hour contention (single-region API); the breaker auto-recovers after 60 s |
| `docker compose` can't find `.env` values | `.env` is gitignored by design — copy `.env.example → .env` on every fresh checkout |

---

## Appendix A: Minimal DeepSeek wiring (4 files, pending /build)

Contract source: ADR-0006 · `LLMProviderAdapter` (`app/gateway/adapters/base.py:8-24`).

### A.1 — New adapter: `app/gateway/adapters/deepseek_adapter.py`

```python
"""DeepSeek (V4) adapter — OpenAI-compatible endpoint (ADR-0006)."""

import logging

from openai import AsyncOpenAI

from app.config import settings
from app.gateway.adapters.base import LLMProviderAdapter

logger = logging.getLogger(__name__)


class DeepSeekAdapter(LLMProviderAdapter):
    """DeepSeek direct API (api.deepseek.com). OpenAI-compatible wire format."""

    supports_embedding: bool = False  # DeepSeek has no embeddings endpoint (TO-8)

    def __init__(self):
        self.client = (
            AsyncOpenAI(api_key=settings.DEEPSEEK_API_KEY, base_url=settings.DEEPSEEK_BASE_URL)
            if settings.DEEPSEEK_API_KEY
            else None
        )

    @property
    def available(self) -> bool:
        return self.client is not None

    async def invoke(self, model: str, messages: list, max_tokens: int = 1024, temperature: float = 0.0) -> dict:
        if not self.client:
            raise RuntimeError("DeepSeek client not configured (DEEPSEEK_API_KEY)")
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return {
            "content": response.choices[0].message.content or "",
            "usage": {
                "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                "output_tokens": response.usage.completion_tokens if response.usage else 0,
            },
        }

    async def embed(self, text: str, model: str = "", dimensions: int = 1536) -> list[float]:
        raise NotImplementedError(
            "DeepSeek has no embeddings endpoint — the factory falls back to OpenAI/Azure (TO-8)"
        )
```

### A.2 — Config: `app/config.py`

```python
# LLM_PROVIDER literal gains "deepseek" (line ~23):
LLM_PROVIDER: Literal["openai", "anthropic", "azure", "bedrock", "deepseek", "google", "local"] = "openai"

# New block next to the other providers (~line 44):
# ── DeepSeek (per ADR-0006 — adapter pending build) ──
DEEPSEEK_API_KEY: str = ""
DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
DEEPSEEK_VISION_ENABLED: bool = False      # experimental vision-exp off by default (TO-7)
DEEPSEEK_PII_POLICY: Literal["allow", "block-sensitive"] = "block-sensitive"  # TO-9 gate
```

### A.3 — Factory: `app/gateway/adapters/factory.py`

```python
# Import (line ~22):
from app.gateway.adapters.deepseek_adapter import DeepSeekAdapter

# _ADAPTER_CLASSES (line ~27):
_ADAPTER_CLASSES: dict[str, type[LLMProviderAdapter]] = {
    "openai": OpenAIAdapter,
    "anthropic": AnthropicAdapter,
    "azure": AzureOpenAIAdapter,
    "deepseek": DeepSeekAdapter,
    # "bedrock": BedrockAdapter,   # ADR-0002 — pending build (needs boto3)
    ...
}
```

The embedding fallback (`get_embedding_adapter`, factory.py:65-77) skips DeepSeek automatically via `supports_embedding = False` — same as `anthropic`.

### A.4 — Registry + telemetry cost rows

`app/gateway/registry.py` — add to `_configured()` (line ~71) and `self._providers` (line ~79):

```python
# _configured():
"deepseek": bool(settings.DEEPSEEK_API_KEY),

# _providers — new entry (V4 list prices 2026-08; per-1K-token):
"deepseek": {
    "configured": _configured("deepseek"),
    "priority": 3,   # behind direct providers; auto-switcher uses it as the cheap tier
    "models": [
        {"id": "deepseek-v4-flash",             "capabilities": ["classification", "mapping", "extraction"], "cost_input": 0.00014,  "cost_output": 0.00028},
        {"id": "deepseek-v4-pro",               "capabilities": ["extraction", "classification"],             "cost_input": 0.00174,  "cost_output": 0.00348},
        {"id": "deepseek-v4-flash-vision-exp",  "capabilities": ["vision", "classification"],                 "cost_input": 0.00014,  "cost_output": 0.00028},
    ],
},
```

`app/gateway/telemetry.py` — add to `COST_PER_1K_TOKENS` (line ~14):

```python
"deepseek": {
    "deepseek-v4-flash":            {"input": 0.00014, "output": 0.00028},
    "deepseek-v4-pro":              {"input": 0.00174, "output": 0.00348},
    "deepseek-v4-flash-vision-exp": {"input": 0.00014, "output": 0.00028},
},
```

### A.5 — `.env.example`

Add the block from §5 (grouped under a `# ── DeepSeek ──` comment) so fresh checkouts document it.

---

*Contract: ADR-0006 · SDD `docs/architecture/deepseek-integration.md` · TO-6..9 `docs/trade-offs/deepseek-integration-trade-offs.md`*
