# Safeguards Audit — OCR Form Fill System

**Date:** 2026-07-21
**Reference:** RAG_DAG_IMPROVEMENT_REVIEW.md guardrail patterns, .claude/rules/crew-boundary-safety.md
**Companion to:** `2026-07-21-ocr-form-fill-design.md`, `architecture.md`

---

## Executive Summary

The current OCR Form Fill design focuses on **accuracy, cost control, and automation** but has **significant gaps in safeguards**. The RAG_DAG_IMPROVEMENT_REVIEW.md defines a guardrail pattern (input → process → output) with hard enforcement at every boundary. The OCR system needs the same treatment.

**Severity: HIGH** — Without these safeguards, the system could fill forms with malicious data, expose PII, exhaust budgets through abuse, or cause unintended state changes in target web forms.

---

## 1. Safeguard Architecture (Reference: RAG DAG §6.2)

The RAG DAG defines a **guardrail sandwich**: input guardrails → process → output guardrails. The OCR system needs the same pattern:

```
  User Upload
      |
      v
  +-----------------------+
  | INPUT GUARDRAILS       |  <-- NEW: document validation, PII scan, abuse detection
  +-----------------------+
      |
      v
  +-----------------------+
  | OCR + EXTRACTION       |  (existing pipeline)
  +-----------------------+
      |
      v
  +-----------------------+
  | OUTPUT GUARDRAILS      |  <-- NEW: field validation, injection check, confidence gate
  +-----------------------+
      |
      v
  +-----------------------+
  | HUMAN REVIEW           |  (existing interrupt)
  +-----------------------+
      |
      v
  +-----------------------+
  | FORM FILL              |  (existing)
  +-----------------------+
      |
      v
  +-----------------------+
  | AUDIT LOG              |  <-- NEW: immutable trail for compliance
  +-----------------------+
```

**RAG DAG reference (§6.2 flow):**
```
User message → LLM Gateway → Guardrails IN → process → Guardrails OUT → response
```

---

## 2. Input Guardrails (Before Processing)

### 2.1 Document Validation

| Check | What it detects | Action | Priority |
|-------|----------------|--------|----------|
| **Magic byte verification** | File extension spoofing (.exe → .pdf) | Reject with `422` | Critical |
| **MIME type validation** | Non-document uploads | Reject | High |
| **Max file size** | DoS via giant files (default: 20MB) | Reject with `413` | Critical |
| **Max page count** | Abuse via 500-page PDFs (default: 50 pages) | Reject | High |
| **PDF structure scan** | Corrupt or malicious PDFs (infinite loops, JS injection) | Reject + log | Critical |
| **Image integrity** | Corrupt image headers, truncated files | Reject | Medium |
| **Encryption/DRM check** | Password-protected PDFs | Return clear error | Medium |
| **Virus/malware scan** | Malicious payloads in documents | Quarantine file + alert | Critical |

```python
class DocumentInputGuardrail:
    """Validates uploaded documents before any processing begins."""

    MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024   # 20 MB
    MAX_PAGE_COUNT = 50
    ALLOWED_MIME_TYPES = {
        "application/pdf",
        "image/png", "image/jpeg", "image/tiff",
        "image/bmp", "image/webp",
    }
    ALLOWED_MAGIC_BYTES = {
        b"%PDF",           # PDF
        b"\x89PNG",        # PNG
        b"\xff\xd8\xff",   # JPEG
        b"II\x2a\x00",     # TIFF (little-endian)
        b"MM\x00\x2a",     # TIFF (big-endian)
    }

    async def validate(self, file: UploadFile) -> ValidationResult:
        # 1. Magic byte check (defeats extension spoofing)
        header = await file.read(8)
        await file.seek(0)
        if not any(header.startswith(m) for m in self.ALLOWED_MAGIC_BYTES):
            return ValidationResult.FAIL("File type mismatch: magic bytes do not match extension")

        # 2. MIME type
        if file.content_type not in self.ALLOWED_MIME_TYPES:
            return ValidationResult.FAIL(f"Unsupported MIME type: {file.content_type}")

        # 3. File size
        file_size = await self._get_file_size(file)
        if file_size > self.MAX_FILE_SIZE_BYTES:
            return ValidationResult.FAIL(f"File too large: {file_size / 1024 / 1024:.1f}MB > {self.MAX_FILE_SIZE_BYTES / 1024 / 1024}MB")

        # 4. Page count (for PDFs)
        if file.content_type == "application/pdf":
            page_count = await self._count_pdf_pages(file)
            if page_count > self.MAX_PAGE_COUNT:
                return ValidationResult.FAIL(f"Too many pages: {page_count} > {self.MAX_PAGE_COUNT}")

        return ValidationResult.PASS()

    async def scan_for_malware(self, file_path: str) -> ScanResult:
        """Integration with ClamAV or similar. Non-blocking, async."""
        result = await clamav.scan(file_path)
        if result.infected:
            alert(f"MALWARE DETECTED in upload: {result.signature}")
            return ScanResult.INFECTED
        return ScanResult.CLEAN
```

### 2.2 PII / Sensitive Data Detection

Before sending document content to LLM providers (which may store data), scan for PII:

```python
class PIIGuardrail:
    """
    Scans document content for PII before it reaches LLM providers or storage.
    Reference: RAG_DAG §4.2 — "Do not cache raw PII"
    """

    PII_PATTERNS = {
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "credit_card": r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "phone": r"\b\+?1?\d{10,15}\b",
        "passport": r"\b[A-Z]{1,2}\d{6,9}\b",
    }

    async def scan_document(self, ocr_text: str) -> PIIReport:
        findings = []
        for pii_type, pattern in self.PII_PATTERNS.items():
            matches = re.finditer(pattern, ocr_text)
            for m in matches:
                findings.append({
                    "type": pii_type,
                    "position": m.start(),
                    "masked_value": self._mask(m.group(), pii_type),
                    "action": "warn",  # or "block" for strict policies
                })
        return PIIReport(findings=findings, has_pii=len(findings) > 0)

    def _mask(self, value: str, pii_type: str) -> str:
        """Mask PII for review UI — show last 4 chars only."""
        if pii_type in ("ssn", "credit_card"):
            return "***" + value[-4:]
        if pii_type == "email":
            parts = value.split("@")
            return f"{parts[0][:2]}***@{parts[1]}"
        return "***" + value[-4:]

    async def apply_policy(self, pii_report: PIIReport) -> PIIDecision:
        """Decide: block, warn, or allow based on PII policy."""
        if any(f["type"] in ("credit_card", "ssn") for f in pii_report.findings):
            return PIIDecision.BLOCK  # Never send sensitive data to LLM
        if pii_report.has_pii:
            return PIIDecision.WARN  # Flag for human review
        return PIIDecision.ALLOW
```

### 2.3 Abuse Detection & Rate Limiting

Reference: RAG_DAG §6.3 D (SaaS cost control patterns)

```python
class AbuseDetector:
    """
    Detects and prevents abusive usage patterns.
    Reference: RAG_DAG §D.5 — reserve/commit/release pattern for budget
    """

    RATE_LIMITS = {
        "anonymous":   {"uploads_per_hour": 5,   "sessions_per_day": 10},
        "authenticated": {"uploads_per_hour": 50,  "sessions_per_day": 200},
        "enterprise":  {"uploads_per_hour": 500, "sessions_per_day": 2000},
    }

    ABUSE_PATTERNS = [
        {
            "name": "rapid_upload",
            "detect": lambda ctx: ctx.uploads_last_minute > 20,
            "action": "throttle",   # Slow down, don't block
            "cooldown_minutes": 5,
        },
        {
            "name": "massive_batch",
            "detect": lambda ctx: ctx.concurrent_sessions > 10,
            "action": "queue",      # Put in backlog, process sequentially
        },
        {
            "name": "repeated_failure",
            "detect": lambda ctx: ctx.failure_rate_last_hour > 0.5,
            "action": "block",      # Possible testing of boundaries
            "cooldown_minutes": 60,
        },
        {
            "name": "suspicious_domain",
            "detect": lambda ctx: ctx.target_url_domain in SUSPICIOUS_DOMAINS,
            "action": "block",
            "alert": True,
        },
        {
            "name": "budget_exhaustion_race",
            "detect": lambda ctx: True,  # Always check before processing
            "action": "reserve_commit",   # RAG DAG §D.5 pattern
        },
    ]

    async def check_upload_allowed(self, tenant_id: str, user_id: str) -> bool:
        """Reserve budget before processing. RAG DAG §D.5 pattern."""
        # 1. Check per-user rate
        rate = self.RATE_LIMITS.get(self._get_user_tier(user_id))
        usage = await self._get_user_usage(user_id, "uploads", window="1h")
        if usage >= rate["uploads_per_hour"]:
            return False

        # 2. Reserve budget (RAG DAG pattern)
        budget_ok = await budget_service.reserve(
            tenant_id=tenant_id,
            estimated_cost=0.10,  # Base cost for OCR + extraction
            ttl_seconds=300,      # Release reservation after 5 min if not used
        )
        if not budget_ok:
            return False

        return True
```

---

## 3. Output Guardrails (Before Form Fill)

### 3.1 Field-Level Validation

Before filling a form field, validate the extracted value against what the form expects:

```python
class FieldOutputGuardrail:
    """
    Validates every extracted field value before it reaches the form.
    Reference: RAG DAG §6.2 — "Never synthesize without sources"
    """

    VALIDATORS = {
        "email": {
            "validator": lambda v: bool(re.match(r"[^@]+@[^@]+\.[^@]+$", str(v))),
            "error": "Invalid email format",
        },
        "phone": {
            "validator": lambda v: bool(re.match(r"^\+?1?\d{7,15}$", re.sub(r"[\s\-\(\)]", "", str(v)))),
            "error": "Invalid phone number format",
        },
        "date": {
            "validator": lambda v: self._validate_date(str(v)),
            "error": "Invalid date format (expected YYYY-MM-DD)",
        },
        "number": {
            "validator": lambda v: self._is_numeric(v),
            "error": "Expected numeric value",
        },
        "zip_code": {
            "validator": lambda v: bool(re.match(r"^\d{5}(-\d{4})?$", str(v))),
            "error": "Invalid ZIP code format",
        },
        "ssn": {
            "validator": lambda v: bool(re.match(r"^\d{3}-\d{2}-\d{4}$", str(v))),
            "error": "Invalid SSN format",
        },
        "url": {
            "validator": lambda v: validators.url(str(v)),
            "error": "Invalid URL",
        },
    }

    async def validate_field(self, field_key: str, value: Any, form_field: FormField) -> ValidationResult:
        """Validate a single field value against form expectations."""
        field_type = form_field.get("type", "text")

        # 1. Required field check
        if form_field.get("required") and (value is None or value == ""):
            return ValidationResult.FAIL(f"Required field '{field_key}' is empty")

        # 2. Pattern check (from HTML pattern attribute)
        if form_field.get("pattern"):
            if not re.match(form_field["pattern"], str(value)):
                return ValidationResult.FAIL(f"Field '{field_key}' does not match required pattern")

        # 3. Type-specific validation
        if field_type in self.VALIDATORS:
            if not self.VALIDATORS[field_type]["validator"](value):
                return ValidationResult.FAIL(f"Field '{field_key}': {self.VALIDATORS[field_type]['error']}")

        # 4. Length checks
        if form_field.get("maxlength") and len(str(value)) > form_field["maxlength"]:
            return ValidationResult.WARN(f"Field '{field_key}' exceeds max length ({form_field['maxlength']})")
        if form_field.get("minlength") and len(str(value)) < form_field["minlength"]:
            return ValidationResult.FAIL(f"Field '{field_key}' below min length ({form_field['minlength']})")

        # 5. Enum check (select/radio fields)
        if form_field.get("accepted_values"):
            if str(value) not in form_field["accepted_values"]:
                return ValidationResult.FAIL(
                    f"Field '{field_key}': '{value}' not in accepted values: {form_field['accepted_values']}"
                )

        return ValidationResult.PASS()

    async def validate_all_fields(self, mappings: dict, form_fields: list) -> FieldValidationReport:
        """Batch validate all mapped fields."""
        results = []
        for field_key, mapping in mappings.items():
            form_field = next((f for f in form_fields if f["field_id"] == mapping["form_field_id"]), None)
            if not form_field:
                results.append(ValidationIssue(field_key, "warn", "Form field not found in current schema"))
                continue
            result = await self.validate_field(field_key, mapping.get("value"), form_field)
            if not result.passed:
                results.append(ValidationIssue(field_key, "error", result.message))
        return FieldValidationReport(
            all_passed=all(r.severity != "error" for r in results),
            issues=results,
        )
```

### 3.2 Injection Protection

OCR'd text could contain malicious content that gets injected into web forms. This is a **critical boundary safety issue** (ref: crew-boundary-safety.md Pattern 1 — Abstractions break at system boundaries).

```python
class InjectionGuardrail:
    """
    Prevents injection attacks through OCR'd content.
    Reference: crew-boundary-safety.md — Pattern 1 (boundary crossing), Pattern 4 (global interceptors)
    """

    INJECTION_PATTERNS = {
        "xss": [
            r"<script[\s>]",
            r"javascript\s*:",
            r"<[^>]+on\w+\s*=",       # onload=, onclick=, etc.
            r"<iframe[\s>]",
            r"<object[\s>]",
            r"<embed[\s>]",
            r"<svg[\s>]",
            r"eval\(.*\)",
            r"document\.cookie",
        ],
        "sql_injection": [
            r"'\s*OR\s*'1'='1",
            r"'\s*OR\s*1\s*=\s*1",
            r"'\s*;\s*DROP\s+TABLE",
            r"'\s*;\s*DELETE\s+FROM",
            r"'\s*;\s*UPDATE\s+\w+\s+SET",
            r"UNION\s+SELECT",
            r"pg_sleep\(",
            r"xp_cmdshell",
        ],
        "html_injection": [
            r"<form[\s>]",
            r"<input[\s>]",
            r"<textarea[\s>]",
            r"<select[\s>]",
            r"<base[\s>]",
        ],
        "template_injection": [
            r"\{\{.*\}\}",
            r"\$\{.*\}",
            r"<%.*%>",
            r"\{\%.*\%\}",
        ],
    }

    async def scan_field(self, field_key: str, value: Any, form_field: FormField) -> InjectionResult:
        """Scan a single field value for injection patterns."""
        text_value = str(value)
        findings = []

        for injection_type, patterns in self.INJECTION_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_value, re.IGNORECASE):
                    findings.append({
                        "field": field_key,
                        "injection_type": injection_type,
                        "pattern_matched": pattern,
                        "severity": "critical" if injection_type in ("xss", "sql_injection") else "high",
                    })

        if findings:
            alert(f"INJECTION DETECTED: field={field_key}, types={set(f['injection_type'] for f in findings)}")
            return InjectionResult(detected=True, findings=findings, action="block")

        return InjectionResult(detected=False)

    async def sanitize_value(self, value: Any, form_field: FormField) -> str:
        """Sanitize a value for safe form filling. Used when guardrail is in 'warn' mode."""
        text = str(value)
        # Strip HTML tags for text fields
        if form_field.get("type") in ("text", "textarea", "email", "url"):
            text = strip_tags(text)
        # Escape HTML entities
        text = html.escape(text, quote=True)
        return text
```

### 3.3 Confidence Gate (Enforce Before Fill)

Reference: RAG DAG §6.2 — "Hard rules: Never synthesize without sources"

```python
class ConfidenceGate:
    """
    Enforces minimum confidence thresholds before filling form fields.
    If confidence is too low, routes back to human review instead of auto-filling.
    Reference: RAG DAG §6.2 — faithfulness gate pattern
    """

    CONFIDENCE_THRESHOLDS = {
        "auto_fill": 0.90,       # Fill without human review (if enabled)
        "human_review": 0.70,     # Must show human for confirmation
        "reject": 0.40,          # Cannot fill — return to re-extraction
    }

    SPECIAL_FIELD_THRESHOLDS = {
        "ssn":          {"auto_fill": 0.95, "human_review": 0.85},
        "credit_card":  {"auto_fill": 0.95, "human_review": 0.85},
        "email":         {"auto_fill": 0.90, "human_review": 0.75},
        "phone":         {"auto_fill": 0.90, "human_review": 0.75},
        "date":          {"auto_fill": 0.85, "human_review": 0.65},
    }

    async def gate_field(self, field_key: str, confidence: float, field_type: str) -> GateDecision:
        """Apply confidence threshold for a single field."""
        thresholds = self.SPECIAL_FIELD_THRESHOLDS.get(field_key, self.CONFIDENCE_THRESHOLDS)

        if confidence >= thresholds["auto_fill"]:
            return GateDecision.ALLOW
        elif confidence >= thresholds["human_review"]:
            return GateDecision.REVIEW
        else:
            return GateDecision.REJECT

    async def gate_session(self, field_confidences: dict) -> SessionGateDecision:
        """Apply confidence gate across all extracted fields."""
        results = {}
        for field_key, data in field_confidences.items():
            results[field_key] = await self.gate_field(field_key, data["confidence"], data.get("type", "text"))

        any_rejected = any(r == GateDecision.REJECT for r in results.values())
        any_review = any(r == GateDecision.REVIEW for r in results.values())

        if any_rejected:
            return SessionGateDecision(
                action="reject",  # Send back to re-extraction
                rejected_fields=[k for k, v in results.items() if v == GateDecision.REJECT],
                review_fields=[k for k, v in results.items() if v == GateDecision.REVIEW],
            )
        if any_review:
            return SessionGateDecision(
                action="review",  # Send to human review (already exists in pipeline)
                review_fields=[k for k, v in results.items() if v == GateDecision.REVIEW],
            )
        return SessionGateDecision(action="allow")
```

---

## 4. Form Fill Safeguards

### 4.1 Pre-Fill Safety Checks

```python
class PreFillSafetyCheck:
    """
    Checks performed immediately before Playwright fills the form.
    Reference: crew-boundary-safety.md — Patterns 1, 5 (test full journeys)
    """

    async def check(self, session: Session) -> PreFillVerdict:
        issues = []

        # 1. Target URL - is it reachable?
        reachable = await self._check_url_reachable(session.target_url)
        if not reachable:
            issues.append(FillIssue("critical", "Target URL is not reachable"))
            return PreFillVerdict.BLOCK, issues

        # 2. Target URL - is it the right environment?
        if self._contains_production_keyword(session.target_url) and session.environment != "production":
            issues.append(FillIssue("critical", "Production URL detected in non-production session"))
            return PreFillVerdict.BLOCK, issues

        # 3. Form still exists? (schema may have changed since analysis)
        form_exists = await self._verify_form_still_present(session.target_url, session.form_fields)
        if not form_exists:
            issues.append(FillIssue("high", "Form structure changed since analysis — re-analysis recommended"))
            return PreFillVerdict.RE_ANALYZE, issues

        # 4. Destructive action detection
        if self._detects_destructive_action(session.target_url):
            issues.append(FillIssue("critical", "Target URL appears to be a delete/remove action"))
            return PreFillVerdict.BLOCK, issues

        # 5. Test mode — don't actually submit
        if session.safety_mode == "test_fill_only":
            return PreFillVerdict.TEST_FILL_ONLY, issues

        return PreFillVerdict.OK, issues
```

### 4.2 Fill Mode Options

```python
FILL_MODES = {
    "test_fill": {
        "description": "Fill all fields but do NOT click submit. Take screenshot.",
        "submit": False,
        "screenshot": True,
        "suitable_for": "Verification before real submission",
    },
    "safe_submit": {
        "description": "Fill and submit, but only for non-destructive forms.",
        "submit": True,
        "require_confirmation": True,
        "suitable_for": "Standard form filling",
    },
    "full_auto": {
        "description": "Fill and submit without additional confirmation (subject to confidence gate).",
        "submit": True,
        "require_confirmation": False,
        "suitable_for": "Trusted, high-confidence automations",
    },
}
```

### 4.3 CAPTCHA / Bot Detection Handling

Already covered in the design — stops and marks session as `captcha_blocked`. Additional safeguard:

```python
class BotDetectionSafeguard:
    """
    Safeguards against bot detection and rate limiting.
    Reference: crew-boundary-safety.md — Pattern 4 (global interceptors)
    """

    MAX_RETRIES_ON_BLOCK = 1        # Only retry once before giving up
    COOLDOWN_BETWEEN_FILLS_S = 30   # Don't hammer the same domain

    SAFEGUARDS = {
        "detected_as_bot": {
            "action": "stop",
            "message": "Target site detected automated input. Session blocked.",
            "human_resolution": "Fill form manually or whitelist IP",
        },
        "rate_limited": {
            "action": "backoff",
            "message": "Target site rate limited. Waiting before retry.",
            "retry_after_s": 60,
        },
        "account_locked": {
            "action": "stop",
            "message": "Account appears locked on target site.",
            "human_resolution": "Check credentials for target form",
        },
        "form_changed": {
            "action": "stop",
            "message": "Form structure changed since analysis.",
            "human_resolution": "Re-analyze form",
        },
    }
```

---

## 5. Data Privacy & Retention

### 5.1 Document Retention Policy

```python
DOCUMENT_RETENTION = {
    "default_retention_days": 30,
    "max_retention_days": 90,
    "auto_delete_policy": {
        "completed_sessions": 30,    # Delete uploaded doc 30 days after completion
        "failed_sessions": 7,        # Delete failed uploads after 7 days
        "abandoned_sessions": 1,     # Clean up unprocessed uploads daily
    },
    "compliance": {
        "gdpr_right_to_deletion": True,   # API endpoint POST /sessions/{id}/delete
        "audit_retention_days": 365,      # Keep audit logs for 1 year (immutable)
    },
}
```

```python
class DataRetentionPolicy:
    """Manages document lifecycle and compliance deletion."""

    async def schedule_deletion(self, session_id: str, policy: str):
        """Schedule document deletion according to policy."""
        delay = DOCUMENT_RETENTION["auto_delete_policy"].get(policy, 30)
        await self._schedule_task(
            task=f"delete_document_{session_id}",
            delay_days=delay,
            action=lambda: self._delete_document(session_id),
        )

    async def delete_session_data(self, session_id: str, reason: str):
        """GDPR right-to-deletion or manual cleanup."""
        # 1. Delete uploaded document
        await self._delete_file(f"uploads/{session_id}.*")
        # 2. Delete vector embeddings (GDPR)
        await vector_db.delete(collection="documents", filter={"session_id": session_id})
        await vector_db.delete(collection="templates", filter={"session_id": session_id})
        # 3. Anonymize session record (keep metadata, remove document content)
        await db.execute(
            "UPDATE sessions SET raw_text = NULL, document_path = NULL, "
            "deleted_at = NOW(), deletion_reason = $1 WHERE session_id = $2",
            reason, session_id,
        )
        # 4. Log the deletion for compliance audit
        await self._audit_log("document_deleted", {
            "session_id": session_id,
            "reason": reason,
            "deleted_by": "auto_policy" if reason == "retention_expiry" else "user_request",
        })
```

### 5.2 Encryption at Rest

```python
ENCRYPTION_CONFIG = {
    "uploaded_documents": {
        "algorithm": "AES-256-GCM",
        "key_source": "AWS KMS / local key file",
        "scope": "per-file random key, wrapped by master key",
    },
    "database_sessions": {
        "encrypted_columns": ["raw_text", "extracted_fields", "human_corrections"],
        "algorithm": "pgcrypto (PostgreSQL) / SQLite encryption extension",
    },
    "vector_db": {
        "note": "Embeddings are not reversible to original text. "
                "Metadata payloads should not contain raw PII.",
    },
    "in_transit": {
        "api": "TLS 1.3",
        "internal_services": "mTLS (optional for production)",
    },
}
```

---

## 6. Audit Logging & Compliance

### 6.1 Immutable Audit Trail

```python
class AuditLogger:
    """
    Immutable audit trail for all operations.
    Reference: RAG_DAG §D.1 — request telemetry, tenant attribution
    """

    AUDIT_EVENTS = [
        "document_uploaded",
        "document_rejected",      # Input guardrail triggered
        "pii_detected",
        "injection_detected",
        "extraction_completed",
        "human_review_submitted",
        "form_fill_started",
        "form_fill_completed",
        "form_fill_failed",
        "form_fill_blocked",      # CAPTCHA / bot detection
        "session_cancelled",
        "session_deleted",
        "budget_exceeded",
        "abuse_pattern_detected",
        "provider_switched",      # AutoSwitcher action
        "admin_override",         # Admin API action
    ]

    async def log(self, event: str, session_id: str, details: dict):
        """
        Write to append-only audit store.
        Immutable: INSERT-only table, no UPDATE/DELETE privileges.
        """
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": event,
            "session_id": session_id,
            "tenant_id": details.get("tenant_id"),
            "user_id": details.get("user_id"),
            "details": json.dumps(details, default=str),
            "hash": self._compute_hash(event, session_id, details),
        }

        # Write to immutable audit table
        await db.execute(
            "INSERT INTO audit_log (timestamp, event, session_id, tenant_id, "
            "user_id, details, hash) VALUES ($1, $2, $3, $4, $5, $6, $7)",
            record.values(),
        )

        # Also emit as structured log for SIEM
        logger.info("audit_event", extra=record)
```

### 6.2 What to Audit (Minimum)

| Event | Data Captured | Retention |
|-------|--------------|-----------|
| Document upload | filename, size, type, user_id, tenant_id | 1 year |
| Input guardrail block | reason, file hash, rejection detail | 1 year |
| PII detection | pii_type, masked_value, action_taken | 1 year |
| Extraction result | field_count, confidence_mean, doc_type | 1 year |
| Human corrections | field_key, original_value (masked), corrected_value (masked) | 1 year |
| Form fill action | target_url, field_count, result, screenshot_ref | 1 year |
| Budget block | session_id, cost_attempted, budget_remaining | 1 year |
| Abuse detection | pattern_name, user_id, tenant_id, action | 1 year |
| Admin action | actor, action, target, reason | 2 years |

---

## 7. Multi-Tenant Isolation

### 7.1 Data Isolation

```python
class TenantIsolation:
    """
    Ensures strict data isolation between tenants.
    Reference: RAG_DAG §D.3 — tenant_id as boundary
    """

    ISOLATION_RULES = {
        "database": {
            "strategy": "row-level-security (RLS)",  # PostgreSQL RLS by tenant_id
            "fallback": "WHERE clause in every query",
        },
        "vector_db": {
            "strategy": "payload filter: tenant_id IN (...)",
            "example": "vector_db.search(filter={'tenant_id': tenant_id})",
        },
        "uploads": {
            "strategy": "path prefix: uploads/{tenant_id}/{session_id}.pdf",
            "permissions": "Tenant can only access own prefix",
        },
        "cache": {
            "strategy": "key prefix: cache:{tenant_id}:{cache_key}",
        },
        "screenshots": {
            "strategy": "path prefix: screenshots/{tenant_id}/{session_id}.png",
        },
    }

    async def enforce(self, tenant_id: str, resource_type: str, resource_id: str) -> bool:
        """Verify that a resource belongs to the requesting tenant."""
        rule = self.ISOLATION_RULES[resource_type]
        if rule["strategy"].startswith("path_prefix"):
            return resource_id.startswith(f"{tenant_id}/")
        return True  # RLS handles it at DB level
```

---

## 8. Operational Safeguards

### 8.1 Secrets Management

Reference: `.claude/rules/crew-secrets-scan.md`

```python
class SecretsManagement:
    """
    All secrets managed via environment variables or secret manager.
    Reference: crew-secrets-scan.md — "Never commit secrets to git"
    """

    SECRETS_CHECKLIST = {
        "llm_api_keys": {
            "location": "Environment variables (LLM_GATEWAY_OPENAI_KEY) or AWS Secrets Manager",
            "rotation": "Every 90 days",
            "git": "NEVER in .env files committed to repo",
        },
        "browser_credentials": {
            "location": "Encrypted in database, masked in logs",
            "rotation": "Per-session or per-tenant",
            "note": "Credentials for target web forms, not system credentials",
        },
        "database_url": {
            "location": "Environment variable only",
            "git": "NEVER in code — use env template (.env.example)",
        },
        "vector_db_key": {
            "location": "Environment variable",
            "git": "NEVER",
        },
        "admin_api_key": {
            "location": "Environment variable",
            "rotation": "Every 30 days",
            "note": "Used for gateway admin API access",
        },
    }

    def validate_env(self):
        """Validate that no secrets are hardcoded."""
        # Check environment variables are set
        required = ["OPENAI_API_KEY", "DATABASE_URL"]
        missing = [v for v in required if not os.environ.get(v)]
        if missing:
            raise ConfigError(f"Missing required secrets: {missing}")

        # Scan for hardcoded secrets in source
        # (ci/cd pipeline also runs detect-secrets pre-commit hook)
```

### 8.2 Degradation & Graceful Failure

Reference: RAG_DAG §6.3 C — degradation patterns

```python
DEGRADATION_MODES = {
    "full_service": {
        "description": "All features available",
        "ocr": "all_backends",
        "llm": "all_models",
        "form_fill": True,
        "vector_search": True,
    },
    "llm_degraded": {
        "description": "LLM provider partial outage — use fallback providers",
        "ocr": "tesseract_only",        # No LLM Vision OCR
        "llm": "cheapest_only",          # No quality_optimized routing
        "form_fill": True,
        "vector_search": True,
    },
    "ocr_degraded": {
        "description": "OCR backend issues — text-only extraction",
        "ocr": "tesseract_only",
        "llm": "all_models",
        "form_fill": True,
        "vector_search": True,
    },
    "cache_only": {
        "description": "Only serve previously cached results. No new processing.",
        "ocr": False,
        "llm": False,
        "form_fill": False,
        "vector_search": True,           # Already indexed docs still searchable
    },
    "read_only": {
        "description": "No new uploads or form fills. Existing sessions viewable.",
        "new_sessions": False,
        "existing_sessions": "view_only",
    },
}
```

---

## 9. Safeguard Integration into the Agent Pipeline

Where each safeguard plugs into the LangGraph:

```
  START
    |
    v
  [INPUT GUARDRAILS]          <-- NEW: Document validation, PII scan, abuse check
    |                              Fails -> session rejected, audit logged
    v
  Agent 1: Document Analyzer
    |
    v
  OCR Engine
    |
    v
  Agent 2: Field Extractor
    |
    v
  [PII GUARDRAIL]             <-- NEW: Scan extracted fields for PII before LLM re-entry
    |                              PII found -> mask in UI, warn human
    v
  Agent 3: Form Analyzer  --> [URL SAFETY CHECK]   <-- NEW: Verify URL safety
    |
    v
  Agent 4: Field Mapper
    |
    v
  [OUTPUT GUARDRAILS]         <-- NEW: Field validation, injection scan, confidence gate
    |                              Fails -> block field, request correction
    v
  HUMAN REVIEW (existing)
    |
    v
  [PRE-FILL SAFETY CHECK]    <-- NEW: URL reachable, form still exists, test mode
    |                              Fails -> stop, log audit
    v
  Agent 5: Form Filler
    |
    v
  [BOT DETECTION SAFEGUARD]  <-- NEW: CAPTCHA handling, rate limit backoff
    |
    v
  INDEXING SERVICE
    |
    v
  [AUDIT LOG]                <-- NEW: Immutable audit trail
    |
    v
  COMPLETE
```

---

## 10. Safeguard Gap Analysis (vs RAG DAG Standards)

| Safeguard | RAG DAG Status | OCR Design Status | Gap |
|-----------|---------------|-------------------|-----|
| **Input guardrails** | §6.2: Guardrails IN | MISSING | Document validation, PII scan, abuse detection |
| **Output guardrails** | §6.2: Guardrails OUT | MISSING | Field validation, injection protection, confidence gate |
| **SaaS cost control** | §6.3 D: Hard caps, reserve/commit, degrade | PARTIAL | Budget exists but no reserve/commit pattern |
| **Tenant isolation** | §D.3: tenant_id on every signal | MISSING | No multi-tenant model in design |
| **Data privacy** | §4.2: No raw PII in cache | MISSING | No PII policy, retention, or encryption |
| **Audit trail** | §D.1: Request telemetry | PARTIAL | LLM telemetry yes, but no full audit trail |
| **Abuse detection** | §D.5: Quota enforcement | MISSING | No per-user rate limits, no abuse patterns |
| **Degradation** | §6.3 C: Degradation modes | PARTIAL | Circuit breaker exists, no full degradation modes |
| **Secrets management** | crew-secrets-scan.md | MISSING | No secrets management policy in design |
| **Boundary safety** | crew-boundary-safety.md | MISSING | Form fill crosses system boundaries without safety checks |
| **Injection protection** | Not in RAG (text-only) | MISSING | Critical for OCR -> web form pipeline |
| **Document retention** | Not in RAG | MISSING | No auto-deletion, no GDPR compliance |

---

## 11. Implementation Priority

| Priority | Safeguard | Effort | Impact | Phase |
|----------|-----------|--------|--------|-------|
| P0 | Document validation (magic bytes, size, malware) | 2 days | Prevents DoS, malware uploads | Before launch |
| P0 | Injection protection (OCR -> form) | 1 day | Prevents XSS/sql injection via forms | Before launch |
| P0 | Secrets management policy | 0.5 day | Prevents credential leaks | Before launch |
| P0 | Immutable audit log | 2 days | Compliance, forensics | Before launch |
| P1 | PII detection & masking | 2 days | GDPR, privacy compliance | Week 1 |
| P1 | Confidence gate | 1 day | Prevents filling low-confidence fields | Week 1 |
| P1 | Pre-fill safety check | 1.5 days | Ensures target URL safety | Week 1 |
| P1 | Abuse detection (per-user rate limits) | 2 days | Prevents budget exhaustion | Week 1 |
| P1 | Field-level validation | 1 day | Ensures data integrity before fill | Week 1 |
| P2 | Encryption at rest (docs, DB) | 2 days | Data security | Week 2 |
| P2 | Document retention & auto-delete | 1 day | GDPR compliance | Week 2 |
| P2 | Degradation modes | 2 days | Operational resilience | Week 2 |
| P2 | Tenant isolation | 3 days | Multi-tenant readiness | Week 2 |
| P3 | reserve/commit budget pattern (RAG DAG §D.5) | 2 days | Prevent race conditions on budget | Week 3+ |
| P3 | Fill modes (test_fill, safe_submit, full_auto) | 1 day | Safety during form filling | Week 3+ |
| P3 | Bot detection evasion limits | 0.5 day | Prevent hammering target sites | Week 3+ |

---

## 12. Key Lessons from RAG_DAG_IMPROVEMENT_REVIEW.md

| Lesson | RAG DAG Reference | How It Applies to OCR |
|--------|------------------|----------------------|
| **Guardrail sandwich** | §6.2 — Guardrails IN and OUT | Same pattern: validate document IN, validate fields OUT |
| **Hard rules over soft warnings** | §6.2 — "Never synthesize without sources" | "Never fill a form field without validation" |
| **Reserve/commit for budget** | §D.5 — Prevents race conditions | Reserve OCR/extraction budget before processing |
| **Three-tier enforcement** | OD-10 — Block / degrade / throttle | Same for OCR: block malicious files, degrade to basic OCR on budget, throttle abusive users |
| **Config-driven policies** | §D.6 — plans.yaml | Safety policies should be config, not code |
| **Tenant identity everywhere** | §D.3 — tenant_id on every signal | Every audit log, cache key, and DB query needs tenant_id |
| **Immutable usage ledger** | §D.8 — PostgreSQL usage_events | Audit logs are INSERT-only |
| **Citations/refusal for low confidence** | §6.2 — Faithfulness gate | Same for form fields: don't fill if confidence is too low |
| **Cache includes index version** | §6.2 — No stale answers | Form schema cache must include version/hash to detect form changes |
| **Degrade before block** | OD-10 — degrade-then-block | If LLM unavailable, fall back to basic OCR + human review |

---

*End of safeguards audit.*
