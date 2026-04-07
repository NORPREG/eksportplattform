from datetime import datetime
from typing import Optional, List

from sqlmodel import SQLModel, Field, Relationship

# sent_status: Not started; Identified; Aria Exported; KREST Exported

# -------------------------
# Patient
# -------------------------

class Patient(SQLModel, table=True):
    patient_ser: Optional[int] = Field(default=None, primary_key=True)

    courses: List["Course"] = Relationship(back_populates="patient")


# -------------------------
# Course
# -------------------------

class Course(SQLModel, table=True):
    course_ser: Optional[int] = Field(default=None, primary_key=True)

    patient_ser: int = Field(foreign_key="patient.patient_ser")
    patient: Optional[Patient] = Relationship(back_populates="courses")

    rtplans: List["RTPlan"] = Relationship(back_populates="course")
    nprs: List["NPR"] = Relationship(back_populates="course")


# -------------------------
# RTPLAN
# -------------------------

class RTPlan(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    course_ser: int = Field(foreign_key="course.course_ser")
    course: Optional[Course] = Relationship(back_populates="rtplans")

    sop_instance_uid: str = Field(unique=True, index=True)
    series_instance_uid: str = Field(unique=True, index=True)

    sent_dt: datetime
    sent_status: str

    file_dt: datetime

    apprec_code: Optional[str] = None
    apprec_text: Optional[str] = None

    rtrecords: List["RTRecord"] = Relationship(back_populates="rtplan")
    rtstructs: List["RTStruct"] = Relationship(back_populates="rtplan")
    rtdoses: List["RTDose"] = Relationship(back_populates="rtplan")
    cts: List["CT"] = Relationship(back_populates="rtplan")


# -------------------------
# RTRECORD
# -------------------------

class RTRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    rtplan_id: int = Field(foreign_key="rtplan.id")
    rtplan: Optional[RTPlan] = Relationship(back_populates="rtrecords")

    sop_instance_uid: str = Field(unique=True, index=True)
    series_instance_uid: str = Field(unique=True, index=True)

    file_dt: datetime


# -------------------------
# RTSTRUCT
# -------------------------

class RTStruct(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    rtplan_id: int = Field(foreign_key="rtplan.id")
    rtplan: Optional[RTPlan] = Relationship(back_populates="rtstructs")

    sop_instance_uid: str = Field(unique=True, index=True)
    series_instance_uid: str = Field(unique=True, index=True)

    file_dt: datetime


# -------------------------
# RTDOSE
# -------------------------

class RTDose(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    rtplan_id: int = Field(foreign_key="rtplan.id")
    rtplan: Optional[RTPlan] = Relationship(back_populates="rtdoses")

    sop_instance_uid: str = Field(unique=True, index=True)
    series_instance_uid: str = Field(unique=True, index=True)

    dose_type: str
    file_dt: datetime


# -------------------------
# CT
# -------------------------

class CT(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    rtplan_id: int = Field(foreign_key="rtplan.id")
    rtplan: Optional[RTPlan] = Relationship(back_populates="cts")

    series_instance_uid: str = Field(unique=True, index=True)

    files_nb: Optional[int] = None
    file_dt: datetime


# -------------------------
# NPR
# -------------------------

class NPR(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    course_ser: int = Field(foreign_key="course.course_ser")
    course: Optional[Course] = Relationship(back_populates="nprs")

    sent_status: str
    sent_dt: Optional[datetime]