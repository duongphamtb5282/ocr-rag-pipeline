"""Database and vector index migration scripts.

Usage:
    python -m scripts.migrate                  # Run all pending migrations
    python -m scripts.migrate --check          # Check migration status
    python -m scripts.migrate --db-only        # DB migrations only
    python -m scripts.migrate --vector-only    # Vector index migrations only
"""

from __future__ import annotations

import argparse
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


async def run_db_migrations() -> None:
    """Run Alembic database migrations."""
    logger.info("Running database migrations...")
    try:
        from app.db.database import create_db_and_tables
        await create_db_and_tables()
        logger.info("Database migrations complete")
    except Exception as e:
        logger.error("Database migration failed: %s", e)
        raise


async def run_vector_migrations() -> None:
    """Ensure vector DB collections exist with correct schemas."""
    logger.info("Running vector index migrations...")
    try:
        from app.vector import vector_db  # noqa: F401
        logger.info("Vector index collections ready")
    except ImportError:
        logger.info("Vector DB not configured — skipping vector migrations")
    except Exception as e:
        logger.error("Vector migration failed: %s", e)
        raise


async def check_status() -> dict:
    """Check migration status of all subsystems."""
    status = {"db": False, "vector": False, "data_dirs": False}

    try:
        from app.db.database import get_session
        async for _ in get_session():
            status["db"] = True
            break
    except Exception:
        pass

    from pathlib import Path
    data_dirs = ["raw", "processed", "storage", "index_config"]
    status["data_dirs"] = all(
        (Path(__file__).parent.parent / "data" / d).exists() for d in data_dirs
    )

    logger.info("Migration status: %s", status)
    return status


async def run_all() -> None:
    await run_db_migrations()
    await run_vector_migrations()
    logger.info("All migrations complete")


def main() -> None:
    parser = argparse.ArgumentParser(description="OCR Migration Tool")
    parser.add_argument("--check", action="store_true", help="Check migration status")
    parser.add_argument("--db-only", action="store_true", help="DB migrations only")
    parser.add_argument("--vector-only", action="store_true", help="Vector index migrations only")
    args = parser.parse_args()

    if args.check:
        asyncio.run(check_status())
    elif args.db_only:
        asyncio.run(run_db_migrations())
    elif args.vector_only:
        asyncio.run(run_vector_migrations())
    else:
        asyncio.run(run_all())


if __name__ == "__main__":
    main()
