# INCOIS Operational Ocean State and Tidal Information Services

## 1. Overview
The Indian National Centre for Ocean Information Services (INCOIS), an autonomous body under the Ministry of Earth Sciences (MoES), operates the national ocean state forecast and storm surge warning system.

For the Mumbai Urban Flood Nowcasting System, live sea-level boundary conditions at the 11 coastal outfalls are provided by:
1. Astronomical Tidal Predictions (harmonic constituent model).
2. Storm Surge Model (ADCIRC / ROMS driven by NCMRWF numerical weather prediction).
3. Real-time Tide Gauges (Apollo Bunder MbPA and JNPT Nhava Sheva acoustic tide gauges).

## 2. API Endpoints
- **INCOIS Web API Service**: `https://incois.gov.in/portal/osf/`
- **Tide Forecast Data API**: `https://incois.gov.in/tides/TidesService`
- **Parameters**:
  - `port_code`: `BOM` (Mumbai Port / Apollo Bunder) or `JNP` (Jawaharlal Nehru Port)
  - `start_date`: `YYYY-MM-DD`
  - `end_date`: `YYYY-MM-DD`
  - `interval`: `60` (minutes)
  - `format`: `JSON`

## 3. Harmonic Constituent Modeling Formulation
When internet connectivity is disconnected or real-time API latency occurs, the local nowcasting hydrodynamic solver computes the tidal water surface boundary condition $h_{tide}(t)$ (meters above Chart Datum) via the classical harmonic summation:

$$h_{tide}(t) = Z_0 + \sum_{i=1}^{M} f_i A_i \cos\left(\omega_i t + (V_0 + u)_i - \kappa_iight)$$

Where:
- $Z_0 = 2.51\text{ m}$ (Mean Sea Level above Chart Datum at Apollo Bunder)
- $A_i, \kappa_i$: Amplitude and epoch phase for constituent $i$ ($M_2, S_2, N_2, K_1, O_1, M_4$)
- $f_i, (V_0 + u)_i$: Nodal factors and astronomical arguments.
