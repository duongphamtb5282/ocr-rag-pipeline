"""DocTR OCR backend — deep learning-based layout analysis and OCR.
 Requires: pip install python-doctr[torch] or python-doctr[tf]
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from app.ocr.preprocessor import preprocessor

logger = logging.getLogger(__name__)


class DocTRBackend:
    """Deep learning OCR backend using DocTR for layout analysis and text recognition."""

    def __init__(self):
        self._model = None
        self._recognizer = None
        self._detector = None

    @property
    def available(self) -> bool:
        try:
            import doctr
            return True
        except ImportError:
            return False

    async def _load_models(self):
        """Lazy-load DocTR models (expensive, only done once)."""
        if self._model is not None:
            return
        try:
            from doctr.io import DocumentFile
            from doctr.models import ocr_predictor

            # Load a pre-trained OCR predictor (detection + recognition)
            self._model = ocr_predictor(
                det_arch="db_resnet50",      # Differentiable Binarization for text detection
                reco_arch="crnn_vgg16_bn",   # CRNN for text recognition
                pretrained=True,
            )
            logger.info("DocTR models loaded (db_resnet50 + crnn_vgg16_bn)")
        except ImportError as e:
            logger.error(f"DocTR not installed. Install with: pip install python-doctr[torch]")
            raise
        except Exception as e:
            logger.error(f"Failed to load DocTR models: {e}")
            raise

    async def extract_text(self, image_path: str | Path) -> dict:
        """
        Extract text with full layout analysis (paragraphs, tables, columns).
        Returns structured blocks with bounding boxes and confidence scores.
        """
        from doctr.io import DocumentFile

        await self._load_models()
        path = Path(image_path)

        # Load document (supports PDF and images natively)
        if path.suffix.lower() == ".pdf":
            doc = DocumentFile.from_pdf(str(path))
        else:
            doc = DocumentFile.from_images(str(path))

        all_text = []
        layout_blocks = []
        confidences = []

        for page_num, page in enumerate(doc):
            # Run OCR
            result = self._model([page])

            # Extract blocks from the result
            for block in result.pages[0].blocks:
                for line in block.lines:
                    line_text = " ".join(word.value for word in line.words)
                    if line_text.strip():
                        # Calculate bounding box from words
                        if line.words:
                            xs = [w.geometry[0][0] for w in line.words] + [w.geometry[1][0] for w in line.words]
                            ys = [w.geometry[0][1] for w in line.words] + [w.geometry[1][1] for w in line.words]
                            bbox = {
                                "x": min(xs) * page.shape[1],
                                "y": min(ys) * page.shape[0],
                                "w": (max(xs) - min(xs)) * page.shape[1],
                                "h": (max(ys) - min(ys)) * page.shape[0],
                            }
                        else:
                            bbox = {"x": 0, "y": 0, "w": 0, "h": 0}

                        word_confidences = [w.confidence for w in line.words if hasattr(w, "confidence")]
                        avg_conf = sum(word_confidences) / len(word_confidences) if word_confidences else 0.0

                        layout_blocks.append({
                            "text": line_text,
                            "confidence": avg_conf,
                            "bbox": bbox,
                            "page": page_num,
                            "block_type": str(type(block).__name__),
                        })
                        all_text.append(line_text)
                        confidences.append(avg_conf)

        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return {
            "text": "\n".join(all_text),
            "layout_blocks": layout_blocks,
            "confidence": avg_confidence,
            "engine": "doctr",
            "page_count": len(doc),
        }


doctr_backend = DocTRBackend()
