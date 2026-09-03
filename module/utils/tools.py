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

logger = logging.getLogger(__name__)

log_database = export_logger_interface.LogDatabase()

def transmit_ct_series(ct_series_uid_list):
    for ct_series_uid in ct_series_uid_list:
        plan_set[patient_ser]["PlanSet"][plan_sop_uid]["CT"].add(ct_series_uid)

        if not conquest_db_interface.check_exists_series(ct_series_uid):
            print(f"- Moving CT Series with Series UID", ct_series_uid)
            assoc = aria_dicom_interface.get_assoc()
            aria_dicom_interface.c_move_series(assoc, ct_series_uid)
            assoc.release()

def transmit_rt_struct(structure_set_uids):
    for instance_uid in structure_set_uids:
        if not conquest_db_interface.check_exists_sop(instance_uid):
            print(f"- Moving Structure set Instance UID {instance_uid}")
            assoc = aria_dicom_interface.get_assoc()
            aria_dicom_interface.c_move_image(assoc, instance_uid)
            assoc.release()

def transmit_rt_plan_dose(uids_exist):
    # Keep single association if any of the files are missing
    if not all(uids_exist.values()):
        assoc = aria_dicom_interface.get_assoc()
        for uid, status in uids_exist.items():
            if not status:
                print("- Moving RT Plan / Dose with SOP UID", uid)
                aria_dicom_interface.c_move_image(assoc, uid)
        assoc.release()