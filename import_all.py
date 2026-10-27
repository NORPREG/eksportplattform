import subprocess
import os
import tomllib
from sqlmodel import Session, create_engine, select
import logging
from datetime import datetime
from pprint import pprint

from config import Config

config = Config("test")

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