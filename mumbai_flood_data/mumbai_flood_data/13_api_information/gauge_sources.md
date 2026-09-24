# Rain Gauge / Station Data Sources for Mumbai - Investigation Notes

## IMD (India Meteorological Department)
- Official stations relevant to Mumbai: **Santacruz** (representing the suburbs) and **Colaba** (representing the island city)
- These two stations' daily rainfall figures are the ones most commonly cited in the literature for the 26 July 2005 event (Santacruz ~944mm/24hr; Colaba figures reported inconsistently across sources as 73-84mm/24hr - VERIFY against IMD primary data before use)
- **No confirmed free bulk API/CSV download** for sub-daily historical IMD station data was found in this session. IMD's public offerings (https://mausam.imd.gov.in, data.gov.in) tend to be at daily/monthly/district granularity for open access; hourly/15-min AWS data typically requires a formal (sometimes paid) data request to IMD Pune or the National Data Centre.
- data.gov.in does host some IMD rainfall datasets - search https://data.gov.in for "rainfall" + "Maharashtra"/"Mumbai" for the current catalogue, as availability changes.

## BMC / MCGM Automatic Weather Station (AWS) network
- Referenced in academic sources (e.g. https://www.toi.no/getfile.php/1348346-1530708133/Publikasjoner/Flooding%20Mumbai.pdf) as providing 15-minute rainfall data used in flood modeling studies
- No public download portal for this network was located in this session - likely accessible only via a direct request to MCGM's Disaster Management / Hydraulic Engineer's department, or via the iFLOWS-Mumbai system (operational, not an open-data portal)

## Fallback used in this package
Gridded reanalysis (Open-Meteo/ERA5-Land, see open_meteo.md) as an hourly proxy, and GPM IMERG
(see imerg.md) as a satellite-derived proxy. Both are clearly weaker than true station data for
convective-extreme events like 26 July 2005 (reanalysis smooths peak intensities), so this is
flagged in MISSING_DATA.md as a real gap for model calibration/validation.
