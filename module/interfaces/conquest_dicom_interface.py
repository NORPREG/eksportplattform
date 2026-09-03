from pynetdicom import AE, evt, build_role, debug_logger
from pynetdicom.sop_class import (
	PatientRootQueryRetrieveInformationModelGet,
	PatientRootQueryRetrieveInformationModelMove,
	PatientRootQueryRetrieveInformationModelFind,
	RTBeamsTreatmentRecordStorage,
	RTPlanStorage
)
from pydicom.dataset import Dataset
from tqdm import tqdm

from module.Interfaces import conquest_db_interface

from config import Config

config = Config()

# debug_logger()

conquest_krest_engine = conquest_db_interface.create_engine(config.conquest_krest.sql.uri)

def c_move_to_krest_hus(plan_set):
	patient_id = plan_set.get("PatientID")
	patient_ser = plan_set.get("PatientSer")

	assert patient_id

	this_ae = AE(ae_title="PYTHON")
	this_ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
	this_ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)

	# Cannot directly check contents in KREST-HUS; it is located behind gateway

	association_medfys2 = this_ae.associate(
		config.conquest_krest.dicom.server,
		config.conquest_krest.dicom.port,
		ae_title=config.conquest_krest.dicom.aet
	)

	if not association_medfys2.is_established:
		raise RuntimeError(f"Association to {config.conquest_krest.dicom.aet} failed")

	images_medfys2 = find_patient_images(association_medfys2, patient_id)

	ds = Dataset()
	ds.QueryRetrieveLevel = "PATIENT"
	ds.PatientID = patient_id

	print(f"Moving patient {patient_ser} to KREST-HUS")

	for series_uid in images_medfys2:
		ds = Dataset()
		ds.QueryRetrieveLevel = "SERIES"
		ds.SeriesInstanceUID = series_uid

		responses = association_medfys2.send_c_move(
			ds,
			move_aet=config.krest.dicom.aet,
			query_model=PatientRootQueryRetrieveInformationModelMove
		)

	association_medfys2.release()

def c_move_to_medfys2(plan_set):
	this_ae = AE(ae_title="PYTHON")
	this_ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)

	assoc = this_ae.associate(
		config.conquest_aria.dicom.server,
        config.conquest_aria.dicom.port,
        ae_title=config.conquest_aria.dicom.aet
	)

	if not assoc.is_established:
		raise RuntimeError(f"Association to {config.conquest_aria.dicom.aet} failed")

	# Send SOP Series UID for CT
	# Send SOP Instance UID for all others

	for plan_uid, plan_set in plan_set["PlanSet"].items():
		for modality, uid_set in plan_set.items():
			if modality == "RTPlanLabel":
				continue

			for uid in uid_set:
				ds = Dataset()
				if modality == "CT":
					ds.QueryRetrieveLevel = "SERIES"
					ds.SeriesInstanceUID = uid
					exists = conquest_db_interface.check_exists_series(uid, conquest_krest_engine)
				else:
					ds.QueryRetrieveLevel = "IMAGE"
					ds.SOPInstanceUID = uid
					exists = conquest_db_interface.check_exists_sop(uid, conquest_krest_engine)

				if not exists:
					responses = assoc.send_c_move(
						ds,
						move_aet=config.conquest_krest.dicom.aet,
						query_model=PatientRootQueryRetrieveInformationModelMove
					)

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

	for status, identifier in responses:
		if status and status.Status in (0xFF00, 0xFF01):
			result.add(identifier.get("SeriesInstanceUID"))

	return result