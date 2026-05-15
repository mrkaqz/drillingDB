"""Unit conversion and detection for drilling data.

Canonical storage units: depth=ft, DLS=deg/100ft, motor_output=deg/ft, mud_weight=PPG.
"""
from __future__ import annotations
import re

M_TO_FT = 3.28084
FT_TO_M = 1.0 / M_TO_FT

# DLS: deg/100ft ↔ deg/Xm
# deg/100ft = deg / (100 ft) = deg / (100/3.28084 m) = deg * 3.28084/100 per m
# deg/30m → deg/100ft:  multiply by (100 ft/100) / (30m * ft_per_m) = ... simplify:
#   1 deg/30m = 1 deg / (30 * 3.28084 ft) = 1 / 98.4252 deg/ft = 100/98.4252 deg/100ft
DLS_30M_TO_100FT = 100.0 / (30.0 * M_TO_FT)   # ≈ 1.01601
DLS_10M_TO_100FT = 100.0 / (10.0 * M_TO_FT)   # ≈ 3.04803
DLS_100FT_TO_30M = 1.0 / DLS_30M_TO_100FT
DLS_100FT_TO_10M = 1.0 / DLS_10M_TO_100FT

SG_TO_PPG = 8.3454
PPG_TO_SG = 1.0 / SG_TO_PPG
KGM3_TO_PPG = 0.0083454


def detect_depth_unit(text: str) -> str:
    """Return 'ft' or 'm' from a label like 'Depth In (ft)', 'ft', 'm', etc."""
    if not text:
        return "ft"
    t = str(text).strip().lower()
    if t in ("m", "meters", "metre", "metres"):
        return "m"
    if "(m)" in t or "(m " in t:
        return "m"
    return "ft"


def detect_dls_unit(text: str) -> str:
    """Return canonical DLS unit string from a label or units-row value."""
    if not text:
        return "deg/100ft"
    t = str(text).strip().lower().replace(" ", "")
    if "deg/10m" in t or "/10m" in t:
        return "deg/10m"
    if "deg/30m" in t or "/30m" in t:
        return "deg/30m"
    if "deg/100ft" in t or "/100ft" in t:
        return "deg/100ft"
    return "deg/100ft"


def detect_mw_unit(text: str) -> str:
    """Return 'ppg', 'sg', or 'kg/m3'."""
    if not text:
        return "ppg"
    t = str(text).strip().lower()
    if "sg" in t:
        return "sg"
    if "kg" in t:
        return "kg/m3"
    return "ppg"


def depth_to_ft(value: float, unit: str) -> float:
    if unit == "m":
        return value * M_TO_FT
    return value


def depth_from_ft(value: float, target_unit: str) -> float:
    if target_unit == "m":
        return value * FT_TO_M
    return value


def dls_to_100ft(value: float, unit: str) -> float:
    if unit == "deg/30m":
        return value * DLS_30M_TO_100FT
    if unit == "deg/10m":
        return value * DLS_10M_TO_100FT
    return value  # already deg/100ft


def dls_from_100ft(value: float, target_unit: str) -> float:
    if target_unit == "deg/30m":
        return value * DLS_100FT_TO_30M
    if target_unit == "deg/10m":
        return value * DLS_100FT_TO_10M
    return value


def motor_output_to_deg_per_ft(value: float, depth_unit: str, dls_unit: str) -> float:
    """Convert motor output calculated as dls/footage to deg/ft canonical."""
    # motor_output = DLS [stored in dls_unit] / slide_footage [stored in depth_unit]
    # We need: (dls in deg/100ft) / (footage in ft)  → deg/100ft / ft → but we want deg/ft
    # So: motor_output_deg_per_ft = dls_deg_100ft / (slide_footage_ft * 100)
    # But callers already pass pre-converted values. This helper is for display.
    if depth_unit == "m":
        value = value * FT_TO_M  # deg/m → deg/ft
    return value


def motor_output_from_deg_per_ft(value: float, target_depth_unit: str) -> float:
    if target_depth_unit == "m":
        return value * M_TO_FT
    return value


def mw_to_ppg(value: float, unit: str) -> float:
    if unit == "sg":
        return value * SG_TO_PPG
    if unit == "kg/m3":
        return value * KGM3_TO_PPG
    return value


def mw_from_ppg(value: float, target_unit: str) -> float:
    if target_unit == "sg":
        return value * PPG_TO_SG
    if target_unit == "kg/m3":
        return value / KGM3_TO_PPG
    return value


# Display helpers used in templates

def fmt_depth(value: float | None, unit: str = "ft", decimals: int = 1) -> str:
    if value is None:
        return ""
    return f"{depth_from_ft(value, unit):.{decimals}f}"


def fmt_dls(value: float | None, unit: str = "deg/100ft", decimals: int = 2) -> str:
    if value is None:
        return ""
    return f"{dls_from_100ft(value, unit):.{decimals}f}"


def fmt_motor(value: float | None, depth_unit: str = "ft", decimals: int = 4) -> str:
    if value is None:
        return ""
    return f"{motor_output_from_deg_per_ft(value, depth_unit):.{decimals}f}"
