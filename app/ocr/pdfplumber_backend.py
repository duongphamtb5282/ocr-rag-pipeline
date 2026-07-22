"""PDF text extraction backend using pdfplumber (for digital, non-scanned PDFs)."""

from __future__ import annotations

import logging
from pathlib import Path

import pdfplumber

logger = logging.getLogger(__name__)


class PdfPlumberBackend:
    """Extracts text directly from digital PDFs without OCR."""

    @property
    def available(self) -> bool:
        return True

    async def extract_text(self, pdf_path: str | Path) -> dict:
        """Extract text and layout from a digital PDF."""
        all_text = []
        layout_blocks = []

        with pdfplumber.open(str(pdf_path)) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text() or ""
                all_text.append(text)

                # Get words with positions
                words = page.extract_words()
                for word in words:
                    layout_blocks.append({
                        "text": word.get("text", ""),
                        "confidence": 1.0,
                        "bbox": {
                            "x": word.get("x0", 0),
                            "y": word.get("top", 0),
                            "w": word.get("x1", 0) - word.get("x0", 0),
                            "h": word.get("bottom", 0) - word.get("top", 0),
                        },
                        "page": page_num,
                    })

                # Extract tables
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        row_text = " | ".join(str(c) for c in row if c)
                        if row_text.strip():
                            all_text.append(row_text)

        return {
            "text": "\n".join(all_text),
            "layout_blocks": layout_blocks,
            "confidence": 1.0,
            "engine": "pdfplumber",
            "page_count": len(list(pdf.pages)),
        }
