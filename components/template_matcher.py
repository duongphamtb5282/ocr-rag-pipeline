"""Template matcher — finds similar past documents using layout fingerprinting.

Canonical location — replaces app/graph/tools/template_matcher.py
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.gateway.service import gateway_embed

logger = logging.getLogger(__name__)


@dataclass
class TemplateMatch:
    template_id: str
    similarity: float
    expected_fields: list[str]


class TemplateMatcher:
    """Find similar previously-processed document templates using vector search."""

    async def find_match(self, doc_type: str, layout_fingerprint: str) -> TemplateMatch | None:
        """Search for a similar document template by layout. Returns None if no match."""
        if not layout_fingerprint:
            return None

        try:
            embedding = await gateway_embed(layout_fingerprint, model="text-embedding-3-small", dimensions=512)
            return None  # Placeholder — wire to vector DB search in production
        except Exception as e:
            logger.warning(f"Template matching failed (non-critical): {e}")
            return None

    @staticmethod
    def fingerprint_layout(layout_blocks: list[dict]) -> str:
        """Create a lightweight text fingerprint from layout blocks."""
        if not layout_blocks:
            return ""
        elements = []
        for block in layout_blocks[:50]:
            text = block.get("text", "")
            bbox = block.get("bbox", {})
            elements.append(f"{bbox.get('x',0)},{bbox.get('y',0)}:{text[:50]}")
        return "|".join(elements)


template_matcher = TemplateMatcher()
