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


logging.basicConfig(
	filename="D:/Brokers/export.log", 
	filemode='a', 
	format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
	datefmt='%Y-%m-%d %H:%M:%S',
	level=logging.INFO)

logger = logging.getLogger(__name__)

log_database = export_logger_interface.LogDatabase()

# FIND RT PLAN, RT DOSE FROM SQL
# BUILD COMPLETE STUDY TREE
# DOWNLOAD RT PLANS (from SQL)
# DOWNLOAD ALL RT DOSE FILES (from SQL)
# FIND THE REFERENCED STRUCTURE FILES IN THE RT PLAN
# DOWNLOAD THE STRUCTURE FILES
# FIND THE REFERENCED CT FILES from RT STRUCT
# DOWNLOAD THE CONNECTED CT SERIES
# SEND TO MEDFYSHUS6666-2
# SEND TO KREST-HUS

dt = datetime(2026, 1, 1)
plan_set = aria_db_interface.get_plan_set(dt)

print(f"Found {len(plan_set)} patients since {dt.isoformat()}")

"""
plan_set = 
[ 
	PatientSer : { 
		"PatientSer": patient_ser,
		"PatientID" : patient_id,
		"PlanSet" : {
			RT Plan SOP UID : {
				"RTPLAN": [ RT Plan SOP UID ],
				"RTPlanLabel", 
				"RTDOSE": RT Dose SOP UID,
				"RTSTRUCT": RT Struct SOP UID,
				"RTRECORD": [ RT Treatment Record SOP UIDs ],
				"CT": Plan CT Series Instance UID,
			}
		}
	}
]

"""

conquest_aria_engine = create_engine(config.conquest_aria.sql.uri)
conquest_krest_engine = create_engine(config.conquest_krest.sql.uri)

transmitted = conquest_db_interface.get_patient_ids(conquest_krest_engine)

for patient_ser in plan_set:
	print("Working on patient", patient_ser)
	sent_dt = log_database.check_patient(patient_ser)

	if sent_dt:
		print(f"- Patient was transmitted to {config.krest.name} at {sent_dt}")
		# continue

	for plan_sop_uid in plan_set[patient_ser]["PlanSet"]:
		patient_id = conquest_db_interface.get_patient_id_from_plan_sop_uid(conquest_aria_engine, plan_sop_uid)
		plan_set[patient_ser]["PatientID"] = patient_id
		if patient_id:
			break

	print(f"{patient_id = }")

	if patient_id and patient_id in transmitted:
		print(f"Found patient in {config.conquest_aria.dicom.aet} database")
		continue

	for plan_sop_uid in plan_set[patient_ser]["PlanSet"]:
		# Move the treated RT Plans to Conquest

		# Check if any of the RT PLAN or RT DOSE files are missing
		uids = [plan_sop_uid]
		for dose_uid in list(plan_set[patient_ser]["PlanSet"][plan_sop_uid]["RTDOSE"]):
			uids.append(dose_uid)

		uids_exist = { uid: conquest_db_interface.check_exists_sop(conquest_aria_engine, uid) for uid in uids}

		# Keep single association if any of the files are missing
		if not all(uids_exist.values()):
			assoc = aria_dicom_interface.get_assoc()
			for uid, status in uids_exist.items():
				if not status:
					print("- Moving RT Plan / Dose with SOP UID", uid)
					aria_dicom_interface.c_move_image(assoc, uid)
			assoc.release()

		# REcheck for patient_id now
		if not plan_set[patient_ser]["PatientID"]:
			patient_id = conquest_db_interface.get_patient_id_from_plan_sop_uid(conquest_aria_engine, plan_sop_uid)
			plan_set[patient_ser]["PatientID"] = patient_id
			print(f"Found {patient_id = }")

		# Find the structure set UIDs + plan labels from the RT Plan file
		structure_set_uids, plan_label = conquest_db_interface.get_rt_struct_uid(conquest_aria_engine, plan_sop_uid)

		plan_set[patient_ser]["PlanSet"][plan_sop_uid]["RTPlanLabel"] = plan_label

		for instance_uid in structure_set_uids:
			plan_set[patient_ser]["PlanSet"][plan_sop_uid]["RTSTRUCT"].add(instance_uid)

			if not conquest_db_interface.check_exists_sop(conquest_aria_engine, instance_uid):
				print(f"- Moving Structure set Instance UID {instance_uid}")
				assoc = aria_dicom_interface.get_assoc()
				aria_dicom_interface.c_move_image(assoc, instance_uid)
				assoc.release()

		# Download the associated CT
		for instance_uid in structure_set_uids:
			ct_series_uid_list = conquest_db_interface.find_referenced_ct_series(conquest_aria_engine, instance_uid)
			for ct_series_uid in ct_series_uid_list:
				plan_set[patient_ser]["PlanSet"][plan_sop_uid]["CT"].add(ct_series_uid)

				if not conquest_db_interface.check_exists_series(conquest_aria_engine, ct_series_uid):
					print(f"- Moving CT Series with Series UID", ct_series_uid)
					assoc = aria_dicom_interface.get_assoc()
					aria_dicom_interface.c_move_series(assoc, ct_series_uid)
					assoc.release()

	conquest_dicom_interface.c_move_to_medfys2(conquest_krest_engine, plan_set[patient_ser])
	conquest_dicom_interface.c_move_to_krest_hus(plan_set[patient_ser])

	if not sent_dt:
		log_database.add_patient(conquest_aria_engine, plan_set[patient_ser])