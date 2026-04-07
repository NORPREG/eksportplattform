import tempfile
import datetime
import pydicom

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

   def getXML(self) -> str:
      self.xml_doc = sr.ContentSequence[0].TextValue
      return self.xml_doc

def makeDataset(parentUID: str, patientID: str, patientName: str, XMLString: str) -> DICOMInterface:
   basicSR = DICOMInterface()
   basicSR.addUIDs(parentUID)
   basicSR.addPatient(patientID=patientID, patientName=patientName)
   basicSR.addDatetimes()
   basicSR.addContent(XMLString)
   return basicSR
