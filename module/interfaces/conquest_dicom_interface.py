from pydicom.uid import BasicTextSRStorage
from pynetdicom import AE
from pynetdicom.sop_class import (
	PatientRootQueryRetrieveInformationModelMove,
	PatientRootQueryRetrieveInformationModelFind,
)
from pydicom.dataset import Dataset

from config import Config
config = Config()

from module.Interfaces import conquest_db_interface
from module.Dataclasses.export_logger_dataclass import Modality
from module.utils.dicom_status import (
	check_c_move_responses,
	check_c_store_response,
	iter_c_find_responses,
	transfer_failure,
)

conquest_krest_engine = conquest_db_interface.create_engine(config.conquest_krest.sql.uri)

def c_move_to_krest_hus(plan_set):
	_move_objects(plan_set, config.conquest_krest.dicom, config.krest.dicom.aet)

def c_move_to_medfys2(plan_set):
	_move_objects(
		plan_set, config.conquest_aria.dicom, config.conquest_krest.dicom.aet,
		conquest_krest_engine,
	)

def _move_objects(plan_set, source, destination, target_engine=None):
	objects = {}
	for plan in plan_set["PlanSet"].values():
		results = plan.setdefault("TransferResults", {})
		for modality in Modality:
			for uid in plan.get(modality.value, []):
				key = (modality.value, uid)
				if results.get(key, (1, ""))[0] == 1:
					objects.setdefault(key, []).append(results)
	if not objects:
		return
	if not plan_set.get("PatientID"):
		failure = transfer_failure("Conquest transfer skipped: missing PatientID")
		for key, results_list in objects.items():
			for results in results_list:
				results[key] = failure
		return

	this_ae = AE(ae_title="PYTHON")
	this_ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
	try:
		assoc = this_ae.associate(source.server, source.port, ae_title=source.aet)
		if not assoc.is_established:
			raise RuntimeError(f"Association to {source.aet} failed")
	except (RuntimeError, OSError) as exc:
		failure = transfer_failure(str(exc))
		for key, results_list in objects.items():
			for results in results_list:
				results[key] = failure
		return

	try:
		ordered_objects = sorted(
			objects.items(),
			key=lambda item: {"RTPLAN": 0, "RTSTRUCT": 1, "CT": 2}.get(item[0][0], 3),
		)
		for (modality, uid), results_list in ordered_objects:
			eligible_results = []
			for results in results_list:
				failed_dependency = any(
					status == 0 and (
						key[0] == "RTPLAN" and modality != "RTPLAN"
						or key[0] == "RTSTRUCT" and modality == "CT"
					)
					for key, (status, _) in results.items()
				)
				if failed_dependency:
					results[(modality, uid)] = transfer_failure(
						f"Transfer to {destination} skipped: dependency failed"
					)
				else:
					eligible_results.append(results)
			if not eligible_results:
				continue
			check_exists = (
				conquest_db_interface.check_exists_series if modality == "CT"
				else conquest_db_interface.check_exists_sop
			)
			result = (1, "")
			if target_engine is None or not check_exists(uid, target_engine):
				ds = Dataset()
				ds.PatientID = plan_set["PatientID"]
				if modality == "CT":
					ds.QueryRetrieveLevel = "SERIES"
					ds.SeriesInstanceUID = uid
				else:
					ds.QueryRetrieveLevel = "IMAGE"
					ds.SOPInstanceUID = uid
				try:
					responses = assoc.send_c_move(
						ds, move_aet=destination,
						query_model=PatientRootQueryRetrieveInformationModelMove,
					)
					result = check_c_move_responses(responses, f"C-MOVE to {destination}")
				except (RuntimeError, OSError, ValueError) as exc:
					result = transfer_failure(f"C-MOVE to {destination}: {exc}")
			for results in eligible_results:
				results[(modality, uid)] = result
	finally:
		assoc.release()

def c_store_krest(ds):
	# This is for DICOM SR
	
	# conquest_krest = medfys2
	# krest = OUS
	# Should fix my naming :D

	this_ae = AE(ae_title=config.conquest_krest.dicom.aet)
	this_ae.add_requested_context(BasicTextSRStorage)

	assert ds.SOPClassUID == BasicTextSRStorage

	try:
		assoc = this_ae.associate(
			config.krest.dicom.server,
			config.krest.dicom.port,
			ae_title=config.krest.dicom.aet
		)
		if not assoc.is_established:
			return transfer_failure(f"Association to {config.krest.dicom.aet} failed")
	except (RuntimeError, OSError) as exc:
		return transfer_failure(f"NPR association failed: {exc}")

	try:
		status = assoc.send_c_store(ds)
		return check_c_store_response(status, "NPR storage in Conquest")
	except (RuntimeError, OSError, ValueError) as exc:
		return transfer_failure(f"NPR storage failed: {exc}")
	finally:
		assoc.release()

def find_patient_images(assoc, patient_id):
	ds = Dataset()
	ds.QueryRetrieveLevel = "SERIES"
	ds.PatientID = patient_id
	ds.SeriesInstanceUID = ""
	ds.StudyInstanceUID = ""
	ds.SOPInstanceUID = ""

	result = set()
	responses = assoc.send_c_find(ds, PatientRootQueryRetrieveInformationModelFind)

	for identifier in iter_c_find_responses(responses, "Conquest patient series lookup"):
		series_uid = identifier.get("SeriesInstanceUID")
		if not series_uid:
			raise RuntimeError("C-FIND returned a series without SeriesInstanceUID")
		result.add(series_uid)

	return result