# Eksportplattform

Dette prosjektet automatiserer eksport av stråleterapi-relaterte DICOM-data fra **ARIA** til **Conquest PACS**, og videre til eksterne mottakere (KREST / NORPREG).

Scriptet finner behandlingsplaner opprettet etter en gitt dato, bygger en komplett DICOM-studiestruktur (RTPLAN → RTDOSE → RTSTRUCT → CT), laster ned manglende objekter til Conquest, og sender deretter studien videre til definerte mottakere.


# Formål

Systemet sikrer at:

* komplette stråleterapiplaner eksporteres
* alle nødvendige DICOM-objekter følger med
* eksporten kan spores og reproduseres

---

# Oversikt

Arbeidsflyten er:

1. Hent alle RT plan-sett fra ARIA etter en gitt dato
2. For hver pasient:

   * Finn RT Plan og tilhørende RT Dose via ARIA DB integrasjon. Behøver en SQL-prosedyre for dette.
   * Finn referert RT Structure Set fra RT Plan-filen
   * Finn CT-serier referert fra Structure Set
3. Last ned DICOM-objekter fra ARIA til lokal Conquest via C-MOVE
4. Send komplett datasett videre til:
   * Intern Conquest-node (nødvendig for port-tøys)
   * KREST-HUS
5. Logg eksporterte pasienter i en eksportdatabase (MSSQL)

Dette sikrer at komplette behandlingsdatasett blir eksportert konsistent.

TODO: Legg til NPR i eksporten
TODO: RT Treatment Record eksport kræsjer pga. bug i Aria. Få dette fikset.

---

# Arkitektur

Scriptet fungerer som en **orkestrator** som koordinerer flere grensesnittmoduler:

```
ARIA Database
      │
      ▼
aria_db_interface
      │
      ▼
PlanSet struktur
      │
      ▼
ARIA DICOM (C-MOVE)
aria_dicom_interface
      │
      ▼
Conquest PACS
      │
      ├─ conquest_db_interface
      │
      └─ conquest_dicom_interface
             │
             ▼
      Eksterne mottakere
      (Medfys / KREST)
```

---

# Datastruktur

`plan_set` representerer behandlingsdata organisert per pasient:

```
PatientSer {
    "PatientID",
    "PlanSet": {
        RT Plan SOP UID: {
            "RTPLAN": RT Plan SOP UID,
            "RTPlanLabel": "...",
            "RTDOSE": {Dose SOP UID},
            "RTSTRUCT": {Structure SOP UID},
            "RTRECORD": [Treatment Record UID],
            "CT": {Series Instance UID}
        }
    }
}
```

Denne strukturen bygges opp gradvis mens scriptet finner refererte objekter.

---

# Arbeidsflyt

## 1. Finn plan-sett

```python
plan_set = aria_db_interface.get_plan_set(dt)
```

Returnerer alle pasienter med RT Plan opprettet etter en gitt dato.

---

## 2. Kontroller om pasienten allerede er eksportert

Eksportdatabasen brukes til å unngå duplikater.

```python
sent_dt = log_database.check_patient(patient_ser)
```

---

## 3. Verifiser RTPLAN og RTDOSE

Scriptet sjekker om disse finnes i Conquest.

Hvis ikke:

```
ARIA → C-MOVE → Conquest
```

---

## 4. Finn RTSTRUCT

Fra RT Plan-filen hentes referert Structure Set.

Hvis mangler:

```
ARIA → C-MOVE → Conquest
```

---

## 5. Finn CT-serie

Fra RTSTRUCT identifiseres refererte CT-serier.

Hvis serien ikke finnes i Conquest:

```
ARIA → C-MOVE → Conquest
```

---

## 6. Send komplett studie

Når alle nødvendige objekter finnes:

```
Conquest (Medfys-1) → Conquest (Medfys-2)
Conquest (Medfys-2) → KREST-HUS
```

Merk at det her benyttes to Conquest-instanser. Det er fordi ulike port-rekkevidder måtte benyttes mot Aria (via "medfys-1") og KREST-HUS (via "medfys-2").
Derfor må dataene først flyttes fra "medfys-1" til "medfys-2" før de kan overføres til KREST-HUS, da via en C-MOVE.

Dette gjøres via:

```python
conquest_dicom_interface.c_move_to_medfys2(...)
conquest_dicom_interface.c_move_to_krest_hus(...)
```

---

# Konfigurasjon

Konfigurasjon lastes fra `Config`, som funker som en Singleton med dot-henvisning:

```python
from config import Config
config = Config()
```

Se `config/test_config.toml` for eksempel.

---

# Viktige moduler

## Interfaces

| Modul                    | Beskrivelse                      |
| ------------------------ | -------------------------------- |
| aria_db_interface        | Leser RT Plan-data fra ARIA SQL  |
| aria_dicom_interface     | DICOM kommunikasjon mot ARIA     |
| conquest_db_interface    | Query mot Conquest database      |
| conquest_dicom_interface | DICOM eksport fra Conquest       |
| export_logger_interface  | Logging av eksporterte pasienter |

---

# Kjøring

Scriptet kan kjøres direkte:

```
python eksportplattform.py
```

Datoen som brukes til å finne nye planer er:

```python
dt = datetime(2025, 1, 1)
```
