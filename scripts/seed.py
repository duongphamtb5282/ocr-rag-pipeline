"""Seed golden dataset and initial data into the system.

Usage:
    python -m scripts.seed                     # Seed golden dataset
    python -m scripts.seed --demo              # Seed with demo sessions
    python -m scripts.seed --clear             # Clear all seeded data
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import shutil
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

GOLDEN_DATASET_PATH = Path(__file__).parent.parent / "evaluation" / "golden_dataset.json"
DATA_DIR = Path(__file__).parent.parent / "data"


def _load_golden_dataset() -> dict:
    """Load the golden dataset for evaluation."""
    if not GOLDEN_DATASET_PATH.exists():
        logger.warning("No golden dataset found at %s", GOLDEN_DATASET_PATH)
        return {"sessions": []}
    with open(str(GOLDEN_DATASET_PATH)) as f:
        return json.load(f)


async def seed_golden_dataset() -> None:
    """Ensure the golden dataset is loaded into the system."""
    dataset = _load_golden_dataset()
    count = len(dataset.get("sessions", []))
    logger.info("Golden dataset loaded: %d sessions ready for evaluation", count)


async def seed_demo_data() -> None:
    """Create demo sessions with sample documents for testing."""
    demo_dir = DATA_DIR / "raw" / "demo"
    demo_dir.mkdir(parents=True, exist_ok=True)

    # Create a minimal demo document placeholder
    readme = demo_dir / "README.txt"
    readme.write_text(
        "Place sample PDF/image files here to seed demo sessions.\n"
        "Run: python -m scripts.seed --demo\n"
    )
    logger.info("Demo data directory ready at %s", demo_dir)
    logger.info("Copy sample documents into %s and re-run.", demo_dir)


async def clear_seeded_data() -> None:
    """Remove all seeded/demo data."""
    demo_dir = DATA_DIR / "raw" / "demo"
    if demo_dir.exists():
        shutil.rmtree(demo_dir)
        logger.info("Cleared demo data")
    logger.info("Seeded data cleared.")


def main() -> None:
    parser = argparse.ArgumentParser(description="OCR Seed & Data Management")
    parser.add_argument("--demo", action="store_true", help="Seed demo sessions")
    parser.add_argument("--clear", action="store_true", help="Clear all seeded data")
    args = parser.parse_args()

    if args.clear:
        asyncio.run(clear_seeded_data())
    elif args.demo:
        asyncio.run(seed_demo_data())
    else:
        asyncio.run(seed_golden_dataset())


if __name__ == "__main__":
    main()
