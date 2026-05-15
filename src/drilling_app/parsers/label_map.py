"""Maps raw label strings from slide sheets and BHA reports to canonical field names.

Keys are lowercase, stripped. Values are canonical snake_case field names.
"""
from __future__ import annotations

# Slide-sheet header labels → canonical key
SLIDE_HEADER_SYNONYMS: dict[str, str] = {
    # location / well
    "location": "location",
    "field": "field",
    "field name": "field",
    "well": "well_name",
    "well name": "well_name",
    "borehole": "borehole",
    "borehole name": "borehole",
    "rig": "rig",
    "client": "client",
    "structure name": "structure_name",
    # BHA run info
    "bha run": "bha_name",
    "bha name": "bha_name",
    "bit run #": "bit_run_number",
    "bit run": "bit_run_number",
    "bit run#": "bit_run_number",
    # casing
    "casing shoe (ft)": "casing_shoe",
    "casing shoe (m)": "casing_shoe",
    "casing shoe": "casing_shoe",
    "casing size (in)": "casing_size_in",
    "casing size (in.)": "casing_size_in",
    "casing size": "casing_size_in",
    "casing weight (lbm/ft)": "casing_weight_lbm_ft",
    "casing wt (lbm/ft)": "casing_weight_lbm_ft",
    "casing wt": "casing_weight_lbm_ft",
    # depth / interval
    "depth in (ft)": "depth_in",
    "depth in (m)": "depth_in",
    "depth in": "depth_in",
    "depth out (ft)": "depth_out",
    "depth out (m)": "depth_out",
    "depth out": "depth_out",
    "incl in (deg)": "incl_in_deg",
    "incl in": "incl_in_deg",
    "incl out (deg)": "incl_out_deg",
    "incl out": "incl_out_deg",
    "azimuth in (deg)": "azimuth_in_deg",
    "azmth in (deg)": "azimuth_in_deg",
    "azimuth in": "azimuth_in_deg",
    "azmth in": "azimuth_in_deg",
    "azimuth out (deg)": "azimuth_out_deg",
    "azmth out (deg)": "azimuth_out_deg",
    "azimuth out": "azimuth_out_deg",
    "azmth out": "azimuth_out_deg",
    "date in": "date_in",
    "date td": "date_td",
    "date out": "date_out",
    "drilling hours": "drilling_hours",
    "pumping hours": "pumping_hours",
    "brt hours": "brt_hours",
    # mud
    "mud type": "mud_type",
    "end mw (ppg)": "end_mw",
    "end mw (sg)": "end_mw",
    "end mw (kg/m3)": "end_mw",
    "end mw": "end_mw",
    "hole size (in)": "hole_size_in",
    "hole size (in.)": "hole_size_in",
    "hole size": "hole_size_in",
    # personnel
    "directional driller #1": "dd_primary",
    "directional driller #2": "dd_secondary",
    "lead dd": "dd_primary",
    "2nd dd": "dd_secondary",
    "client representative #1": "client_rep_primary",
    "client representative #2": "client_rep_secondary",
    "client rep 1": "client_rep_primary",
    "client rep 2": "client_rep_secondary",
    "client rep#1": "client_rep_primary",
    "client rep#2": "client_rep_secondary",
    # bit
    "serial number": "bit_serial",
    "s/n": "bit_serial",
    "type": "bit_type",
    "manuf/model name": "bit_manuf",
    "manuf/model": "bit_manuf",
    "iadc": "bit_iadc",
    "jets (1/32 in)": "bit_jets",
    "jets (1/32in)": "bit_jets",
    "tfa (in2)": "bit_tfa_in2",
    "tfa (in²)": "bit_tfa_in2",
    # dull grading
    "inner rows": "dull_inner_rows",
    "in row": "dull_inner_rows",
    "outer rows": "dull_outer_rows",
    "out row": "dull_outer_rows",
    "dull char": "dull_char",
    "bearings": "dull_bearings",
    "gauge": "dull_gauge",
    "other": "dull_other",
    "reason pulled": "dull_reason_pulled",
}

# Operations table column headers → canonical column key
OPS_COL_SYNONYMS: dict[str, str] = {
    "date": "date",
    "start time": "start_time",
    "end time": "end_time",
    "start bittime": "start_bittime",
    "end bittime": "end_bittime",
    "bit time": "bit_time",
    "md from": "md_from",
    "md to": "md_to",
    "operation mode": "operation_mode",
    "mode": "operation_mode",
    "course": "course",
    "calc rop": "calc_rop",
    "rop": "calc_rop",
    "tf mode": "tf_mode",
    "tf angle": "tf_angle",
    "svy md": "svy_md",
    "incl": "incl",
    "azmth": "azmth",
    "azimuth": "azmth",
    "dls": "dls",
    "br": "br",
    "tr": "tr",
    "tvd": "tvd",
    "flow": "flow",
}


def normalize(text: str) -> str:
    return str(text).strip().lower()


def lookup_header(text: str) -> str | None:
    return SLIDE_HEADER_SYNONYMS.get(normalize(text))


def lookup_ops_col(text: str) -> str | None:
    return OPS_COL_SYNONYMS.get(normalize(text))
