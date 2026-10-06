"""Automatic artefact collection on failure for GPU driver test framework.

Collects driver version, WMI GPU state, and Event Viewer entries
into a bundle when a test fails. Cleanup on test pass.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class ArtifactCollector:
    """Collects and manages artefacts when tests fail.

    On failure: captures driver version, WMI GPU state, Event Viewer entries.
    On pass: removes artefact bundle if it exists.
    """

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    def collect_on_failure(
        self,
        test_name: str,
        error: BaseException,
        driver_install: "DriverInstall",
        telemetry: "TelemetryCapture",
    ) -> Path:
        """Collect artefacts when a test fails.

        Creates a bundle directory under artefacts/ containing:
        - driver_version.txt  : currently installed driver version
        - gpu_state.json      : WMI GPU state capture
        - event_viewer.json   : Event Viewer entries capture

        Args:
            test_name: Name of the test that failed.
            error: The exception that caused the failure.
            driver_install: DriverInstall instance for version info.
            telemetry: TelemetryCapture instance for GPU/EventViewer data.

        Returns:
            Path to the artefact bundle directory.
        """
        logger.info("Collecting artefacts for failed test: %s", test_name)
        bundle_dir = Path("artifacts") / test_name

        # Clean any previous bundle for this test
        if bundle_dir.exists():
            shutil.rmtree(bundle_dir)

        bundle_dir.mkdir(parents=True, exist_ok=True)

        # 1. Driver version
        version = driver_install.current_version or "unknown"
        (bundle_dir / "driver_version.txt").write_text(version)
        logger.debug("Wrote driver version %s to bundle", version)

        # 2. WMI GPU state
        gpu_state = telemetry.capture_gpu_state()
        (bundle_dir / "gpu_state.json").write_text(json.dumps(gpu_state, indent=2))
        logger.debug("Wrote GPU state to bundle")

        # 3. Event Viewer entries
        events = telemetry.capture_event_viewer()
        (bundle_dir / "event_viewer.json").write_text(json.dumps(events, indent=2))
        logger.debug("Wrote Event Viewer entries to bundle")

        logger.info("Artefact bundle created at %s", bundle_dir)
        return bundle_dir

    def cleanup_on_pass(self, test_name: Optional[str] = None) -> None:
        """Clean up artefacts when a test passes.

        If test_name is provided, only remove that specific bundle;
        otherwise remove the entire artefacts/ directory.

        Args:
            test_name: Optional name of the test that passed.
        """
        logger.info("Cleaning up artefacts (test passed: %s)", test_name)

        artefacts_dir = Path("artifacts")

        if test_name:
            bundle_dir = artefacts_dir / test_name
            if bundle_dir.exists():
                shutil.rmtree(bundle_dir)
                logger.debug("Removed bundle for test %s", test_name)
        else:
            if artefacts_dir.exists():
                shutil.rmtree(artefacts_dir)
                logger.debug("Removed entire artefacts/ directory")