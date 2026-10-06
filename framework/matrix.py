"""OS build x GPU SKU matrix expansion for parametrised test suites.

Defines the matrix YAML format and provides an expander that converts
the definition into a list of test configuration dicts passed to pytest
via @pytest.mark.parametrize.
"""

from __future__ import annotations

import logging

import yaml
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

MATRIX_DEF_PATH = Path("specs/matrix.yaml")


def load_matrix(path: str = str(MATRIX_DEF_PATH)) -> Dict[str, Any]:
    """Load the matrix definition from YAML path.

    Returns:
        Dict with keys "os_builds" and "gpu_skus".
    """
    p = Path(path)
    if not p.exists():
        msg = f"Matrix definition not found at {p}"
        raise FileNotFoundError(msg)
    with p.open("r") as f:
        data: Dict[str, Any] = yaml.safe_load(f)
    # Ensure required keys exist
    data.setdefault("os_builds", [])
    data.setdefault("gpu_skus", [])
    return data


def expand_matrix(matrix_def: Dict[str, Any]) -> List[Dict[str, str]]:
    """Expand a matrix definition into a list of test configurations.

    Args:
        matrix_def: Dict with keys "os_builds" (list) and "gpu_skus" (list).

    Returns:
        List of dicts, each with keys "os_build" and "gpu_sku".
        Example: [{"os_build": "10.0.19044", "gpu_sku": "RTX3090"}, ...]
    """
    os_builds: List[str] = matrix_def.get("os_builds", [])
    gpu_skus: List[str] = matrix_def.get("gpu_skus", [])

    configurations: List[Dict[str, str]] = []
    for os_build in os_builds:
        for gpu_sku in gpu_skus:
            configurations.append(
                {"os_build": str(os_build), "gpu_sku": str(gpu_sku)}
            )

    logger.info("Expanded matrix to %d configurations", len(configurations))
    return configurations


# -----------------------------------------------------------------
# CLI helper (optional)
# -----------------------------------------------------------------

def print_matrix() -> None:
    """Print the expanded matrix to stdout for debugging."""
    matrix_def = load_matrix()
    configs = expand_matrix(matrix_def)
    print("Test matrix configurations:")
    for cfg in configs:
        print(f"  OS Build: {cfg['os_build']}, GPU SKU: {cfg['gpu_sku']}")