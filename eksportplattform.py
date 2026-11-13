import logging
from datetime import datetime

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

plan_sets = orchestrator.find_all_patients_in_aria_since(start_date)
print(f"Found {len(plan_sets)} patients since {start_date.isoformat()}")

# Transmit patients
for patient_ser, plan_set in plan_sets.items():
	print("Working on patient", patient_ser)
	plan_set_changes = orchestrator.check_for_changes_and_errors(plan_set)
	if not plan_set_changes["PlanSet"]:
		print(f"- No new objects to transmit to {config.krest.name}")
		continue

	print("Moving patient to MF2")
	orchestrator.move_patient_to_conquest(plan_set_changes)
	if not plan_set_changes["PlanSet"]:
		continue
	print("Moving patient to KREST")
	orchestrator.move_patient_to_ous(plan_set_changes)

	log_database.add_patient(conquest_db_interface.get_conquest_aria_engine(), plan_set_changes)

	break

print("Processing NPR")
orchestrator.process_npr()

#orchestrator.process_apprec()