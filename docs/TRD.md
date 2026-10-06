# TRD: GPU Driver Test Automation Framework

## Architecture Design

The framework follows a fixture-based design with modular components. Below is the component diagram and interaction flow.

### Component Layout

```
framework/
├── driver_install.py    # Install/uninstall/rollback fixtures
├── telemetry.py         # WMI + Event Viewer capture
├── artifacts.py         # Failure artefact collection
├── matrix.py            # OS build × GPU SKU expansion
└── report.py            # JUnit XML + Go/No-Go summary

tests/
├── conftest.py          # Fixtures: installed_driver, telemetry, artifact_dir
├── test_install.py      # Install, verify binding, rollback, verify clean state
├── test_smoke.py        # Smoke test suite
└── test_regression.py   # Regression test suite

specs/
└── matrix.yaml          # OS builds × GPU SKUs matrix

.github/workflows/ci.yml # GitHub Actions CI pipeline
```

### Data Flow

1. **Setup Phase**: `conftest.py` runs `driver_install.py` fixture
   - Installs target GPU driver version
   - Captures initial WMI state via `telemetry.py`
   - Creates artifact directory via `artifacts.py`

2. **Test Execution Phase**: pytest runs test functions
   - Tests parametrised over `matrix.yaml` matrix
   - Smoke tests (`-m smoke`) executed on every commit
   - Regression tests (`-m regression`) executed nightly

3. **Teardown Phase**: `conftest.py` teardown runs even on test failure
   - `driver_install.py` rollback via `pnputil` / `setupapi`
   - `telemetry.py` captures final WMI state and Event Viewer entries
   - `artifacts.py` packages logs/dumps from failure if occurred

4. **Reporting Phase**: `report.py` generates outputs
   - JUnit XML via `--junitxml=results.xml`
   - Coverage via `pytest-cov` producing `coverage.xml`
   - Go/No-Go summary with verdict

### Design Decisions & Rationale

| Decision | Rationale |
|----------|-----------|
| **Fixture-based install/rollback** (not per-test install) | Driver install is expensive; fixture runs once per test module; teardown-always ensures clean state even on failure. This is the key interview answer. |
| **Matrix YAML parametrisation** | Avoids code duplication; `@pytest.mark.parametrize` over YAML entries. Easy to extend with new OS builds/GPU SKUs. |
| **Mockable privileged layer behind interface** | GitHub `windows-latest` runner has no real GPU. Mock `driver_install.py` calls so CI runs green → convinces reviewers even without GPU hardware. |
| **JUnit XML + pytest-cov** | Both are CI-consumable formats. `coverage.xml` and `results.xml` are standard GitHub Actions artifact names. |
| **Artefact collection on failure only** | On failure, `artifacts.py` collects: driver version, WMI GPU state (`Get-WmiObject Win32_VideoController`), Event Viewer entries (`wevtutil`). On pass, minimal cleanup. |
| **Go/No-Go summary output** | Single-line verdict (`go` or `no-go`) plus counts and coverage %. Designed for CI step that checks exit code 0 or non-zero. |

---

## Interface Specifications

### `driver_install.py` Interface

```python
class DriverInstall:
    """Interface for GPU driver install/uninstall/rollback operations."""
    
    def install(self, driver_path: str, driver_version: str) -> bool:
        """Install GPU driver from path. Returns True on success."""
        ...
    
    def uninstall(self) -> bool:
        """Uninstall current GPU driver. Returns True on success."""
        ...
    
    def rollback(self) -> bool:
        """Rollback to previous driver version. Returns True on success."""
        ...
    
    @property
    def current_version(self) -> str:
        """Return currently installed driver version."""
        ...
```

The implementation in `driver_install.py` will use:
- `pnputil` for driver package management on Windows
- `setupapi` API for device enumeration
- WMI queries via `wmic` or `pywin32`

### `telemetry.py` Interface

```python
class TelemetryCapture:
    """Interface for WMI and Event Viewer telemetry capture."""
    
    def capture_gpu_state(self) -> dict:
        """Capture GPU WMI state. Returns dict with GPU info."""
        ...
    
    def capture_event_viewer(self, log_name: str = "System", since_minutes: int = 60) -> list:
        """Capture Event Viewer entries. Returns list of event dicts."""
        ...
```

### `artifacts.py` Interface

```python
class ArtifactCollector:
    """Interface for failure artefact collection."""
    
    def collect_on_failure(self, test_name: str, error: Exception) -> Path:
        """Collect artefacts when test fails. Returns path to artefact bundle."""
        ...
    
    def cleanup_on_pass(self) -> None:
        """Clean up artefacts when test passes."""
        ...
```

### `matrix.py` Interface

```python
def expand_matrix(matrix_def: dict) -> list[dict]:
    """Expand matrix definition into list of test configurations.
    
    matrix_def format:
    {
        "os_builds": ["10.0.19044", "10.0.19045"],
        "gpu_skus": ["RTX3090", "RTX3080", "RTX4090"]
    }
    
    Returns list of {"os_build": "...", "gpu_sku": "..."} dicts.
    """
    ...
```

### `report.py` Interface

```python
def generate_junit_xml(results_path: Path, output_path: Path) -> None:
    """Convert test results to JUnit XML format."""
    ...

def generate_go_no_go(coverage_pct: float, pass_count: int, fail_count: int) -> dict:
    """Generate Go/No-Go summary dict.
    
    Returns:
    {
        "verdict": "go" | "no-go",
        "pass_count": int,
        "fail_count": int,
        "coverage_pct": float,
        "threshold_met": bool  # whether coverage >= configured threshold
    }
    """
    ...
```

---

## Interface Contracts

All modules follow these contracts:

1. **No global state mutation** between test runs (fixtures reset state)
2. **All functions are pure where possible** (no hidden side effects)
3. **Interface mockability** - `driver_install.py` implements an abstract base class so it can be mocked in CI
4. **Error handling propagates upwards** - callers decide how to handle install failures
5. **All paths are documented** in module docstrings

---

## Acceptance Criteria Translation to Tests

| AC # | Translation to Test |
|------|---------------------|
| 1 | `pytest -m smoke` runs green on Windows with NVIDIA GPU |
| 2 | `--junitxml` output parses; `coverage.xml` produced |
| 3 | Install fixture teardown removes driver even when test fails mid-run |
| 4 | Failing test drops log bundle into `artifacts/` with driver version, WMI GPU state, Event Viewer entries |
| 5 | `report.py` turns results file into Go/No-Go summary with pass count, fail count, coverage % and gating verdict |
| 6 | GitHub Actions workflow runs green on `windows-latest` with privileged layer mocked |
| 7 | README documents matrix format and shows real run output |
| 8 | Public repo, MIT licence |