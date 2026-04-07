from pydantic_xml import BaseXmlModel, attr, element
from typing import Optional, List
from datetime import datetime, date

from polyfactory.factories.pydantic_factory import ModelFactory


class TypeId(BaseXmlModel, nsmap={'': 'http://www.kith.no/xmlstds/msghead/2006-05-24'}):
	V: str = attr()
	S: str = attr()
	DN: str = attr()

class Ident(BaseXmlModel, nsmap={'': 'http://www.kith.no/xmlstds/msghead/2006-05-24'}):
	Id: str = element()
	TypeId: TypeId

class Organisation(BaseXmlModel, nsmap={'': 'http://www.kith.no/xmlstds/msghead/2006-05-24'}):
	OrganisationName: str = element()

	Ident: Ident
	organisation: "Optional[Organisation]" = element(tag="Organisation", default=None)

	class Config:
		validate_assignment = True

Organisation.model_rebuild()

class Sender(BaseXmlModel, nsmap={'': 'http://www.kith.no/xmlstds/msghead/2006-05-24'}):
	Organisation: Organisation

class Receiver(BaseXmlModel, nsmap={'': 'http://www.kith.no/xmlstds/msghead/2006-05-24'}):
	Organisation: Organisation

class Type(BaseXmlModel, nsmap={'': 'http://www.kith.no/xmlstds/msghead/2006-05-24'}):
	V: str = attr()
	DN: str = attr()

class MsgInfo(BaseXmlModel, nsmap={'': 'http://www.kith.no/xmlstds/msghead/2006-05-24'}):
	Type: Type
	MIGversion: str = element()
	GenDate: datetime = element()
	MsgId: str = element()

	Sender: Sender
	Receiver: Receiver

class Kontaktperson(BaseXmlModel, nsmap={'': 'http://www.npr.no/xmlstds/57_0_1_ide'}):
	"""Kontaktpersoner for dialog mellom kommune/helseinstitusjon og Helsedirektoratet.

	Kontaktpersoner angitt i denne klassen vil motta tilbakemelding som inneholder særlige kategorier av personopplysninger.
	NB: Det kan registreres flere kontaktpersoner per Type kontaktperson.
	Assosierte klasser:
	Er en del av  'Melding'  (Side: 8) 'by value'"""


	kontPerson: str = attr()
	meldTelefon: Optional[str] = attr(default=None)
	meldEpost1: str = attr()
	meldEpost2: Optional[str] = attr(default=None)
	typeKontaktperson: int = attr()

class PasientIdent(BaseXmlModel, nsmap={'': 'http://www.npr.no/xmlstds/57_0_1_ide'}):
	"""Finner ingen dokumentasjon på denne, unik ved ident. Paste inn her om jeg finner."""

	pid: int = attr()
	fid: str = attr() # Kan starte med 0, så ikke int
	typeID: int = attr()

class Institusjon(BaseXmlModel, nsmap={'': 'http://www.npr.no/xmlstds/57_0_1_ide'}):
	"""Institusjon som hører under lov om spesialisthelsetjenesten.
	Assosierte klasser:
	Er en del av  'Melding'  (Side: 8) 'by value'
	Inneholder 1..* 'Enhet'  (Side: 15) 'by value' 
	Inneholder 0..* 'Slett'  (Side: 19) 'by value' 
	Inneholder 1..* 'Objektholder'  (Side: 20) 'by value' 
	Har primærnøkkel: 'Institusjon identifikator'"""

	institusjonID: int = attr()
	foretak: Optional[str] = attr(default=None)

	PasientIdent: List[PasientIdent]

class Melding(BaseXmlModel, nsmap={'': 'http://www.npr.no/xmlstds/57_0_1_ide'}):
	"""Opplysninger som leverandører av helsetjenester i kommuner, 
	helsevirksomheter eller helsepersonell etter bestemmelser i lov eller 
	i medhold av lov i gitte situasjoner er pliktig til å rapportere.

		Assosierte klasser:
		Inneholder 1..* 'Kontaktperson'  (Side: 12) 'by value' 
		Inneholder 1..* 'Helseinstitusjon'  (Side: 14) 'by value' """

	versjon: str = attr()
	meldingstype: str = attr()
	fraDatoPeriode: date = attr()
	uttakDato: date = attr()
	leverandor: str = attr() # Navn på leverandør av EPJ/PAS/RIS eller annet fagsystem.
	navnEPJ: str = attr() # Navnet på EPJ/PAS/RIS eller annet fagsystem.
	versjonEPJ: str = attr() # Versjon av EPJ/PAS/RIS eller annet fabsystem.
	versjonUt: str = attr() # Uttrekksprogram er det program eller system som kopierer data fra EPJ/PAS/RIS eller annet fagsystem til XML-melding.
	lopenr: int = attr() # Entydig løpenummer (heltall) for denne melding i forhold til alle meldinger for inneværende år.
	tilDatoPeriode: date = attr() # 2003-03-01 betyr at denne melding gjelder for perioden til og med 1 mars 2003.
	lokalident: Optional[str] = attr(default=None) # Et tekstfelt leverandørene fritt kan bruke til å identifisere meldingen.
	uttakTidspunkt: Optional[datetime] = attr(default=None)

	Kontaktperson: List[Kontaktperson]
	Institusjon: List[Institusjon]

class Content(BaseXmlModel, nsmap={'': 'http://www.kith.no/xmlstds/msghead/2006-05-24'}):
	Melding: Melding

class IssueDate(BaseXmlModel, nsmap={'': 'http://www.kith.no/xmlstds/msghead/2006-05-24'}):
	V: datetime = attr()

class MsgType(BaseXmlModel, nsmap={'': 'http://www.kith.no/xmlstds/msghead/2006-05-24'}):
	V: str = attr()
	DN: str = attr()

class RefDoc(BaseXmlModel, nsmap={'': 'http://www.kith.no/xmlstds/msghead/2006-05-24'}):
	IssueDate: IssueDate
	MsgType: MsgType
	Content: Content

class Document(BaseXmlModel, nsmap={'': 'http://www.kith.no/xmlstds/msghead/2006-05-24'}):
	RefDoc: RefDoc

class MsgHead(BaseXmlModel, nsmap={'': 'http://www.kith.no/xmlstds/msghead/2006-05-24'}):
	#xmlns_xsd: str = attr(name="xmlns:xsd")
	#xmlns_xsi: str = attr(name="xmlns:xsi")
	#xmlns: str = attr(name="xmlns")

	MsgInfo: MsgInfo
	Document: Document

# Kan man ha flere tiltak per tjeneste?
# Kan man ha flere prosedyrer per tiltak?
# Kan man ha flere koder per tilstand / prosedyre?
# Innkonsekvent kapitalisering et problem? inntilstnad / utTilstand; noen med stor forbokstav ...
# Kan man ha flere behandlingsserier per medisinsk stråling?
# Kan man ha flere medisinsk stråling per objektholder?
# Er medisinskStralingID samme som pasientID?

# Er også en ident XML for å koble person ID mot personnr

class MsgHeadFactory(ModelFactory[MsgHead]):
	__model__ = MsgHead
	__allow_none_optionals__ = False
	__min_collection_length__ = 1
	__max_collection_length__ = 1