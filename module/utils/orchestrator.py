import subprocess
import os
import tomllib
from sqlmodel import Session, create_engine, select
import logging
from datetime import datetime
from pprint import pprint
import json
from glob import glob
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

log_database = export_logger_interface.LogDatabase()

from module.utils import tools
from module.utils.DICOMSR import make_dataset, DICOMSR

logger = logging.getLogger(__name__)

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
				raise ValueError(f"Apprec SR file does not contain a text payload: {filepath}")

			apprec_payload = json.loads(raw_message)
		except (OSError, json.JSONDecodeError, ValueError) as exc:
			raise ValueError(f"Unable to parse apprec SR file {filepath}: {exc}")

		if not isinstance(apprec_payload, dict):
			raise ValueError(f"Apprec payload is not a JSON object: {filepath}")

		status = apprec_payload.get("status")
		message = apprec_payload.get("message")
		plan_sop_uid = apprec_payload.get("plan_sop_uid")

		apprecs.append({
			"plan_sop_uid": plan_sop_uid,
			"status": status,
			"message": message,
			"apprec_message": raw_message,
			"dicom_uid": getattr(sr_document.ds, "SOPInstanceUID", sr_file.SOPInstanceUID),
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

		# patient_id = apprec.get("patient_id") or "<unknown>"
		patient_id = "<redacted>"
		study_uid = apprec.get("study_uid") or "<unknown>"
		dicom_uid = apprec.get("dicom_uid") or "<unknown>"
		filepath = apprec.get("filepath") or "<unknown>"
		error_message = message or "Ukjent apprec-feil"

		formatted_message = (
			f"Apprec-feil for patient_id={patient_id}, study_uid={study_uid}: "
			f"{error_message} (dicom_uid={dicom_uid}, filepath={filepath})"
		)

		logger.error(formatted_message)
		print(formatted_message)
		error_apprecs.append(apprec)

	return error_apprecs

def remove_old_apprec_messages(apprecs):
	# Dersom flere apprecs er funnet på samme Plan SOP UID, behold kun den nyeste.
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
				return apprec_dt, str(apprec.get("dicom_uid") or "")
			except ValueError:
				pass

		if image_date:
			try:
				apprec_dt = datetime.strptime(image_date, "%Y-%m-%d")
				return apprec_dt, str(apprec.get("dicom_uid") or "")
			except ValueError:
				pass

		filepath = apprec.get("filepath")
		if filepath and Path(filepath).exists():
			modified_dt = datetime.fromtimestamp(Path(filepath).stat().st_mtime)
			return modified_dt, str(apprec.get("dicom_uid") or "")

		return datetime.min, str(apprec.get("dicom_uid") or "")

	newest_by_plan_sop_uid = {}

	for apprec in apprecs:
		plan_sop_uid = apprec.get("plan_sop_uid")
		if not plan_sop_uid:
			continue

		existing_apprec = newest_by_plan_sop_uid.get(plan_sop_uid)
		if existing_apprec is None:
			newest_by_plan_sop_uid[plan_sop_uid] = apprec
			continue

		if get_apprec_sort_key(apprec) >= get_apprec_sort_key(existing_apprec):
			newest_by_plan_sop_uid[plan_sop_uid] = apprec

	filtered_apprecs = []
	for apprec in apprecs:
		plan_sop_uid = apprec.get("plan_sop_uid")
		if not plan_sop_uid:
			filtered_apprecs.append(apprec)
			continue

		if newest_by_plan_sop_uid.get(plan_sop_uid) is apprec:
			filtered_apprecs.append(apprec)

	removed_count = len(apprecs) - len(filtered_apprecs)
	if removed_count > 0:
		logger.info("Removed %s outdated apprec messages", removed_count)

	return filtered_apprecs


def find_all_npr_files() -> list[str]:
	npr_files = []

	if not Path(config.npr.root_dir).exists():
		logger.warning("NPR directory does not exist: %s", config.npr.root_dir)
		return npr_files

	if config.npr.structure == "YEAR":
		for year_folder in glob(f"{config.npr.root_dir}/*"):
			for file in glob(f"{year_folder}/*.{config.npr.file_extension}"):
				npr_files.append(file)

	elif config.npr.structure == "FLAT":
		for file in glob(f"{config.npr.root_dir}/*.{config.npr.file_extension}"):
			npr_files.append(file)

	return npr_files

def process_npr():
	all_available_npr_files = find_all_npr_files()
	for npr_file in all_available_npr_files:
		if log_database.check_if_nprfile_is_sent(npr_file):
			continue

		dicom_uid = send_nprfile_to_krest(npr_file)

		npr_file_info = {
			"file_name": npr_file,
			"bytes": tools.get_bytes_stored([npr_file]),
			"md5_hash": tools.md5hash(npr_file),
			"dicom_uid": dicom_uid,
			"sent_dt": datetime.now()
		}

		log_database.add_nprfile(npr_file_info)

def send_nprfile_to_krest(npr_file):
	"""	Send NPR files to KREST-HUS and return a list of dictionaries with file information.
		Encapsulate contents of each npr_file in a new DICOM SR file
		Send this DICOM SR til KREST	
	"""

	contents = Path(npr_file).read_text(encoding="utf-8")
	ds = make_dataset(parentUID=config.npr.uid_root, patientID="NPR FILE", patientName="NPR FILE", content_string=contents)
	sop_uid = ds.SOPInstanceUID

	conquest_dicom_interface.c_store_krest(ds)

	return sop_uid