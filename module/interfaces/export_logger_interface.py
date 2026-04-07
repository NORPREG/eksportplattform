import datetime
from config import Config
import json

config = Config()

class SetEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)
        return json.JSONEncoder.default(self, obj)

class LogDatabase:
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