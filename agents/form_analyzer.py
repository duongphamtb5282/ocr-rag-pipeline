"""Agent 3: Form Analyzer — visits target URL and extracts form structure."""

from __future__ import annotations

import json
import logging
from urllib.parse import urlparse

from app.gateway.router import LLMRequest
from app.gateway.service import gateway_call
from graph.state import OCRFormFillState
from tools.browser_tools import browser_tools
from prompts.registry import get_system_prompt

logger = logging.getLogger(__name__)


async def form_analyzer_node(state: OCRFormFillState) -> dict:
    """Analyze the target web form."""
    target_url = state.get("target_url")
    if not target_url:
        return {"form_fields": None, "form_cache_used": False}

    logger.info(f"Analyzing form at: {target_url}")

    # 1. URL safety check
    parsed = urlparse(target_url)
    if parsed.scheme not in ("http", "https"):
        return {"form_fields": None, "form_cache_used": False, "url_safety_ok": False}

    # 2. Try to extract form fields via Playwright
    try:
        raw_fields = await browser_tools.extract_form_fields(target_url)
        if raw_fields:
            fields_data = [
                {
                    "field_id": f.field_id,
                    "selector": f.selector,
                    "label": f.label,
                    "type": f.type,
                    "required": f.required,
                    "accepted_values": f.accepted_values,
                }
                for f in raw_fields
            ]
        else:
            fields_data = []

        # 3. Enrich with LLM semantic analysis if we have fields
        if fields_data:
            try:
                system_prompt = get_system_prompt("form_analysis")
                result = await gateway_call(LLMRequest(
                    session_id=state["session_id"],
                    agent="form_analyzer",
                    route_key="form_analysis",
                    system_prompt=system_prompt,
                    messages=[{"role": "user", "content": json.dumps(fields_data)}],
                    max_tokens=1024,
                    temperature=0.0,
                    estimated_tokens=500,
                ))
                enriched = json.loads(result)
                return {"form_fields": enriched.get("form_fields", fields_data), "form_cache_used": False}
            except Exception:
                return {"form_fields": fields_data, "form_cache_used": False}
        else:
            return {"form_fields": [], "form_cache_used": False}

    except Exception as e:
        logger.error(f"Form analysis failed: {e}")
        return {"form_fields": None, "form_cache_used": False}
