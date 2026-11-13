import datetime
from config import Config
import json
from sqlmodel import Session, create_engine, select

config = Config()

from module.Dataclasses import export_logger_dataclass
from module.Interfaces import conquest_db_interface
from module.utils import tools
from module.utils.dicom_status import transfer_failure

class SetEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)
        return json.JSONEncoder.default(self, obj)

class LogDatabase:
	def __init__(self):
		self.engine = create_engine(config.log_db.uri)

	def check_patient(self, patient_ser: str) -> bool:
		"""Check whether patient has data sent already"""

		with Session(self.engine) as session:
			statement = select(export_logger_dataclass.DicomTransfer) \
				.where(export_logger_dataclass.DicomTransfer.patient_ser == str(patient_ser))
			course = session.exec(statement).first()
			if not course:
				return False

			else:
				return course.sent_dt

	def add_npr_file(self, npr_file: dict):
		"""Add NPRFile to the logger database"""

		db_npr_file = export_logger_dataclass.NPRFile(
			file_name = npr_file.get("file_name"),
			bytes = npr_file.get("bytes"),
			md5_hash = npr_file.get("md5_hash"),
			dicom_uid = npr_file.get("dicom_uid"),
			sent_dt = npr_file.get("sent_dt"),
		)

		with Session(self.engine) as session:
			session.add(db_npr_file)
			session.commit()

	def get_npr_files(self) -> list[dict]:
		"""Get all NPRFiles from the logger database. 
			Use this to check whether a file has already been sent to NORPREG"""

		with Session(self.engine) as session:
			statement = select(export_logger_dataclass.NPRFile)
			npr_files = session.exec(statement).all()
			return npr_files

	def check_if_npr_file_is_sent(self, file_name: str) -> bool:
		"""Check whether a file has already been sent to NORPREG"""

		with Session(self.engine) as session:
			statement = select(export_logger_dataclass.NPRFile) \
				.where(export_logger_dataclass.NPRFile.file_name == file_name)
			npr_files = session.exec(statement).all()
			if not any(npr_files):
				return False
			else:
				md5_hash = tools.md5hash(file_name)
				for npr_file in npr_files:
					if md5_hash == npr_file.md5_hash:
						return True
				return False

	def add_patient(self, conquest_aria_engine, plan_sets: dict):
		"""Add patient to the logger database from plan_set"""

		# Add Course object
		db_dicomtransfer = export_logger_dataclass.DicomTransfer(
			patient_ser = str(plan_sets.get("PatientSer")),
			sent_dt = datetime.datetime.now()
		)

		for plan_uid, plan_set in plan_sets.get("PlanSet", {}).items():
			db_plan_set = export_logger_dataclass.RTPlan(
				plan_sop_uid = plan_uid,
				plan_label = plan_set.get("RTPlanLabel")
			)

			for modality_c in export_logger_dataclass.Modality:
				modality = modality_c.value
				for item in plan_set.get(modality, []):
					transfer_status, transfer_message = plan_set.get("TransferResults", {}).get(
						(modality, item), (0, "No final transfer result recorded")
					)
					if modality == "CT":
						type_uid = "SERIES_INSTANCE"
					else:
						type_uid = "SOP_INSTANCE"
					bytes_stored = None
					if transfer_status == 1:
						if modality == "CT":
							filenames = conquest_db_interface.get_series_filenames(item, conquest_aria_engine)
						else:
							filenames = conquest_db_interface.get_sop_filenames(item, conquest_aria_engine)
						try:
							if not filenames or any(filename is None for filename in filenames):
								raise OSError("Transferred object has no local file")
							bytes_stored = tools.get_bytes_stored(filenames)
						except OSError as exc:
							_, transfer_message = transfer_failure(
								f"Transfer succeeded, but local file size is unavailable: {exc}"
							)

					db_dicom_object = export_logger_dataclass.DicomObject(
						reference_uid = item,
						type_uid = type_uid,
						bytes_stored = bytes_stored,
						modality = modality,
						transfer_status = transfer_status,
						transfer_message = transfer_message,
					)

					db_plan_set.dicom_objects.append(db_dicom_object)
			db_dicomtransfer.rtplans.append(db_plan_set)

		with Session(self.engine) as session:
			session.add(db_dicomtransfer)
			session.commit()

	def get_rtplan_id(self, plan_sop_uid: str) -> int:
		"""Get the rtplan_id for a given plan_sop_uid"""

		# Should be only one plan table here
		with Session(self.engine) as session:
			statement = select(export_logger_dataclass.RTPlan) \
				.where(export_logger_dataclass.RTPlan.plan_sop_uid == plan_sop_uid)
			rtplan = session.exec(statement).first()
			if not rtplan:
				return None
			else:
				return rtplan.rtplan_id

	def add_apprecs(self, apprecs: list[dict]):
		"""Add apprecs to the logger database"""

		with Session(self.engine) as session:
			for apprec in apprecs:
				puid = apprec.get("plan_sop_uid")
				rt_plan_id = self.get_rtplan_id(puid)
				if rt_plan_id is None:
					print(f"Could not find rtplan_id for plan_sop_uid {puid}. Skipping apprec.")
					continue

				statement = select(export_logger_dataclass.Apprec) \
					.where(export_logger_dataclass.Apprec.dicom_uid == apprec.get("dicom_uid"))
				if session.exec(statement).first():
					# Apprec already exists
					continue

				db_apprec = export_logger_dataclass.Apprec(
					dicom_uid = apprec.get("dicom_uid"),
					rt_plan_id = rt_plan_id,
					received_dt = apprec.get("received_dt"),
					message_contents = apprec.get("message_contents"),
					message_status=apprec.get("message_status")
				)
				session.add(db_apprec)
			session.commit()