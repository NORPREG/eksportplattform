import subprocess
import os
import tomllib
from sqlmodel import Session, create_engine, select
import logging
from datetime import datetime
from pprint import pprint
import json
from pathlib import Path

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

from module.utils import tools
from module.utils.DICOMSR import DICOMSR

logger = logging.getLogger(__name__)

def find_transmitted_patients():
    # TODO: Change this to use the log database instead of the conquest database
	return conquest_db_interface.get_patient_ids(conquest_krest_engine)

def find_all_patients_in_aria_since(start_date):
	return aria_db_interface.get_plan_set(start_date)

def find_patient_id(plan_set):
    for plan_sop_uid in plan_set["PlanSet"]:
        if patient_id := conquest_db_interface.get_patient_id_from_plan_sop_uid(plan_sop_uid):
            plan_set["PatientID"] = patient_id
            break

def move_patient_to_conquest(plan_set):
	for plan_sop_uid in plan_set["PlanSet"]:
		plan_root = plan_set["PlanSet"][plan_sop_uid]

		# Check if any of the RT PLAN or RT DOSE files are missing
		uids = [plan_sop_uid]
		for dose_uid in list(plan_root["RTDOSE"]):
			uids.append(dose_uid)

		uids_exist = { uid: conquest_db_interface.check_exists_sop(uid) for uid in uids}

		tools.transmit_rt_plan_dose(uids_exist)

		# Find the structure set UIDs + plan labels from the RT Plan file
		structure_set_uids, plan_label = conquest_db_interface.get_rt_struct_uid(plan_sop_uid)

		plan_root["RTPlanLabel"] = plan_label
        plan_root["RTSTRUCT"].update(structure_set_uids)
		tools.transmit_rt_struct(structure_set_uids)
        
		# Download the associated CT
		for instance_uid in structure_set_uids:
			ct_series_uid_list = conquest_db_interface.find_referenced_ct_series(instance_uid)

            plan_root["CT"].update(ct_series_uid_list)
			tools.transmit_ct_series(ct_series_uid_list)

    if not plan_set["PatientID"]:
        find_patient_id(plan_set)

    # Two conquest interfaces locally:
    # 1. conquest_aria.dicom.aet ('medfys') to talk to aria
    #   At this state the patient is located here
    # 2. conquest_krest.dicom.aet ('medfys2') to talk to KREST-HUS

    # Now we transmit the patient to the second internal Conquest
	conquest_dicom_interface.c_move_to_medfys2(plan_set)

def move_patient_to_ous(plan_set):
	conquest_dicom_interface.c_move_to_krest_hus(plan_set)

def parse_apprecs():
	engine = create_engine(config.conquest_krest.sql.uri)
	statement = select(DICOMImages).where(
		DICOMImages.SOPClassUID == str(DICOMSR.basicTextSRStorage)
	)

	apprecs = []

	with Session(engine) as session:
		sr_files = session.exec(statement).all()

	for sr_file in sr_files:
		filepath = Path(config.conquest_krest.root_dir) / sr_file.ObjectFile
		if not filepath.exists():
			logger.warning("Apprec SR file is missing on disk: %s", filepath)
			continue

		try:
			sr_document = DICOMSR.from_file(str(filepath))
			raw_message = sr_document.get_text_value()
			if not raw_message:
				logger.warning("Apprec SR file does not contain a text payload: %s", filepath)
				continue

			apprec_payload = json.loads(raw_message)
		except (OSError, json.JSONDecodeError, ValueError) as exc:
			logger.warning("Unable to parse apprec SR file %s: %s", filepath, exc)
			continue

		if not isinstance(apprec_payload, dict):
			logger.warning("Apprec payload is not a JSON object: %s", filepath)
			continue

		status = apprec_payload.get("status")
		if isinstance(status, str):
			status = status.strip().lower() == "true"

		message = apprec_payload.get("message")
		if message is None:
			message = ""
		else:
			message = str(message)

		study_uid = getattr(sr_document.ds, "StudyInstanceUID", None)
		patient_id = getattr(sr_document.ds, "PatientID", None) or sr_file.ImagePat

		apprecs.append({
			"patient_id": patient_id,
			"study_uid": study_uid,
			"status": status,
			"message": message,
			"apprec_message": raw_message,
			"image_date": sr_file.ImageDate,
			"image_time": sr_file.ImageTime,
			"sr_sop_uid": getattr(sr_document.ds, "SOPInstanceUID", sr_file.SOPInstanceUID),
			"filepath": str(filepath),
		})

	return apprecs

def print_error_messages(apprecs):
	error_apprecs = []

    print(f"Fant {len(apprecs)} apprec SR-filer i Conquest-databasen.")
	for apprec in apprecs:
		status = apprec.get("status")
		message = str(apprec.get("message") or "").strip()

		if status is True and not message:
			continue

		patient_id = apprec.get("patient_id") or "<unknown>"
		study_uid = apprec.get("study_uid") or "<unknown>"
		sr_sop_uid = apprec.get("sr_sop_uid") or "<unknown>"
		filepath = apprec.get("filepath") or "<unknown>"
		error_message = message or "Ukjent apprec-feil"

		formatted_message = (
			f"Apprec-feil for patient_id={patient_id}, study_uid={study_uid}: "
			f"{error_message} (sr_sop_uid={sr_sop_uid}, filepath={filepath})"
		)

		logger.error(formatted_message)
		print(formatted_message)
		error_apprecs.append(apprec)

	return error_apprecs

def remove_old_apprec_messages(apprecs):
	# Dersom flere apprecs er funnet på samme study, behold kun den nyeste.
	# Dette for å unngå at gamle apprec-meldinger overskriver nyere meldinger.
	if not apprecs:
		return []

	def get_apprec_sort_key(apprec: dict) -> tuple[datetime, str]:
		image_date = str(apprec.get("image_date") or "").strip()
		image_time = str(apprec.get("image_time") or "").strip()

		if image_date and image_time:
			try:
				apprec_dt = datetime.strptime(
					f"{image_date} {image_time.split('.')[0]}",
					"%Y-%m-%d %H:%M:%S",
				)
				return apprec_dt, str(apprec.get("sr_sop_uid") or "")
			except ValueError:
				pass

		if image_date:
			try:
				apprec_dt = datetime.strptime(image_date, "%Y-%m-%d")
				return apprec_dt, str(apprec.get("sr_sop_uid") or "")
			except ValueError:
				pass

		filepath = apprec.get("filepath")
		if filepath and Path(filepath).exists():
			modified_dt = datetime.fromtimestamp(Path(filepath).stat().st_mtime)
			return modified_dt, str(apprec.get("sr_sop_uid") or "")

		return datetime.min, str(apprec.get("sr_sop_uid") or "")

	newest_by_study_uid = {}

	for apprec in apprecs:
		study_uid = apprec.get("study_uid")
		if not study_uid:
			continue

		existing_apprec = newest_by_study_uid.get(study_uid)
		if existing_apprec is None:
			newest_by_study_uid[study_uid] = apprec
			continue

		if get_apprec_sort_key(apprec) >= get_apprec_sort_key(existing_apprec):
			newest_by_study_uid[study_uid] = apprec

	filtered_apprecs = []
	for apprec in apprecs:
		study_uid = apprec.get("study_uid")
		if not study_uid:
			filtered_apprecs.append(apprec)
			continue

		if newest_by_study_uid.get(study_uid) is apprec:
			filtered_apprecs.append(apprec)

	removed_count = len(apprecs) - len(filtered_apprecs)
	if removed_count > 0:
		logger.info("Removed %s outdated apprec messages", removed_count)

	return filtered_apprecs

    