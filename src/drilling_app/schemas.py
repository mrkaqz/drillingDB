from __future__ import annotations
from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel


class WellCreate(BaseModel):
    name: str
    field: Optional[str] = None
    borehole: Optional[str] = None
    location: Optional[str] = None
    rig: Optional[str] = None
    client: Optional[str] = None
    notes: Optional[str] = None


class WellOut(WellCreate):
    id: int
    created_at: datetime
    class Config: from_attributes = True


class BhaConfigCreate(BaseModel):
    name: str
    hole_size_in: Optional[float] = None
    motor_make: Optional[str] = None
    motor_model: Optional[str] = None
    motor_serial: Optional[str] = None
    motor_bent_deg: Optional[float] = None
    bend_to_bit_ft: Optional[float] = None
    motor_od_in: Optional[float] = None
    motor_length_ft: Optional[float] = None
    designed_by: Optional[str] = None
    bha_date: Optional[date] = None
    notes: Optional[str] = None
    source_filename: Optional[str] = None
    source_unit_system: Optional[str] = None
    components_json: Optional[str] = None
    stabilizers_json: Optional[str] = None
    sensor_offsets_json: Optional[str] = None
    nozzles_json: Optional[str] = None


class BhaConfigOut(BhaConfigCreate):
    id: int
    created_at: datetime
    class Config: from_attributes = True


class ImportFormData(BaseModel):
    well_name: str
    field: Optional[str] = None
    location: Optional[str] = None
    rig: Optional[str] = None
    client: Optional[str] = None
    motor_bent_deg: Optional[float] = None
    motor_make: Optional[str] = None
    motor_model: Optional[str] = None
    stand_length_ft: float = 96.0
    notes: Optional[str] = None


class MotorOutputOut(BaseModel):
    sequence: int
    svy_md_ft: float
    incl_deg: float
    azmth_deg: float
    dls_deg_per_100ft: float
    slide_footage_ft: Optional[float]
    motor_output_deg_per_ft: Optional[float]
    full_stand_deg: Optional[float]
    class Config: from_attributes = True


class BhaRunOut(BaseModel):
    id: int
    well_id: int
    bha_name: Optional[str]
    bit_run_number: Optional[int]
    hole_size_in: Optional[float]
    motor_bent_deg: Optional[float]
    motor_make: Optional[str]
    motor_model: Optional[str]
    depth_in_ft: Optional[float]
    depth_out_ft: Optional[float]
    incl_in_deg: Optional[float]
    incl_out_deg: Optional[float]
    date_in: Optional[datetime]
    date_out: Optional[datetime]
    drilling_hours: Optional[float]
    pumping_hours: Optional[float]
    stand_length_ft: float
    source_filename: Optional[str]
    source_unit_system: Optional[str]
    imported_at: datetime
    class Config: from_attributes = True
