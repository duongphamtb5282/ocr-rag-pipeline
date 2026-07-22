"""Input guard — document validation before any processing.

First layer of defense: validates file existence, size, magic bytes,
MIME type, and computes file hash for abuse tracking.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

ALLOWED_MAGIC_BYTES = {
    b"%PDF",           # PDF
    b"\x89PNG",        # PNG
    b"\xff\xd8\xff",   # JPEG
    b"II\x2a\x00",     # TIFF little-endian
    b"MM\x00\x2a",     # TIFF big-endian
    b"BM",             # BMP
}


class InputGuard:
    """Validates uploaded documents before any processing begins."""

    MAX_FILE_SIZE_BYTES: int = 20 * 1024 * 1024

    async def validate(self, file_path: str | Path) -> dict:
        """Run all input guard checks. Returns dict with passed/error."""
        path = Path(file_path)
        issues = []

        # 1. File exists
        if not path.exists():
            return {"passed": False, "error": "File not found", "flag": "missing_file"}

        # 2. File size check
        file_size = path.stat().st_size
        if file_size > self.MAX_FILE_SIZE_BYTES:
            return {
                "passed": False,
                "error": f"File too large: {file_size / 1024 / 1024:.1f}MB exceeds {self.MAX_FILE_SIZE_BYTES / 1024 / 1024}MB limit",
                "flag": "file_too_large",
            }

        # 3. Magic byte check (defeats extension spoofing)
        try:
            with open(path, "rb") as f:
                header = f.read(8)
            if not any(header.startswith(m) for m in ALLOWED_MAGIC_BYTES):
                return {"passed": False, "error": "File type not recognized by magic bytes", "flag": "invalid_file_type"}
        except Exception as e:
            return {"passed": False, "error": f"Could not read file: {e}", "flag": "read_error"}

        # 4. MIME type check
        try:
            import magic
            mime_type = magic.from_file(str(path), mime=True)
            allowed_mimes = {"application/pdf", "image/png", "image/jpeg", "image/tiff", "image/bmp", "image/webp"}
            if mime_type not in allowed_mimes:
                return {"passed": False, "error": f"Unsupported MIME type: {mime_type}", "flag": "unsupported_mime"}
        except ImportError:
            pass  # python-magic might not be installed; skip this check
        except Exception:
            pass

        # 5. File hash (for dedup / abuse tracking)
        file_hash = hashlib.sha256(open(path, "rb").read()).hexdigest()

        return {"passed": True, "file_hash": file_hash, "flag": None}

    async def scan_for_malware(self, file_path: str | Path) -> dict:
        """Placeholder for malware scanning integration."""
        return {"infected": False}


input_guard = InputGuard()
