"""Go / No-Go summary generation and JUnit XML output.

Produces:
1. JUnit XML consumable by GitHub Actions and CI pipelines.
2. Go / No-Go verdict dict based on pass/fail counts and coverage threshold.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------
# JUnit XML generation
# -----------------------------------------------------------------


def parse_junit_xml(input_path: Path) -> Dict[str, Any]:
    """Parse an existing JUnit XML file and extract summary stats.

    Args:
        input_path: Path to results.xml produced by pytest --junitxml.

    Returns:
        Dict with keys: "tests", "failures", "errors", "time".
    """
    try:
        from xml.etree import ElementTree as ET

        tree = ET.parse(input_path)
        root = tree.getroot()

        # Handle both <testsuites> root and direct <testsuite> root element
        testsuites = root.find("testsuites")
        if testsuites is not None:
            suite = testsuites.find("testsuite")
        else:
            # If root element IS the testsuite, use it directly
            if root.tag == "testsuite":
                suite = root
            else:
                suite = root.find("testsuite")

        if suite is None:
            logger.warning("No testsuite element found in %s", input_path)
            return {"tests": 0, "failures": 0, "errors": 0, "time": 0.0}

        tests = int(suite.get("tests", 0))
        failures = int(suite.get("failures", 0))
        errors = int(suite.get("errors", 0))
        time_val = float(suite.get("time", 0.0))

        logger.debug(
            "Parsed JUnit XML: tests=%d failures=%d errors=%g time=%s",
            tests,
            failures,
            errors,
            time_val,
        )
        return {"tests": tests, "failures": failures, "errors": errors, "time": time_val}
    except Exception as exc:  # pylint: disable-broad-excuse
        logger.error("Failed to parse JUnit XML %s: %s", input_path, exc)
        return {"tests": 0, "failures": 0, "errors": 0, "time": 0.0}


def generate_junit_xml(results_path: Path, output_path: Path) -> None:
    """Convert pytest results to JUnit XML format.

    If output_path already exists, it is overwritten.

    Args:
        results_path: Path to the pytest-generated results.xml.
        output_path: Where to write the final JUnit XML (may be same as input).
    """
    stats = parse_junit_xml(results_path)

    # Build a minimal valid JUnit XML
    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<testsuites>",
        '  <testsuite name="gpu-driver-test-framework"',
        f'    tests="{stats["tests"]}"',
        f'    failures="{stats["failures"]}"',
        f'    errors="{stats["errors"]}"',
        f'    time="{stats["time"]}"',
        ">",
        "  </testsuite>",
        "</testsuites>",
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(xml_lines) + "\n")
    logger.info("Generated JUnit XML at %s", output_path)


# -----------------------------------------------------------------
# Go / No-Go summary
# -----------------------------------------------------------------


COVERAGE_THRESHOLD = 80.0  # percent


def generate_go_no_go(
    pass_count: int,
    fail_count: int,
    coverage_pct: float,
    threshold: float = COVERAGE_THRESHOLD,
) -> Dict[str, Any]:
    """Generate a Go / No-Go summary dict.

    The verdict is derived from hard rules:
    - No-go if any tests failed OR coverage below threshold.
    - Go otherwise.

    Args:
        pass_count: Number of tests that passed.
        fail_count: Number of tests that failed.
        coverage_pct: Coverage percentage (0-100).
        threshold: Coverage threshold percentage (default 80%).

    Returns:
        Dict with keys:
        - "verdict": "go" or "no-go"
        - "pass_count": int
        - "fail_count": int
        - "coverage_pct": float
        - "threshold_met": bool
        - "message": human-readable summary
    """
    threshold_met = coverage_pct >= threshold

    if fail_count > 0 or not threshold_met:
        verdict = "no-go"
    else:
        verdict = "go"

    message = (
        f"Verdict: {verdict.upper()} | "
        f"Pass: {pass_count}, Fail: {fail_count}, "
        f"Coverage: {coverage_pct:.1f}%, "
        f"Threshold met: {threshold_met}"
    )

    result: Dict[str, Any] = {
        "verdict": verdict,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "coverage_pct": round(coverage_pct, 1),
        "threshold_met": threshold_met,
        "message": message,
    }

    logger.info("Go/No-Go summary: %s", result)
    return result


def write_go_no_go(
    result: Dict[str, Any],
    output_path: Path,
) -> None:
    """Write the Go/No-Go dict to a JSON file.

    Args:
        result: Dict as returned by generate_go_no_go().
        output_path: Path to write the JSON file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n")
    logger.info("Wrote Go/No-Go summary to %s", output_path)