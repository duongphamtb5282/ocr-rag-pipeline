"""Agent 2: Field Extractor — extracts structured fields from OCR output."""

from __future__ import annotations

import json
import logging

from app.gateway.router import LLMRequest
from app.gateway.service import gateway_call
from graph.state import OCRFormFillState
from tools.validation import validation_tools
from prompts.registry import get_system_prompt

logger = logging.getLogger(__name__)


async def field_extractor_node(state: OCRFormFillState) -> dict:
    """Extract structured fields from OCR text."""
    raw_text = state.get("raw_text", "")
    if not raw_text or not raw_text.strip():
        return {"extracted_fields": {}, "low_confidence_fields": []}

    logger.info(f"Extracting fields from {len(raw_text)} chars of OCR text")

    try:
        system_prompt = get_system_prompt("field_extraction")
        result = await gateway_call(LLMRequest(
            session_id=state["session_id"],
            agent="field_extractor",
            route_key="field_extraction",
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": f"OCR Text:\n{raw_text[:8000]}"}],
            max_tokens=2048,
            temperature=0.0,
            estimated_tokens=2000,
        ))

        parsed = json.loads(result)
        fields = parsed.get("fields", [])

        # Normalize and validate each field
        extracted = {}
        low_conf = []
        for field in fields:
            name = field.get("field_name", "unknown")
            value = field.get("value", "")
            conf = float(field.get("confidence", 0.5))
            ftype = field.get("type", "text")

            # Normalize based on type
            if ftype == "date" and value:
                val_result = validation_tools.validate_date(value)
                if val_result["valid"]:
                    value = val_result["parsed"]
                else:
                    conf *= 0.8

            elif ftype == "currency" and value:
                val_result = validation_tools.normalize_currency(value)
                if val_result["valid"]:
                    value = val_result["value"]
                else:
                    conf *= 0.8

            elif ftype == "phone" and value:
                val_result = validation_tools.validate_phone(value)
                if val_result["valid"]:
                    value = val_result["normalized"]

            elif ftype == "email" and value:
                val_result = validation_tools.validate_email(value)
                if not val_result["valid"]:
                    conf *= 0.7

            extracted[name] = {"value": value, "confidence": round(conf, 2), "type": ftype}
            if conf < 0.8:
                low_conf.append(name)

        return {
            "extracted_fields": extracted,
            "low_confidence_fields": low_conf,
        }

    except Exception as e:
        logger.error(f"Field extraction failed: {e}")
        return {"extracted_fields": {}, "low_confidence_fields": []}
