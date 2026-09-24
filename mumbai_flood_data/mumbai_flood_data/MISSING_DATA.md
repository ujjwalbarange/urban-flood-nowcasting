# Missing / Unverified Data

Per task instructions: nothing below is fabricated. Each item states exactly what was checked and why
it's marked unavailable or unverified.

## 1. MCGM/BMC storm-water drainage network (lines, nodes, manholes, outfalls, pumping stations, hydraulic parameters)
**Status: NOT PUBLICLY AVAILABLE / NOT VERIFIED**
- Sources checked: MCGM website, "One MCGM GIS" ArcGIS portal, MCGM Disaster Management Dept pages,
  data.gov.in, Maharashtra govt/AMRUT portals, OpenStreetMap drain tags, DataMeet/OpenCity/bharatlas
  aggregators, academic literature (arxiv.org/abs/2306.09770, nidm.gov.in journal), iFLOWS-Mumbai
  (MoES/MCGM flood early-warning system).
- Why unavailable: MCGM operates this data internally (via its GIS portal and iFLOWS-Mumbai) but does
  not expose a public open-data download of drain geometry or hydraulic attributes.
- Recommended fallback: OSM `waterway=drain` tags (sparse) + DEM-derived synthetic drainage network
  from the downstream pipeline, clearly labeled as derived/assumed.
- Affects: **Physics** (hydraulic routing model has no real network to route through) and
  **Validation** (can't check modeled flows against real infrastructure capacity).
- To actually get this: a formal data request to MCGM's Disaster Management Department / Hydraulic
  Engineer's Department would likely be required.

## 2. CartoDEM / India-specific DEM
**Status: NOT VERIFIED (requires interactive Bhuvan account)**
- ISRO Bhuvan (bhuvan.nrsc.gov.in) offers a free account and DEM download tools, but completing
  registration and confirming exact tile coverage/terms requires an interactive session this research
  pass could not complete.
- Affects: **Physics** only marginally — Copernicus GLO-30 (verified, P0) is the primary DEM and is
  sufficient on its own; CartoDEM was a "secondary, if accessible" request.

## 3. IMD sub-daily gauge data (Santacruz, Colaba stations) and BMC AWS network
**Status: NOT PUBLICLY AVAILABLE as a bulk, machine-readable download**
- Sources checked: IMD public site, data.gov.in, Maharashtra disaster management portals.
- Why unavailable: IMD's freely open offerings are generally daily/monthly/district-level; sub-daily
  station archives typically require a formal (sometimes paid) request to IMD Pune. The BMC AWS
  network (referenced in academic literature as the true 15-min source used for Mumbai flood studies)
  has no public download portal that could be located.
- Fallback in this package: Open-Meteo ERA5/ERA5-Land reanalysis (hourly, ~9-25km grid) and GPM IMERG
  (30-min/daily, ~11km grid) — both weaker than true gauge data for capturing convective extremes.
- Affects: **Validation** most significantly — model calibration against the 26 July 2005 benchmark
  event will be working from secondary-reported station totals (Santacruz ~944mm/24hr) rather than a
  primary sub-daily time series.

## 4. MOSDAC products (exact IDs, resolutions, sample downloads)
**Status: Access method fully documented; actual data NOT pulled (needs the user's own login)**
- MOSDAC's Data Download API requires account credentials in a local config file. The user stated
  they already have access; a ready-to-run script (`scripts/download_mosdac.py`) and the product
  investigation notes (`13_api_information/mosdac.md`) are provided for them to complete locally.
- Affects: **ML** (MOSDAC's satellite rainfall products could supplement IMERG/ERA5 as training
  features) — not blocking since IMERG/ERA5 fallbacks exist.

## 5. Emergency / flood shelters (structured list with coordinates)
**Status: NOT PUBLICLY AVAILABLE**
- Sources checked: MCGM Disaster Management advisories (PDF/news format only, not structured data),
  data.gov.in, OpenStreetMap shelter tags (sparse), NDMA portals.
- Affects: **UI** (a shelter-finder feature would have no real data to display).
- No coordinates were invented for any address-only mention found in passing.

## 6. Historical Mumbai flood point/polygon observations beyond the two national catalogues
**Status: Partially available (via India Flood Inventory v3 + NDEM 1998-2022, both national, need
Mumbai filtering) — a Mumbai-specific, higher-precision dataset (individual waterlogging points,
road-closure records, per-event water depths) was NOT found as open, structured, downloadable data.**
- The Maharashtra Government Fact Finding Committee report (2006) on the 2005 floods contains
  inundation-extent figures, but as embedded images in a PDF, not machine-readable GIS.
- Affects: **Validation** — coarser than ideal for point-level nowcasting validation.

## 7. Tide gauge historical time series (beyond live INCOIS predictions)
**Status: NOT VERIFIED as freely bulk-downloadable**
- INCOIS publishes tide *predictions* via a portal (documented as a live/API source per the task's
  file-vs-API rule); a historical *observed* tide gauge archive for Mumbai was not confirmed as openly
  downloadable in this session — would likely require a request to INCOIS or Survey of India.
- Affects: **Physics** (compound flood modeling — storm surge/high-tide coincidence, as happened on
  26 July 2005) and **Validation**.

## 8. Gridded (sub-ward) population
**Status: Documented, not downloaded — ward-level Census 2011 data (verified, scripted) was judged
sufficient per task instructions ("do not make this a blocker if only ward-level data is available").**
WorldPop's ~100m gridded product is documented in `09_population/metadata.json` as an optional
enhancement for anyone who wants finer spatial resolution.
