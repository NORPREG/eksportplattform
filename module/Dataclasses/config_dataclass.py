from pydantic import BaseModel
from typing import Optional

class BaseSql(BaseModel):
    uri: Optional[str] = None
    file: Optional[str] = None

class BaseDicom(BaseModel):
    aet: str
    server: Optional[str] = None
    port: Optional[int] = None
    name: Optional[str] = None

class Pacs(BaseModel):
    sql: BaseSql
    dicom: BaseDicom
    root_dir: Optional[str] = None

class Krest(BaseModel):
    dicom: BaseDicom
    name: str

class ConfigDataclass(BaseModel):
    conquest_aria: Pacs
    conquest_krest: Pacs
    aria: Pacs
    log_db: BaseSql
    krest: Krest