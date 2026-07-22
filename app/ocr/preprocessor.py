"""Document image preprocessing — deskew, denoise, enhance contrast."""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class Preprocessor:
    """Image preprocessing pipeline for OCR quality improvement."""

    @staticmethod
    def load_image(path: str | Path) -> np.ndarray:
        """Load image from path, converting to OpenCV BGR format."""
        pil_image = Image.open(path)
        if pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")
        return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

    @staticmethod
    def deskew(image: np.ndarray) -> np.ndarray:
        """Correct skew in scanned documents."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        coords = np.column_stack(np.where(gray > 0))
        if len(coords) == 0:
            return image
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = 90 + angle
        if abs(angle) < 0.5:
            return image  # No significant skew
        h, w = image.shape[:2]
        center = (w // 2, h // 2)
        matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        return cv2.warpAffine(image, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

    @staticmethod
    def denoise(image: np.ndarray) -> np.ndarray:
        """Remove noise from scanned images."""
        return cv2.fastNlMeansDenoisingColored(image, None, 10, 10, 7, 21)

    @staticmethod
    def enhance_contrast(image: np.ndarray) -> np.ndarray:
        """Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)."""
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        lab = cv2.merge([l, a, b])
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    @staticmethod
    def binarize(image: np.ndarray) -> np.ndarray:
        """Convert to binary (black/white) for Tesseract."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)

    @staticmethod
    def detect_dpi(image: np.ndarray) -> int:
        """Estimate DPI from image metadata. Returns 0 if unknown."""
        return 0  # Would need header parsing for actual DPI

    def preprocess(self, image_path: str | Path, strategy: str = "full") -> np.ndarray:
        """Run full preprocessing pipeline."""
        image = self.load_image(image_path)
        if strategy in ("full", "deskew"):
            image = self.deskew(image)
        if strategy in ("full", "denoise"):
            image = self.denoise(image)
        if strategy in ("full", "contrast"):
            image = self.enhance_contrast(image)
        return image


preprocessor = Preprocessor()
