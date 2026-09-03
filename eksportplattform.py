import subprocess
import os
import tomllib
from sqlmodel import Session, create_engine, select
import logging
from datetime import datetime
from pprint import pprint

from config import Config

config = Config()

from module.Dataclasses.conquest_dataclass import (
	DICOMImages, 
	DICOMPatients,
	DICOMSeries
)

from module.Dataclasses import export_logger_dataclass

from module.Interfaces import (
	aria_db_interface,
	aria_dicom_interface,
	conquest_db_interface,
	conquest_dicom_interface,
	export_logger_interface
)

from module.utils import tools, orchestrator

logging.basicConfig(
	filename="D:/Brokers/export.log", 
	filemode='a', 
	format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
	datefmt='%Y-%m-%d %H:%M:%S',
	level=logging.INFO)

logger = logging.getLogger(__name__)

log_database = export_logger_interface.LogDatabase()

start_date = datetime(2026, 1, 1)

print(f"Found {len(plan_set)} patients since {dt.isoformat()}")

existing_conquest = orchestrator.find_existing_patients_in_conquest()
plan_sets = orchestrator.find_all_patients_in_aria_since(start_date)

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

	log_database.add_patient(plan_set)

apprecs = orchestrator.parse_apprecs()
apprecs = orchestrator.remove_old_apprecs(apprecs)
orchestrator.print_error_messages(apprecs)
log_database.add_apprecs(apprecs)