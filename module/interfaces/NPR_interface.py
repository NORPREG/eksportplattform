import pathlib
import numpy as np

from module.dataclass import NPR_dataclass
from module.dataclass.ICD10 import ICD10
from module.dataclass.Region import Region
from module.dataclass.NKPK import NKPK


"""
This file is responsible for extracting data from the NPR XML file.
The XML file is either parsed from DICOM SR here, or earlier in the process.
"""

class ListStructureAssertionException(Exception):
	pass


class NPRInterface:
	def __init__(self, path: str = None, xml_string: str = None, encoding: str = "utf-8") -> None:
		# Reads files fine with utf-8, crashes with iso-8859-1
		# even if the source document is the latter...?
		self.path = path
		self.encoding = encoding
		self.xml_string = xml_string
		self.npr = None

		if self.path:
			self.xml_doc = pathlib.Path(self.path).read_text().encode(self.encoding)
			self.npr = NPR_dataclass.MsgHead.from_xml(self.xml_doc)
			self.inst = self.npr.Document.RefDoc.Content.Melding.Institusjon[0]

		elif self.xml_string:
			self.npr = NPR_dataclass.MsgHead.from_xml(self.xml_string)
			self.inst = self.npr.Document.RefDoc.Content.Melding.Institusjon[0]

		else:
			self.inst = None

		self.ICD10 = ICD10()
		self.NKPK = NKPK()
		self.Region = Region()

	def fill_with_dummy(self) -> None:
		self.npr = NPR_dataclass.MsgHeadFactory.build()
		self.inst = self.npr.Document.RefDoc.Content.Melding.Institusjon[0]

	def get_XML(self) -> str:
		if not self.npr:
			return ""

		return str(self.npr.to_xml(skip_empty=True))

	def get_patients(self) -> list:
		if not self.inst:
			return list()

		return [obj.Pasient for obj in self.inst.Objektholder]

	def get_patientNrs(self) -> list:
		if not self.inst:
			return list()

		return [obj.Pasient.pasientNr for obj in self.inst.Objektholder]

	def get_patient(self, pasientNr: int):
		if not self.inst:
			return None

		for objekt in self.inst.Objektholder:
			if objekt.pasientNr != pasientNr:
				continue

			if len(objekt.medisinskStraling) > 1:
				raise ListStructureAssertionException(
					 'medisinskStraling encountered more than one')

			return objekt.Pasient

	def get_behandlingsserie(self, pasientNr: int) -> list:
		if not self.inst:
			return list()

		for objekt in self.inst.Objektholder:
			if not objekt.pasientNr == pasientNr:
				continue

			if len(objekt.medisinskStraling) > 1:
				raise ListStructureAssertionException(
					 'medisinskStraling encountered more than one')

			return objekt.medisinskStraling[0].behandlingsserie

	def get_referenced_volumes(self, pasientNr: int) -> list:
		# TODO: Sjekk at pasientNr == attr i medisinsk stråling her i stedet for å bruke indeksert patID

		if not self.inst:
			return list()

		vols = None
		for objekt in self.inst.Objektholder:
			for medisinskStraling in objekt.medisinskStraling:
				if not medisinskStraling.medisinskStralingID == pasientNr:
					continue

				if isinstance(vols, list):
					raise ListStructureAssertionException('medisinskStraling encountered more than one')

				vols = medisinskStraling.referansevolum

		return {v.referansevolumID: v.referansevolumNavn for v in vols}

	def get_dose_fractions(self, pasientNr: int) -> dict:
		if not self.inst:
			return dict()

		doseDict = dict()

		structureDict = self.get_referenced_volumes(pasientNr)

		for structureName in structureDict.values():
			doseDict[structureName] = {'plan': list(), 'gitt': list()}

		for behandlingsserie in self.get_behandlingsserie(pasientNr):
			for apparatFremmote in behandlingsserie.ApparatFremmote:
				for doseBidrag in apparatFremmote.doseBidrag:
					structureName = structureDict[doseBidrag.referansevolumID]
					doseDict[structureName]['plan'].append(float(doseBidrag.planDose))
					doseDict[structureName]['gitt'].append(float(doseBidrag.gittDose))

		return doseDict

	def get_dose_total(self, pasientNr: int) -> dict:
		if not self.inst:
			return dict()

		dose_fractions = self.get_dose_fractions(pasientNr)
		dose_fractions_total = dict()

		for structure, data in dose_fractions.items():
			dose_fractions_total[structure] = dict()
			dose_fractions_total[structure]['gitt'] = np.sum(data['gitt'])
			dose_fractions_total[structure]['plan'] = np.sum(data['plan'])

		return dose_fractions_total

	def get_behandlingsserie_navn(self, pasientNr: int) -> set:
		if not self.inst:
			return set()

		"""Løpenummer som beskriver antall slike behandlinger pasienter har fått + serienavn."""

		serier = set()

		for behandlingsserie in self.get_behandlingsserie(pasientNr):
			serier.add(behandlingsserie.behandlingsserieNavn)

		return serier

	def get_episodes(self, pasientNr: int) -> list:
		if not self.inst:
			return list()

		# episode id: diagnosis, treatment code
		episodes = list()
		for obj in self.inst.Objektholder:
			if not obj.pasientNr == pasientNr:
				continue

			for episode in obj.episode:
				episodes.append(episode)

		return episodes

	def get_diagnoses(self, pasientNr: int) -> dict:
		if not self.inst:
			return dict()

		diagnoser = set()

		episodes = self.get_episodes(pasientNr)
		for episode in episodes:
			for tilstand in episode.tilstand:
				for kode in tilstand.kode:
					diagnoser.add(kode.kodeVerdi)

		return {diag: self.ICD10.getICD10Definition(diag) for diag in diagnoser}

	def get_prosedyrer(self, pasientNr: int) -> dict:
		if not self.inst:
			return dict()

		prosedyrer = set()

		episodes = self.get_episodes(pasientNr)
		for episode in episodes:
			for tjeneste in episode.tjeneste:
				for tiltak in tjeneste.tiltak:
					for prosedyre in tiltak.prosedyre:
						for kode in prosedyre.kode:
							prosedyrer.add(kode.kodeVerdi)

		return {pros: self.NKPK.getNKPKDefinition(pros) for pros in prosedyrer}
