"""WMI and Event Viewer telemetry capture for GPU state on Windows.

Provides the TelemetryCapture interface implemented via WMI queries
and wevtutil for Event Viewer log collection.

The mockable interface allows CI to run without a real NVIDIA GPU.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class TelemetryCapture:
    """Interface for WMI and Event Viewer telemetry capture on Windows.

    Concrete implementation queries:
    - WMI: Win32_VideoController for GPU state
    - Event Viewer: System log entries via wevtutil

    The interface is designed to be mockable so the suite runs on
    GitHub windows-latest without a physical GPU.
    """

    # -----------------------------------------------------------------
    # GPU State via WMI
    # -----------------------------------------------------------------

    def capture_gpu_state(self) -> Dict[str, Any]:
        """Capture GPU state via WMI queries.

        Returns:
            Dict with GPU information keys:
            - "name": GPU device name
            - "driver_version": installed driver version
            - "capacity": video memory capacity
            - "temperature": current GPU temperature (if available)
        """
        logger.info("Capturing GPU state via WMI")
        try:
            # Query via wmic - fallback to synthetic data if no GPU
            result = self._wmi_query("select * from Win32_VideoController")
            gpus = []

            for gpu in result:
                info: Dict[str, Any] = {
                    "name": gpu.get("Name", "Unknown GPU"),
                    "driver_version": gpu.get("DriverVersion", "unknown"),
                    "capacity": gpu.get("Caption", ""),
                    "temperature": gpu.get("CurrentTemperature", 0),
                }
                gpus.append(info)

            # If no GPU found, return synthetic baseline
            if not gpus:
                logger.warning("No WMI GPU found; returning baseline state")
                gpus = [
                    {
                        "name": "No GPU detected",
                        "driver_version": "unknown",
                        "capacity": "",
                        "temperature": 0,
                    }
                ]

            return {"gpus": gpus, "source": "wmi", "query": "Win32_VideoController"}

        except Exception as exc:  # pylint: disable-broad-excuse
            logger.error("WMI GPU state capture failed: %s", exc)
            return {
                "gpus": [
                    {
                        "name": "WMI query failed",
                        "driver_version": "error",
                        "capacity": "",
                        "temperature": 0,
                    }
                ],
                "source": "wmi",
                "error": str(exc),
            }

    # -----------------------------------------------------------------
    # Event Viewer capture
    # -----------------------------------------------------------------

    def capture_event_viewer(
        self, log_name: str = "System", since_minutes: int = 60
    ) -> List[Dict[str, Any]]:
        """Capture Event Viewer entries from the specified log.

        Args:
            log_name: Name of the Event Viewer log (e.g. "System", "Application").
            since_minutes: Only return events from the last N minutes.

        Returns:
            List of event dicts with keys:
            - "time": Event timestamp
            - "event_id": Event identifier
            - "message": Event message text
        """
        logger.info(
            "Capturing Event Viewer entries from %s (last %d min)", log_name, since_minutes
        )
        try:
            # wevtutil qe <log> /q:*[System[Time[@SystemTime >= ...]]] /c:1 /f:text
            since_ts = self._timestamp_minutes_ago(since_minutes)
            cmd = [
                "wevtutil",
                "qe",
                log_name,
                f"/q:[System[Time[@SystemTime >= '{since_ts}']]]",
                "/c:1",
                "/f:text",
            ]
            raw = _run_cmd(cmd)

            events: List[Dict[str, Any]] = []
            for line in raw.splitlines():
                line = line.strip()
                if not line:
                    continue
                # wevtutil text format parsing (simplified)
                if line.startswith("TimeCreated"):
                    time_val = line.split('SystemTime="')[1].split('"')[0]
                    events.append({"time": time_val})
                elif line.startswith("EventID"):
                    evt_id = line.split('>')[1].split("<")[0]
                    events[-1]["event_id"] = evt_id
                elif line.startswith("Message"):
                    # Capture the full message; subsequent lines are continuation
                    msg = line.split(">")[1].split("<")[0]
                    events[-1]["message"] = msg

            logger.info("Captured %d Event Viewer events", len(events))
            return events

        except Exception as exc:  # pylint: disable-broad-excuse
            logger.error("Event Viewer capture failed: %s", exc)
            return [
                {
                    "time": "error",
                    "event_id": "0",
                    "message": str(exc),
                }
            ]

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------

    @staticmethod
    def _timestamp_minutes_ago(minutes: int) -> str:
        """Return ISO 8601 timestamp for `minutes` ago (UTC)."""
        from datetime import datetime, timezone, timedelta

        ts = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        # wmic expects W3C datetime format
        return ts.strftime("%Y%m%d%H%M%S.000000+000")

    @staticmethod
    def _wmi_query(query: str) -> list:
        """Execute a wmic query and return parsed results.

        Returns a list of dicts, one per matching object.
        """
        try:
            cmd = ["wmic", "process", "where", f"'{query}'", "get", "/all", "/format:list"]  # noqa: E501
            # Simplified: use wmic with the provided query directly
            full_cmd = ["wmic", query.split()[0], "get", "/format:list"]  # noqa: E501
            # Actually let's just call wmic with the full query
            result = subprocess.run(
                ["wmic"] + query.split(), capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                logger.warning("WMI query returned non-zero: %s", result.stderr)
                return []

            # Parse simple key=value pairs across lines
            output = result.stdout
            entries: list = []
            current: dict = {}
            for line in output.splitlines():
                line = line.strip()
                if "=" in line and not line.startswith("="):
                    key, _, value = line.partition("=")
                    current[key.strip()] = value.strip()
                elif line == "" and current:
                    entries.append(current)
                    current = {}
            if current:
                entries.append(current)

            return entries
        except Exception as exc:  # pylint: disable-broad-excuse
            logger.error("WMI query execution failed: %s", exc)
            return []