from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from sqlmodel import Session, create_engine, select
from typing import List
import pyodbc
import logging
from pprint import pprint
import os
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

"""
CREATE proc [dbo].[blp_GetTxRecordsProtonToExport]
	(@FromDateTime	datetime = null)
 
as
 
declare @fromdate date
 
--If fromdate not given, get plans 6 month before
 
if (@FromDateTime is null) 
	select @FromDateTime = dateadd(month, -1, getdate())
 
select @fromdate = convert(date, @FromDateTime)
 
select distinct tr.PatientSer, tr.PlanUID, tr.TreatmentRecordUID, dm.DoseUID
from TreatmentRecord tr join Patient p on tr.PatientSer = p.PatientSer 
						join RTPlan rtp on tr.RTPlanSer = rtp.RTPlanSer
						join PlanSetup ps on rtp.PlanSetupSer = ps.PlanSetupSer
						left outer join DoseMatrix dm on ps.PlanSetupSer = dm.PlanSetupSer
where convert(date, tr.TreatmentRecordDateTime) > @fromdate
and tr.ActualMachineSer in (select distinct ResourceSer
					from Machine
					where lower(MachineId) like 'sb9_%' 
					or lower(MachineId) like 'sb10_%')
and p.PatientSer = tr.PatientSer
and lower(p.PatientId) not like 'z%'
 
return 0
 
GO
"""

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

"""
Used for identification + logging
plan_set = 
[ 
	PatientSer : { 
		"PatientSer": patient_ser,
		"PatientID" : patient_id,
		"PlanSet" : {
			RT Plan SOP UID : {
				"RTPLAN": [ RT Plan SOP UID ],
				"RTPlanLabel", 
				"RTDOSE": RT Dose SOP UID,
				"RTSTRUCT": RT Struct SOP UID,
				"RTRECORD": [ RT Treatment Record SOP UIDs ],
				"CT": Plan CT Series Instance UID,
			}
		}
	}
]

"""

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
				"CT": set()
			}
		
		plan_set[rtrecord.PatientSer]["PlanSet"][rtrecord.PlanUID]["RTPLAN"].add(rtrecord.PlanUID)
		plan_set[rtrecord.PatientSer]["PlanSet"][rtrecord.PlanUID]["RTRECORD"].add(rtrecord.TreatmentRecordUID)
		plan_set[rtrecord.PatientSer]["PlanSet"][rtrecord.PlanUID]["RTDOSE"].add(rtrecord.DoseUID)

	return plan_set