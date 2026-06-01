import datetime
from config import Config
import json
from sqlmodel import Session, create_engine, select
import os

config = Config()

from module.Dataclasses import export_logger_dataclass
from module.Interfaces import conquest_db_interface

class SetEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)
        return json.JSONEncoder.default(self, obj)

def get_bytes_stored(filenames):
	size = 0
	for filename in filenames:
		if filename:
			size += os.path.getsize(config.conquest_aria.root_dir + filename)

	return size

class LogDatabaseJSON:
	def __init__(self):
		self.log = self.get_log()

	def get_log(self):
		try:
			with open(config.log_db.file, "r", encoding="utf-8") as input_file:
				d =  json.load(input_file)
				print(f"Found {len(d)} patients in {config.log_db.file}.")
				return d
		except Exception as e:
			print("LogDatabase __init__ error: ", e)
			return list()

	def save(self):
		with open(config.log_db.file, "w", encoding="utf-8") as output_file:
			json.dump(self.log, output_file, indent=3, cls=SetEncoder)
		
 
	def add_patient(self, patient_ser, plan_set: dict):
		new_entry = {
			"sent_dt": datetime.datetime.now().isoformat(),
			"patient_ser": patient_ser,
			"plan_set": plan_set["PlanSet"]
		}
		self.log.append(new_entry)

	def check_patient(self, patient_ser: str) -> bool:
		for entry in self.log:
			if entry.get("patient_ser") == patient_ser:
				return entry.get("sent_dt")
		return False

	@property
	def plan_set(self):
		return self.log

class LogDatabase:
	def __init__(self):
		self.engine = create_engine(config.log_db.uri)

	def check_patient(self, patient_ser: str) -> bool:
		"""Check whether patient has data sent already"""

		with Session(self.engine) as session:
			statement = select(export_logger_dataclass.Course).where(export_logger_dataclass.Course.PatientSer == patient_ser)
			course = session.exec(statement).first()
			if not course:
				return False

			else:
				return course.sent_dt

	def add_patient(self, conquest_aria_engine, course: dict):
		"""Add patient to the logger database from plan_set"""

		# Add Course object
		db_course = export_logger_dataclass.Course(
			patient_ser = str(course.get("PatientSer")),
			sent_dt = datetime.datetime.now()
		)

		for plan_uid, plan_set in course.get("PlanSet", {}).items():
			db_plan_set = export_logger_dataclass.RTPlan(
				plan_sop_uid = plan_uid,
				plan_label = plan_set.get("RTPlanLabel")
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

		with Session(self.engine) as session:
			session.add(db_course)
			session.commit()