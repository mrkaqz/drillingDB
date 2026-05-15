"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-12
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wells",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("field", sa.String()),
        sa.Column("borehole", sa.String()),
        sa.Column("location", sa.String()),
        sa.Column("rig", sa.String()),
        sa.Column("client", sa.String()),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "bha_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("source_filename", sa.String()),
        sa.Column("source_unit_system", sa.String()),
        sa.Column("hole_size_in", sa.Float()),
        sa.Column("motor_make", sa.String()),
        sa.Column("motor_model", sa.String()),
        sa.Column("motor_serial", sa.String()),
        sa.Column("motor_bent_deg", sa.Float()),
        sa.Column("bend_to_bit_ft", sa.Float()),
        sa.Column("motor_od_in", sa.Float()),
        sa.Column("motor_length_ft", sa.Float()),
        sa.Column("designed_by", sa.String()),
        sa.Column("bha_date", sa.Date()),
        sa.Column("notes", sa.Text()),
        sa.Column("components_json", sa.Text()),
        sa.Column("stabilizers_json", sa.Text()),
        sa.Column("sensor_offsets_json", sa.Text()),
        sa.Column("nozzles_json", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "bha_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("well_id", sa.Integer(), sa.ForeignKey("wells.id"), nullable=False),
        sa.Column("bha_config_id", sa.Integer(), sa.ForeignKey("bha_configs.id")),
        sa.Column("bha_name", sa.String()),
        sa.Column("bit_run_number", sa.String()),
        sa.Column("source_unit_system", sa.String()),
        sa.Column("hole_size_in", sa.Float()),
        sa.Column("casing_shoe_ft", sa.Float()),
        sa.Column("casing_size_in", sa.Float()),
        sa.Column("casing_weight_lbm_ft", sa.Float()),
        sa.Column("mud_type", sa.String()),
        sa.Column("end_mw_ppg", sa.Float()),
        sa.Column("motor_bent_deg", sa.Float()),
        sa.Column("motor_make", sa.String()),
        sa.Column("motor_model", sa.String()),
        sa.Column("depth_in_ft", sa.Float()),
        sa.Column("depth_out_ft", sa.Float()),
        sa.Column("incl_in_deg", sa.Float()),
        sa.Column("incl_out_deg", sa.Float()),
        sa.Column("azimuth_in_deg", sa.Float()),
        sa.Column("azimuth_out_deg", sa.Float()),
        sa.Column("date_in", sa.DateTime()),
        sa.Column("date_td", sa.DateTime()),
        sa.Column("date_out", sa.DateTime()),
        sa.Column("drilling_hours", sa.Float()),
        sa.Column("pumping_hours", sa.Float()),
        sa.Column("brt_hours", sa.Float()),
        sa.Column("dd_primary", sa.String()),
        sa.Column("dd_secondary", sa.String()),
        sa.Column("client_rep_primary", sa.String()),
        sa.Column("client_rep_secondary", sa.String()),
        sa.Column("bit_serial", sa.String()),
        sa.Column("bit_type", sa.String()),
        sa.Column("bit_manuf", sa.String()),
        sa.Column("bit_iadc", sa.String()),
        sa.Column("bit_jets", sa.String()),
        sa.Column("bit_tfa_in2", sa.Float()),
        sa.Column("bit_dull_in_json", sa.Text()),
        sa.Column("bit_dull_out_json", sa.Text()),
        sa.Column("stand_length_ft", sa.Float(), server_default="96.0"),
        sa.Column("source_filename", sa.String()),
        sa.Column("imported_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("notes", sa.Text()),
    )
    op.create_index("ix_bha_runs_well_id", "bha_runs", ["well_id"])
    op.create_index("ix_bha_runs_motor_bent_deg", "bha_runs", ["motor_bent_deg"])
    op.create_index("ix_bha_runs_hole_size_in", "bha_runs", ["hole_size_in"])

    op.create_table(
        "surveys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bha_run_id", sa.Integer(), sa.ForeignKey("bha_runs.id"), nullable=False),
        sa.Column("sequence", sa.Integer()),
        sa.Column("svy_md_ft", sa.Float()),
        sa.Column("incl_deg", sa.Float()),
        sa.Column("azmth_deg", sa.Float()),
        sa.Column("dls_deg_per_100ft", sa.Float()),
    )
    op.create_index("ix_surveys_bha_run_id", "surveys", ["bha_run_id", "sequence"])

    op.create_table(
        "slide_intervals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bha_run_id", sa.Integer(), sa.ForeignKey("bha_runs.id"), nullable=False),
        sa.Column("sequence", sa.Integer()),
        sa.Column("md_from_ft", sa.Float()),
        sa.Column("md_to_ft", sa.Float()),
        sa.Column("mode", sa.String()),
        sa.Column("course_ft", sa.Float()),
        sa.Column("calc_rop", sa.Float()),
        sa.Column("tf_mode", sa.String()),
        sa.Column("tf_angle", sa.Float()),
        sa.Column("start_time", sa.DateTime()),
        sa.Column("end_time", sa.DateTime()),
    )
    op.create_index("ix_slide_intervals_bha_run_id", "slide_intervals", ["bha_run_id", "sequence"])

    op.create_table(
        "motor_outputs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bha_run_id", sa.Integer(), sa.ForeignKey("bha_runs.id"), nullable=False),
        sa.Column("sequence", sa.Integer()),
        sa.Column("svy_md_ft", sa.Float()),
        sa.Column("incl_deg", sa.Float()),
        sa.Column("azmth_deg", sa.Float()),
        sa.Column("dls_deg_per_100ft", sa.Float()),
        sa.Column("slide_footage_ft", sa.Float()),
        sa.Column("motor_output_deg_per_ft", sa.Float()),
        sa.Column("full_stand_deg", sa.Float()),
    )
    op.create_index("ix_motor_outputs_bha_run_id", "motor_outputs", ["bha_run_id"])


def downgrade() -> None:
    op.drop_table("motor_outputs")
    op.drop_table("slide_intervals")
    op.drop_table("surveys")
    op.drop_table("bha_runs")
    op.drop_table("bha_configs")
    op.drop_table("wells")
