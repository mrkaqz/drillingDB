"""Compute motor output per survey interval.

Motor Output (deg/ft) = DLS (deg/100ft) / Slide footage (ft) * 100
                       [note: DLS is per 100ft so divide by 100 to get per ft]
Full Stand = Motor Output (deg/ft) * stand_length_ft

Actually more precisely:
  DLS (deg/100ft) is the curvature rate.
  Slide footage (ft) is how much of the interval was slid.
  Motor Output shows how much dogleg (deg) the motor produces per ft slid.

  Since DLS = delta_dogleg / survey_interval_ft * 100:
    delta_dogleg (deg) = DLS * survey_interval_ft / 100
  And:
    Motor Output = delta_dogleg / slide_footage
                = DLS * survey_interval_ft / (100 * slide_footage)

  But the Excel uses: Motor Output = DLS / slide_footage (no interval factor).
  Looking at the VBA: F3 = D3/E3 where D=DLS (deg/100ft), E=slide footage (ft).
  So Motor Output = DLS / slide_footage → units: (deg/100ft) / ft = deg/100ft/ft
  And Full Stand = Motor Output * stand_length_ft → deg/100ft ... that's deg/100.

  Actually looking at Sample data: DLS=1.76, slide=30, motor output=0.0587 deg/ft
  0.0587 * 30 = 1.76 ... so motor output (deg/ft) * slide (ft) = DLS (deg/100ft)?
  That means: motor_output = DLS / slide_footage is actually DLS(deg/100ft)/ft.

  So in practice: motor_output_deg_per_ft = DLS_deg_per_100ft / slide_footage_ft
  The unit is technically (deg/100ft)/ft = deg/100ft² but practitioners call it deg/ft.

  Full Stand = motor_output * stand_length_ft has units deg/100ft which ≈ DLS for one stand.

  We replicate the Excel formula exactly.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .units import dls_from_100ft, depth_from_ft


@dataclass
class MotorOutputRow:
    sequence: int
    svy_md_ft: float
    incl_deg: float
    azmth_deg: float
    dls_deg_per_100ft: float
    slide_footage_ft: Optional[float]
    motor_output_deg_per_ft: Optional[float]
    full_stand_deg: Optional[float]


def compute_motor_outputs(
    surveys: list,       # list of SurveyRow or similar with svy_md_ft, incl_deg, azmth_deg, dls_deg_per_100ft
    intervals: list,     # list of IntervalRow or similar with md_from_ft, md_to_ft, mode
    stand_length_ft: float = 96.0,
) -> list[MotorOutputRow]:
    """
    For each consecutive survey pair (prev_md, curr_md):
      slide_ft = sum of Sliding interval overlap within [prev_md, curr_md]
      motor_output = DLS / slide_ft  (if slide_ft > 0)
      full_stand = motor_output * stand_length_ft
    """
    results: list[MotorOutputRow] = []

    for i, svy in enumerate(surveys):
        prev_md = surveys[i - 1].svy_md_ft if i > 0 else 0.0
        curr_md = svy.svy_md_ft

        slide_ft = 0.0
        for iv in intervals:
            if iv.mode.title() == "Sliding" and iv.md_to_ft > prev_md and iv.md_from_ft < curr_md:
                overlap = min(iv.md_to_ft, curr_md) - max(iv.md_from_ft, prev_md)
                if overlap > 0:
                    slide_ft += overlap

        dls = svy.dls_deg_per_100ft

        if slide_ft > 0 and dls is not None:
            motor_output = dls / slide_ft
            full_stand = motor_output * stand_length_ft
        else:
            motor_output = None
            full_stand = None

        results.append(MotorOutputRow(
            sequence=i,
            svy_md_ft=svy.svy_md_ft,
            incl_deg=svy.incl_deg,
            azmth_deg=svy.azmth_deg,
            dls_deg_per_100ft=dls,
            slide_footage_ft=slide_ft if slide_ft > 0 else None,
            motor_output_deg_per_ft=motor_output,
            full_stand_deg=full_stand,
        ))

    return results
