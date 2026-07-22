"""Offline evaluation — batch evaluate system against golden dataset.

Usage:
    python -m evaluation.offline_eval                  # Run full eval
    python -m evaluation.offline_eval --tag smoke      # Run smoke tests only
    python -m evaluation.offline_eval --report         # Generate report
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

GOLDEN_DATASET_PATH = Path(__file__).parent / "golden_dataset.json"
EVAL_RESULTS_DIR = Path(__file__).parent / "eval_results"


def _load_golden() -> dict:
    """Load the golden dataset."""
    if not GOLDEN_DATASET_PATH.exists():
        raise FileNotFoundError(f"Golden dataset not found at {GOLDEN_DATASET_PATH}")
    with open(GOLDEN_DATASET_PATH) as f:
        return json.load(f)


async def evaluate_session(test_case: dict) -> dict:
    """Run a single test case against the system and compare results.

    This is a placeholder — in production, this would:
    1. Upload a test document via the API
    2. Wait for processing to complete
    3. Compare extracted fields against expected fields
    4. Score accuracy, confidence, and latency
    """
    name = test_case.get("name", "unnamed")
    expected = test_case.get("expected_fields", {})

    # Simulated evaluation result
    return {
        "name": name,
        "passed": False,  # Overridden after real comparison
        "expected_fields": len(expected),
        "matched_fields": 0,
        "field_accuracy": 0.0,
        "avg_confidence": 0.0,
        "latency_ms": 0,
        "timestamp": datetime.utcnow().isoformat(),
        "notes": f"Placeholder — implement actual API call for {name}",
    }


async def run_eval(tag: str | None = None) -> list[dict]:
    """Run evaluation on the golden dataset, optionally filtered by tag."""
    dataset = _load_golden()
    sessions = dataset.get("sessions", [])

    if tag:
        sessions = [s for s in sessions if tag in s.get("tags", [])]
        logger.info("Filtered to %d sessions with tag '%s'", len(sessions), tag)

    results = []
    for test_case in sessions:
        logger.info("Evaluating: %s", test_case.get("name", "unnamed"))
        result = await evaluate_session(test_case)
        results.append(result)

    return results


def _score_summary(results: list[dict]) -> dict:
    """Compute aggregate scores across all evaluation results."""
    if not results:
        return {"total": 0, "passed": 0, "failed": 0, "accuracy": 0.0}

    total = len(results)
    passed = sum(1 for r in results if r.get("passed"))
    field_accuracies = [r.get("field_accuracy", 0.0) for r in results]

    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / total * 100, 1) if total else 0.0,
        "avg_field_accuracy": round(sum(field_accuracies) / len(field_accuracies), 3) if field_accuracies else 0.0,
    }


def save_report(results: list[dict]) -> Path:
    """Save evaluation report to eval_results/."""
    EVAL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "timestamp": datetime.utcnow().isoformat(),
        "summary": _score_summary(results),
        "results": results,
    }
    path = EVAL_RESULTS_DIR / f"eval_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
    logger.info("Report saved to %s", path)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="OCR Offline Evaluation")
    parser.add_argument("--tag", help="Filter by tag (smoke, regression, edge_case)")
    parser.add_argument("--report", action="store_true", help="Save report to eval_results/")
    args = parser.parse_args()

    results = asyncio.run(run_eval(tag=args.tag))

    summary = _score_summary(results)
    print(f"\n{'='*50}")
    print(f"Evaluation Results: {summary['passed']}/{summary['total']} passed")
    print(f"{'='*50}")
    print(f"  Pass rate:       {summary['pass_rate']}%")
    print(f"  Avg accuracy:    {summary['avg_field_accuracy']}")
    print(f"{'='*50}\n")

    for r in results:
        icon = "✓" if r.get("passed") else "✗"
        print(f"  {icon} {r['name']}: {r.get('matched_fields', 0)}/{r.get('expected_fields', 0)} fields matched")

    if args.report:
        path = save_report(results)
        print(f"\nReport: {path}")


if __name__ == "__main__":
    main()
