# OCR + Automated Web Form Filling System — Design Document

**Date:** 2026-07-21
**Status:** Draft
**Version:** 1.0

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Architecture & Agent Topology](#2-system-architecture--agent-topology)
3. [LangGraph State Machine](#3-langgraph-state-machine)
4. [Agent Design](#4-agent-design)
5. [OCR Tool Layer](#5-ocr-tool-layer)
6. [Browser Automation Strategy](#6-browser-automation-strategy)
7. [Human Review Web UI](#7-human-review-web-ui)
8. [API Contract](#8-api-contract)
9. [Project Structure](#9-project-structure)
10. [Tech Stack](#10-tech-stack)
11. [Error Handling & Edge Cases](#11-error-handling--edge-cases)
12. [Development Roadmap](#12-development-roadmap)
13. [Cross-Cutting Evaluation](#cross-cutting-evaluation)

---

## 1. Executive Summary

A standalone OCR + automated form-filling system that:
- Accepts uploaded documents (PDFs, scanned images, photos)
- Uses a multi-tier OCR pipeline (Tesseract → DocTR → LLM Vision) to extract text
- Deploys LangChain agents orchestrated by LangGraph to analyze, extract, and map fields
- Provides a human review UI with edit/approve before submission
- Automatically fills target web forms using Playwright
- Handles both known enterprise apps (pre-configured schemas) and generic unknown websites (dynamic analysis)

The system is built as a standalone FastAPI service but shares the LangChain/LangGraph stack already present in the larger Sadar Navigator project.

---

## 2. System Architecture & Agent Topology

### High-Level Flow

```
                    ┌─────────────────────────────┐
                    │   Input: Document Upload +   │
                    │   Target URL (optional)      │
                    └──────────┬──────────────────┘
                               │
                    ┌──────────▼──────────────────┐
                    │  Agent 1: Document Analyzer  │
                    │  - Classifies doc type       │
                    │  - Assesses quality          │
                    │  - Picks OCR strategy        │
                    └──────────┬──────────────────┘
                               │
                    ┌──────────▼──────────────────┐
                    │  OCR Tool Layer              │
                    │  (Tool, not agent):          │
                    │  • Tesseract for text docs   │
                    │  • DocTR for layout docs     │
                    │  • LLM Vision for complex    │
                    └──────────┬──────────────────┘
                               │
                    ┌──────────▼──────────────────┐
                    │  Agent 2: Field Extractor    │
                    │  - LLM extracts fields       │
                    │  - Validates against schema  │
                    │  - Flags low confidence      │
                    └──────────┬──────────────────┘
                               │
                    ┌──────────▼──────────────────┐
                    │  Agent 3: Form Analyzer      │
                    │  - Fetches target page       │
                    │  - Identifies form fields    │
                    │  - Infers field semantics    │
                    └──────────┬──────────────────┘
                               │
                    ┌──────────▼──────────────────┐
                    │  Agent 4: Field Mapper       │
                    │  - Maps extracted → form     │
                    │  - Semantic matching (LLM)   │
                    │  - Confidence scoring        │
                    └──────────┬──────────────────┘
                               │
                    ┌──────────▼──────────────────┐
                    │  ★ HUMAN REVIEW NODE ★      │
                    │  Web UI: review, correct,   │
                    │  approve/reject mappings     │
                    └──────────┬──────────────────┘
                               │
                    ┌──────────▼──────────────────┐
                    │  Agent 5: Form Filler        │
                    │  - Playwright automation     │
                    │  - Fills mapped fields       │
                    │  - Reports success/failure   │
                    └──────────┬──────────────────┘
                               │
                    ┌──────────▼──────────────────┐
                    │      Completion Receipt      │
                    └─────────────────────────────┘
```

### Design Principles

1. **Agents as graph nodes, not orchestrators** — Each agent is a LangChain Runnable. The LangGraph edges control flow, not the agents themselves.
2. **Tools, not agents for infrastructure** — OCR backends, Playwright, and validators are tools agents invoke, not agents themselves.
3. **Human-in-the-loop interrupt** — The graph pauses at the review checkpoint. Execution only resumes after human approval.
4. **Fallback escalation** — Each stage can escalate to a higher-capability backend (e.g., Tesseract → LLM Vision) on low confidence.

---

## 3. LangGraph State Machine

### State Schema

```python
from typing import TypedDict, Optional

class OCRFormFillState(TypedDict):
    # ── Input ──
    session_id: str                    # UUID for this session
    document_path: str                 # Uploaded file path on disk
    target_url: Optional[str]          # Web form URL (optional at upload time)

    # ── Stage 1: Document Analysis ──
    doc_type: Optional[str]            # "scanned_form" | "invoice" | "letter" | "id_card" | "digital_pdf" | "table" | "other"
    doc_quality: Optional[str]         # "high" | "medium" | "low"
    ocr_strategy: Optional[str]        # "tesseract" | "doctr" | "llm_vision" | "none"

    # ── Stage 2: OCR Output ──
    raw_text: Optional[str]            # Full OCR text output
    layout_blocks: Optional[list]      # Bounding boxes with content for structured docs
    markdown_output: Optional[str]     # Markdown-formatted document with layout preserved

    # ── Stage 3: Extraction ──
    extracted_fields: Optional[dict]   # { "field_name": { "value": str, "confidence": float, "source_region": str } }
    low_confidence_fields: list        # Field keys needing human attention (confidence < 0.8)

    # ── Stage 4: Form Analysis ──
    form_fields: Optional[list]        # [ { "field_id": str, "selector": str, "label": str, "type": str, "required": bool, "accepted_values": list } ]

    # ── Stage 5: Mapping ──
    field_mappings: Optional[dict]     # { "extracted_field_key": { "form_field_id": str, "confidence": float, "reasoning": str } }
    unmapped_fields: list              # Extracted fields with no good form match

    # ── Stage 6: Human Review ──
    review_status: Optional[str]       # "pending" | "approved" | "rejected" | "corrected"
    human_corrections: Optional[dict]  # User overrides { "field_key": "corrected_value" }
    human_mappings: Optional[dict]     # User-provided mappings for unmapped fields

    # ── Stage 7: Filling ──
    fill_status: Optional[str]         # "success" | "partial" | "failed" | "captcha_blocked"
    fill_errors: Optional[list]        # Per-field error details
    submission_proof: Optional[str]    # Screenshot path after fill
    filled_fields_count: int           # Number of successfully filled fields
    total_fields_count: int            # Total form fields targeted

    # ── Metadata ──
    error: Optional[str]               # Terminal error message if failed
    created_at: str                    # ISO timestamp
    completed_at: Optional[str]        # ISO timestamp
```

### Graph Structure

```python
from langgraph.graph import StateGraph

builder = StateGraph(OCRFormFillState)

# Nodes
builder.add_node("analyze_document", document_analyzer_node)
builder.add_node("run_ocr", ocr_node)
builder.add_node("extract_fields", field_extractor_node)
builder.add_node("analyze_form", form_analyzer_node)
builder.add_node("map_fields", field_mapper_node)
builder.add_node("human_review", human_review_node)
builder.add_node("fill_form", form_filler_node)
builder.add_node("complete", completion_node)

# Edges
builder.set_entry_point("analyze_document")
builder.add_edge("analyze_document", "run_ocr")
builder.add_edge("run_ocr", "extract_fields")
builder.add_conditional_edges(
    "extract_fields",
    router_has_target_url,
    {True: "analyze_form", False: "map_fields"}
)
builder.add_edge("analyze_form", "map_fields")
builder.add_edge("map_fields", "human_review")
builder.add_conditional_edges(
    "human_review",
    router_review_approved,
    {True: "fill_form", False: "map_fields"}   # Rejected → re-map with corrections
)

# Human-in-the-loop interrupt
builder.add_interrupt_node("human_review", wait_for_input=True)

builder.set_conditional_entry_point("fill_form", lambda s: s.fill_status == "success", "complete")
builder.add_edge("fill_form", "complete")
builder.set_finish_point("complete")
```

### Human-in-the-Loop Mechanism

The graph pauses at `human_review`. The LangGraph `interrupt` mechanism suspends execution and serializes state. When the user submits corrections via the API (`POST /api/v1/sessions/{id}/review`), the state is updated and the graph resumes from the interrupt point.

```python
# Resuming after human review
thread.update_state(
    {
        "review_status": "approved",
        "human_corrections": {...},
        "human_mappings": {...},
    }
)
thread.resume()  # Continues to fill_form
```

---

## 4. Agent Design

### Agent 1 — Document Analyzer

**Role:** Classify the uploaded document and select the optimal OCR strategy.

**System Prompt (shortened):**
```
You are a Document Analyzer for the OCR Form Fill system. Given an uploaded file:

1. Read file metadata (extension, size, page count)
2. Generate a thumbnail preview
3. Classify the document into one of: 
   - digital_pdf: text-based PDF, text is selectable
   - scanned_form: structured form with labeled fields
   - invoice: typical invoice layout with line items
   - id_card: government ID, driver's license, passport
   - letter: free-form correspondence
   - table: primarily tabular data
   - other: none of the above
4. Assess quality: high / medium / low (based on estimated DPI, skew, noise, handwritten content)
5. Recommend OCR strategy:
   - "none" for digital_pdf (use pdfplumber)
   - "tesseract" for high-quality printed text
   - "doctr" for complex layouts, tables, multi-column
   - "llm_vision" for low quality, handwritten, or ambiguous docs

Output your analysis as a structured JSON object.
```

**Tools:**
- `get_file_metadata(path) → dict` — extension, size, page count, DPI estimate
- `generate_thumbnail(path) → base64` — first page preview for quality assessment

**Outputs to state:** `doc_type`, `doc_quality`, `ocr_strategy`

---

### Agent 2 — Field Extractor

**Role:** Extract structured data fields from OCR output using LLM understanding.

**System Prompt (shortened):**
```
You are a Field Extractor. Given OCR output (raw text + layout blocks), you must:

1. Identify all data fields in the document (names, dates, amounts, IDs, addresses, phone numbers, etc.)
2. Extract values with confidence scores (0.0 - 1.0)
3. Normalize values:
   - Dates → ISO 8601 (YYYY-MM-DD)
   - Currency → decimal float
   - Phone → E.164 format
   - SSN/Tax IDs → canonical format
4. For structured forms with labels, associate label-value pairs
5. For unstructured documents, extract all named entities
6. Flag any field where confidence < 0.8 for human review

Return a JSON object with all extracted fields and their metadata.
```

**Tools:**
- `call_llm_vision(image_region) → str` — Read a specific document region with multimodal LLM
- `validate_date(value) → dict` — Parse and verify date format
- `validate_phone(value) → dict` — Parse and verify phone number
- `validate_email(value) → dict` — Validate email address
- `normalize_currency(value) → dict` — Convert currency strings to float

**Outputs to state:** `extracted_fields`, `low_confidence_fields`

---

### Agent 3 — Form Analyzer

**Role:** Visit the target URL and reverse-engineer its form structure.

**System Prompt (shortened):**
```
You are a Form Analyzer. Given a target URL:

1. Navigate to the page using Playwright
2. Identify all <form> elements on the page
3. For each form field, extract:
   - CSS selector (unique, stable)
   - Input type (text, email, select, checkbox, radio, date, tel, etc.)
   - Label text (from <label>, aria-label, placeholder, or surrounding text)
   - Whether the field is required
   - Any pattern, min/max, or validation attributes
   - Acceptable values (for select/radio fields)
4. Infer semantic meaning from label text, name attribute, and context
5. Group related fields (e.g., address lines, name parts)
6. Detect multi-page forms and pagination controls

Output a structured form field inventory.
```

**Tools:**
- `browser_navigate(url) → str` — Navigate Playwright to the URL
- `browser_extract_form_fields() → list` — Extract all form field details from current page
- `browser_screenshot() → str` — Take a screenshot of the form (for the review UI)
- `browser_get_inner_text(selector) → str` — Get inner text for context analysis

**Caching:** For known enterprise apps (domain maintained in a database), load pre-cached form schema instead of live analysis.

**Outputs to state:** `form_fields`

---

### Agent 4 — Field Mapper

**Role:** The critical bridge — map extracted document fields to web form fields.

**System Prompt (shortened):**
```
You are a Field Mapper. Given:
- Extracted fields from the document
- Form fields from the target web page

For each extracted field, find the best matching form field. Use this strategy:

1. **Exact label match** — When the extracted field label exactly matches a form field label
2. **Semantic match** — Use LLM understanding to match semantically equivalent labels:
   - "Full Name" ↔ "customer_name"
   - "Date of Birth" ↔ "birthDate"
   - "SSN" ↔ "tax_id"
3. **Value pattern match** — When label match is weak, match by expected format:
   - A phone-number-shaped value → form field of type "tel"
   - A date-shaped value → form field of type "date" or "text" with date label
4. **Group/context match** — Use surrounding field groups for disambiguation:
   - Address line 1 + City + ZIP → form address group

Score every mapping 0.0 - 1.0.
- Confidence ≥ 0.9: auto-accept
- Confidence 0.6 - 0.89: flag for human review
- Confidence < 0.6: mark as unmapped (human must resolve)

Output all mappings and any unmapped fields.
```

**Tools:**
- `semantic_similarity(text_a, text_b) → float` — Embedding-based similarity score
- `formats_match(extracted_value, form_field_type) → dict` — Check format compatibility

**Outputs to state:** `field_mappings`, `unmapped_fields`

---

### Agent 5 — Form Filler

**Role:** Execute the approved field mappings against the live web form using Playwright.

**System Prompt (shortened):**
```
You are a Form Filler. Given approved field mappings:

1. Navigate to the target URL
2. For each mapping, locate the form field by its CSS selector
3. Fill the field with the approved value:
   - text/email/number → page.fill()
   - select → page.select_option()
   - checkbox → page.check() or page.uncheck()
   - radio → page.check() matching value
   - date → page.fill() with formatted date
4. Handle multi-page forms by detecting "Next" buttons and continuing
5. If a field fails, record the error but continue filling others
6. After all fields filled, take a proof screenshot
7. If CAPTCHA or bot detection is encountered, STOP and mark as blocked

Do NOT submit the form unless explicitly configured to do so.
Default behavior: fill only, allow final human review before submission.
```

**Tools:**
- `browser_navigate(url) → str`
- `browser_fill_field(selector, value) → dict` — Fill a single field
- `browser_select_option(selector, value) → dict` — Select dropdown option
- `browser_check_element(selector) → dict` — Check/uncheck a checkbox
- `browser_click_next() → dict` — Navigate to next page in multi-page form
- `browser_screenshot() → str`
- `detect_captcha() → bool` — Check for CAPTCHA presence

**Outputs to state:** `fill_status`, `fill_errors`, `submission_proof`, `filled_fields_count`, `total_fields_count`

---

## 5. OCR Tool Layer

The OCR layer is a tool set that agents invoke. Three backends orchestrated by the Document Analyzer's strategy recommendation.

### Backend Selection Strategy

| Doc Type | Quality | Backend | Notes |
|----------|---------|---------|-------|
| Digital PDF (text-based) | High | **pdfplumber** | Direct text extraction — fastest path, no OCR needed |
| Scanned image | High | **Tesseract 5** + LSTM | Fast, accurate for clean printed text. Page segmentation mode based on layout |
| Complex layout | High | **DocTR** | Deep learning-based layout analysis. Preserves table structure, columns, reading order |
| Scanned form | Medium | **Tesseract** | Legacy typewriter fonts, pre-printed form fields |
| Low quality / noisy | Low | **LLM Vision** | Reads directly from image. Handles low DPI, stains, faded text |
| Handwritten | Low | **LLM Vision** | GPT-4o or Claude Vision for cursive handwriting recognition |
| Mixed / uncertain | Any | **DocTR → LLM Vision** | DocTR does initial layout, LLM reads ambiguous regions on fallback |

### Preprocessing Pipeline

```
Upload (.pdf / .png / .jpg / .tiff / .bmp)
    │
    ▼
  [Preprocessing]
    ├── detect_file_type()        → PDF → convert pages to images if scanned
    ├── deskew()                  → Straighten crooked scans (< 5° rotation)
    ├── denoise()                 → Remove speckle, salt-and-pepper noise
    ├── enhance_contrast()        → Adaptive thresholding (CLAHE)
    ├── detect_dpi()              → Reject if < 150 DPI; upscale if between 150-200
    └── split_pages()             → Multi-page → individual page images
    │
    ▼
  [OCR Engine Selection]
    │
    ├── pdfplumber ────────────► Direct text extraction (digital PDFs only)
    ├── Tesseract ─────────────► Page → hOCR (HTML OCR) output with bounding boxes
    ├── DocTR ─────────────────► Page → structured JSON (blocks, lines, words, confidence)
    └── LLM Vision ────────────► Page → LLM reads image, returns Markdown-formatted text
    │
    ▼
  [Postprocessing]
    ├── spelling_correction()    → LLM-correct common OCR artifacts
    ├── reconstruct_layout()     → Map text back to document structure (paragraphs, tables, fields)
    ├── tag_coordinates()        → Attach bounding boxes to each extracted element
    └── format_for_agent()       → Bundle text + layout into the agent-friendly state format
```

### Cost-Efficiency Design

LLM Vision is NOT the default OCR — it's the **escalation path**. The design keeps costs low:

| Volume Tier | Primary OCR | LLM Vision Usage | Est. Cost/Page |
|-------------|-------------|-------------------|----------------|
| ~80% of docs | Tesseract / pdfplumber | Never | ~$0.001 |
| ~15% of docs | DocTR | Never | ~$0.005 |
| ~5% of docs | Tesseract/DocTR → low confidence | LLM Vision fallback on specific blocks | ~$0.01-0.03 |
| <1% of docs | Skip all — direct LLM Vision | Full document | ~$0.05-0.10 |

---

## 6. Browser Automation Strategy

### Tool: Playwright (async)

Playwright is chosen over Selenium for:
- Native async support (fits FastAPI event loop)
- Auto-waiting mechanisms (waits for element visibility by default)
- Faster execution (lighter protocol)
- Built-in network interception
- Screenshot and video recording

### Automation Flow

```python
class FormFillerAgent:
    """Fills web forms using Playwright, driven by approved field mappings."""

    async def fill_form(self, state: OCRFormFillState) -> dict:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"]
            )
            context = await browser.new_context(
                viewport={"width": 1280, "height": 1024},
                user_agent="Mozilla/5.0 ..."  # Realistic UA to avoid detection
            )
            page = await context.new_page()
            await page.goto(state["target_url"], wait_until="networkidle")

            filled = 0
            total = len(state.get("approved_mappings", {}))
            errors = []

            for field_key, mapping in state.get("approved_mappings", {}).items():
                selector = mapping["form_field"]["selector"]
                value = state.get("human_corrections", {}).get(field_key, mapping["value"])
                field_type = mapping["form_field"]["type"]

                try:
                    if field_type in ("select", "dropdown"):
                        await page.select_option(selector, value)
                    elif field_type in ("checkbox",):
                        if value.lower() in ("yes", "true", "1", "x"):
                            await page.check(selector)
                        else:
                            await page.uncheck(selector)
                    elif field_type in ("radio",):
                        await page.check(f"{selector}[value='{value}']")
                    else:
                        await page.fill(selector, str(value))
                    filled += 1
                except Exception as e:
                    errors.append({"field": field_key, "selector": selector, "error": str(e)})

            # Detect CAPTCHA
            captcha_detected = await self._detect_captcha(page)
            if captcha_detected:
                return {"fill_status": "captcha_blocked", "fill_errors": ["CAPTCHA detected"]}

            # Proof screenshot
            screenshot_path = f"proof_{state['session_id']}.png"
            await page.screenshot(path=screenshot_path, full_page=True)

            await browser.close()

            return {
                "fill_status": "success" if filled == total else "partial",
                "fill_errors": errors if errors else None,
                "submission_proof": screenshot_path,
                "filled_fields_count": filled,
                "total_fields_count": total,
            }

    async def _detect_captcha(self, page) -> bool:
        """Check for common CAPTCHA indicators."""
        captcha_indicators = [
            'iframe[src*="recaptcha"]',
            'iframe[src*="hcaptcha"]',
            'div[class*="captcha"]',
            '#captcha',
            '[aria-label*="captcha"]',
        ]
        for selector in captcha_indicators:
            if await page.query_selector(selector):
                return True
        return False
```

### Multi-Page Form Handling

The `form_analyzer_agent` detects pagination (multiple form steps). Each form page's fields are stored as a group. The filler navigates through each page sequentially, filling visible fields before clicking "Next" / "Continue".

### Anti-Detection Measures

- Realistic viewport and user agent
- Human-like typing speed (configurable delay between keystrokes)
- Random mouse movements before interactions (configurable)
- Respect `robots.txt` (advisory — not enforced in automation but logged)
- Session isolation — each fill uses a fresh browser context

---

## 7. Human Review Web UI

### Architecture

The Web UI is served by FastAPI Jinja2 templates with Alpine.js for interactivity. No heavy SPA framework. The UI talks to the Review API endpoints.

### Screen Layout

```
┌──────────────────────────────────────────────────────────────┐
│  OCR Form Fill — Review & Approve          Session #abc123   │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────────┐  ┌─────────────────────────┐  │
│  │   Document Preview       │  │   Extracted Fields      │  │
│  │                          │  │                         │  │
│  │   ┌──────────────────┐   │  │   Field       Value  ⚡ │  │
│  │   │                  │   │  │   ───────────────────── │  │
│  │   │   [PDF Viewer /  │   │  │   Full Name   John D.. ✓│  │
│  │   │    Image Display]│   │  │   DOB         1990-05.. ✎│  │
│  │   │                  │   │  │   SSN         123-45.. ⚠│  │
│  │   │                  │   │  │   Address     123 Ma.. ✓│  │
│  │   └──────────────────┘   │  │                         │  │
│  │                          │  │   Icon legend:          │  │
│  │   ◄ Page 1 of 3 ►       │  │   ✓ high conf  ✎ edited │  │
│  │                          │  │   ⚠ low conf            │  │
│  └──────────────────────────┘  └─────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────────┐│
│  │   Form Mapping Preview                                   ││
│  │                                                          ││
│  │   Extracted Field  →  Web Form Field         Confidence  ││
│  │   ─────────────────────────────────────────────────────  ││
│  │   Full Name        →  #customer_name           0.97     ││
│  │   DOB              →  #date_of_birth           0.89     ││
│  │   SSN              →  [unmapped]                —  ⚠   ││
│  │   Address          →  #street_address          0.94     ││
│  │                                                          ││
│  │   Click ⚠ to manually map or correct                    ││
│  └──────────────────────────────────────────────────────────┘│
│                                                              │
│          ┌────────────┐     ┌──────────────────────────┐    │
│          │  Reject    │     │  Approve & Fill Form     │    │
│          └────────────┘     └──────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

### UI Functionality

| Element | Behavior |
|---------|----------|
| Document preview | PDF.js for PDFs, raw image for scans. Page navigation for multi-page docs |
| Extracted fields table | Editable inline. Low-confidence fields highlighted. User can type corrections |
| Form mapping preview | Shows each extracted field → which form field it maps to. Unmapped fields shown with resolution UI |
| Confidence indicators | Color-coded: green (≥ 0.9), yellow (0.6 - 0.89), red (< 0.6) |
| Manual mapping | Click unmapped field → dropdown of all form fields to choose from |
| Approve & Fill | Posts corrections and approved mappings, resumes the LangGraph |
| Reject | Marks session as rejected, archives with user's rejection reason |

### Realtime Progress via SSE

While the graph is running (before the interrupt), the UI subscribes to an SSE endpoint:

```
GET /api/v1/sessions/{id}/events
→ data: {"node": "analyze_document", "status": "running"}
→ data: {"node": "analyze_document", "status": "complete"}
→ data: {"node": "run_ocr", "status": "running", "progress": "Page 3/5"}
→ data: {"node": "human_review", "status": "waiting"}
```

The UI shows a progress stepper during graph execution:

```
  ● Analyze Doc  ✓  ●  Run OCR  ✓  ●  Extract Fields  ✓  ●  Review →
```

---

## 8. API Contract

### Endpoints

| Method | Endpoint | Request | Response | Purpose |
|--------|----------|---------|----------|---------|
| `POST` | `/api/v1/sessions` | `multipart/form-data`: `file` + optional `target_url` | `201 { session_id, status }` | Upload document and optionally specify target URL |
| `GET` | `/api/v1/sessions` | — | `200 [{ session_id, status, created_at }]` | List all sessions |
| `GET` | `/api/v1/sessions/{id}` | — | `200 { session_id, status, doc_type, time_elapsed }` | Get session detail and current graph status |
| `GET` | `/api/v1/sessions/{id}/review` | — | `200 { extracted_fields, form_fields, field_mappings, unmapped_fields }` | Get data pending human review |
| `POST` | `/api/v1/sessions/{id}/review` | `{ corrections, mappings, action: "approve" | "reject" }` | `200 { status, next_step }` | Submit review decisions and resume/terminate graph |
| `POST` | `/api/v1/sessions/{id}/resume` | — | `200 { status }` | Resume graph execution (after interrupt) |
| `GET` | `/api/v1/sessions/{id}/receipt` | — | `200 { fill_status, screenshot_url, filled_count, total_count, errors }` | Get completion proof |
| `POST` | `/api/v1/sessions/{id}/cancel` | — | `200 { status: "cancelled" }` | Cancel a running session |
| `GET` | `/api/v1/sessions/{id}/events` | SSE | Stream of graph node status updates | Real-time progress |
| `GET` | `/health` | — | `200 { status, ocr_backends, browser_available, db_connected }` | Service health |

### Session Status Lifecycle

```
uploaded → analyzing → ocr_running → extracting → analyzing_form →
mapping → awaiting_review → filling → completed
                                                                   
                        cancel → cancelled                           
                        reject → rejected                           
                        error → failed                              
```

---

## 9. Project Structure

```
ocr/
├── app/
│   ├── __init__.py
│   ├── main.py                       # FastAPI app entry point
│   ├── config.py                     # Environment-based settings
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── sessions.py           # Session CRUD endpoints
│   │       ├── review.py             # Human review endpoints
│   │       ├── health.py             # Health check
│   │       └── schemas.py            # Pydantic request/response schemas
│   │
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── state.py                  # OCRFormFillState TypedDict
│   │   ├── builder.py                # LangGraph construction
│   │   ├── routers.py                # Conditional routing functions
│   │   ├── agents/
│   │   │   ├── __init__.py
│   │   │   ├── document_analyzer.py  # Agent 1
│   │   │   ├── field_extractor.py    # Agent 2
│   │   │   ├── form_analyzer.py      # Agent 3
│   │   │   ├── field_mapper.py       # Agent 4
│   │   │   └── form_filler.py        # Agent 5
│   │   └── tools/
│   │       ├── __init__.py
│   │       ├── ocr_toolbox.py        # OCR backends wrapper
│   │       ├── browser_tools.py      # Playwright tools
│   │       └── validation.py         # Format validators
│   │
│   ├── ocr/
│   │   ├── __init__.py
│   │   ├── preprocessor.py           # Deskew, denoise, enhance
│   │   ├── tesseract_backend.py      # Tesseract wrapper
│   │   ├── doctr_backend.py          # DocTR wrapper
│   │   ├── pdfplumber_backend.py     # Digital PDF extractor
│   │   └── llm_vision_backend.py     # GPT-4o / Claude Vision
│   │
│   ├── web/
│   │   ├── __init__.py
│   │   ├── routes.py                 # UI routes (Jinja2)
│   │   ├── templates/
│   │   │   ├── base.html             # Base layout
│   │   │   ├── index.html            # Upload page
│   │   │   ├── session.html          # Session detail + progress
│   │   │   └── review.html           # Human review page
│   │   └── static/
│   │       ├── css/
│   │       │   └── app.css           # Styles (Tailwind)
│   │       └── js/
│   │           └── app.js            # Alpine.js behaviors
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   └── session.py                # SQLAlchemy session model
│   │
│   └── db/
│       ├── __init__.py
│       ├── database.py               # Connection management
│       └── migrations/               # Alembic migrations
│
├── docs/
│   └── 2026-07-21-ocr-form-fill-design.md   # This document
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                   # Shared fixtures
│   ├── unit/
│   │   ├── test_preprocessor.py
│   │   ├── test_tesseract_backend.py
│   │   ├── test_doctr_backend.py
│   │   ├── test_graph_state.py
│   │   ├── test_field_mapper.py
│   │   └── test_browser_tools.py
│   ├── integration/
│   │   ├── test_session_api.py
│   │   ├── test_review_flow.py
│   │   └── test_ocr_pipeline.py
│   └── fixtures/
│       ├── sample_invoice.pdf
│       ├── sample_form.pdf
│       ├── sample_letter.png
│       └── test_form.html
│
├── uploads/                          # Uploaded documents (gitignored)
├── screenshots/                      # Proof screenshots (gitignored)
├── storage/                          # Session DB (gitignored)
│
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

---

## 10. Tech Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| **Web framework** | FastAPI | Async-native, automatic OpenAPI docs, Pydantic integration |
| **Graph orchestration** | LangGraph | State machine with human-in-the-loop interrupts, fits LangChain ecosystem |
| **LLM framework** | LangChain | Provider-agnostic, tool-calling, structured output |
| **LLM providers** | OpenAI GPT-4o / Claude | Vision capability for LLM Vision OCR and extraction |
| **OCR — Digital PDF** | pdfplumber | Direct text extraction, table support |
| **OCR — Printed text** | Tesseract 5 | Mature, fast, open-source, LSTM-based |
| **OCR — Layout/Table** | DocTR | Deep learning, layout preservation, bounding boxes |
| **OCR — Vision fallback** | GPT-4o Vision / Claude Vision | Multimodal LLM for hard cases |
| **Image preprocessing** | OpenCV + Pillow | Deskew, denoise, contrast enhancement |
| **Browser automation** | Playwright (async) | Async-native, fast, auto-waiting, CAPTCHA detection |
| **Database** | SQLite (dev) / PostgreSQL (prod) | Session state, form schemas cache |
| **ORM** | SQLAlchemy 2.0 | Mature, async support |
| **Frontend** | Jinja2 + Alpine.js + Tailwind CSS | Lightweight, no SPA overhead |
| **Container** | Docker + docker-compose | Consistent deployment |
| **File storage** | Local filesystem (dev) / S3 (prod) | Document and screenshot storage |

### Python Dependencies

```toml
[project]
dependencies = [
    "fastapi>=0.110.0",
    "uvicorn[standard]>=0.27.0",
    "pydantic>=2.5.0",
    "python-multipart>=0.0.9",
    "python-dotenv>=1.0.0",
    "langchain>=0.2.0",
    "langchain-openai>=0.1.0",
    "langchain-anthropic>=0.1.0",
    "langgraph>=0.1.0",
    "playwright>=1.40.0",
    "pdfplumber>=0.10.0",
    "pytesseract>=0.3.10",
    "python-doctr>=0.8.0",
    "opencv-python>=4.9.0",
    "Pillow>=10.0.0",
    "sqlalchemy>=2.0.25",
    "aiosqlite>=0.19.0",
    "jinja2>=3.1.2",
    "aiofiles>=23.2.0",
    "sse-starlette>=1.8.0",
]
```

---

## 11. Error Handling & Edge Cases

### Error Matrix

| Scenario | Detection | Resolution |
|----------|-----------|------------|
| **Empty/blank document** | Document Analyzer: zero text after OCR | Return terminal error. Session → `failed` |
| **Unsupported file format** | Upload validation: reject non-PDF/image | `422` response with supported formats list |
| **Low DPI scan** | Preprocessor: DPI < 150 | Attempt upscale. If still low → escalate to LLM Vision. Report quality issue |
| **OCR low confidence** | OCR tools: confidence < 0.7 | Auto-retry with next backend in chain. If all fail → flag for human |
| **No form on page** | Form Analyzer: zero `<form>` | Terminal error. Session → `failed` with explanation |
| **Unmapped field** | Field Mapper: no match ≥ 0.6 | Show in UI for manual mapping. User must resolve before approve |
| **CAPTCHA detected** | Form Filler: CAPTCHA element found | STOP. Session → `captcha_blocked`. Notify user to solve manually |
| **Element not found** | Playwright: selector missing | Retry 3× with 2s wait. If still missing → skip, record error |
| **Network timeout** | Playwright: page.goto() timeout | Retry 3× with exponential backoff (2s, 4s, 8s). Fail on final |
| **Agent timeout** | Each agent has 60s timeout | Fail that node. Error preserved in state for debugging |
| **Concurrent sessions** | Multiple uploads | Each session is isolated. LangGraph `thread_id` per session |
| **Large document** | File size > 20MB | Reject with "file too large" or offer compression. Page limit: 50 pages |
| **Password-protected PDF** | pdfplumber: PDF encrypted | Return error. Cannot process without password |
| **LLM rate limit hit** | LangChain: 429 response | Exponential backoff up to 3 retries. If persists → session to `failed` |

### Graceful Degradation

```
Full pipeline (all backends available)
    → Best accuracy, full features

Missing Tesseract
    → DocTR handles all non-digital docs, LLM Vision for low quality

Missing DocTR
    → Tesseract for all image docs, LLM Vision for layout-heavy docs

Missing LLM Vision (no API key)
    → Pure extraction from OCR text only. No layout understanding.
      Confidence scores lowered accordingly.

Missing Playwright
    → Extraction and mapping still work. Form filling unavailable.
```

### Retry Logic

```python
RETRY_CONFIG = {
    "ocr_tesseract":  {"max_retries": 2, "backoff": 1.0},
    "ocr_doctr":      {"max_retries": 2, "backoff": 1.5},
    "ocr_llm_vision": {"max_retries": 3, "backoff": 2.0},
    "browser_nav":    {"max_retries": 3, "backoff": 2.0},
    "browser_fill":   {"max_retries": 3, "backoff": 1.0},
    "llm_extraction": {"max_retries": 3, "backoff": 2.0},
}
```

---

## 12. Development Roadmap

### Phase 1 — Foundation (Week 1-2)

- [ ] Scaffold FastAPI project with `pyproject.toml` and Docker
- [ ] Implement LangGraph state schema (`OCRFormFillState`)
- [ ] Set up SQLite database and session model
- [ ] Implement file upload endpoint (`POST /api/v1/sessions`)
- [ ] Create health check endpoint
- [ ] Write basic tests

### Phase 2 — OCR Pipeline (Week 3-4)

- [ ] Implement image preprocessing (deskew, denoise, contrast)
- [ ] Integrate Tesseract backend
- [ ] Integrate pdfplumber backend
- [ ] Integrate DocTR backend
- [ ] Implement LLM Vision backend (OpenGPT-4o/Claude)
- [ ] Implement OCR escalation logic (fallback chain)
- [ ] Write OCR tool layer for agent invocation
- [ ] Unit test each backend with fixtures

### Phase 3 — Agents (Week 5-6)

- [ ] Implement Document Analyzer agent
- [ ] Implement Field Extractor agent
- [ ] Implement Form Analyzer agent (Playwright)
- [ ] Implement Field Mapper agent
- [ ] Implement Form Filler agent (Playwright)
- [ ] Wire LangGraph with all nodes and edges
- [ ] Add human-in-the-loop interrupt

### Phase 4 — Web UI (Week 7)

- [ ] Build upload page (drag-and-drop)
- [ ] Build session progress view (SSE live updates)
- [ ] Build human review page (editable fields + mappings)
- [ ] Build session history list
- [ ] Integrate Tailwind CSS + Alpine.js
- [ ] End-to-end testing of review flow

### Phase 5 — Hardening (Week 8)

- [ ] Error handling for all edge cases
- [ ] CAPTCHA detection
- [ ] Multi-page form support
- [ ] Anti-detection measures
- [ ] Rate limiting and concurrent session limits
- [ ] Documentation and README
- [ ] Performance benchmarking
- [ ] docker-compose for full stack

### Phase 6 — Production (Week 9+)

- [ ] PostgreSQL support
- [ ] S3 file storage
- [ ] Form schema cache (for known enterprise apps)
- [ ] Authentication and API keys
- [ ] Prometheus metrics
- [ ] Load testing and optimization
- [ ] CI/CD pipeline

---

## Appendix A — LangGraph Execution Flow (Detailed)

```python
import asyncio
from langgraph.graph import StateGraph
from langgraph.checkpoint.sqlite import SqliteSaver

# Build graph
graph = StateGraph(OCRFormFillState)

graph.add_node("analyze_document", document_analyzer_agent)
graph.add_node("run_ocr", ocr_orchestrator)
graph.add_node("extract_fields", field_extractor_agent)
graph.add_node("analyze_form", form_analyzer_agent)
graph.add_node("map_fields", field_mapper_agent)
graph.add_node("human_review", human_review_interrupt)
graph.add_node("fill_form", form_filler_agent)
graph.add_node("complete", completion_handler)

graph.set_entry_point("analyze_document")
graph.add_edge("analyze_document", "run_ocr")
graph.add_edge("run_ocr", "extract_fields")
graph.add_conditional_edges("extract_fields", has_target_url, {True: "analyze_form", False: "map_fields"})
graph.add_edge("analyze_form", "map_fields")
graph.add_edge("map_fields", "human_review")
graph.add_conditional_edges("human_review", is_approved, {True: "fill_form", False: "map_fields"})
graph.add_conditional_edges("fill_form", fill_successful, {True: "complete", False: "map_fields"})

graph.set_finish_point("complete")

# Compile with checkpointer
checkpointer = SqliteSaver.from_conn_string("sqlite:///storage/sessions.db")
app = graph.compile(checkpointer=checkpointer)

# Execute
config = {"configurable": {"thread_id": session_id}}
async for event in app.astream_events(input_state, config, version="v2"):
    if event["event"] == "on_chain_end":
        print(f"Node complete: {event['name']}")
    # SSE stream to frontend
```

---

## Appendix B — Sample API Interactions

### Upload Document

```bash
curl -X POST http://localhost:8000/api/v1/sessions \
  -F "file=@invoice.pdf" \
  -F "target_url=https://example.com/payment-form"
```

```json
{
  "session_id": "abc123",
  "status": "analyzing",
  "created_at": "2026-07-21T10:30:00Z"
}
```

### Poll Status

```bash
curl http://localhost:8000/api/v1/sessions/abc123
```

```json
{
  "session_id": "abc123",
  "status": "awaiting_review",
  "doc_type": "invoice",
  "time_elapsed_seconds": 12.4
}
```

### Get Review Data

```bash
curl http://localhost:8000/api/v1/sessions/abc123/review
```

```json
{
  "extracted_fields": {
    "invoice_number": { "value": "INV-2024-0042", "confidence": 0.98 },
    "vendor_name": { "value": "Acme Corp", "confidence": 0.95 },
    "total_amount": { "value": 1249.99, "confidence": 0.92 },
    "due_date": { "value": "2026-08-15", "confidence": 0.85 }
  },
  "form_fields": [
    { "field_id": "inv_no", "selector": "#invoice_number", "label": "Invoice #", "type": "text" },
    { "field_id": "amount", "selector": "#amount", "label": "Amount", "type": "number" },
    { "field_id": "date", "selector": "#due_date", "label": "Due Date", "type": "date" }
  ],
  "field_mappings": {
    "invoice_number": { "form_field_id": "inv_no", "confidence": 0.97 },
    "total_amount": { "form_field_id": "amount", "confidence": 0.93 },
    "due_date": { "form_field_id": "date", "confidence": 0.88 }
  },
  "unmapped_fields": ["vendor_name"]
}
```

### Approve & Fill

```bash
curl -X POST http://localhost:8000/api/v1/sessions/abc123/review \
  -H "Content-Type: application/json" \
  -d '{
    "corrections": {
      "total_amount": 1249.99
    },
    "mappings": {
      "vendor_name": { "form_field_id": "inv_no" }
    },
    "action": "approve"
  }'
```

```json
{
  "status": "filling",
  "next_step": "/api/v1/sessions/abc123"
}
```

---

## Appendix C — Design Decisions Log

| Decision | Option Chosen | Alternatives Considered | Rationale |
|----------|---------------|------------------------|-----------|
| Orchestration | LangGraph agents | Simple pipeline, LLM chain | Agent-based handles variability; existing LangChain in project |
| OCR primary | Multi-tier fallback | Single engine only | Cost efficiency: fast/cheap OCR for 90%+, LLM Vision only for 5% |
| Human review | Interrupt node | Always auto-fill | Safety for production use; user explicitly wanted full review |
| Frontend | Jinja2 + Alpine | React, Vue, HTMX | No build step, light weight, fits FastAPI natively |
| Browser automation | Playwright | Selenium, Puppeteer | Async-native, auto-waiting, better DevTools protocol |
| State persistence | SQLite/PostgreSQL | Redis, in-memory | LangGraph checkpointer supports SQL; can add Redis for caching later |
| Form mapping | Semantic LLM matching | Template-only, regex | Handles unknown forms dynamically; templates provide boost for known ones |

---

---

## Cross-Cutting Evaluation

A companion document evaluates six cross-cutting concerns for this design:

- [**LLM Gateway**](2026-07-21-ocr-cross-cutting-evaluation.md#1-llm-gateway-architecture) — Centralized routing, **dynamic provider switching** (4 strategies: cost_optimized, quality_optimized, balanced, manual), pluggable provider adapters (OpenAI, Azure, Anthropic, AWS Bedrock, Google Vertex, local), circuit breakers, auto-switcher rules, rate limiting, response caching
- [**LLMOps**](2026-07-21-ocr-cross-cutting-evaluation.md#2-llmops) — Prompt versioning, quality evaluation pipeline, drift detection, A/B testing, cost reporting
- [**Ranking System**](2026-07-21-ocr-cross-cutting-evaluation.md#3-ranking-system) — Multi-factor field confidence scoring, form match ranking, decision thresholds
- [**Self-Reflection & Feedback Loops**](2026-07-21-ocr-cross-cutting-evaluation.md#4-self-reflection--feedback-loops) — Human correction capture, weekly quality reports, form schema cache from user mappings
- [**CI/CD & Trunking**](2026-07-21-ocr-cross-cutting-evaluation.md#5-trunking--cicd-strategy) — Trunk-based development, GitHub Actions pipelines, canary deploys, feature flags
- [**Budget & Cost Control**](2026-07-21-ocr-cross-cutting-evaluation.md#6-budget--cost-control-deep-dive) — Hard/soft budget limits per day/month/session/route, cost-aware routing with auto-downgrade, ~80% cost reduction vs naive approach

→ See [`2026-07-21-ocr-cross-cutting-evaluation.md`](2026-07-21-ocr-cross-cutting-evaluation.md) for full evaluation.

---

*End of design document.*
