"""System health check — verifies all subsystems are operational.

Usage:
    python -m scripts.healthcheck              # Full health check
    python -m scripts.healthcheck --quick      # Quick check (skip LLM gateway)
    python -m scripts.healthcheck --json       # Machine-readable JSON output
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class HealthResult:
    status: str  # healthy | degraded | unhealthy
    checks: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return {"status": self.status, "timestamp": self.timestamp, "checks": self.checks}


async def check_database() -> dict:
    """Check DB connectivity and basic operations."""
    try:
        from app.db.database import get_session
        async for _ in get_session():
            return {"status": "healthy", "detail": "DB reachable"}
        return {"status": "degraded", "detail": "No session returned"}
    except Exception as e:
        return {"status": "unhealthy", "detail": str(e)}


async def check_data_dirs() -> dict:
    """Check that required data directories exist and are writable."""
    from pathlib import Path

    base = Path(__file__).parent.parent
    required = ["data/raw", "data/processed", "data/storage", "data/index_config"]
    missing = [d for d in required if not (base / d).exists()]
    if missing:
        return {"status": "degraded", "detail": f"Missing directories: {', '.join(missing)}"}
    return {"status": "healthy", "detail": "All data directories exist"}


async def check_vector_db() -> dict:
    """Check vector DB connectivity."""
    try:
        from app.vector import vector_db
        healthy = await vector_db.health_check()
        if healthy:
            return {"status": "healthy", "detail": "Vector DB reachable"}
        return {"status": "degraded", "detail": "Vector DB health check failed"}
    except Exception as e:
        return {"status": "degraded", "detail": str(e)}


async def check_gateway() -> dict:
    """Check LLM gateway configuration."""
    try:
        from app.config import settings
        providers = []
        if settings.OPENAI_API_KEY:
            providers.append("openai")
        if settings.ANTHROPIC_API_KEY:
            providers.append("anthropic")
        if settings.GOOGLE_API_KEY:
            providers.append("google")
        if providers:
            return {"status": "healthy", "detail": f"Configured: {', '.join(providers)}"}
        return {"status": "degraded", "detail": "No LLM providers configured"}
    except Exception as e:
        return {"status": "unhealthy", "detail": str(e)}


async def full_health_check() -> HealthResult:
    """Run all health checks."""
    db = await check_database()
    data = await check_data_dirs()
    vector = await check_vector_db()
    gateway = await check_gateway()

    checks = {"database": db, "data_dirs": data, "vector_db": vector, "gateway": gateway}
    all_healthy = all(c["status"] == "healthy" for c in checks.values())
    any_unhealthy = any(c["status"] == "unhealthy" for c in checks.values())

    if all_healthy:
        status = "healthy"
    elif any_unhealthy:
        status = "unhealthy"
    else:
        status = "degraded"

    return HealthResult(status=status, checks=checks)


async def quick_health_check() -> HealthResult:
    """Quick health check (skip LLM gateway)."""
    db = await check_database()
    data = await check_data_dirs()

    checks = {"database": db, "data_dirs": data}
    all_healthy = all(c["status"] == "healthy" for c in checks.values())
    any_unhealthy = any(c["status"] == "unhealthy" for c in checks.values())

    status = "healthy" if all_healthy else ("unhealthy" if any_unhealthy else "degraded")
    return HealthResult(status=status, checks=checks)


def main() -> None:
    parser = argparse.ArgumentParser(description="OCR System Health Check")
    parser.add_argument("--quick", action="store_true", help="Skip LLM gateway check")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    result = asyncio.run(quick_health_check() if args.quick else full_health_check())

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(f"\n{'='*50}")
        print(f"Health Check: {result.status.upper()}")
        print(f"{'='*50}")
        for name, check in result.checks.items():
            icon = {"healthy": "✓", "degraded": "⚠", "unhealthy": "✗"}.get(check["status"], "?")
            print(f"  {icon} {name}: {check['detail']}")
        print(f"{'='*50}\n")

    sys.exit(0 if result.status == "healthy" else 1)


if __name__ == "__main__":
    main()
