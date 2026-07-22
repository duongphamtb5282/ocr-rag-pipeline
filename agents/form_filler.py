"""Agent 5: Form Filler — fills web form fields using Playwright."""

from __future__ import annotations

import logging
from pathlib import Path

from app.config import settings
from graph.state import OCRFormFillState
from tools.browser_tools import browser_tools

logger = logging.getLogger(__name__)


async def form_filler_node(state: OCRFormFillState) -> dict:
    """Fill the target web form with approved field values."""
    target_url = state.get("target_url")
    mappings = state.get("field_mappings", {})
    corrections = state.get("human_corrections", {})
    fill_mode = state.get("fill_mode", "safe_submit")

    if not target_url or not mappings:
        return {"fill_status": "failed", "fill_errors": [{"error": "No URL or mappings"}]}

    logger.info(f"Filling form at {target_url} with {len(mappings)} fields (mode: {fill_mode})")

    # 1. Navigate to URL
    navigated = await browser_tools.navigate(target_url)
    if not navigated:
        return {"fill_status": "failed", "fill_errors": [{"error": f"Could not navigate to {target_url}"}]}

    # 2. CAPTCHA check before filling
    captcha = await browser_tools.detect_captcha()
    if captcha:
        logger.warning("CAPTCHA detected — stopping form fill")
        return {"fill_status": "captcha_blocked", "fill_errors": [{"error": "CAPTCHA detected"}]}

    # 3. Fill each mapped field
    filled = 0
    total = len(mappings)
    errors = []

    for field_key, mapping in mappings.items():
        form_field_id = mapping.get("form_field_id")
        if not form_field_id:
            errors.append({"field": field_key, "error": "No form_field_id in mapping"})
            continue

        value = corrections.get(field_key) or state.get("extracted_fields", {}).get(field_key, {}).get("value")
        if value is None:
            errors.append({"field": field_key, "error": "No value available"})
            continue

        # In test_fill mode, take screenshot but don't fill
        if fill_mode == "test_fill":
            filled += 1
            continue

        try:
            selector = f"#{form_field_id}"
            await browser_tools.fill_field(selector, str(value))
            filled += 1
        except Exception as e:
            errors.append({"field": field_key, "selector": form_field_id, "error": str(e)})

    # 4. Take proof screenshot
    screenshot_path = str(Path(settings.SCREENSHOT_DIR) / f"proof_{state['session_id']}.png")
    await browser_tools.screenshot(screenshot_path)

    return {
        "fill_status": "success" if filled == total else "partial",
        "fill_errors": errors if errors else None,
        "submission_proof": screenshot_path,
        "filled_fields_count": filled,
        "total_fields_count": total,
    }
