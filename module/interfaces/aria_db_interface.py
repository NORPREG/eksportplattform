from sqlalchemy import create_engine, text
from sqlmodel import create_engine
from typing import List
import logging
from datetime import datetime

from config import Config

from module.Dataclasses.aria_dataclass import TxRecordsProtonToExport

config = Config()
logger = logging.getLogger(__name__)

# Aria SQL Interface

def get_sqlalchemy():
	conn_string = config.aria.sql.uri
	engine = create_engine(conn_string)
	return engine

def blp_GetTxRecordsProtonToExport(from_dt: datetime = None) -> List[TxRecordsProtonToExport]:
	engine_aria = get_sqlalchemy()

	with engine_aria.connect() as conn:
		if from_dt:
			result = conn.execute(text("SET NOCOUNT ON; EXEC blp_GetTxRecordsProtonToExport @FromDateTime = :from_datetime"), 
				{"from_datetime": from_dt.strftime("%Y%m%d")})
		else:
			result = conn.execute(text("SET NOCOUNT ON; EXEC blp_GetTxRecordsProtonToExport"))
		rows = result.mappings().all()

		return [TxRecordsProtonToExport(**dict(row)) for row in rows]

def get_plan_set(from_dt: datetime):
	rtrecords = blp_GetTxRecordsProtonToExport(from_dt)
	plan_set = dict()

	for rtrecord in rtrecords:
		if not rtrecord.PatientSer in plan_set:
			plan_set[rtrecord.PatientSer] = {
				"PatientID": None,
				"PatientSer": rtrecord.PatientSer,
				"PlanSet": dict(),
			}
		

		if rtrecord.PlanUID not in plan_set[rtrecord.PatientSer]["PlanSet"]:
			plan_set[rtrecord.PatientSer]["PlanSet"][rtrecord.PlanUID] = {
				"RTPlanLabel": str(),
				"RTDOSE": set(),
				"RTRECORD": set(),
				"RTSTRUCT": set(),
				"RTPLAN": set(),
				"CT": set(),
				"SR": set()
			}
		
		plan_set[rtrecord.PatientSer]["PlanSet"][rtrecord.PlanUID]["RTPLAN"].add(rtrecord.PlanUID)
		plan_set[rtrecord.PatientSer]["PlanSet"][rtrecord.PlanUID]["RTRECORD"].add(rtrecord.TreatmentRecordUID)
		if rtrecord.DoseUID:
			plan_set[rtrecord.PatientSer]["PlanSet"][rtrecord.PlanUID]["RTDOSE"].add(rtrecord.DoseUID)

	return plan_set