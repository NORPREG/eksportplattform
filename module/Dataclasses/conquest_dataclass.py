from pydantic import PlainSerializer, BeforeValidator
from sqlalchemy import String, Column
from typing import List, Optional
from typing_extensions import Annotated
from datetime import datetime
from sqlmodel import Field, SQLModel, Relationship

# See dicom.sql in the Conquest folder for more info on how the SQL values are connected
# to the DICOM tags

# Definitions of the custom Conquest date formats. See the following on the Annotated style
# https://stackoverflow.com/questions/66548586/how-to-change-date-format-in-pydantic
# https://docs.pydantic.dev/latest/concepts/types/#adding-validation-and-serialization


# Implement the new sa_column type from here:
# https://github.com/tiangolo/sqlmodel/pull/436

def dicom_date_formatter(d: str) -> str:
	return datetime.strptime(d, "%Y%m%d").strftime("%Y-%m-%d")


def dicom_date_serializer(d: str) -> str:
	if not d:
		return d

	return datetime.strptime(d, "%Y%m%d").strftime("%Y-%m-%d")


def dicom_time_formatter(t: str) -> str:
	# Not consequent if the time is stored with or without trailing micro seconds
	# We drop them, shouldn't be neccessary
	t_int = t.split(".")[0]

	return datetime.strptime(t_int, "%H%M%S").strftime("%H:%M:%S")


def dicom_time_serializer(t: str) -> str:
	if not t:
		return t

	# Not consequent if the time is stored with or without trailing micro seconds
	# We drop them, shouldn't be neccessary
	t_int = t.split(".")[0]

	return datetime.strptime(t_int, "%H%M%S").strftime("%H:%M:%S")


DICOMDate = Annotated[str, BeforeValidator(dicom_date_formatter), PlainSerializer(dicom_date_serializer)]
DICOMTime = Annotated[str, BeforeValidator(dicom_time_formatter), PlainSerializer(dicom_time_serializer)]

# SQLModel class definitions
# The alias=... doesn't seem to work when using the SQLModel wrapper,
# so the sa_column SQL Alchemy method had to be used


class DICOMImages(SQLModel, table=True):

	# By default, SQLModel assumes that the SQL table name is __class__.__name__.lower()
	# Can be overriden by the __tablename__ property
	__tablename__ = "DICOMImages"

	SOPInstanceUID: str = Field(sa_column=Column("SOPInstanc", String, primary_key=True))
	SOPClassUID: str = Field(sa_column=Column("SOPClassUI", String))
	ImageNumber: Optional[int] = Field(sa_column=Column("ImageNumbe", String), default=None)
	ImageDate: DICOMDate
	ImageTime: DICOMTime
	NumberOfFrames: int = Field(sa_column=Column("NumberOfFr", String))
	AcquisitionDate: DICOMDate = Field(sa_column=Column("AcqDate", String))
	AcquisitionTime: DICOMTime = Field(sa_column=Column("AcqTime", String))
	AcquisitionNumber: str = Field(sa_column=Column("AcqNumber", String))
	SliceLocation: str = Field(sa_column=Column("SliceLocat", String))
	Rows: int = Field(sa_column=Column("QRows", String))
	Columns: int = Field(sa_column=Column("QColumns", String))
	ImageType: str
	ImageID: str
	DeviceName: str
	ObjectFile: str
	SeriesInst: str = Field(default=None, foreign_key="DICOMSeries.SeriesInst")
	ImagePat: str = Field(default=None, foreign_key="DICOMPatients.PatientID")

	# SQLModel defined relationship tags to model the hierarchy
	series: "DICOMSeries" = Relationship(back_populates="images")


class DICOMSeries(SQLModel, table=True):
	__tablename__ = "DICOMSeries"

	SeriesInstanceUID: str = Field(sa_column=Column("SeriesInst", 
						String, primary_key=True))
	SeriesNumber: str = Field(sa_column=Column("SeriesNumb", String))
	SeriesDate: DICOMDate
	SeriesTime: DICOMTime
	SeriesDescription: str = Field(sa_column=Column("SeriesDesc", String))
	Modality: str
	PatientPosition: str = Field(sa_column=Column("PatientPos", String))
	Manufacturer: str = Field(sa_column=Column("Manufactur", String))
	ModelName: str
	BodyPartExamined: str = Field(sa_column=Column("BodyPartEx", String))
	ProtocolName: str = Field(sa_column=Column("ProtocolNa", String))
	StationName: str = Field(sa_column=Column("StationNam", String))
	Institution: str = Field(sa_column=Column("Institutio", String))
	FrameOfReferenceUID: str = Field(sa_column=Column("FrameOfRef", String))
	AccessTime: int

	StudyInsta: str = Field(foreign_key="DICOMStudies.StudyInsta")

	# SQLModel defined relationship tags to model the hierarchy
	images: List[DICOMImages] = Relationship(back_populates="series")
	study: Optional["DICOMStudies"] = Relationship(back_populates="series")


class DICOMStudies(SQLModel, table=True):
	__tablename__ = "DICOMStudies"

	# StudyInsta: str = Field(primary_key=True)
	StudyInstanceUID: str = Field(sa_column=Column("StudyInsta", String, primary_key=True))
	StudyDate: DICOMDate
	StudyTime: DICOMTime
	StudyID: str
	StudyDescription: str = Field(sa_column=Column("StudyDescr", String))
	AccessionNumber: str = Field(sa_column=Column("AccessionN", String))
	ReferringPhysician: str = Field(sa_column=Column("ReferPhysi", String))
	PatientsAge: str = Field(sa_column=Column("PatientsAg", String))
	PatientsWeight: str = Field(sa_column=Column("PatientsWe", String))
	AccessTime: int

	PatientID: str = Field(foreign_key="DICOMPatients.PatientID")

	# SQLModel defined relationship tags to model the hierarchy
	series: List[DICOMSeries] = Relationship(back_populates="study")
	patient: Optional["DICOMPatients"] = Relationship(back_populates="studies")


class DICOMPatients(SQLModel, table=True):
	__tablename__ = "DICOMPatients"

	PatientID: str = Field(primary_key=True)
	PatientName: str = Field(sa_column=Column("PatientNam", String))
	PatientBirthdate: DICOMDate = Field(sa_column=Column("PatientBir", String))
	PatientSex: str
	AccessTime: int

	# SQLModel defined relationship tags to model the hierarchy
	studies: List[DICOMStudies] = Relationship(back_populates="patient")


DICOMImages.model_rebuild()
DICOMSeries.model_rebuild()
DICOMStudies.model_rebuild()
DICOMPatients.model_rebuild()
