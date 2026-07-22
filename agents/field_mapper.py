"""Agent 4: Field Mapper — maps extracted fields to web form fields."""

from __future__ import annotations

import json
import logging

from app.gateway.router import LLMRequest
from app.gateway.service import gateway_call
from graph.state import OCRFormFillState
from prompts.registry import get_system_prompt

logger = logging.getLogger(__name__)


async def field_mapper_node(state: OCRFormFillState) -> dict:
    """Map extracted fields to form fields using semantic matching."""
    extracted = state.get("extracted_fields", {})
    form_fields = state.get("form_fields", [])

    if not extracted:
        return {"field_mappings": {}, "unmapped_fields": list(extracted.keys()) if extracted else []}

    if not form_fields:
        return {"field_mappings": {}, "unmapped_fields": list(extracted.keys())}

    logger.info(f"Mapping {len(extracted)} extracted fields to {len(form_fields)} form fields")

    extracted_summary = {k: {"value": str(v.get("value", "")), "type": v.get("type", "text")} for k, v in extracted.items()}
    form_summary = {f["field_id"]: {"label": f.get("label", ""), "type": f.get("type", "text")} for f in form_fields}

    try:
        system_prompt = get_system_prompt("field_mapping")
        result = await gateway_call(LLMRequest(
            session_id=state["session_id"],
            agent="field_mapper",
            route_key="semantic_mapping",
            system_prompt=system_prompt,
            messages=[{
                "role": "user",
                "content": f"Extracted fields: {json.dumps(extracted_summary)}\n\nForm fields: {json.dumps(form_summary)}",
            }],
            max_tokens=2048,
            temperature=0.1,
            estimated_tokens=1000,
        ))

        parsed = json.loads(result)
        mappings = parsed.get("mappings", {})
        unmapped = parsed.get("unmapped", [])

        # Validate mappings against actual field keys
        valid_mappings = {}
        for ext_key, mapping in mappings.items():
            if ext_key in extracted:
                form_id = mapping.get("form_field_id")
                if any(f["field_id"] == form_id for f in form_fields):
                    valid_mappings[ext_key] = mapping

        return {
            "field_mappings": valid_mappings,
            "unmapped_fields": unmapped,
        }

    except Exception as e:
        logger.error(f"Field mapping failed: {e}")
        return {"field_mappings": {}, "unmapped_fields": list(extracted.keys())}
