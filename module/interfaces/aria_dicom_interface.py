from sqlalchemy import create_engine
import logging
from pprint import pprint
from glob import glob
from pydicom.dataset import Dataset
from sqlmodel import create_engine

from pynetdicom import AE
from pynetdicom.sop_class import (
	PatientRootQueryRetrieveInformationModelMove,
	PatientRootQueryRetrieveInformationModelFind,
)

from config import Config
from module.utils.dicom_status import check_c_move_responses, iter_c_find_responses

logger = logging.getLogger(__name__)
config = Config()

engine = create_engine(config.aria.sql.uri)

def get_assoc():
	ae = AE(ae_title=config.conquest_aria.dicom.aet)
	ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
	ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)

	assoc = ae.associate(
		config.aria.dicom.server,
		config.aria.dicom.port,
		ae_title=config.aria.dicom.aet
	)

	if not assoc.is_established:
		raise RuntimeError("Association to ARIA failed")

	return assoc

def c_move_image(association, uid):
	ds = Dataset()
	ds.QueryRetrieveLevel = "IMAGE"
	ds.SOPInstanceUID = uid

	responses = association.send_c_move(
		ds,
		move_aet=config.conquest_aria.dicom.aet,
		query_model=PatientRootQueryRetrieveInformationModelMove
	)

	return check_c_move_responses(responses, "ARIA image transfer")

def c_move_series(association, uid):
	ds = Dataset()
	ds.QueryRetrieveLevel = "SERIES"
	ds.SeriesInstanceUID = uid

	responses = association.send_c_move(
		ds,
		move_aet=config.conquest_aria.dicom.aet,
		query_model=PatientRootQueryRetrieveInformationModelMove
	)

	return check_c_move_responses(responses, "ARIA series transfer")

def c_find_study(association, uid):
	ds = Dataset()
	ds.QueryRetrieveLevel = "SERIES"
	ds.StudyInstanceUID = uid
	ds.SeriesInstanceUID = ""
	ds.Modality = ""

	result = list()

	responses = association.send_c_find(ds, PatientRootQueryRetrieveInformationModelFind)

	for identifier in iter_c_find_responses(responses, "ARIA study lookup"):

		result.append({
			"SeriesInstanceUID": identifier.get("SeriesInstanceUID"),
			"StudyInstanceUID": identifier.get("StudyInstanceUID"),
			"Modality": identifier.get("Modality"),
		})

	return result

def get_study_uid_from_plan_sop_uid(association, plan_sop_uid):
	ds = Dataset()
	ds.QueryRetrieveLevel = "IMAGE"
	ds.SOPInstanceUID = plan_sop_uid
	ds.StudyInstanceUID = ""
	ds.SeriesInstanceUID = ""
	ds.Modality = ""

	result = list()

	responses = association.send_c_find(ds, PatientRootQueryRetrieveInformationModelFind)

	for identifier in iter_c_find_responses(responses, "ARIA plan lookup"):

		result.append({
			"StudyInstanceUID": identifier.get("StudyInstanceUID"),
			"SOPInstanceUID": identifier.get("SOPInstanceUID"),
			"SeriesInstanceUID": identifier.get("SeriesInstanceUID"),
			"Modality": identifier.get("Modality"),
		})

	return result