import tempfile
import datetime
import pydicom
from typing import Optional

from pydicom.filereader import dcmread
from pydicom.sr.codedict import codes
from pydicom.uid import generate_uid, UID


class DICOMSR:
   explicitVR = UID("1.2.840.10008.1.2.1")
   basicTextSRStorage = UID("1.2.840.10008.5.1.4.1.1.88.11")
   pythonClassUID = UID("1.2.826.0.1.3680043.8.498.1")
   documentTitleCode = "121144"
   externalDataSourceCode = "111781"

   def __init__(self):
      self.ds = None
      self.setup()

   def setup(self, filename: str = None) -> None:

      if filename:
         self.ds = pydicom.dcmread(filename)
      elif not self.ds:
         suffix = ".dcm"
         filename_little_endian = tempfile.NamedTemporaryFile(suffix=suffix).name

         file_meta = pydicom.dataset.FileMetaDataset()
         file_meta.TransferSyntaxUID = self.explicitVR
         file_meta.ImplementationClassUID = self.pythonClassUID
         file_meta.ImplementationVersionName = "Pydicom v" + pydicom.__version__

         self.ds = pydicom.FileDataset(filename_little_endian, {}, file_meta=file_meta, preamble=b"\0" * 128)
         self.ds.is_little_endian = True
         self.ds.is_implicit_VR = False

   def addUIDs(self, studyUID: str) -> None:
      self.ds.SpecificCharacterSet = "ISO_IR 192"
      self.ds.SOPClassUID = self.basicTextSRStorage
      self.ds.SOPInstanceUID = generate_uid()
      self.ds.Modality = "SR"
      self.ds.StudyInstanceUID = studyUID
      self.ds.SeriesInstanceUID = generate_uid()

   def addPatient(self, patientID: str, patientName: str) -> None:
      self.ds.PatientName = patientName
      self.ds.PatientID = patientID

   def addDatetimes(self):
      dt = datetime.datetime.now()
      self.ds.ContentDate = dt.strftime('%Y%m%d')
      self.ds.SeriesDate = dt.strftime('%Y%m%d')
      self.ds.ContentTime = dt.strftime('%H%M%S.%f')
      self.ds.SeriesTime = dt.strftime('%H%M%S.%f')

   def addContent(self, XMLString: str) -> None:
      title = pydicom.Dataset()
      title.CodeValue = self.documentTitleCode
      title.CodingSchemeDesignator = "DCM"
      title.CodeMeaning = "Document Title"

      self.ds.ValueType = "CONTAINER"
      self.ds.ConceptNameCodeSequence = pydicom.sequence.Sequence()
      self.ds.ConceptNameCodeSequence.append(title)
      self.ds.ContinuityOfContent = "CONTAINER"

      textDesignator = pydicom.Dataset()
      textDesignator.CodeValue = self.externalDataSourceCode
      textDesignator.CodingSchemeDesignator = "DCM"
      textDesignator.CodeMeaning = "External Data Source"

      report = pydicom.Dataset()
      report.RelationshipType = "CONTAINS"
      report.ValueType = "TEXT"
      report.ConceptNameCodeSequence = pydicom.sequence.Sequence()
      report.ConceptNameCodeSequence.append(textDesignator)

      report.TextValue = XMLString

      self.ds.ContentSequence = pydicom.sequence.Sequence()
      self.ds.ContentSequence.append(report)

   def saveFile(self, filename: str) -> None:
      self.ds.save_as(filename, write_like_original=False)

   def getXML(self) -> Optional[str]:
      return self.get_text_value()

   def get_text_value(self) -> Optional[str]:
      if not self.ds:
         return None

      preferred_text = self._find_text_value(
         getattr(self.ds, "ContentSequence", []),
         preferred_code=self.externalDataSourceCode,
      )
      if preferred_text is not None:
         return preferred_text

      return self._find_text_value(getattr(self.ds, "ContentSequence", []))

   @classmethod
   def from_file(cls, filename: str) -> "DICOMSR":
      instance = cls()
      instance.setup(filename)
      return instance

   def _find_text_value(self, content_sequence, preferred_code: str = None) -> Optional[str]:
      for item in content_sequence or []:
         concept_sequence = getattr(item, "ConceptNameCodeSequence", [])
         concept_value = None
         if concept_sequence:
            concept_value = getattr(concept_sequence[0], "CodeValue", None)

         if getattr(item, "ValueType", None) == "TEXT":
            text_value = getattr(item, "TextValue", None)
            if text_value and (preferred_code is None or concept_value == preferred_code):
               return text_value

         nested_result = self._find_text_value(getattr(item, "ContentSequence", []), preferred_code)
         if nested_result is not None:
            return nested_result

      return None

def makeDataset(parentUID: str, patientID: str, patientName: str, XMLString: str) -> DICOMSR:
   basicSR = DICOMSR()
   basicSR.addUIDs(parentUID)
   basicSR.addPatient(patientID=patientID, patientName=patientName)
   basicSR.addDatetimes()
   basicSR.addContent(XMLString)
   return basicSR
