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

class Kontaktperson(BaseXmlModel, nsmap={'': 'http://www.npr.no/xmlstds/57_0_1_str'}):
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

class Utstyrsegenskaper(BaseXmlModel, nsmap={'': 'http://www.npr.no/xmlstds/57_0_1_str'}):
	"""Assosierte klasser:

	Er en del av  'Utstyr'  (Side: 21) 'by value'"""

	egenskapType: str = attr()
	verdi: str = attr()
	benevning: Optional[str] = attr(default=None) # kV, MV, MeV, Gy, ...

class Utstyr(BaseXmlModel, nsmap={'': 'http://www.npr.no/xmlstds/57_0_1_str'}):
	"""Dokumentasjon av medisinsk utstyr.

		Eksempler:
		Utstyr for medisinsk strålebruk
		Assosierte klasser:
		Er en del av  'Enhet'  (Side: 15) 'by value'
		Er referert av 0..* 'Apparat-fremmøte'  (Side: 59) 'by reference' 
		Inneholder 0..* 'Utstyrselementer'  (Side: 42) 'by value' 
		Inneholder 0..* 'Utstyrsegenskaper'  (Side: 43) 'by value' """


	# Unik identifikasjon av utstyr innen Melding. Dette kan være en system-generert nøkkel fra IT-system (eks. RIS/PACS/HIS) som benyttes når rapporten NPR-melding lages.
	utstyrID: str = attr()
	typeUtstyrsdatabase: Optional[str] = attr(default=None)
	referanseUtstyrsdatabase: Optional[str] = attr(default=None) # f.eks. MTU nummer
	meldenummerEMS: Optional[str] = attr(default=None)

	"""
	for typeUtstyr:
	Kodeverk: 9183 Type utstyr som anvendes i stråleterapi
	1 Behandlingsapparater (eksterne, høyenergetisk, C-arm linak)
	2 Behandlingsapparater (eksterne, lav/mellomenergetisk)
	3 Behandlingsapparater (strålekniv)
	4 Behandlingsapparater (brakyterapi)
	5 Terapikilder (lukkete kilder) ikke nevnt under 3 eller 4
	6 Simulatorer
	7 Skannere (CT, MR, PET, UL)
	8 Doseplanleggingssystem
	9 Informasjons- og verifikasjonssystem
	10 Felt/isosenter-kontrollsystem
	...Totalt antall koder:15
	"""

	typeUtstyr: int = attr()
	modalitetDICOM: Optional[str] = attr(default=None) # CR, CT, DX, IO, MG, MR, NM, PT, RF, etc.
	lokaltNavnUtstyr: Optional[str] = attr(default=None)
	plassering: Optional[str] = attr(default=None)
	produsent: str = attr()
	modell: Optional[str] = attr(default=None)
	statusUtstyr: Optional[int] = attr(default=None) # 1 Planlagt anskaffet, 2 Under installasjon, 3 I drift, 4 Tatt ut av drift, 5 Kassert
	oppgradert: Optional[date] = attr(default=None) # Årstall for siste vesentlige endring eller oppgradering.

	utstyrsegenskaper: Optional[List[Utstyrsegenskaper]] = element(tag="Utstyrsegenskaper", default_factory=list)

class Enhet(BaseXmlModel, nsmap={'': 'http://www.npr.no/xmlstds/57_0_1_str'}):
	"""Organisatorisk enhet ved en helseinstitusjon eller et selvstendig foretak (eks avtalespesialist) 
		uten organisatoriske inndelinger, eller organisatorisk enhet innenfor kommunale helse- og omsorgstjenester.
		
		Bruk:
		En enhet kan være et Behandlingssted, en Fagenhet, en Avdeling eller en Tjenesteenhet - eller en kombinasjon av flere muligheter. Rapporteringsenheter som har flat org. enhetsstruktur kan representere dette med kun en rad i Enhet-klassen, så for små organisasjoner, for eksempel en avtalespesialist, vil samme Enhet kunne dekke alle aktuelle roller.
		I kommunal helse- og omsorgstjenester finnes det ikke en forhåndsdefinert struktur, så benytt struktur for helsestasjon- og skolehelsetjeneste som allerede ligger i EPJ.
		Kommentar:
		En organisatorisk enhet kan for eksempel være en sengepost eller en klinisk avdeling, en serviceavdeling eller en ikke-medisinsk avdeling.
		Assosierte klasser:
		Er en del av  'Helseinstitusjon'  (Side: 14) 'by value'
		Er referert av 0..* 'Tjeneste'  (Side: 52) 'by reference' 
		Er referert av 1..* 'Referanse til enhet'  (Side: 49) 'by reference' 
		Inneholder 0..* 'Utstyr'  (Side: 21) 'by value' 
		Har primærnøkkel: 'Enhet løpenummer'"""


	enhetID: int = attr()
	orgNr: Optional[int] = attr(default=None)
	isfRefusjon: Optional[int] = attr(default=None)
	enhetLokal: Optional[str] = attr(default=None)
	offAvdKode: Optional[int] = attr(default=None)
	reshID: Optional[int] = attr(default=None)
	sektor: Optional[int] = attr(default=None)

	utstyr: Optional[List[Utstyr]] = element(tag="Utstyr", default_factory=list)

class Pasient(BaseXmlModel, nsmap={'': 'http://www.npr.no/xmlstds/57_0_1_str'}):
	"""En person som henvender seg til helsevesenet med anmodning om helsehjelp, eller som helsevesenet gir eller tilbyr helsehjelp i individuelle tilfeller.

		Assosierte klasser:
		Er en del av 1 'Objektholder'  (Side: 20) 'by value'
		Har primærnøkkel: 'Pasient nummer'"""

	pasientNr: int = attr()
	fodselsvekt: Optional[int] = attr(default=None)
	pasientGUID: Optional[str] = attr(default=None)
	kjonn: int = attr()
	fodselsar: int = attr()

class Helseperson(BaseXmlModel, nsmap={'': 'http://www.npr.no/xmlstds/57_0_1_str'}):
	"""En bokstav- og/eller tallkombinasjon, eventuelt med skilletegn i form av f. eks. punktum eller mellomrom, som utvetydig representerer en kategori i et medisinsk kodeverk.
	
	Bruk:
	Regler for om skilletegn som punktum eller mellomrom skal rapporteres er fastsatt for hvert enkelt kodeverk. 
	For ICD-10 skal ikke punktum  rapporteres.
	Eksempler:
	E70.2 rapporteres som E702
	Assosierte klasser:
	Er en del av  'Tilstand'  (Side: 50) 'by value'
	Er en del av  'Prosedyre'  (Side: 62) 'by value'
	Har primærnøkkel: 'Rekkefølge for kode'"""

	polUtforende: int = attr()

	# Spesialist 
	spesialist: Optional[str] = attr(default=None) # 1: ja, 2: nei, 9: ukjent
	rolle: Optional[str] = attr(default=None) # 1: ansvarlig; 2: ko-teraput
	helsepersonHPR: Optional[str] = attr(default=None) # HPR nummer til utførende helsepersonell

class Kontakt(BaseXmlModel, nsmap={'': 'http://www.npr.no/xmlstds/57_0_1_str'}):
	"""Uavbrutt samhandling mellom pasient og helsepersonell hvor det utføres helsehjelp for pasienten eller indirekte kontakt.

	Bruk:
	ISF: Helseperson er obligatorisk.
	Eksempler:
	Inkluderer også samhandlinger mellom pasient og helsepersonell innenfor et opphold (dag/døgnopphold).
	Behandling som utføres ved konsultasjoner ved en poliklinisk enhet, og som er mindre omfattende enn Dagbehandling.
	Konsultasjon hos primærlege, seanser under dagbehandling på poliklinikk eller sykehus, mm.
	Assosierte klasser:
	Er en del av 1 'Episode'  (Side: 25) 'by value'
	Inneholder 0..* 'Helseperson'  (Side: 60) 'by value' """

	kontaktType: int = attr()
	stedAktivitet: int = attr()

	Helseperson: List[Helseperson]

class RefEnhet(BaseXmlModel, nsmap={'': 'http://www.npr.no/xmlstds/57_0_1_str'}):
	"""Inneholder alle referanser av forskjellige typer til klassen Enhet. Type referanse er bestemt av kode i kodeverk.
	
	Obligatoriske referanser i NPR-melding fra Episode og Henvisning er av typene
	1 Behandlingsted
	7 Avdeling
	2 Fagenhet
	Det kan godt være at ulike referanser refererer til samme Enhet.
	Assosierte klasser:
	Refererer til 1 'Enhet'  (Side: 15) 'by reference'
	Er en del av  'Episode'  (Side: 25) 'by value'"""

	enhetID: int = attr()

	"""
	Hvilken type enhet denne referansen peker på. Type enhet kan f. eks. være Behandlingssted eller Tjenesteenhet.
	Kodeverk: 8476 Type enhet
	1 Behandlingssted
	2 Fagenhet
	3 Tjenesteenhet
	4 Klinikk
	5 Poliklinikk
	6 Post
	7 Avdeling
	8 Hjemmesykehus
	9 Helsestasjon- og skolehelsetjeneste

	"""
	typeEnhet: int = attr()

class Kode(BaseXmlModel, nsmap={'': 'http://www.npr.no/xmlstds/57_0_1_str'}):
	"""Medlem av Tilstand og Prosedyre"""

	# Plass-nummer for kode.
	# Hvilket nummer denne koden er i rekkefølgen av koder som tilsammen beskriver for eksempel en tilstand.
	kodeNr: int = attr()

	# Identifikasjon av hvilket kodeverk denne koden tilhører: ICD-10, NCSP-N, ATC, SNOMED etc.
	# Kodeverk: 8410 Medisinske kodeverk: D ICD, F ATC, G NORPAT, H ICPC, K NCSP-N, M NCMP,P Pakkeforløp kreft prosedyrekoder, Q NCSP/NCMP/NCRP, R NCRP, S Midlertidige nasjonale særkoder
	# ...Totalt antall koder:16
	Kodeverk: str = attr()

	# Hvilken versjon av det aktuelle kodeverk som er benyttet.
	# Identifikasjon av versjon av kodeverk skjer ved bruk av kode for versjon i henhold til liste (www.ehelse.no). 
	# For de store medisinske kodeverk vil versjonene falle sammen med årstall. Det vil kunne innføres kodeverk der versjonsnummer bygges opp på annen måte.
	kodeVersjon: int = attr()

	# Selve kodeverdien.
	# Eksempel: ICD-10 koden E70.2 rapporteres som E702
	kodeVerdi: str = attr() 

class Tilstand(BaseXmlModel, nsmap={'': 'http://www.npr.no/xmlstds/57_0_1_str'}):
	"""En tilstand uttrykt med en eller flere diagnosekoder (ICD-10).

	Bruk:
	Den første tilstanden av de registrerte tilstandene skal være hovedtilstanden. Hovedtilstanden er den tilstanden som helsehjelpen hovedsakelig er gitt for under oppholdet eller konsultasjonen, bedømt ved slutten av oppholdet eller konsultasjonen. Hvis mer enn én tilstand kan være aktuell, velges den som har krevd mest behandlingsressurser medisinsk sett. For diagnoser er gyldige koder de som er gyldige på det tidspunktet den aktuelle Episode avsluttes.
	Eksempler:
	E70.2 M36.8 (etiologi+manifestasjon, i følge regler om multippel koding i ICD-10)
	Kommentar:
	En tilstand kan inneholde flere koder (fra ICD-10 og andre kodeverk)
	Assosierte klasser:
	Er en del av  'Episode'  (Side: 25) 'by value'
	Inneholder 1..* 'Kode'  (Side: 64) 'by value' """

	tilstNr: int = attr()

	kode: Optional[List[Kode]] = element(tag="Kode", default_factory=list)

class Prosedyre(BaseXmlModel, nsmap={'': 'http://www.npr.no/xmlstds/57_0_1_str'}):
	"""Pasientrettet tiltak kategorisert etter en normgivende beskrivelse eller et kodeverk.
	
	Bruk:
 	For prosedyrer er gyldige koder de som er gyldige på det tidspunktet prosedyren utføres.
	Assosierte klasser:
	Er en del av  'Tiltak'  (Side: 57) 'by value'
	Inneholder 1..* 'Kode'  (Side: 64) 'by value' 
	Har primærnøkkel: 'Rekkefølge Prosedyre'"""


	prosNr: int = attr()
	tilstNr: Optional[int] = attr(default=None)

	kode: Optional[List[Kode]] = element(tag="Kode")

class Tiltak(BaseXmlModel, nsmap={'': 'http://www.npr.no/xmlstds/57_0_1_str'}):
	"""Representerer et tiltak i en tjeneste. 

	Et tiltak kan inneholde null, en eller flere forekomster av klassen Prosedyre.
	Assosierte klasser:
	Er en del av  'Tjeneste'  (Side: 52) 'by value'
	Inneholder 0..* 'Helseperson'  (Side: 60) 'by value' 
	Inneholder 0..* 'Prosedyre'  (Side: 62) 'by value' """


	typeTiltak: int = attr() # 1: medisinske og kirurgiske tiltak; 2: bildediagnostikk
	startDatoTid: Optional[datetime] = attr(default=None)
	sluttDatoTid: Optional[datetime] = attr(default=None)

	prosedyre: Optional[List[Prosedyre]] = element(tag="Prosedyre", default_factory=list)
	helseperson: Optional[List[Helseperson]] = element(tag="Helseperson", default_factory=list)

class Tjeneste(BaseXmlModel, nsmap={'': 'http://www.npr.no/xmlstds/57_0_1_str'}):
	"""En eller flere behandlingsrettede tiltak som utføres for en pasient under en og samme tjeneste (seanse).
			
	Bruk:
	 Det kan være ingen, en eller flere Tjenester i en Episode.
	Assosierte klasser:
	Refererer til 1 'Enhet'  (Side: 15) 'by reference'
	Er en del av  'Episode'  (Side: 25) 'by value'
	Inneholder 0..* 'Tiltak'  (Side: 57) 'by value' """

	startDatoTid: datetime = attr()
	sluttDatoTid: Optional[datetime] = attr(default=None)

	# Identifikasjon av den helseinstitusjon som utfører tjenesten, i tilfelle det er en annen institusjon som 
	# utfører tjenesten enn den institusjon og enhet som utfører pasientbehandlingen.
	instID: Optional[str] = attr(default=None)

	tiltak: Optional[List[Tiltak]] = element(tag="Tiltak", default_factory=list)

class Episode(BaseXmlModel, nsmap={'': 'http://www.npr.no/xmlstds/57_0_1_str'}):
	"""Tidsperiode hvor pasienten får helsehjelp ved én og samme helseinstitusjon for ett og samme helseproblem.

		Bruk:
		En episode kan være en poliklinisk konsultasjon, et dagopphold eller et døgnopphold. 
		NB: En episode betegner aktivitet, ikke bare behandling.
		Assosierte klasser:
		Er en del av  'Objektholder'  (Side: 20) 'by value'
		Inneholder 1 'Kontakt'  (Side: 44) 'by value' 
		Inneholder 0..* 'Referanse til enhet'  (Side: 49) 'by value' 
		Inneholder 0..* 'Tilstand'  (Side: 50) 'by value' 
		Inneholder 0..* 'Tjeneste'  (Side: 52) 'by value' 
		Er assosiert med  'Apparat-fremmøte'  (Side: 59) 
		Har primærnøkkel: 'EpisodeID'"""

	episodeID: str = attr()
	episodeGUID: Optional[str] = attr(default=None)
	henvisningsperiodeID: Optional[str] = attr(default=None) # !!!!
	fraInstitusjonID: Optional[str] = attr(default=None)
	serieID: int = attr()
	innDatoTid: datetime = attr()
	fraSted: Optional[int] = attr(default=None)
	debitor: int = attr()
	komNrHjem: int = attr()
	kommTjeneste: Optional[int] = attr(default=None)
	inntilstand: int = attr() # 1: levende ved ankomst til instutusjon, 2: død ved ankomst, 3: levende født i sykehus
	innmateHast: int = attr()
	omsorgsniva: int = attr()
	arenafleksibel: Optional[int] = attr(default=None)
	utTilstand: Optional[int] = attr(default=None)
	tilSted: Optional[int] = attr(default=None)
	utDatoTid: Optional[datetime] = attr(default=None)

	Kontakt: Kontakt
	refEnhet: Optional[List[RefEnhet]] = element(tag="RefEnhet", default_factory=list)
	tilstand: Optional[List[Tilstand]] = element(tag="Tilstand", default_factory=list)
	tjeneste: Optional[List[Tjeneste]] = element(tag="Tjeneste", default_factory=list)

class Dosebidrag(BaseXmlModel, nsmap={'': 'http://www.npr.no/xmlstds/57_0_1_str'}):
	"""Angivelse av planlagt og gitt dose til Referansevolum.
	
	Assosierte klasser:
	Refererer til 1 'Referansevolum stråleterapi'  (Side: 56) 'by reference'
	Er en del av  'Apparat-fremmøte'  (Side: 59) 'by value'"""


	referansevolumID: int = attr()
	planDose: float = attr()
	gittDose: float = attr()

class ApparatFremmote(BaseXmlModel, nsmap={'': 'http://www.npr.no/xmlstds/57_0_1_str'}):
	"""Det enkelte apparats bidrag til et fremmøte.

	Det kan være flere apparat-fremmøter per Episode.
	Assosierte klasser:
	Refererer til 1 'Utstyr'  (Side: 21) 'by reference'
	Er en del av  'Behandlingsserie'  (Side: 54) 'by value'
	Inneholder 0..* 'Dosebidrag'  (Side: 63) 'by value' 
	Er assosiert med  'Episode'  (Side: 25) """

	episodeID: str = attr() # check that this exists in Episode
	refUtstyr: int = attr() # check that this exists in Utstyr

	doseBidrag: Optional[List[Dosebidrag]] = element(tag="Dosebidrag", default_factory=list)

class Behandlingsserie(BaseXmlModel, nsmap={'': 'http://www.npr.no/xmlstds/57_0_1_str'}):
	"""En serie med fremmøter innen medisinsk strålebruk.

		Assosierte klasser:
		Er en del av  'Medisinsk stråling'  (Side: 40) 'by value'
		Inneholder 1..* 'Apparat-fremmøte'  (Side: 59) 'by value'"""

	serieID: int = attr() # check that this exists in Episode
	behandlingsserieNavn: Optional[str] = attr(default=None)
	intensjon: Optional[int] = attr(default=None)
	nyPasient: int = attr() # 1: ja; 2: nei
	datoForste: Optional[date] = attr(default=None) # Dato for det første fremmøte i en serie med fremmøter

	ApparatFremmote: List[ApparatFremmote]

class Referansevolum(BaseXmlModel, nsmap={'': 'http://www.npr.no/xmlstds/57_0_1_str'}):
	"""Anatomi og Referansevolum der rekvirert dose skal gis.

	Assosierte klasser:
	Er en del av  'Medisinsk stråling'  (Side: 40) 'by value'
	Er referert av 1..* 'Dosebidrag'  (Side: 63) 'by reference' 
	Har primærnøkkel: 'Referansevolum identifikasjon'"""

	referansevolumID: int = attr()
	referansevolumNavn: str = attr()
	regionkode: int = attr()
	regionNavn: Optional[str] = attr(default=None)
	planlagtTotalDose: float = attr()
	dosekorreksjon: int = attr()
	merknad: Optional[str] = attr(default=None)

class MedisinskStraling(BaseXmlModel, nsmap={'': 'http://www.npr.no/xmlstds/57_0_1_str'}):
	"""Medisinsk stråling er en samlebetegnelse for informasjoner som knytter seg til all bruk av bildedannende utstyr, 
		nukleærmedisin og stråleterapi.

		Assosierte klasser:
		Er en del av  'Objektholder'  (Side: 20) 'by value'
		Inneholder 0..* 'Behandlingsserie'  (Side: 54) 'by value' 
		Inneholder 0..* 'Referansevolum stråleterapi'  (Side: 56) 'by value' """

	medisinskStralingID: int = attr()
	medisinskStralingGUID: Optional[int] = attr(default=None)
	tilleggsopplysninger: Optional[str] = attr(default=None)

	behandlingsserie: Optional[List[Behandlingsserie]] = element(tag="Behandlingsserie", default_factory=list)
	referansevolum: Optional[List[Referansevolum]] = element("Referansevolum", default_factory=list)

class Objektholder(BaseXmlModel, nsmap={'': 'http://www.npr.no/xmlstds/57_0_1_str'}):
	"""Er en container som holder objekter fra lavere nivå. 

	Hver av objektene på lavere nivå skal identifiseres ved hjelp av GUID eller annen unik identifikasjon 
	slik at alle objekter kan identifiseres på tvers av meldinger.

	Bruk:
	Det finnes en objektholder per pasient/bruker.
	Assosierte klasser:
	Er en del av  'Helseinstitusjon'  (Side: 14) 'by value'
	Inneholder 0..* 'Episode'  (Side: 25) 'by value' 
	Inneholder 0..* 'Medisinsk stråling'  (Side: 40) 'by value' 
	Inneholder 0..1 'Pasient'  (Side: 41) 'by value' med 'constraints' {XOR Objektholder}
	Har primærnøkkel: 'Pasient/brukernummer'"""
 
	pasientNr: int = attr() #  brukes i forbindelse med tilbakemelding av feil, og kobling av personidentifikasjon i Ident-meldingen (ide) til andre meldinger.
	pasientGUID: Optional[int] = attr(default=None)

	Pasient: Pasient
	# Pasient: Optional[Pasient]
	episode: List[Episode] = element(tag="Episode", default_factory=list)
	medisinskStraling: Optional[List[MedisinskStraling]] = element(tag="MedisinskStraling", default_factory=list)

class Institusjon(BaseXmlModel, nsmap={'': 'http://www.npr.no/xmlstds/57_0_1_str'}):
	"""Institusjon som hører under lov om spesialisthelsetjenesten.
	Assosierte klasser:
	Er en del av  'Melding'  (Side: 8) 'by value'
	Inneholder 1..* 'Enhet'  (Side: 15) 'by value' 
	Inneholder 0..* 'Slett'  (Side: 19) 'by value' 
	Inneholder 1..* 'Objektholder'  (Side: 20) 'by value' 
	Har primærnøkkel: 'Institusjon identifikator'"""

	institusjonID: int = attr()
	foretak: Optional[str] = attr(default=None)

	Enhet: List[Enhet]
	Objektholder: List[Objektholder]

class Melding(BaseXmlModel, nsmap={'': 'http://www.npr.no/xmlstds/57_0_1_str'}):
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

class MsgHeadFactory(ModelFactory[MsgHead]):
	__model__ = MsgHead
	__allow_none_optionals__ = False
	__min_collection_length__ = 1
	__max_collection_length__ = 1
