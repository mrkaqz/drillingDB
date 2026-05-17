from datetime import datetime, date
from typing import Optional
from sqlalchemy import (
    Boolean, Integer, Float, String, Text, DateTime, Date, ForeignKey, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(200), nullable=False)
    # role values: "admin" | "readwrite" | "readonly"
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="readwrite")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Well(Base):
    __tablename__ = "wells"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    field: Mapped[Optional[str]] = mapped_column(String(200))
    borehole: Mapped[Optional[str]] = mapped_column(String(200))
    location: Mapped[Optional[str]] = mapped_column(String(200))
    rig: Mapped[Optional[str]] = mapped_column(String(200))
    client: Mapped[Optional[str]] = mapped_column(String(200))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    bha_runs: Mapped[list["BhaRun"]] = relationship(back_populates="well", cascade="all, delete-orphan")


class BhaConfig(Base):
    __tablename__ = "bha_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(300), unique=True, nullable=False)
    source_filename: Mapped[Optional[str]] = mapped_column(String(500))
    source_unit_system: Mapped[Optional[str]] = mapped_column(String(20))  # "field" | "metric"
    hole_size_in: Mapped[Optional[float]] = mapped_column(Float)
    motor_make: Mapped[Optional[str]] = mapped_column(String(200))
    motor_model: Mapped[Optional[str]] = mapped_column(String(200))
    motor_serial: Mapped[Optional[str]] = mapped_column(String(200))
    motor_bent_deg: Mapped[Optional[float]] = mapped_column(Float)
    bend_to_bit_ft: Mapped[Optional[float]] = mapped_column(Float)
    motor_od_in: Mapped[Optional[float]] = mapped_column(Float)
    motor_length_ft: Mapped[Optional[float]] = mapped_column(Float)
    designed_by: Mapped[Optional[str]] = mapped_column(String(200))
    bha_date: Mapped[Optional[date]] = mapped_column(Date)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    components_json: Mapped[Optional[str]] = mapped_column(Text)
    stabilizers_json: Mapped[Optional[str]] = mapped_column(Text)
    sensor_offsets_json: Mapped[Optional[str]] = mapped_column(Text)
    nozzles_json: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    bha_runs: Mapped[list["BhaRun"]] = relationship(back_populates="bha_config")


class BhaRun(Base):
    __tablename__ = "bha_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    well_id: Mapped[int] = mapped_column(ForeignKey("wells.id"), nullable=False)
    bha_config_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bha_configs.id"))
    bha_name: Mapped[Optional[str]] = mapped_column(String(300))
    bit_run_number: Mapped[Optional[int]] = mapped_column(Integer)
    source_unit_system: Mapped[Optional[str]] = mapped_column(String(20))

    hole_size_in: Mapped[Optional[float]] = mapped_column(Float)
    casing_shoe_ft: Mapped[Optional[float]] = mapped_column(Float)
    casing_size_in: Mapped[Optional[float]] = mapped_column(Float)
    casing_weight_lbm_ft: Mapped[Optional[float]] = mapped_column(Float)
    mud_type: Mapped[Optional[str]] = mapped_column(String(200))
    end_mw_ppg: Mapped[Optional[float]] = mapped_column(Float)

    motor_bent_deg: Mapped[Optional[float]] = mapped_column(Float)
    motor_make: Mapped[Optional[str]] = mapped_column(String(200))
    motor_model: Mapped[Optional[str]] = mapped_column(String(200))

    depth_in_ft: Mapped[Optional[float]] = mapped_column(Float)
    depth_out_ft: Mapped[Optional[float]] = mapped_column(Float)
    incl_in_deg: Mapped[Optional[float]] = mapped_column(Float)
    incl_out_deg: Mapped[Optional[float]] = mapped_column(Float)
    azimuth_in_deg: Mapped[Optional[float]] = mapped_column(Float)
    azimuth_out_deg: Mapped[Optional[float]] = mapped_column(Float)

    date_in: Mapped[Optional[datetime]] = mapped_column(DateTime)
    date_td: Mapped[Optional[datetime]] = mapped_column(DateTime)
    date_out: Mapped[Optional[datetime]] = mapped_column(DateTime)
    drilling_hours: Mapped[Optional[float]] = mapped_column(Float)
    pumping_hours: Mapped[Optional[float]] = mapped_column(Float)
    brt_hours: Mapped[Optional[float]] = mapped_column(Float)

    dd_primary: Mapped[Optional[str]] = mapped_column(String(200))
    dd_secondary: Mapped[Optional[str]] = mapped_column(String(200))
    client_rep_primary: Mapped[Optional[str]] = mapped_column(String(200))
    client_rep_secondary: Mapped[Optional[str]] = mapped_column(String(200))

    bit_serial: Mapped[Optional[str]] = mapped_column(String(200))
    bit_type: Mapped[Optional[str]] = mapped_column(String(200))
    bit_manuf: Mapped[Optional[str]] = mapped_column(String(200))
    bit_iadc: Mapped[Optional[str]] = mapped_column(String(100))
    bit_jets: Mapped[Optional[str]] = mapped_column(String(100))
    bit_tfa_in2: Mapped[Optional[float]] = mapped_column(Float)
    bit_dull_in_json: Mapped[Optional[str]] = mapped_column(Text)
    bit_dull_out_json: Mapped[Optional[str]] = mapped_column(Text)

    stand_length_ft: Mapped[float] = mapped_column(Float, default=96.0)
    source_filename: Mapped[Optional[str]] = mapped_column(String(500))
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    well: Mapped["Well"] = relationship(back_populates="bha_runs")
    bha_config: Mapped[Optional["BhaConfig"]] = relationship(back_populates="bha_runs")
    surveys: Mapped[list["Survey"]] = relationship(back_populates="bha_run", cascade="all, delete-orphan", order_by="Survey.sequence")
    slide_intervals: Mapped[list["SlideInterval"]] = relationship(back_populates="bha_run", cascade="all, delete-orphan", order_by="SlideInterval.sequence")
    motor_outputs: Mapped[list["MotorOutput"]] = relationship(back_populates="bha_run", cascade="all, delete-orphan", order_by="MotorOutput.sequence")

    __table_args__ = (
        Index("ix_bha_runs_well_id", "well_id"),
        Index("ix_bha_runs_motor_bent_deg", "motor_bent_deg"),
        Index("ix_bha_runs_hole_size_in", "hole_size_in"),
    )


class Survey(Base):
    __tablename__ = "surveys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bha_run_id: Mapped[int] = mapped_column(ForeignKey("bha_runs.id"), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    svy_md_ft: Mapped[float] = mapped_column(Float, nullable=False)
    incl_deg: Mapped[float] = mapped_column(Float, nullable=False)
    azmth_deg: Mapped[float] = mapped_column(Float, nullable=False)
    dls_deg_per_100ft: Mapped[float] = mapped_column(Float, nullable=False)

    bha_run: Mapped["BhaRun"] = relationship(back_populates="surveys")

    __table_args__ = (Index("ix_surveys_bha_run_id", "bha_run_id"),)


class SlideInterval(Base):
    __tablename__ = "slide_intervals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bha_run_id: Mapped[int] = mapped_column(ForeignKey("bha_runs.id"), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    md_from_ft: Mapped[float] = mapped_column(Float, nullable=False)
    md_to_ft: Mapped[float] = mapped_column(Float, nullable=False)
    mode: Mapped[str] = mapped_column(String(50), nullable=False)
    course_ft: Mapped[Optional[float]] = mapped_column(Float)
    calc_rop: Mapped[Optional[float]] = mapped_column(Float)
    tf_mode: Mapped[Optional[str]] = mapped_column(String(50))
    tf_angle: Mapped[Optional[float]] = mapped_column(Float)
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime)

    bha_run: Mapped["BhaRun"] = relationship(back_populates="slide_intervals")

    __table_args__ = (Index("ix_slide_intervals_bha_run_id", "bha_run_id"),)


class MotorOutput(Base):
    __tablename__ = "motor_outputs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bha_run_id: Mapped[int] = mapped_column(ForeignKey("bha_runs.id"), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    svy_md_ft: Mapped[float] = mapped_column(Float, nullable=False)
    incl_deg: Mapped[float] = mapped_column(Float, nullable=False)
    azmth_deg: Mapped[float] = mapped_column(Float, nullable=False)
    dls_deg_per_100ft: Mapped[float] = mapped_column(Float, nullable=False)
    slide_footage_ft: Mapped[Optional[float]] = mapped_column(Float)
    motor_output_deg_per_ft: Mapped[Optional[float]] = mapped_column(Float)
    full_stand_deg: Mapped[Optional[float]] = mapped_column(Float)

    bha_run: Mapped["BhaRun"] = relationship(back_populates="motor_outputs")

    __table_args__ = (Index("ix_motor_outputs_bha_run_id", "bha_run_id"),)
