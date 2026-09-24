# Mumbai Rain Gauge Networks & Government Portals

## 1. Network Overview
Mumbai has one of the densest urban rain gauge networks in South Asia, divided across three primary agencies:

1. **India Meteorological Department (IMD)**:
   - Primary Synoptic Observatories:
     * **IMD Santacruz** (Suburban Mumbai, Station Index 43003, 19.1172°N, 72.8561°E)
     * **IMD Colaba** (Island City, Station Index 43057, 18.8987°N, 72.8094°E)
   - Secondary AWS Network: 15+ automated weather stations located at Vidyavihar, Borivali, Bhandup, Powai, Byculla, Juhu, and Mahalaxmi.
   - Portal: `https://mahaveer.imd.gov.in/` and Regional Met Centre Mumbai (`http://www.imdmumbai.gov.in/`).
2. **Brihanmumbai Municipal Corporation (BMC / MCGM) Disaster Management Network**:
   - Total Stations: 60 Automatic Weather Stations (AWS) distributed across all 24 administrative wards (average density: 1 station per 7 sq km).
   - Sensor Type: Automated tipping bucket rain gauges calibrated to 0.5 mm resolution.
   - Reporting Frequency: **15 minutes**.
   - Transmission: Cellular GPRS telemetry to the Central Emergency Operations Centre (EOC) at BMC Headquarters, Fort.
   - Public Dashboard: `https://dm.mcgm.gov.in/` (live monsoon rainfall tab).
3. **MahaVedh (Government of Maharashtra Agriculture AWS Portal)**:
   - Covers peri-urban fringe: Thane, Mira-Bhayandar, Navi Mumbai, Kalyan, Panvel.
   - Portal: `https://mahaveh.maharashtra.gov.in/`.

## 2. API Integration & Real-Time Scraping Standards
- BMC provides a JSON telemetry endpoint consumed by the municipal mobile app ("Disaster Management MCGM"):
  - Endpoint: `https://dm.mcgm.gov.in/api/v1/rainfall/realtime`
  - Frequency: Refreshed every 15 minutes.
  - Schema:
    ```json
    {
      "station_id": "AWS_KE_01",
      "ward": "K/East",
      "location": "Andheri East Ward Office",
      "timestamp_ist": "2026-07-15 14:15:00",
      "rainfall_last_15min_mm": 18.5,
      "rainfall_last_1hr_mm": 52.0,
      "rainfall_cumulative_24hr_mm": 142.5
    }
    ```
