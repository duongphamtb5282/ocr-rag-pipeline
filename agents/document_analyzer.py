"""Agent 1: Document Analyzer — classifies doc type, quality, picks OCR strategy."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.gateway.router import LLMRequest
from app.gateway.service import gateway_call
from graph.state import OCRFormFillState
from prompts.registry import get_system_prompt

logger = logging.getLogger(__name__)


async def document_analyzer_node(state: OCRFormFillState) -> dict:
    """Analyze document and determine OCR strategy."""
    logger.info(f"Analyzing document: {state['document_path']}")

    doc_path = Path(state["document_path"])
    file_ext = doc_path.suffix.lower()
    file_size = doc_path.stat().st_size if doc_path.exists() else 0

    features = f"File: {doc_path.name}, Ext: {file_ext}, Size: {file_size} bytes"

    try:
        system_prompt = get_system_prompt("document_analysis")
        result = await gateway_call(LLMRequest(
            session_id=state["session_id"],
            agent="document_analyzer",
            route_key="doc_classification",
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": features}],
            max_tokens=256,
            temperature=0.0,
            estimated_tokens=200,
        ))

        parsed = json.loads(result)
        doc_type = parsed.get("doc_type", "other")
        quality = parsed.get("quality", "medium")
        strategy = parsed.get("ocr_strategy", "tesseract")

        # Override for digital PDFs
        if file_ext == ".pdf" and strategy == "none":
            strategy = "pdfplumber"

        return {
            "doc_type": doc_type,
            "doc_quality": quality,
            "ocr_strategy": strategy,
        }

    except Exception as e:
        logger.warning(f"LLM classification failed, using rules: {e}")
        # Rule-based fallback
        if file_ext == ".pdf":
            return {"doc_type": "digital_pdf", "doc_quality": "medium", "ocr_strategy": "pdfplumber"}
        elif file_ext in (".png", ".jpg", ".jpeg", ".tiff", ".bmp"):
            return {"doc_type": "scanned_form", "doc_quality": "medium", "ocr_strategy": "tesseract"}
        else:
            return {"doc_type": "other", "doc_quality": "low", "ocr_strategy": "tesseract"}
