"""Test GPU driver install, verify binding, rollback, and clean state."""

from __future__ import annotations

import pytest

from framework.driver_install import DriverInstall


@pytest.mark.install
class TestDriverInstall:
    """Test driver install/uninstall/rollback lifecycle."""

    def test_install_driver(self, driver_install: DriverInstall) -> None:
        """Install a driver and verify version is recorded."""
        success = driver_install.install(
            driver_path="specs/drivers/nvidia_560.94_win10.inf",
            driver_version="560.94",
        )
        assert success is True
        assert driver_install.installed is True
        assert driver_install.current_version == "560.94"

    def test_uninstall_driver(self, driver_install: DriverInstall) -> None:
        """Uninstall the current driver and verify state is cleared."""
        # First ensure a driver is "installed"
        driver_install.install(
            driver_path="specs/drivers/nvidia_560.94_win10.inf",
            driver_version="560.94",
        )
        assert driver_install.installed is True

        # Now uninstall
        success = driver_install.uninstall()
        assert success is True
        assert driver_install.installed is False
        assert driver_install.current_version is None

    def test_rollback_driver(self, driver_install: DriverInstall) -> None:
        """Rollback the driver and verify state."""
        # Install then rollback
        driver_install.install(
            driver_path="specs/drivers/nvidia_560.94_win10.inf",
            driver_version="560.94",
        )
        assert driver_install.installed is True

        success = driver_install.rollback()
        assert success is True
        # After rollback state is cleared in this MVP
        assert driver_install.installed is False