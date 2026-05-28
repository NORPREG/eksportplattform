from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String


class Modality(str, Enum):
    RTDOSE = "RTDOSE"
    RTSTRUCT = "RTSTRUCT"
    RTRECORD = "RTRECORD"
    RTPLAN = "RTPLAN"
    CT = "CT"
    CBCT = "CBCT"
    MR = "MR"

class TypeUid(str, Enum):
    SOP_INSTANCE = "SOP_INSTANCE"
    SERIES_INSTANCE = "SERIES_INSTANCE"
    STUDY_INSTANCE = "STUDY_INSTANCE"

class Course(SQLModel, table=True):
    __tablename__ = "Course"

    course_id: Optional[int] = Field(default=None, sa_column=Column("CourseId", Integer, primary_key=True))
    patient_ser: str = Field(sa_column=Column("PatientSer"))
    sent_dt: datetime = Field(default_factory=datetime.utcnow, sa_column=Column("SentDt", DATETIME2))

    rtplans: list["RTPlan"] = Relationship(back_populates="course")


class RTPlan(SQLModel, table=True):
    __tablename__ = "RTPlan"

    rtplan_id: Optional[int] = Field(sa_column=Column("RtPlanId", Integer, primary_key=True))
    course_id: int = Field(sa_column=Column("CourseId", Integer, ForeignKey("Course.CourseId")))

    plan_sop_uid: str = Field(sa_column=Column("PlanSopUid"))
    plan_label: Optional[str] = Field(default=None, sa_column=Column("PlanLabel"))

    course: Optional[Course] = Relationship(back_populates="rtplans")

    dicom_objects: list["DicomObject"] = Relationship(
        back_populates="rtplan"
    )


class DicomObject(SQLModel, table=True):
    __tablename__ = "DicomObject"

    dicom_object_id: Optional[int] = Field(sa_column=Column("DicomObjectId", Integer, primary_key=True))

    rtplan_id: int = Field(
        sa_column=Column("RtPlanId", Integer, ForeignKey("RTPlan.RtPlanId"))
    )

    reference_uid: Optional[str] = Field(default=None, sa_column=Column("ReferenceUid"))
    type_uid: Optional[str] = Field(default=None, sa_column=Column("TypeUid"))

    modality: Modality = Field(sa_column=Column("Modality")) 

    bytes_stored: Optional[int] = Field(default=None, sa_column=Column("BytesStored"))

    created_dt: datetime = Field(default_factory=datetime.utcnow, sa_column=Column("CreatedDt", DATETIME2))

    rtplan: Optional[RTPlan] = Relationship(
        back_populates="dicom_objects"
    )