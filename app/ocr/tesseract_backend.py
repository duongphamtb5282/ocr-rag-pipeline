"""Tesseract OCR backend."""

from __future__ import annotations

import logging
from pathlib import Path

import pytesseract

from app.config import settings

logger = logging.getLogger(__name__)


class TesseractBackend:
    """Wrapper around Tesseract 5 OCR engine."""

    def __init__(self):
        pytesseract.pytesseract.tesseract_cmd = settings.OCR_TESSERACT_CMD

    @property
    def available(self) -> bool:
        try:
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    async def extract_text(self, image_path: str | Path) -> dict:
        """Extract text with bounding boxes from an image."""
        try:
            # hOCR output includes bounding boxes and confidence
            hocr = pytesseract.image_to_pdf_or_hocr(str(image_path), extension="hocr")
            text = pytesseract.image_to_string(str(image_path))
            data = pytesseract.image_to_data(str(image_path), output_type=pytesseract.Output.DICT)

            # Build layout blocks from Tesseract data
            layout_blocks = []
            for i, word in enumerate(data.get("text", [])):
                if word.strip():
                    layout_blocks.append({
                        "text": word,
                        "confidence": data.get("conf", [0])[i],
                        "bbox": {
                            "x": data.get("left", [0])[i],
                            "y": data.get("top", [0])[i],
                            "w": data.get("width", [0])[i],
                            "h": data.get("height", [0])[i],
                        },
                    })

            # Average confidence
            confs = [b["confidence"] for b in layout_blocks if b["confidence"] > 0]
            avg_confidence = sum(confs) / len(confs) if confs else 0.0

            return {
                "text": text,
                "layout_blocks": layout_blocks,
                "confidence": avg_confidence / 100.0,  # Normalize to 0-1
                "engine": "tesseract",
            }
        except Exception as e:
            logger.error(f"Tesseract OCR failed: {e}")
            raise
