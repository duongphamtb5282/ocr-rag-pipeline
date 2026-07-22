"""Tests for image preprocessing."""

from __future__ import annotations

import numpy as np

from app.ocr.preprocessor import Preprocessor

preprocessor = Preprocessor()


def test_deskew_no_skew():
    """A straight image should not be modified."""
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    result = preprocessor.deskew(img)
    assert result.shape == img.shape


def test_denoise():
    img = np.random.randint(0, 255, (50, 50, 3), dtype=np.uint8)
    result = preprocessor.denoise(img)
    assert result.shape == img.shape


def test_enhance_contrast():
    img = np.ones((50, 50, 3), dtype=np.uint8) * 128
    result = preprocessor.enhance_contrast(img)
    assert result.shape == img.shape
