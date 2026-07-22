"""OCR toolbox — unified interface for all OCR backends with fallback logic.

Canonical location. Replaces app/ocr/toolbox.py
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from app.config import settings
from app.ocr.doctr_backend import doctr_backend
from app.ocr.pdfplumber_backend import PdfPlumberBackend
from app.ocr.preprocessor import preprocessor
from app.ocr.tesseract_backend import TesseractBackend

logger = logging.getLogger(__name__)


class OCRToolbox:
    """
    Unified OCR interface with multi-backend support and automatic fallback.
    Strategy: pdfplumber (digital) -> Tesseract (print) -> DocTR (layout) -> LLM Vision (hard).
    """

    FALLBACK_CHAIN = ["pdfplumber", "tesseract", "doctr", "llm_vision"]

    def __init__(self):
        self.pdfplumber = PdfPlumberBackend()
        self.tesseract = TesseractBackend()
        self.llm_vision = None

    async def extract(self, file_path: str | Path, strategy: str = "auto") -> dict:
        """Extract text from document using the specified strategy."""
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        is_digital_pdf = await self._is_digital_pdf(file_path) if file_path.suffix.lower() == ".pdf" else False

        if strategy == "auto":
            strategy = "pdfplumber" if is_digital_pdf else "tesseract"

        last_error = None
        fallback_used = False

        try:
            if strategy == "pdfplumber" and is_digital_pdf:
                result = await self.pdfplumber.extract_text(file_path)
                if result["text"].strip():
                    return result

            elif strategy == "tesseract":
                images = await self._pdf_to_images(file_path) if file_path.suffix.lower() == ".pdf" else [file_path]
                all_text, all_blocks, confidences = [], [], []

                for img_path in images:
                    processed = preprocessor.preprocess(img_path, strategy="full")
                    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                        import cv2
                        cv2.imwrite(tmp.name, processed)
                        result = await self.tesseract.extract_text(tmp.name)
                        all_text.append(result["text"])
                        all_blocks.extend(result["layout_blocks"])
                        confidences.append(result["confidence"])

                avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
                if avg_conf < 0.7:
                    logger.info(f"Tesseract confidence low ({avg_conf:.2f}), trying DocTR")
                    if doctr_backend.available:
                        return await self._run_doctr(file_path)
                    return await self._fallback_to_llm(file_path)

                return {
                    "text": "\n".join(all_text),
                    "layout_blocks": all_blocks,
                    "confidence": avg_conf,
                    "engine": "tesseract",
                    "fallback_used": fallback_used,
                }

            elif strategy == "doctr":
                if doctr_backend.available:
                    return await self._run_doctr(file_path)
                raise RuntimeError("DocTR not installed")

            elif strategy == "llm_vision":
                return await self._fallback_to_llm(file_path)

        except Exception as e:
            logger.warning(f"Strategy {strategy} failed: {e}")
            last_error = e

        for fallback in self.FALLBACK_CHAIN:
            if fallback == strategy:
                continue
            try:
                result = await self.extract(file_path, strategy=fallback)
                result["fallback_used"] = True
                return result
            except Exception as e:
                last_error = e

        raise RuntimeError(f"All OCR backends failed. Last error: {last_error}")

    async def _is_digital_pdf(self, file_path: Path) -> bool:
        try:
            import pdfplumber
            with pdfplumber.open(str(file_path)) as pdf:
                for page in pdf.pages[:3]:
                    text = page.extract_text()
                    if text and len(text.strip()) > 50:
                        return True
                return False
        except Exception:
            return False

    async def _pdf_to_images(self, pdf_path: Path) -> list[Path]:
        from pdf2image import convert_from_path
        images = convert_from_path(str(pdf_path), dpi=300)
        paths = []
        for i, img in enumerate(images):
            tmp = Path(tempfile.mktemp(suffix=f"_page_{i}.png"))
            img.save(tmp)
            paths.append(tmp)
        return paths

    async def _run_doctr(self, file_path: Path) -> dict:
        result = await doctr_backend.extract_text(str(file_path))
        result["fallback_used"] = True
        return result

    async def _fallback_to_llm(self, file_path: Path) -> dict:
        from app.ocr.llm_vision_backend import LLMVisionBackend
        if self.llm_vision is None:
            self.llm_vision = LLMVisionBackend()
        if file_path.suffix.lower() == ".pdf":
            images = await self._pdf_to_images(file_path)
            all_text = [await self.llm_vision.extract_text(img_path) for img_path in images]
            return {
                "text": "\n\n".join(t["text"] for t in all_text),
                "layout_blocks": [],
                "confidence": 0.85,
                "engine": "llm_vision",
                "fallback_used": True,
            }
        return await self.llm_vision.extract_text(file_path)


ocr_toolbox = OCRToolbox()
