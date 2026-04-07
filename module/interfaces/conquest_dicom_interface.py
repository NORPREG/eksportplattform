from pynetdicom import AE, evt, build_role
from pynetdicom.sop_class import (
	PatientRootQueryRetrieveInformationModelGet,
	PatientRootQueryRetrieveInformationModelMove,
	PatientRootQueryRetrieveInformationModelFind,
	RTBeamsTreatmentRecordStorage,
	RTPlanStorage
)
from pydicom.dataset import Dataset
from module.Interfaces import conquest_db_interface

from config import Config

config = Config()

def c_move_to_krest_hus(patient_id):
	this_ae = AE(ae_title="PYTHON")
	this_ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)

	assoc = this_ae.associate(
		config.conquest_krest.dicom.server,
        config.conquest_krest.dicom.port,
        ae_title=config.conquest_krest.dicom.aet
	)

	if not assoc.is_established:
		raise RuntimeError(f"Association to {config.conquest_krest.dicom.aet} failed")

	# Send SOP Series UID for CT
	# Send SOP Instance UID for all others

	ds = Dataset()
	ds.QueryRetrieveLevel = "PATIENT"
	ds.PatientID = patient_id

	responses = assoc.send_c_move(
		ds,
		move_aet=config.krest.dicom.aet,
		query_model=PatientRootQueryRetrieveInformationModelMove
	)

	assoc.release()

def c_move_to_medfys2(engine, plan_set):
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
					exists = conquest_db_interface.check_exists_series(engine, uid)
				else:
					ds.QueryRetrieveLevel = "IMAGE"
					ds.SOPInstanceUID = uid
					exists = conquest_db_interface.check_exists_sop(engine, uid)

				if not exists:
					responses = assoc.send_c_move(
						ds,
						move_aet=config.conquest_krest.dicom.aet,
						query_model=PatientRootQueryRetrieveInformationModelMove
					)

	assoc.release()