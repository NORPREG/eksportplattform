from sqlmodel import Session, create_engine, select
import logging
from datetime import datetime
from pprint import pprint
import json
from glob import glob
from pathlib import Path

from config import Config

config = Config()

DEBUG = True
USE_RTRECORD = False

from module.Dataclasses.conquest_dataclass import (
	DICOMImages,
	DICOMSeries,
)
from module.Dataclasses import export_logger_dataclass

from module.Interfaces import (
	aria_db_interface,
	conquest_db_interface,
	conquest_dicom_interface,
	export_logger_interface
)

log_database = export_logger_interface.LogDatabase()

from module.utils import tools
from module.utils.DICOMSR import make_dataset, DICOMSR
from module.utils.dicom_status import transfer_failure

logger = logging.getLogger(__name__)

def find_existing_patients_in_conquest():
	return conquest_db_interface.get_patient_ids()

def find_all_patients_in_aria_since(start_date):
	return aria_db_interface.get_plan_set(start_date)

def find_patient_id(plan_set):
	for plan_sop_uid in plan_set["PlanSet"]:
		if patient_id := conquest_db_interface.get_patient_id_from_plan_sop_uid(plan_sop_uid):
			plan_set["PatientID"] = patient_id
			break

def check_for_changes_and_errors(plan_set: dict) -> dict:
	"""Return new object UIDs and UIDs whose latest transmission attempt failed.

	History may contain more objects than the current, partially populated extract.
	Plan keys and labels are retained as context, not as objects to retransmit.
	"""
	patient_ser = int(plan_set["PatientSer"])
	plans = plan_set["PlanSet"]

	if DEBUG:
		print("plan_set = ")
		pprint(plan_set)

	transfer = export_logger_dataclass.DicomTransfer
	rtplan = export_logger_dataclass.RTPlan
	dicom_object = export_logger_dataclass.DicomObject

	if DEBUG:
		print("Identifying existing objects for patient_ser:", patient_ser)

	statement = (
		select(
			dicom_object.modality,
			dicom_object.type_uid,
			dicom_object.reference_uid,
			dicom_object.transfer_status,
			rtplan.plan_sop_uid,
		)
		.join(transfer, dicom_object.dicom_transfer_id == transfer.dicom_transfer_id)
		.join(rtplan, rtplan.rtplan_id == dicom_object.rtplan_id)
		.where(
			transfer.patient_ser == patient_ser,
			transfer.sent_dt.is_not(None),
		)
		.order_by(
			transfer.sent_dt.desc(),
			transfer.dicom_transfer_id.desc(),
			dicom_object.dicom_object_id.desc(),
		)
	)
	
	with Session(log_database.engine) as session:
		rows = session.exec(statement).all()

	if DEBUG:
		print(f"Found {len(rows)} existing objects in Logger DB:")
		pprint(rows)

	latest_objects = {}
	for plan_uid, modality, type_uid, reference_uid, status in rows:
		if reference_uid is not None:
			latest_objects.setdefault((plan_uid, modality, type_uid, reference_uid), status)

	sent_objects = {}
	failed_objects = {}
	for (plan_uid, modality, type_uid, reference_uid), status in latest_objects.items():
		if status == 1:
			sent_objects.setdefault(plan_uid, set()).add((modality, type_uid, reference_uid))
		elif status == 0:
			failed_objects.setdefault(plan_uid, set()).add((modality, type_uid, reference_uid))

	plan_set_changes = {**plan_set, "PlanSet": {}}
	for plan_uid, plan in plans.items():
		changed_plan = {"RTPlanLabel": plan.get("RTPlanLabel", "")}
		for modality in export_logger_dataclass.Modality:
			type_uid = (
				export_logger_dataclass.TypeUid.SERIES_INSTANCE.value
				if modality == export_logger_dataclass.Modality.CT
				else export_logger_dataclass.TypeUid.SOP_INSTANCE.value
			)
			changed_plan[modality.value] = {
				uid for uid in plan.get(modality.value, [])
				if (modality.value, type_uid, uid) not in sent_objects.get(plan_uid, set())
			}
			changed_plan[modality.value].update(
				uid for logged_modality, logged_type, uid in failed_objects.get(plan_uid, set())
				if logged_modality == modality.value and logged_type == type_uid
			)

		if any(changed_plan[modality.value] for modality in export_logger_dataclass.Modality):
			changed_plan["TransferResults"] = {
				(modality.value, uid): plan["TransferResults"][(modality.value, uid)]
				for modality in export_logger_dataclass.Modality
				for uid in changed_plan[modality.value]
				if (modality.value, uid) in plan.get("TransferResults", {})
			}
			plan_set_changes["PlanSet"][plan_uid] = changed_plan


	if DEBUG:
		print(f"After removing existing objects, remaining plans: {len(plan_set_changes['PlanSet'])}")

	return plan_set_changes

def move_patient_to_conquest(plan_set):
	def skip_plan(plan, message):
		failure = transfer_failure(message)
		results = plan.setdefault("TransferResults", {})
		for modality in export_logger_dataclass.Modality:
			for uid in plan.get(modality.value, []):
				results[(modality.value, uid)] = failure

	if DEBUG:
		print("Looping over PlanSet with ", len(plan_set["PlanSet"]), " plans.")

	for plan_sop_uid in plan_set["PlanSet"]:
		plan_root = plan_set["PlanSet"][plan_sop_uid]
		results = plan_root.setdefault("TransferResults", {})

		# Check if any of the RT PLAN or RT DOSE files are missing
		uids = [plan_sop_uid]
		for dose_uid in list(plan_root["RTDOSE"]):
			uids.append(dose_uid)

		uids_exist = { uid: conquest_db_interface.check_exists_sop(uid) for uid in uids}

		if DEBUG: 
			print("Transmit RT dose from Aria")

		local_results = tools.transmit_rt_plan_dose(uids_exist)
		for uid in plan_root["RTPLAN"]:
			results[("RTPLAN", uid)] = local_results[uid]
		for uid in plan_root["RTDOSE"]:
			results[("RTDOSE", uid)] = local_results[uid]
		if not local_results[plan_sop_uid][0]:
			skip_plan(
				plan_root,
				f"Transfer skipped: RTPLAN could not be retrieved: {local_results[plan_sop_uid][1]}",
			)
			continue

		# Find the structure set UIDs + plan labels from the RT Plan file
		if DEBUG: 
			print("Transmit RT struct from Aria")
		try:
			structure_set_uids, plan_label = conquest_db_interface.get_rt_struct_uid(plan_sop_uid)
			if not structure_set_uids:
				raise ValueError("RTPLAN has no referenced structure sets")
		except (OSError, ValueError, AttributeError) as exc:
			skip_plan(plan_root, f"Transfer skipped: cannot read RTPLAN references: {exc}")
			continue

		# Download the associated RTRECORD files

		if USE_RTRECORD:
			if DEBUG: 
				print("Transmit RT Record from Aria")
			rtrecord_uids = plan_root.get("RTRECORD", set())
			for uid, result in tools.transmit_rt_record(rtrecord_uids).items():
				results[("RTRECORD", uid)] = result

		plan_root["RTPlanLabel"] = plan_label
		plan_root["RTSTRUCT"].update(structure_set_uids)
		structure_results = tools.transmit_rt_struct(plan_root["RTSTRUCT"])
		for uid, result in structure_results.items():
			results[("RTSTRUCT", uid)] = result
        
		# Download the associated CT
		if DEBUG: 
			print("Find CT from Aria")
		failed_reference = False
		for instance_uid in plan_root["RTSTRUCT"]:
			if not structure_results[instance_uid][0]:
				failed_reference = True
				continue
			try:
				ct_series_uid_list = conquest_db_interface.find_referenced_ct_series(instance_uid)
				if not ct_series_uid_list:
					raise ValueError("RTSTRUCT has no referenced CT series")
				plan_root["CT"].update(ct_series_uid_list)
			except (OSError, ValueError, AttributeError) as exc:
				results[("RTSTRUCT", instance_uid)] = transfer_failure(
					f"Cannot read RTSTRUCT references: {exc}"
				)
				failed_reference = True

		if failed_reference:
			failure = transfer_failure("CT transfer skipped: RTSTRUCT references unavailable")
			for uid in plan_root["CT"]:
				results[("CT", uid)] = failure
		else:
			if DEBUG: 
				print("Find CT from Aria")

			for uid, result in tools.transmit_ct_series(plan_root).items():
				results[("CT", uid)] = result

	if not plan_set["PatientID"]:
		find_patient_id(plan_set)

	# Reference discovery may have added previously sent RTSTRUCT and CT objects.
	plan_set["PlanSet"] = check_for_changes_and_errors(plan_set)["PlanSet"]

    # Two conquest interfaces locally:
    # 1. conquest_aria.dicom.aet ('medfys') to talk to aria
    #   At this state the patient is located here
    # 2. conquest_krest.dicom.aet ('medfys2') to talk to KREST-HUS

    # Now we transmit the patient to the second internal Conquest
	if plan_set["PlanSet"]:
		conquest_dicom_interface.c_move_to_medfys2(plan_set)

def move_patient_to_ous(plan_set):
	conquest_dicom_interface.c_move_to_krest_hus(plan_set)

def parse_apprecs():
	engine = create_engine(config.conquest_krest.sql.uri)
	statement = select(DICOMImages).join(
		DICOMSeries, DICOMImages.SeriesInst == DICOMSeries.SeriesInstanceUID
	).where(
		DICOMImages.SOPClassUID == str(DICOMSR.basicTextSRStorage),
		DICOMSeries.SeriesDescription == "Apprec",
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

		status = apprec_payload.get("message_status")
		message = apprec_payload.get("message_contents")
		plan_sop_uid = apprec_payload.get("plan_sop_uid")

		apprecs.append({
			"plan_sop_uid": plan_sop_uid,
			"message_status": status,
			"message_contents": message,
			"received_dt": getattr(sr_document.ds, "SeriesDate", None),
			"dicom_uid": getattr(sr_document.ds, "SOPInstanceUID", sr_file.SOPInstanceUID),
			"filepath": str(filepath),
		})

	return apprecs

def print_error_messages(apprecs):
	error_apprecs = []

	print(f"Fant {len(apprecs)} apprec SR-filer i Conquest-databasen.")
	for apprec in apprecs:
		status = apprec.get("message_status")
		message = str(apprec.get("message_contents") or "").strip()

		if status is True and not message:
			continue

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
		for year_folder in glob(f"{config.npr.root_dir}"):
			print(f"{year_folder = }")
			for file in glob(f"{year_folder}/*.{config.npr.file_extension}"):
				print(f"{file = }")
				npr_files.append(file)

	elif config.npr.structure == "FLAT":
		for file in glob(f"{config.npr.root_dir}/*.{config.npr.file_extension}"):
			npr_files.append(file)

	return npr_files

def process_npr():
	all_available_npr_files = find_all_npr_files()
	
	if DEBUG:
		print(f"Found the following NPR files: {all_available_npr_files}")
	
	for npr_file in all_available_npr_files:
		if log_database.check_if_npr_file_is_sent(npr_file):
			print(f"NPR file already sent: {npr_file}")
			continue

		if DEBUG:
			print(f"Processing NPR file: {npr_file}")
		dicom_uid = send_npr_file_to_krest(npr_file)
		if dicom_uid is None:
			print(f"Failed to process NPR file (no dicom_uid): {npr_file}")
			continue

		npr_file_info = {
			"file_name": npr_file,
			"bytes": tools.get_bytes_stored([npr_file], append_root=False),
			"md5_hash": tools.md5hash(npr_file),
			"dicom_uid": dicom_uid,
			"sent_dt": datetime.now()
		}

		print(f"Successfully processed NPR file: {npr_file_info}")

		log_database.add_npr_file(npr_file_info)

def send_npr_file_to_krest(npr_file):
	"""	Send NPR files to KREST-HUS and return a list of dictionaries with file information.
		Encapsulate contents of each npr_file in a new DICOM SR file
		Send this DICOM SR til KREST	
	"""

	contents = Path(npr_file).read_text(encoding="utf-8")
	dicom_sr = make_dataset(parentUID=config.krest.uid_root, patientID="NPR^FILE", patientName="NPR^FILE", content_string=contents)
	sop_uid = dicom_sr.ds.SOPInstanceUID

	passed, message = conquest_dicom_interface.c_store_krest(dicom_sr.ds)
	if not passed:
		logger.error("NPR file was not sent to KREST: %s", message)
		print(f"Failed to send NPR file to KREST: {npr_file} - {message}")
		return None

	return sop_uid

def process_apprec():
	apprecs = parse_apprecs()
	apprecs = remove_old_apprec_messages(apprecs)
	print_error_messages(apprecs)
	log_database.add_apprecs(apprecs)