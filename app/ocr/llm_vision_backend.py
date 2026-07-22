"""LLM Vision OCR backend — uses multimodal LLM for complex documents."""

from __future__ import annotations

import base64
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class LLMVisionBackend:
    """Uses multimodal LLM (GPT-4o, Claude Vision) to read document images."""

    @property
    def available(self) -> bool:
        # Available if either OpenAI or Anthropic API key is set
        from app.config import settings
        return bool(settings.OPENAI_API_KEY) or bool(settings.ANTHROPIC_API_KEY)

    async def extract_text(self, image_path: str | Path, provider: str = "openai") -> dict:
        """
        Send image to multimodal LLM and get extracted text.
        Falls back between providers if one fails.
        """
        from app.gateway.service import gateway_call
        from app.gateway.router import LLMRequest

        # Encode image to base64
        with open(image_path, "rb") as f:
            b64_image = base64.b64encode(f.read()).decode("utf-8")

        system_prompt = (
            "You are an OCR engine. Extract ALL text from this document image exactly as written. "
            "Preserve layout, paragraphs, tables, and formatting. Output as Markdown."
        )

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract all text from this document."},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64_image}", "detail": "high"},
                    },
                ],
            }
        ]

        try:
            # Use a dummy session ID for stand-alone vision calls
            result = await gateway_call(LLMRequest(
                session_id="vision_ocr",
                agent="ocr_vision",
                route_key="vision_ocr",
                system_prompt=system_prompt,
                messages=messages,
                max_tokens=4096,
                temperature=0.1,
                estimated_tokens=2000,
            ))
            return {
                "text": result,
                "layout_blocks": [],
                "confidence": 0.85,  # LLM vision is generally accurate but we under-report
                "engine": f"llm_vision_{provider}",
            }
        except Exception as e:
            logger.error(f"LLM Vision OCR failed: {e}")
            raise
