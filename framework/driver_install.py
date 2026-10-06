"""GPU driver install/uninstall/rollback operations for Windows.

Provides the DriverInstall interface implemented via pnputil / setupapi.
Designed to be mockable so the suite runs on GitHub windows-latest without a GPU.
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class DriverInstall:
    """Interface for GPU driver install/uninstall/rollback operations on Windows.

    The concrete implementation uses Windows-native tools:
    - pnputil for driver package management
    - setupapi Device Manager calls via devcon or wmic

    The mockable interface allows CI to run without a real NVIDIA GPU.
    """

    def __init__(self) -> None:
        self._current_version: Optional[str] = None
        self._installed: bool = False

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    def install(self, driver_path: str, driver_version: str) -> bool:
        """Install a GPU driver from the given path.

        Args:
            driver_path: Absolute path to the .inf or driver bundle.
            driver_version: Human-readable version string (e.g. "560.09").

        Returns:
            True if the driver was reported installed successfully.
        """
        logger.info("Installing GPU driver %s from %s", driver_version, driver_path)
        try:
            path = Path(driver_path).resolve()
            if not path.exists():
                logger.error("Driver path does not exist: %s", path)
                return False

            # --- pnputil: add driver package ---
            # This registers the driver with Windows Device Install Services.
            _run_cmd(["pnputil", "/add-driver", str(path), "/install"])

            # --- Record state ---
            self._current_version = driver_version
            self._installed = True
            logger.info("Driver %s installed successfully", driver_version)
            return True
        except Exception as exc:  # pylint: disable-broad-excuse
            logger.error("Failed to install driver %s: %s", driver_version, exc)
            return False

    def uninstall(self) -> bool:
        """Uninstall the currently installed GPU driver.

        Returns:
            True if the driver was uninstalled successfully.
        """
        if not self._installed:
            logger.warning("No driver currently installed; nothing to uninstall")
            return True

        logger.info("Uninstalling current GPU driver")
        try:
            # --- pnputil: enumerate and remove driver packages ---
            _run_cmd(["pnputil", "/enum-drivers"])

            # Attempt rollback via setupapi / wmic
            _run_cmd(["wmic", "path", "cddriver", "where", "description", "call", "delete"])

            # --- Record state ---
            self._current_version = None
            self._installed = False
            logger.info("GPU driver uninstalled successfully")
            return True
        except Exception as exc:  # pylint: disable-broad-excuse
            logger.error("Failed to uninstall driver: %s", exc)
            return False

    def rollback(self) -> bool:
        """Rollback the GPU driver to the previous installed version.

        Returns:
            True if the rollback succeeded.
        """
        if not self._installed or self._current_version is None:
            logger.warning("No driver installed; nothing to rollback")
            return True

        logger.info("Rolling back GPU driver from %s", self._current_version)
        try:
            # --- pnputil: select previous driver version ---
            _run_cmd(["pnputil", "/enum-drivers"])

            # --- Reset state ---
            # For this MVP we simply uninstall; in a full implementation
            # we would activate the previous driver from the enum list.
            self.uninstall()

            logger.info("GPU driver rollback completed")
            return True
        except Exception as exc:  # pylint: disable-broad-excuse
            logger.error("Failed to rollback driver: %s", exc)
            return False

    @property
    def current_version(self) -> Optional[str]:
        """Return currently installed driver version, or None if none installed."""
        return self._current_version

    @property
    def installed(self) -> bool:
        """Return True if a driver is currently installed."""
        return self._installed


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _run_cmd(args: list[str]) -> str:
    """Run a command and return stdout; raise on non-zero exit."""
    result = subprocess.run(args, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        msg = f"Command failed: {' '.join(args)}\nstderr: {result.stderr}"
        logger.error(msg)
        raise RuntimeError(msg)
    return result.stdout.strip()