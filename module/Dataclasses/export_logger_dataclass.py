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
    SR = "SR"

class TypeUid(str, Enum):
    SOP_INSTANCE = "SOP_INSTANCE"
    SERIES_INSTANCE = "SERIES_INSTANCE"
    STUDY_INSTANCE = "STUDY_INSTANCE"

class DicomTransfer(SQLModel, table=True):
    __tablename__ = "DicomTransfer"

    dicom_transfer_id: int = Field(default=None, sa_column=Column("DicomTransferId", Integer, primary_key=True))
    patient_ser: str = Field(sa_column=Column("PatientSer"))
    sent_dt: datetime = Field(default_factory=datetime.now, sa_column=Column("SentDt", DATETIME2))

    rtplans: list["RTPlan"] = Relationship(back_populates="dicom_transfer")


class RTPlan(SQLModel, table=True):
    __tablename__ = "RTPlan"

    rtplan_id: int = Field(sa_column=Column("RtPlanId", Integer, primary_key=True))
    dicom_transfer_id: int = Field(sa_column=Column("DicomTransferId", Integer, ForeignKey("DicomTransfer.DicomTransferId")))

    plan_sop_uid: str = Field(sa_column=Column("PlanSopUid"))
    plan_label: Optional[str] = Field(default=None, sa_column=Column("PlanLabel"))
    apprec: Optional[str] = Field(default=None, sa_column=Column("Apprec"))

    dicom_transfer: Optional[DicomTransfer] = Relationship(back_populates="rtplans")
    apprecs: list["Apprec"] = Relationship(back_populates="rtplan")

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

class NPRFile(SQLModel, table=True):
    __tablename__ = "NPRFile"

    file_id: Optional[int] = Field(sa_column=Column("FileId", Integer, primary_key=True))
    file_name: Optional[str] = Field(default=None, sa_column=Column("FileName"))
    bytes: Optional[int] = Field(default=None, sa_column=Column("Bytes"))
    md5_hash: Optional[str] = Field(default=None, sa_column=Column("Md5Hash"))
    dicom_uid: Optional[str] = Field(default=None, sa_column=Column("DicomUid"))
    sent_dt: Optional[datetime] = Field(default=None, sa_column=Column("SentDt", DATETIME2))

class Apprec(SQLModel, table=True):
    __tablename__ = "Apprec"

    apprec_id: Optional[int] = Field(sa_column=Column("ApprecId", Integer, primary_key=True))
    rt_plan_id: int = Field(sa_column=Column("RtPlanId", Integer, ForeignKey("RTPlan.RtPlanId")))
    dicom_uid: Optional[str] = Field(default=None, sa_column=Column("DicomUid"))
    recieved_dt : Optional[datetime] = Field(default=None, sa_column=Column("RecievedDt", DATETIME2))
    message_contents: Optional[str] = Field(default=None, sa_column=Column("MessageContents"))
    message_status: Optional[int] = Field(default=None, sa_column=Column("MessageStatus"))

    rtplan: Optional[RTPlan] = Relationship(
        back_populates="apprecs"
    )