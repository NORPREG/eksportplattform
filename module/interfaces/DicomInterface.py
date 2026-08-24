from pprint import pprint
import tempfile

import datetime

import pydicom

from pydicom.filereader import dcmread
from pydicom.sr.codedict import codes
from pydicom.uid import generate_uid, UID

from pprint import pprint
import zlib
import base64

from hypothesis import given
from hypothesis.strategies import text

import pydantic
from pydantic_xml import BaseXmlModel, RootXmlModel, attr, element, wrapped
from typing import Optional, List

from config import Config
config = Config()

class DICOMInterface:
   explicitVR = UID("1.2.840.10008.1.2.1")
   basicTextSRStorage = UID("1.2.840.10008.5.1.4.1.1.88.11")
   enhancedSR = UID("1.2.840.10008.5.1.4.1.1.88.22")
   pythonClassUID = UID("1.2.826.0.1.3680043.8.498.1")
   documentTitleCode = "121144"
   externalDataSourceCode = "111781"

   def __init__(self):
      self.ds = None
      self.setup()

   def setup(self, filename: str = None) -> None:
      if not self.ds:
         suffix = ".dcm"
         filename_little_endian = tempfile.NamedTemporaryFile(suffix=suffix).name

         file_meta = pydicom.dataset.FileMetaDataset()
         file_meta.TransferSyntaxUID = self.explicitVR
         file_meta.ImplementationClassUID = self.pythonClassUID
         file_meta.ImplementationVersionName = "Pydicom v" + pydicom.__version__

         self.ds = pydicom.FileDataset(filename_little_endian, {}, file_meta=file_meta, preamble=b"\0" * 128)
         self.ds.is_little_endian = True
         self.ds.is_implicit_VR = False

      else:
         self.ds = pydicom.dcmread(filename)

   def add_UIDs(self) -> None:
      self.ds.SpecificCharacterSet = "ISO_IR 192"
      self.ds.SOPClassUID = self.enhancedSR
      self.ds.SOPInstanceUID = generate_uid(config.rtmodel.dicom_root_uid)
      self.ds.Modality = "SR"
      self.ds.StudyInstanceUID = generate_uid(config.rtmodel.dicom_root_uid)
      self.ds.SeriesInstanceUID = generate_uid(config.rtmodel.dicom_root_uid)

   def add_patient(self, patient_id: str, patient_name: str) -> None:
      self.ds.PatientName = patient_name
      self.ds.PatientID = patient_id

   def add_datetimes(self):
      dt = datetime.datetime.now()
      self.ds.ContentDate = dt.strftime('%Y%m%d')
      self.ds.SeriesDate = dt.strftime('%Y%m%d')
      self.ds.ContentTime = dt.strftime('%H%M%S.%f')
      self.ds.SeriesTime = dt.strftime('%H%M%S.%f')

   def add_content(self, JSON_string: str) -> None:
      title = pydicom.Dataset()
      title.CodeValue = self.documentTitleCode
      title.CodingSchemeDesignator = "DCM"
      title.CodeMeaning = "Document Title"

      self.ds.ValueType = "CONTAINER"
      self.ds.ConceptNameCodeSequence = pydicom.sequence.Sequence()
      self.ds.ConceptNameCodeSequence.append(title)
      self.ds.ContinuityOfContent = "SEPARATE"
      
      """
      Add the following:
      Warning - Missing attribute or value that would be needed to build DICOMDIR - Study Date
      Warning - Missing attribute or value that would be needed to build DICOMDIR - Study Time
      Warning - Missing attribute or value that would be needed to build DICOMDIR - Study ID
      Warning - Missing attribute or value that would be needed to build DICOMDIR - Series Number
      Warning - Value dubious for this VR - (0x0010,0x0010) PN Patient's Name  PN [1] = <UNKNOWN> - Retired Person Name form
      EnhancedSR
      Error - Missing attribute Type 2 Required Element=<PatientBirthDate> Module=<Patient>
      Error - Missing attribute Type 2 Required Element=<PatientSex> Module=<Patient>
      Error - Missing attribute Type 2 Required Element=<StudyDate> Module=<GeneralStudy>
      Error - Missing attribute Type 2 Required Element=<StudyTime> Module=<GeneralStudy>
      Error - Missing attribute Type 2 Required Element=<ReferringPhysicianName> Module=<GeneralStudy>
      Error - Missing attribute Type 2 Required Element=<StudyID> Module=<GeneralStudy>
      Error - Missing attribute Type 2 Required Element=<AccessionNumber> Module=<GeneralStudy>
      Error - Missing attribute Type 1 Required Element=<SeriesNumber> Module=<SRDocumentSeries>
      Error - Missing attribute Type 2 Required Element=<ReferencedPerformedProcedureStepSequence> Module=<SRDocumentSeries>
      Error - Missing attribute Type 2 Required Element=<Manufacturer> Module=<GeneralEquipment>
      Error - Missing attribute Type 1 Required Element=<InstanceNumber> Module=<SRDocumentGeneral>
      Error - Missing attribute Type 1 Required Element=<CompletionFlag> Module=<SRDocumentGeneral>
      Error - Missing attribute Type 1 Required Element=<VerificationFlag> Module=<SRDocumentGeneral>
      Error - Missing attribute Type 2 Required Element=<PerformedProcedureCodeSequence> Module=<SRDocumentGeneral>
      """

      textDesignator = pydicom.Dataset()
      textDesignator.CodeValue = self.externalDataSourceCode
      textDesignator.CodingSchemeDesignator = "DCM"
      textDesignator.CodeMeaning = "External Data Source"

      report = pydicom.Dataset()
      report.RelationshipType = "CONTAINS"
      report.ValueType = "TEXT"
      report.ConceptNameCodeSequence = pydicom.sequence.Sequence()
      report.ConceptNameCodeSequence.append(textDesignator)

      report.TextValue = str(JSON_string)

      self.ds.ContentSequence = pydicom.sequence.Sequence()
      self.ds.ContentSequence.append(report)

   def save_file(self, filename: str) -> None:
      self.ds.save_as(filename, write_like_original=False)

   def get_JSON(self) -> str:
      self.json_string = sr.ContentSequence[0].TextValue
      return self.json_string