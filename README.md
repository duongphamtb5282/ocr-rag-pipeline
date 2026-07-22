# OCR Form Fill System

Upload documents -> OCR -> extract fields -> map to web forms -> human review -> auto-fill.

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for C4 diagrams, sequence diagrams, and component details.

## Quick Start

```bash
cd ocr

# Install dependencies
pip install -e ".[dev]"

# Install Playwright browsers
playwright install chromium

# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys

# Run
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000 in your browser.

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/v1/sessions` | Upload document (multipart) |
| `GET` | `/api/v1/sessions` | List all sessions |
| `GET` | `/api/v1/sessions/{id}` | Get session details |
| `GET` | `/api/v1/sessions/{id}/review` | Get review data |
| `POST` | `/api/v1/sessions/{id}/review` | Submit review |
| `POST` | `/api/v1/sessions/{id}/process` | Run LangGraph pipeline |
| `POST` | `/api/v1/sessions/{id}/cancel` | Cancel session |
| `DELETE` | `/api/v1/sessions/{id}` | Delete session (GDPR) |
| `GET` | `/api/v1/search` | Semantic search across documents |
| `GET` | `/api/v1/admin/gateway/status` | Gateway admin status |

## Running Tests

```bash
pytest tests/ -v
```

## Docker

```bash
docker compose up --build
```

## Project Structure

```
ocr/
├── app/             FastAPI entry point & config (canonical)
├── api/             REST API v1 (re-exports from app/api/v1/)
├── agents/          LangGraph agent nodes (canonical)
├── components/      Reusable retrieval & ranking
├── services/        Business logic & pipelines
├── tools/           Pluggable tool definitions
├── prompts/         Versioned prompt templates + registry
├── security/        Guardrails & compliance (replaces app/safeguards/)
├── gateway/         LLM gateway (cost-aware routing)
├── graph/           LangGraph orchestration
├── web/             Web UI (re-exports from app/web/)
├── models/          Database models
├── db/              Database setup & migrations
├── evaluation/      Golden dataset, offline eval, online monitor
├── observability/   Tracing, feedback, cost tracking
├── data/            Raw/processed/storage/index_config
├── scripts/         Seed, migrate, healthcheck
├── tests/           Unit, integration, retrieval, cache, routing
└── docs/            Architecture, API reference, deployment
```

> See `docs/AI-production-structure.md` for the target architecture this follows.

## Key Features

- **Multi-backend OCR**: pdfplumber (digital), Tesseract (print), DocTR (layout), LLM Vision (hard cases)
- **LLM Gateway**: Cost-aware routing, provider switching (OpenAI/Anthropic/Google/Local), circuit breakers
- **Budget Control**: Daily/session/route hard limits with auto-downgrade
- **Vector DB**: Semantic search, template matching, duplicate detection
- **Safeguards**: Input validation, PII detection, injection protection, audit logging
- **Human Review**: Web UI with editable fields, confidence indicators, approve/reject
- **GDPR Compliance**: Data retention policies, right-to-deletion, immutable audit trail
