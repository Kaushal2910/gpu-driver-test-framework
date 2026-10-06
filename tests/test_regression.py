"""Regression test suite for GPU driver test framework.

These tests exercise edge cases and ensure the framework behaves
correctly under various configurations. Meant to be run nightly or
on PR merge for full validation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from framework.report import generate_go_no_go, generate_junit_xml, parse_junit_xml


# -----------------------------------------------------------------
# Edge case: JUnit XML parsing
# -----------------------------------------------------------------


@pytest.mark.regression
class TestJUnitParsing:
    """Edge cases for JUnit XML parsing."""

    def test_parse_junit_xml_with_testsuites_root(self, tmp_path) -> None:
        """Parse JUnit XML that uses <testsuites> as root element."""
        xml_content = '<?xml version="1.0" encoding="UTF-8"?>' + \
                      "<testsuites>\n" + \
                      '  <testsuite name="gpu-driver-test-framework" tests="10" failures="2" errors="0" time="15.3">\n' + \
                      "    <testsuite name='gpu_driver_smoke' tests='5' failures='2' errors='0' time='8.1'/>\n" + \
                      "  </testsuite>\n" + \
                      "</testsuites>\n"
        results_path = tmp_path / "results.xml"
        results_path.write_text(xml_content)

        stats = parse_junit_xml(results_path)
        assert stats["tests"] == 10
        assert stats["failures"] == 2

    def test_parse_junit_xml_direct_suite(self, tmp_path) -> None:
        """Parse JUnit XML with direct <testsuite> root (no testsuites wrapper)."""
        xml_content = '<?xml version="1.0" encoding="UTF-8"?>' + \
                      '<testsuite name="gpu-driver-test-framework" tests="3" failures="0" errors="0" time="5.2">\n' + \
                      "  <testcase name='test_pass' class='SmokeTest' time='2.1'/>\n" + \
                      "</testsuite>\n"
        results_path = tmp_path / "results.xml"
        results_path.write_text(xml_content)

        stats = parse_junit_xml(results_path)
        assert stats["tests"] == 3
        assert stats["failures"] == 0


# -----------------------------------------------------------------
# Edge case: Go/No-Go with various scenarios
# -----------------------------------------------------------------


@pytest.mark.regression
class TestGoNoGoEdgeCases:
    """Verify Go/No-Go verdict logic across edge cases."""

    def test_go_when_all_pass_and_coverage_ok(self) -> None:
        """Verdict is go when all pass and coverage above threshold."""
        result = generate_go_no_go(
            pass_count=10,
            fail_count=0,
            coverage_pct=92.0,
        )
        assert result["verdict"] == "go"
        assert result["threshold_met"] is True

    def test_no_go_when_any_failure(self) -> None:
        """Verdict is no-go when any test fails, even with high coverage."""
        result = generate_go_no_go(
            pass_count=9,
            fail_count=1,
            coverage_pct=95.0,
        )
        assert result["verdict"] == "no-go"

    def test_no_go_when_coverage_below_threshold(self) -> None:
        """Verdict is no-go when coverage is below threshold, even with 0 failures."""
        result = generate_go_no_go(
            pass_count=10,
            fail_count=0,
            coverage_pct=70.0,  # below default 80% threshold
        )
        assert result["verdict"] == "no-go"
        assert result["threshold_met"] is False

    def test_no_go_when_both_failure_and_low_coverage(self) -> None:
        """Verdict is no-go when both failures and low coverage present."""
        result = generate_go_no_go(
            pass_count=5,
            fail_count=3,
            coverage_pct=45.0,
        )
        assert result["verdict"] == "no-go"


# -----------------------------------------------------------------
# Integration: full pipeline smoke test
# -----------------------------------------------------------------


@pytest.mark.smoke
@pytest.mark.regression
class TestFullPipeline:
    """Integration test: matrix → test → artefacts → report."""

    def test_full_pipeline_matrix_expansion(self) -> None:
        """End-to-end: load matrix → expand → validate configs."""
        from framework.matrix import load_matrix, expand_matrix
        matrix = load_matrix()
        configs = expand_matrix(matrix)
        assert len(configs) > 0
        # Verify all configs have required keys
        for cfg in configs:
            assert "os_build" in cfg
            assert "gpu_sku" in cfg

    def test_go_no_go_json_output(self, tmp_path) -> None:
        """Write Go/No-Go result to JSON and verify round-trip."""
        from framework.report import generate_go_no_go, write_go_no_go
        pass_count = 4
        fail_count = 0
        coverage_pct = 88.5
        result = generate_go_no_go(
            pass_count=pass_count,
            fail_count=fail_count,
            coverage_pct=coverage_pct,
        )
        output_path = tmp_path / "gono-go.json"
        write_go_no_go(result=result, output_path=output_path)

        # Read back and verify
        stored = json.loads(output_path.read_text())
        assert stored["verdict"] == "go"
        assert stored["pass_count"] == 4