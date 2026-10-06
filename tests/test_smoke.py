"""Smoke test suite for GPU driver test framework.

These tests validate the core framework functions: matrix expansion,
artefact collection, and report generation. They are designed to run
without a real GPU by using mock fixtures.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from framework.matrix import load_matrix, expand_matrix
from framework.artifacts import ArtifactCollector
from framework.report import generate_go_no_go, generate_junit_xml


# -----------------------------------------------------------------
# Matrix expansion smoke test
# -----------------------------------------------------------------


@pytest.mark.smoke
class TestMatrixExpansion:
    """Verify matrix YAML loading and expansion."""

    def test_matrix_yaml_loads(self) -> None:
        """Load matrix.yaml exists and has expected structure."""
        matrix = load_matrix()
        assert "os_builds" in matrix
        assert "gpu_skus" in matrix
        assert len(matrix["os_builds"]) > 0
        assert len(matrix["gpu_skus"]) > 0

    def test_matrix_expansion(self) -> None:
        """Expanded matrix should produce os_build × gpu_sku combos."""
        matrix = load_matrix()
        configs = expand_matrix(matrix)
        # At minimum 1 × 1 = 1 config; our default has 2 × 3 = 6
        assert len(configs) >= 1
        # Verify each config has required keys
        for cfg in configs:
            assert "os_build" in cfg
            assert "gpu_sku" in cfg


# -----------------------------------------------------------------
# Artefact collection smoke test (mock fixtures)
# -----------------------------------------------------------------


@pytest.mark.smoke
class TestArtefactCollection:
    """Verify artefact collection on failure and cleanup on pass."""

    def test_collect_artefacts_on_failure(self, tmp_path, driver_install, telemetry) -> None:
        """Collect artefacts when a test fails; bundle contains expected files."""
        collector = ArtifactCollector()
        test_name = "test_sample_failure"

        # Simulate a failure by collecting artefacts
        bundle = collector.collect_on_failure(
            test_name=test_name,
            error=RuntimeError("deliberate failure"),
            driver_install=driver_install,
            telemetry=telemetry,
        )

        # Bundle should exist and contain files
        assert bundle.exists()
        assert (bundle / "driver_version.txt").exists()
        assert (bundle / "gpu_state.json").exists()
        assert (bundle / "event_viewer.json").exists()

        # Verify content types
        version = (bundle / "driver_version.txt").read_text().strip()
        assert version != ""

        gpu_state = json.loads((bundle / "gpu_state.json").read_text())
        assert "gpus" in gpu_state

        events = json.loads((bundle / "event_viewer.json").read_text())
        assert isinstance(events, list)

    def test_cleanup_on_pass(self, tmp_path, driver_install, telemetry) -> None:
        """Cleanup artefacts when test passes; bundle removed."""
        collector = ArtifactCollector()
        test_name = "test_sample_pass"

        # First create a bundle (simulate failure then immediate pass scenario)
        bundle = collector.collect_on_failure(
            test_name=test_name,
            error=RuntimeError("test error"),
            driver_install=driver_install,
            telemetry=telemetry,
        )
        assert bundle.exists()

        # Now cleanup on pass
        collector.cleanup_on_pass(test_name=test_name)
        assert not bundle.exists()


# -----------------------------------------------------------------
# Report generation smoke test
# -----------------------------------------------------------------


@pytest.mark.smoke
class TestReportGeneration:
    """Verify JUnit XML and Go/No-Go report generation."""

    def test_generate_go_no_go(self) -> None:
        """Generate Go/No-Go summary with pass/fail/coverage."""
        result = generate_go_no_go(
            pass_count=3,
            fail_count=0,
            coverage_pct=85.5,
        )
        assert result["verdict"] == "go"
        assert result["pass_count"] == 3
        assert result["fail_count"] == 0
        assert result["threshold_met"] is True
        assert "Verdict: GO" in result["message"]

    def test_go_no_go_no_go(self) -> None:
        """Generate Go/No-Go summary when coverage below threshold."""
        result = generate_go_no_go(
            pass_count=2,
            fail_count=0,
            coverage_pct=70.0,
        )
        assert result["verdict"] == "no-go"
        assert result["threshold_met"] is False

    def test_generate_junit_xml(self, tmp_path) -> None:
        """Generate JUnit XML from results stats."""
        results_path = tmp_path / "results.xml"
        output_path = tmp_path / "junit_results.xml"

        # Create a minimal results XML first (pytest format)
        results_path.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<testsuite tests=\"5\" failures=\"0\" errors=\"0\" time=\"10.5\"/>\n"
        )

        generate_junit_xml(results_path=results_path, output_path=output_path)
        assert output_path.exists()

# Parse and verify - generated XML has <testsuites> root
        from xml.etree import ElementTree as ET
        tree = ET.parse(output_path)
        root = tree.getroot()  # <testsuites>
        # The nested <testsuite> has the attributes
        suite = root.find("testsuite")
        assert suite is not None
        assert suite.get("tests") == "5"
        assert suite.get("failures") == "0"