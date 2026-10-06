"""Pytest conftest for GPU Driver Test Automation Framework.

Provides fixtures:
- driver_install: DriverInstall fixture (real or mocked)
- telemetry: TelemetryCapture fixture (real or mocked)
- artifact_dir: Directory for artefact collection on failure
- test_config: Parametrised matrix configuration from specs/matrix.yaml
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any, Generator

import pytest

from framework.driver_install import DriverInstall
from framework.telemetry import TelemetryCapture
from framework.artifacts import ArtifactCollector
from framework.matrix import load_matrix, expand_matrix

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------
# Mock vs Real implementation selection
# -----------------------------------------------------------------

# Default to real implementations; CI can override via environment
_IMPLEMENTATION = os_env = __import__("os").environ.get


def _use_mocks() -> bool:
    """Determine if we should use mock implementations.

    Mocks are used when running on GitHub windows-latest without a GPU,
    or when Gpu_TEST_MOCK=1 is set in the environment.
    """
    val = _IMPLEMENTATION("Gpu_TEST_MOCK", "0")
    # Also mock on GitHub Actions windows-latest by default
    if "GITHUB_ACTIONS" in _IMPLEMENTATION("os", ""):
        val = "1"
    return val == "1"


_USE_MOCKS = _use_mocks()


# -----------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------


@pytest.fixture(scope="module")
def driver_install() -> DriverInstall:
    """Provide a DriverInstall instance.

    Returns real DriverInstall on hardware; mock on CI/without GPU.
    """
    if _USE_MOCKS:
        from unittest.mock import MagicMock

        mock = MagicMock(spec=DriverInstall)
        mock.install.return_value = True
        mock.uninstall.return_value = True
        mock.rollback.return_value = True
        mock.current_version = "mocked.driver.version"
        mock.installed = True
        return mock
    return DriverInstall()


@pytest.fixture(scope="module")
def telemetry() -> TelemetryCapture:
    """Provide a TelemetryCapture instance.

    Returns real TelemetryCapture on hardware; mock on CI/without GPU.
    """
    if _USE_MOCKS:
        from unittest.mock import MagicMock

        mock = MagicMock(spec=TelemetryCapture)
        mock.capture_gpu_state.return_value = {
            "gpus": [
                {
                    "name": "Mock GPU",
                    "driver_version": "mocked.version",
                    "capacity": "",
                    "temperature": 0,
                }
            ],
            "source": "mock",
        }
        mock.capture_event_viewer.return_value = [
            {"time": "2024-01-01T00:00:00", "event_id": "1", "message": "Mock event"}
        ]
        return mock
    return TelemetryCapture()


@pytest.fixture(scope="module")
def artifact_dir() -> Generator[Path, None, None]:
    """Provide a temporary artefact directory.

    Yields a clean artefacts/ path; cleanup happens after tests.
    """
    d = Path("artifacts")
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True, exist_ok=True)
    yield d
    # Cleanup after module
    if d.exists():
        shutil.rmtree(d)


@pytest.fixture(params=expand_matrix(load_matrix()), scope="module")
def test_config(request) -> Dict[str, str]:
    """Parametrised matrix configuration from specs/matrix.yaml.

    Yields one dict per matrix entry: {"os_build": "...", "gpu_sku": "..."}.
    """
    return request.param


# -----------------------------------------------------------------
# Module-level cleanup (ensure driver uninstalled after all tests)
# -----------------------------------------------------------------


def pytest_unconfigure(config: pytest.Config) -> None:
    """Ensure driver rollback when test module finishes."""
    from framework.driver_install import DriverInstall

    installer = DriverInstall()
    if installer.installed:
        logger.info("Module ending: rolling back driver")
        installer.rollback()