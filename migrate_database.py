import subprocess
import os
import tomllib
from sqlmodel import Session, create_engine, select
import logging
from datetime import datetime
from pprint import pprint

from config import Config

config = Config()

from module.Dataclasses.conquest_dataclass import (
	DICOMImages, 
	DICOMPatients,
	DICOMSeries
)

from module.Dataclasses import export_logger_dataclass

from module.Interfaces import (
	aria_db_interface,
	aria_dicom_interface,
	conquest_db_interface,
	conquest_dicom_interface,
	export_logger_interface
)

log_database = export_logger_interface.LogDatabase()


def get_bytes_stored(filenames):
	size = 0
	for filename in filenames:
		if filename:
			size += os.path.getsize(config.conquest_aria.root_dir + filename)

	return size

engine = create_engine(config.log_db.uri)
conquest_aria_engine = conquest_db_interface.create_engine(config.conquest_aria.sql.uri)

log = log_database.log
for course in log:

	db_course = export_logger_dataclass.Course(
		patient_ser = str(course.get("patient_ser")),
		sent_dt = datetime.fromisoformat(course.get("sent_dt"))
	)

	for plan_uid, plan_set in course.get("plan_set", {}).items():
		rt_plan_label = plan_set.get("RTPlanLabel")

		db_plan_set = export_logger_dataclass.RTPlan(
			plan_sop_uid = plan_uid,
			plan_label = rt_plan_label
		)

		for modality_c in export_logger_dataclass.Modality:
			modality = modality_c.value
			for item in plan_set.get(modality, []):
				if modality == "CT":
					type_uid = "SERIES_INSTANCE"
					filenames = conquest_db_interface.get_series_filenames(conquest_aria_engine, item)
				else:
					type_uid = "SOP_INSTANCE"
					filenames = conquest_db_interface.get_sop_filenames(conquest_aria_engine, item)
				
				bytes_stored = get_bytes_stored(filenames)

				db_dicom_object = export_logger_dataclass.DicomObject(
					reference_uid = item,
					type_uid = type_uid,
					bytes_stored = bytes_stored,
					modality = modality
				)

				db_plan_set.dicom_objects.append(db_dicom_object)

		db_course.rtplans.append(db_plan_set)

	with Session(engine) as session:
		session.add(db_course)
		session.commit()