# MOSDAC (Meteorological & Oceanographic Satellite Data Archival Centre, ISRO)

The user stated they already have MOSDAC access (registered account). The following is what could be
verified from MOSDAC's public documentation in this session WITHOUT logging in on the user's behalf
(credentials were not requested or used, per policy).

## Relevant open/rainfall-nowcasting products identified
| Product name | Description | Relevance |
|---|---|---|
| GSMaP-ISRO Rain | Global Satellite Mapping of Precipitation, ISRO-adapted | Near-real-time rainfall estimate, useful for nowcasting validation |
| Bayesian-based MT-SAPHIR rainfall | Microwave-derived rainfall (Megha-Tropiques SAPHIR sensor) | Rainfall estimate over tropics incl. India |
| 3D Volumetric TERLS DWR product | Doppler Weather Radar (Thumba) volumetric data | Radar reflectivity/rainfall - check spatial coverage includes Mumbai (TERLS is in Kerala; Mumbai may be better served by IMD's Mumbai/Colaba DWR, not confirmed on MOSDAC) |
| Soil Moisture | Land product | Useful for infiltration/runoff modeling context |
| Inland Water Height / River Discharge | Land hydrology products | Potentially useful for the Mithi river / creeks around Mumbai |

**Exact product IDs, spatial/temporal resolution figures, and API endpoints require being logged in**
to the MOSDAC "Order Data" / "API based Access" / "Open Data" sections
(https://mosdac.gov.in - see the top navigation: Data Access > Order Data / API based Access / Open Data)
to view the full product catalogue with resolution and coverage specs. This was not verifiable without
the user's own credentials.

## Authentication method
- Free account required: sign up at https://mosdac.gov.in/signup/
- Approval is manual (email notification once approved) - per https://www.mosdac.gov.in/how-be-registered-user-mosdac
- The MOSDAC Data Download API authenticates via a `config.json` file containing `user_credentials`
  (username/password) - see https://www.mosdac.gov.in/user-manual-mosdac-data-download-api
- **3 incorrect login attempts locks the account for 1 hour** - be careful with credential scripts.

## What this package provides
`scripts/download_mosdac.py` is a template script following MOSDAC's documented Data Download API
pattern (config.json with user_credentials + search_parameters), ready for the user to fill in their
own MOSDAC username/password and run locally. This session does not have and did not request those
credentials.

## Example config.json structure (per MOSDAC's own user manual, fields to fill in)
```json
{
  "user_credentials": {
    "username": "YOUR_MOSDAC_USERNAME",
    "password": "YOUR_MOSDAC_PASSWORD"
  },
  "search_parameters": {
    "product": "FILL_IN_EXACT_PRODUCT_NAME_FROM_PORTAL",
    "start_date": "2015-01-01",
    "end_date": "2025-12-31",
    "bbox": [72.75, 18.85, 72.98, 19.30]
  }
}
```
