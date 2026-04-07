import pathlib

from module.dataclass.NPR_ident_dataclass import NPRIdent

"""
The NPR Ident file contains the fødselsnummer of the patient 
referred to in the NPR file.
Here the NPR Ident file is parsed using Pydantic
(with data class in Terminologies.NPRIdent)
"""

class ListStructureAssertionException(Exception):
	pass

class NPRIdentInterface:
	def __init__(self, path: str = None, encoding: str = "utf-8") -> None:
		# Reads files fine with utf-8, crashes with iso-8859-1
		# even if the source document is the latter...?
		self.path = path
		self.encoding = encoding

		if self.path:
			self.xml_doc = pathlib.Path(self.path).read_text().encode(self.encoding)
			self.nprIdent = NPRIdent.MsgHead.from_xml(self.xml_doc)

	def fillWithDummy(self) -> None:
		self.nprIdent = NPRIdent.MsgHeadFactory.build()	

	def getXML(self) -> str:
		return str(self.nprIdent.to_xml(skip_empty=True))

	def getPatients(self) -> dict:
		"""Returns a dictionary of {patientPID : patientFNR}"""

		patients = dict()

		for ident in self.nprIdent.Document.RefDoc.Content.Melding.Institusjon[0].PasientIdent:
			patients[ident.pid] = ident.fid

		return patients