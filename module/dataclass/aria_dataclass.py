from pydantic import PlainSerializer, BeforeValidator, Basemodel, Field
from sqlalchemy import String, Column
from typing import List, Optional
from typing_extensions import Annotated
from datetime import datetime

class TxRecordsProtonToExport(BaseModel):
	PatientSer: int
	PlanUID: str
	TreatmentRecordUID: str