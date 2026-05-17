"""CI-safe smoke tests — no xlsx fixture files required.

These tests verify that the app and its key modules import and
initialise correctly. They run in every environment including CI.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_app_imports():
    """FastAPI app object loads without errors."""
    from drilling_app.main import app
    assert app is not None
    assert app.title == "Drilling Motor Output DB"


def test_app_version():
    """Version string is set and non-empty."""
    from drilling_app.config import VERSION, RELEASE_DATE
    assert VERSION, "VERSION must not be empty"
    assert RELEASE_DATE, "RELEASE_DATE must not be empty"
    # v1.1+
    major, minor = VERSION.split(".")
    assert int(major) >= 1


def test_routes_registered():
    """Key page and API routes are registered."""
    from drilling_app.main import app
    paths = {r.path for r in app.routes if hasattr(r, "path")}
    required = {"/", "/login", "/logout", "/import", "/wells", "/compare",
                "/benchmarks", "/bha-configs", "/batch-import",
                "/admin/users", "/api/bha-runs/import"}
    missing = required - paths
    assert not missing, f"Missing routes: {missing}"


def test_auth_module():
    """Auth utilities are importable and hash/verify work correctly."""
    from drilling_app.auth import hash_password, verify_password
    hashed = hash_password("testpassword")
    assert hashed != "testpassword"
    assert verify_password("testpassword", hashed)
    assert not verify_password("wrongpassword", hashed)


def test_unit_conversions():
    """Core unit conversion helpers return correct values."""
    from drilling_app.compute.units import depth_from_ft, dls_from_100ft

    # 1 ft → 1 ft (identity)
    assert abs(depth_from_ft(1.0, "ft") - 1.0) < 1e-9
    # 1 ft → ~0.3048 m
    assert abs(depth_from_ft(1.0, "m") - 0.3048) < 1e-4

    # 1 deg/100ft → 1 deg/100ft (identity)
    assert abs(dls_from_100ft(1.0, "deg/100ft") - 1.0) < 1e-9
    # 1 deg/100ft → ~0.3048 deg/30m
    assert abs(dls_from_100ft(1.0, "deg/30m") - 0.3048) < 1e-3


def test_motor_output_compute():
    """Motor output computation handles basic sliding/rotating intervals."""
    from drilling_app.parsers.slide_sheet import SurveyRow, IntervalRow
    from drilling_app.compute.motor_output import compute_motor_outputs

    surveys = [
        SurveyRow(sequence=0, svy_md_ft=0.0,   incl_deg=0.0, azmth_deg=0.0, dls_deg_per_100ft=0.0),
        SurveyRow(sequence=1, svy_md_ft=100.0,  incl_deg=2.0, azmth_deg=0.0, dls_deg_per_100ft=2.0),
        SurveyRow(sequence=2, svy_md_ft=200.0,  incl_deg=4.0, azmth_deg=0.0, dls_deg_per_100ft=2.0),
    ]
    intervals = [
        IntervalRow(sequence=0, md_from_ft=0.0,  md_to_ft=50.0,  mode="Sliding"),
        IntervalRow(sequence=1, md_from_ft=50.0, md_to_ft=100.0, mode="Rotating"),
        IntervalRow(sequence=2, md_from_ft=100.0, md_to_ft=200.0, mode="Sliding"),
    ]
    results = compute_motor_outputs(surveys, intervals, stand_length_ft=96.0)

    # Interval 0→100: 50 ft sliding, DLS=2 deg/100ft → motor output = 2/50 = 0.04 deg/ft
    mo0 = next(r for r in results if abs(r.svy_md_ft - 100.0) < 0.1)
    assert mo0.slide_footage_ft == pytest.approx(50.0)
    assert mo0.motor_output_deg_per_ft == pytest.approx(0.04)
    assert mo0.full_stand_deg == pytest.approx(0.04 * 96.0)

    # Interval 100→200: all sliding
    mo1 = next(r for r in results if abs(r.svy_md_ft - 200.0) < 0.1)
    assert mo1.slide_footage_ft == pytest.approx(100.0)
    assert mo1.motor_output_deg_per_ft == pytest.approx(0.02)
