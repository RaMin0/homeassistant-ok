<div align="center">
  <img src="custom_components/ok/brand/logo.png" alt="OK logo" width="180">

  <h1>OK til Home Assistant</h1>

  <p>
    <strong>OK hjemmeladning, styring, ladeplaner, sessionsdata og danske elpriser i Home Assistant, med realtime-status når OKs Firestore-opdateringer er tilgængelige.</strong>
  </p>

  <p>
    <a href="https://github.com/RaMin0/homeassistant-ok/releases"><img alt="GitHub release" src="https://img.shields.io/github/v/release/RaMin0/homeassistant-ok?style=for-the-badge"></a>
    <a href="https://github.com/RaMin0/homeassistant-ok/actions/workflows/validate.yml"><img alt="Valideringsstatus" src="https://img.shields.io/github/actions/workflow/status/RaMin0/homeassistant-ok/validate.yml?branch=main&style=for-the-badge&label=validate"></a>
    <a href="https://hacs.xyz"><img alt="HACS custom repository" src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge&logo=homeassistant&logoColor=white"></a>
    <a href="https://github.com/RaMin0/homeassistant-ok/blob/main/LICENSE"><img alt="Licens" src="https://img.shields.io/github/license/RaMin0/homeassistant-ok?style=for-the-badge"></a>
  </p>

  <p>
    <img alt="Home Assistant 2025.12.5+" src="https://img.shields.io/badge/Home%20Assistant-2025.12.5%2B-18BCF2.svg?style=for-the-badge&logo=homeassistant&logoColor=white">
  </p>

  <p>
    <a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=RaMin0&repository=homeassistant-ok&category=integration"><img alt="Åbn dette repository i HACS" src="https://my.home-assistant.io/badges/hacs_repository.svg"></a>
    <a href="https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fraw.githubusercontent.com%2FRaMin0%2Fhomeassistant-ok%2Fmain%2Fblueprints%2Fscript%2Fok%2Fschedule_charging.yaml"><img alt="Importer blueprint til planlagt opladning" src="https://my.home-assistant.io/badges/blueprint_import.svg"></a>
  </p>

  <p>
    <a href="README.md">English</a> | <a href="README.da.md">Dansk</a>
  </p>
</div>

## ✨ Hvad Det Tilføjer

| Område | Funktion |
| --- | --- |
| ⚡ Charger-status | Connector- og ladesessionsstatus med Firestore realtime-opdateringer når de er tilgængelige, og polling som fallback. |
| 🎛️ Styring | Start, stop, ladeplan, opdater ladeplan, annuller ladeplan, genstart charger og auto start fra Home Assistant. |
| 🔋 Sessionsdata | Aktuel connector sessions-effekt/-energi, ladeplanens tider og valgfri data fra seneste afsluttede session. |
| 💰 Elpriser | OK-priser med en normaliseret `prices` tidslinje til grafer og kompatible attributter til `energidataservice`-lignende brug. |
| 🧰 Vedligeholdelse | Force refresh til fejlsøgning og diagnostiske tidspunkter for seneste opdatering på konto og charger. |
| 🔒 Privatliv | Diagnostics skjuler OK konto-, app-, device- og legacy token-identifikatorer. Integrationen tilføjer ingen egen telemetri. |

## 🤝 Passer Godt Sammen Med

- [ApexCharts Card](https://github.com/RomRider/apexcharts-card), via `prices` attributten til
  timebaserede elprisgrafer.
- [energy_price_window](https://github.com/JBoye/energy_price_window) og
  `energidataservice`-lignende automations via kompatible attributter på elpris-sensoren.
- Home Assistant scripts og dashboard-knapper via den medfølgende blueprint til planlagt
  opladning.

Eksempler til ApexCharts, kompakt charger-kort og blueprint findes i
[docs/USAGE_EXAMPLES.md](docs/USAGE_EXAMPLES.md).

## ✅ Understøttet Setup

- Home Assistant `2025.12.5+`. CI tester også mod Home Assistants aktuelle `stable` container image.
- OK konto-login der virker i OK appen.
- En OK hjemmelader som returneres af OK appens APIer.
- Danske elpriser fra OK for den konfigurerede charger.

Offentlige OK hurtigladere og produkter uden for OK hjemmeladning er ikke en del af det nuværende
scope.

## 🏅 Kvalitetsstatus

Denne custom integration vedligeholdes efter interne **Gold+** kvalitetskrav for HACS/custom
integrations. Den er ikke en Home Assistant Core integration og har ikke en officiel Home Assistant
quality-scale certificering. Tilbageværende Core/Platinum-relaterede tradeoffs er beskrevet i
[ROADMAP.md](ROADMAP.md).

## ⚠️ Kendte Begrænsninger

- Dette er et uofficielt community-projekt. Det er ikke tilknyttet, godkendt, sponsoreret eller
  supporteret af OK a.m.b.a.
- OK-navne, logoer og varemærker tilhører OK a.m.b.a. De bruges kun til at identificere den service
  integrationen forbinder til.
- Integrationen bruger OK app APIer, som ikke er en offentlig Home Assistant API-kontrakt. OK kan
  ændre, rotere, rate-limitte, begrænse eller blokere API-adfærd uden varsel.
- Realtime-status afhænger af OK Firestore-dokumenter og watcher-support. Hvis Firestore-runtime
  mangler eller er fejlkonfigureret, opretter Home Assistant en repair issue, og integrationen
  fortsætter med polling. Forbigående watcher-fejl forsøges igen med bounded backoff.
- Polling styres internt med freshness windows og backoff for at reducere OK API-trafik. Force
  refresh går uden om disse vinduer, henter HTTP snapshots for realtime-backed status og kan øge OK
  API-trafik. Brug ikke force refresh i gentagne automations eller som en ofte brugt dashboard-knap.
- OK API-klienten er med vilje bundlet inde i `custom_components/ok/api` for nu, så HACS og manuel
  installation leveres som ét projekt.
- Lokale brand-assets er inkluderet i repositoriet og kan bruges af Home Assistant-versioner der
  understøtter lokale custom-integration brand-filer. På ældre Home Assistant-versioner kan frontend
  branding stadig kræve OK-assets i Home Assistant brands-repositoriet.

## 🚀 Installation

### HACS

[![Åbn dette repository i HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=RaMin0&repository=homeassistant-ok&category=integration)

1. Brug HACS-knappen ovenfor, eller tilføj dette repository som et custom HACS integration repository.
2. Installer `OK`.
3. Genstart Home Assistant.
4. Gå til **Indstillinger > Enheder og tjenester > Tilføj integration** og søg efter `OK`.

Repositoriet bruger HACS release assets. Installer en udgivet release der indeholder `ok.zip`; undgå
at installere direkte fra `main`, medmindre du bevidst tester kode der endnu ikke er udgivet.

HACS installerer filerne, men konfigurerer ikke integrationen for dig. Setup sker stadig gennem Home
Assistants integrations-UI efter genstart.

### Manuel

1. Kopiér `custom_components/ok` til din Home Assistant `custom_components` mappe.
2. Genstart Home Assistant.
3. Gå til **Indstillinger > Enheder og tjenester > Tilføj integration** og søg efter `OK`.

## ⚙️ Setup Og Indstillinger

Config flowet beder om den email og adgangskode du bruger i OK appen. Adgangskoden bruges til at
registrere og autentificere Home Assistant som en OK app-enhed og gemmes derefter ikke.
Config entry gemmer email-adresse og de OK app/device-identifikatorer der kræves til fremtidige API
kald. Disse værdier skjules i diagnostics.

Options flowet lader dig slå valgfrie dele fra:

- **Elpris-entities**: henter OK-priser og opretter elpris-sensoren.
- **Seneste session entities**: henter lade-kvitteringer og opretter de valgfrie last-session sensorer.
- **Kontrolknapper**: opretter start, stop, annuller ladeplan og genstart-knapper. Genstart er en
  config-category knap og er deaktiveret som standard i entity registry.
- **Avanceret > Realtime updates**: bruger Firestore realtime watchers for connector- og
  ladesessionsstatus. Slå dette fra for kun at bruge polling.

Pollingfrekvens styres af integrationen. Charger metadata og priser opdateres cirka hvert 30. minut.
Aktive ladesessioner opdateres oftere mens de er aktive og sjældnere når de er idle. Når seneste
session entities er slået til, hentes den fulde kvitteringsliste ved setup, force refresh og cirka
hver 12. time; quick receipt bruges for kendte sessioner efter de afsluttes.

## 🧩 Entities Og Actions

Den fulde entity-model, scopes, defaults, attributter og action target-regler er dokumenteret i
[docs/ENTITY_MODEL.md](docs/ENTITY_MODEL.md).

Overordnet opretter integrationen en `OK Account` service device, én Home Assistant device per OK
charger, charger/connector entities til status og kontrol, valgfrie receipt-backed last-session
entities og diagnostiske refresh-sensorer på konto og charger.

Actions tager en OK connector status sensor `entity_id`, så automations ikke behøver rå OK charger-
eller connector-IDer. Schedule actions bruger Home Assistant datetime selectors. Naive datetimes
fortolkes i Home Assistants lokale tidszone før de sendes til OK.

## 🕒 Schedule Script Blueprint

Repositoriet indeholder en script blueprint der kan kaldes fra en dashboard-knap og spørge efter et
tidsrum for planlagt opladning. Import, manuel kopi, dashboard-brug og tilsvarende script action er
dokumenteret i [docs/USAGE_EXAMPLES.md](docs/USAGE_EXAMPLES.md).

My Home Assistant blueprint-knappen øverst importerer blueprinten fra den aktuelle `main` branch.
Hvis du vil bruge den præcise blueprint fra en installeret release, så kopiér den fra release-kilden
eller fra din installerede custom component.

## ⚡ Realtime Og Polling

Connector- og ladesessionsstatus bruger OK Firestore document watches når realtime updates er slået
til og tilgængelige. Integrationen bruger Firestores synkrone `on_snapshot()` watcher gennem en async
wrapper, så watch setup, events og cleanup holdes væk fra Home Assistants event loop.

Noget data er ikke fuldt dækket af realtime-dokumenter, herunder charger discovery, prisvinduer,
aktive ladesessioner, kvitteringer og watcher recovery. Polling er derfor stadig aktivt for disse
kilder. Den detaljerede fallback-adfærd er beskrevet i
[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md#how-realtime-updates-work).

## 🔒 Support, Diagnostics Og Sikkerhed

Læs [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) før du opretter en issue, og brug den
relevante issue template. Inkludér OK integrationens version, Home Assistant-version,
installationsmetode, redigerede logs og diagnostics når det er relevant.

Indsæt ikke adgangskoder, tokens, Home Assistant `.storage` filer, `secrets.yaml`, databaser eller
urensede API captures i offentlige issues. Rapporter sårbarheder privat som beskrevet i
[SECURITY.md](SECURITY.md). Kun den seneste udgivne release supporteres aktivt for sikkerhedsfixes.

OK mobile app secret er med vilje inkluderet som en konstant i integrationen. Det er en delt
applikationscredential der bruges til at registrere og signere OK app requests, ikke en
brugerspecifik secret. OK kan rotere eller blokere denne credential, hvilket vil kræve en
integrationsopdatering.

## 🗑️ Fjernelse

1. Slet OK integrationens entry fra **Indstillinger > Enheder og tjenester**.
2. Genstart Home Assistant hvis du installerede custom component manuelt og vil fjerne filerne.
3. Slet `custom_components/ok` ved manuel installation, eller afinstaller gennem HACS.

Når integrationens entry fjernes, slettes de gemte OK app/device-identifikatorer fra Home Assistants
config entry storage.

## 🛠️ Udvikling

Bidragsvejledning findes i [CONTRIBUTING.md](CONTRIBUTING.md). Repository-specifik automation og
AI agent-regler findes i [AGENTS.md](AGENTS.md). Docker-validering er dokumenteret i
[docs/VALIDATION.md](docs/VALIDATION.md), og det lokale Home Assistant compose-miljø er dokumenteret
i [docker/README.md](docker/README.md).
