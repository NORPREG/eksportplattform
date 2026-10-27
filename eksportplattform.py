import logging
from datetime import datetime
from pprint import pprint

from config import Config

config = Config()

from module.Interfaces import (
	conquest_db_interface,
	export_logger_interface
)

from module.utils import orchestrator

logging.basicConfig(
	filename="D:/Brokers/export.log", 
	filemode='a', 
	format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
	datefmt='%Y-%m-%d %H:%M:%S',
	level=logging.INFO)

logger = logging.getLogger(__name__)

log_database = export_logger_interface.LogDatabase()

start_date = datetime(2026, 1, 1)

existing_conquest = orchestrator.find_existing_patients_in_conquest()
plan_sets = orchestrator.find_all_patients_in_aria_since(start_date)
print(f"Found {len(plan_sets)} patients since {start_date.isoformat()}")

# Transmit patients
for patient_ser, plan_set in plan_sets.items():
	print("Working on patient", patient_ser)
	sent_dt = log_database.check_patient(patient_ser)
	if sent_dt:
		print(f"- Patient was transmitted to {config.krest.name} at {sent_dt}")
		continue

	patient_id = orchestrator.find_patient_id(plan_set)

	if patient_id in existing_conquest:
		print(f"- Found patient in {config.conquest_aria.dicom.aet} database")
		continue

	orchestrator.move_patient_to_conquest(plan_set)
	orchestrator.move_patient_to_ous(plan_set)

	log_database.add_patient(conquest_db_interface.get_conquest_aria_engine(), plan_set)

orchestrator.process_npr()
orchestrator.process_apprec()