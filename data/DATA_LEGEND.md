# Data Legend — Battery Arbitrage Thesis

All data covers the Czech Republic for the period **2020-01-01 → 2024-12-31** (5 years, hourly resolution unless noted).

---

## 1. OTE — Day-ahead Market Prices

| Property | Value |
|---|---|
| **File** | `data/ote/cz_dam_ote.csv` |
| **Source** | OTE, a.s. (Czech electricity market operator) |
| **URL** | https://www.ote-cr.cz |
| **Download method** | Daily XLS reports, URL pattern: `/pubweb/attachments/01/{year}/month{MM}/day{DD}/DT_{DD}_{MM}_{YYYY}_CZ.xls` |
| **Time span** | 2020-01-01 00:00 → 2024-12-31 23:00 |
| **Resolution** | 1 hour |
| **Rows** | 43,843 |
| **Missing** | 5 hours (DST spring-forward transitions — no market hour exists) |
| **Index** | `datetime` — naive **CET/CEST local time** (not tz-aware). `build_panel.py` localizes it to Europe/Prague and converts to UTC when building the panel; DST fall-back duplicate hours are dropped as ambiguous. |

### Columns

| Column | Unit | Description | Range |
|---|---|---|---|
| `price_eur_mwh` | EUR/MWh | Day-ahead clearing price on the Czech DAM | −138.8 to +871.0, mean 113.5 |
| `volume_mwh` | MWh | Total traded volume in that hour | 762.6 to 5,447.8, mean 2,799 |

**Notes:**
- Negative prices occur during periods of excess renewable generation.
- The 871 EUR/MWh peak corresponds to the 2021/2022 energy crisis.
- OTE restructured their XLS format in mid-2024 (data table moved further down the sheet); the parser handles both formats automatically.

---

## 2. ČEPS — Imbalance Price

| Property | Value |
|---|---|
| **File** | `data/ceps/cz_imbalance_price.csv` |
| **Source** | ČEPS, a.s. (Czech transmission system operator) |
| **URL** | https://www.ceps.cz/en/all-data → endpoint `/downloads/graph` |
| **Download method** | GET request: `method=OdhadovanaCenaOdchylky&format=csv&agregation=QH` |
| **Time span** | 2020-01-01 00:00 → 2025-01-01 00:45 |
| **Resolution** | 15 minutes |
| **Rows** | 57,059 |

### Columns

| Column | Unit | Description | Range |
|---|---|---|---|
| `Odhadovaná cena [Kč/MWh]` | CZK/MWh | Estimated imbalance settlement price (positive = shortage, negative = surplus) | −664,968 to +213,623, mean 2,070 |

**Notes:**
- Extreme outliers (±100,000+ CZK/MWh) correspond to severe grid imbalance events.
- 15-minute resolution matches Czech imbalance settlement intervals.
- To convert to EUR/MWh, divide by the EUR/CZK exchange rate (~25 CZK/EUR).

---

## 3. ČEPS — Cross-border Physical Flows

| Property | Value |
|---|---|
| **File** | `data/ceps/cz_crossborder_flows.csv` |
| **Source** | ČEPS, a.s. |
| **URL** | https://www.ceps.cz/en/all-data → `/downloads/graph` |
| **Download method** | GET request: `method=CrossborderPowerFlows&format=csv&agregation=HR` |
| **Time span** | 2020-01-01 00:00 → 2025-01-01 00:00 |
| **Resolution** | 1 hour |
| **Rows** | 43,844 |

### Columns

Sign convention: **positive = export from CZ**, negative = import to CZ.

| Column | Unit | Counterpart TSO | Description |
|---|---|---|---|
| `PSE Skutečnost [MW]` | MW | PSE (Poland) | Actual physical flow CZ ↔ PL |
| `PSE Plán [MW]` | MW | PSE (Poland) | Planned/scheduled flow CZ ↔ PL |
| `SEPS Skutečnost [MW]` | MW | SEPS (Slovakia) | Actual physical flow CZ ↔ SK |
| `SEPS Plán [MW]` | MW | SEPS (Slovakia) | Planned flow CZ ↔ SK |
| `APG Skutečnost [MW]` | MW | APG (Austria) | Actual physical flow CZ ↔ AT |
| `APG Plán [MW]` | MW | APG (Austria) | Planned flow CZ ↔ AT |
| `TenneT Skutečnost [MW]` | MW | TenneT (Germany) | Actual physical flow CZ ↔ DE (TenneT zone) |
| `TenneT Plán [MW]` | MW | TenneT (Germany) | Planned flow CZ ↔ DE (TenneT) |
| `50HzT Skutečnost [MW]` | MW | 50Hertz (Germany) | Actual physical flow CZ ↔ DE (50Hertz zone) |
| `50HzT Plán [MW]` | MW | 50Hertz (Germany) | Planned flow CZ ↔ DE (50Hertz) |
| `CEPS Skutečnost [MW]` | MW | ČEPS total | Net cross-border balance of Czech grid |
| `CEPS Plán [MW]` | MW | ČEPS total | Planned net cross-border balance |

---

## 4. ČEPS — System Load

| Property | Value |
|---|---|
| **File** | `data/ceps/cz_load.csv` |
| **Source** | ČEPS, a.s. |
| **Download method** | GET request: `method=Load&format=csv&agregation=HR` |
| **Time span** | 2020-01-01 00:00 → 2025-01-01 00:00 |
| **Resolution** | 1 hour |
| **Rows** | 43,844 |

### Columns

| Column | Unit | Description | Range |
|---|---|---|---|
| `Zatížení s čerpáním [MW]` | MW | Total system load **including** pumped-storage consumption | 4,224 to 12,133, mean 8,014 |
| `Zatížení [MW]` | MW | Net system load **excluding** pumped-storage consumption | 4,224 to 12,133, mean 7,854 |

**Notes:**
- "Zatížení" = load in Czech.
- The difference between the two columns reveals pumped-storage hydro activity.

---

## 5. ČEPS — Generation Mix

| Property | Value |
|---|---|
| **File** | `data/ceps/cz_generation_mix.csv` |
| **Source** | ČEPS, a.s. |
| **Download method** | GET request: `method=Generation&format=csv&agregation=HR` (yearly chunks due to server limit) |
| **Time span** | 2020-01-01 00:00 → 2025-01-01 00:00 |
| **Resolution** | 1 hour |
| **Rows** | 43,844 |

### Columns

| Column | Unit | Description | Range |
|---|---|---|---|
| `PE [MW]` | MW | Thermal power plants (coal, gas, oil) | 734 to 7,165, mean 4,009 |
| `PPE [MW]` | MW | Industrial co-generation (heat & power) | 0 to 1,453, mean 459 |
| `JE [MW]` | MW | Nuclear power plants (Dukovany + Temelín) | 1,171 to 4,221, mean 3,462 |
| `VE [MW]` | MW | Run-of-river hydro | −20 to 800, mean 225 |
| `PVE [MW]` | MW | Pumped-storage hydro (positive = generating, negative = pumping) | −52 to 1,068, mean 129 |
| `AE [MW]` | MW | Other / auxiliary generation | 156 to 386, mean 242 |
| `ZE [MW]` | MW | Storage / other (currently zero in data) | 0 |
| `VTE [MW]` | MW | Wind turbines | 0 to 295, mean 74 |
| `FVE [MW]` | MW | Photovoltaic (solar) | 0 to 3,182, mean 308 |

**Notes:**
- Czech abbreviations: PE = parní elektrárna (thermal), JE = jaderná elektrárna (nuclear), VE = vodní elektrárna (hydro), PVE = přečerpávací vodní elektrárna (pumped-storage), VTE = větrná turbína (wind), FVE = fotovoltaická elektrárna (solar).
- Nuclear (JE) is the largest and most stable source, running near 4,000 MW baseload.

---

## 6. ČEPS — Renewable Generation

| Property | Value |
|---|---|
| **File** | `data/ceps/cz_renewable_generation.csv` |
| **Source** | ČEPS, a.s. |
| **Download method** | GET request: `method=GenerationRES&format=csv&agregation=HR` |
| **Time span** | 2020-01-01 00:00 → 2025-01-01 00:00 |
| **Resolution** | 1 hour |
| **Rows** | 43,844 |

### Columns

| Column | Unit | Description | Range |
|---|---|---|---|
| `VTE [MW]` | MW | Wind power generation (all Czech turbines) | 0 to 295, mean 74 |
| `FVE [MW]` | MW | Solar PV generation (all Czech panels) | 0 to 3,182, mean 308 |

**Notes:**
- These are the same values as in `cz_generation_mix.csv` but provided as a standalone dataset.
- Czech installed capacity is small for wind (~335 MW) but larger for solar (~3,500 MW).
- Solar output naturally follows daily and seasonal cycles (zero at night).

---

## 7. ERA5 — Weather Reanalysis

| Property | Value |
|---|---|
| **Files** | `data/era5/era5_cz_{YYYY}_{MM}.nc` (one ZIP archive per month, 60 total) |
| **Source** | Copernicus Climate Data Store (CDS), ECMWF |
| **Dataset** | `reanalysis-era5-single-levels` |
| **URL** | https://cds.climate.copernicus.eu |
| **Access** | Free account required; Personal Access Token in `.env` as `CDS_API_KEY` |
| **Time span** | 2020-01-01 00:00 UTC → 2024-12-31 23:00 UTC |
| **Resolution** | 1 hour (temporal), 0.25° × 0.25° (spatial) |
| **Spatial extent** | 48°N – 52°N, 12°E – 19°E (bounding box covering Czech Republic) |
| **Grid** | 17 latitude × 29 longitude = 493 grid points |
| **Format** | ZIP archive containing two NetCDF4 files per month |

### Inner files (per monthly ZIP)

| Inner file | Variables | Step type |
|---|---|---|
| `data_stream-oper_stepType-instant.nc` | u100, v100, t2m | Instantaneous (valid at each hour) |
| `data_stream-oper_stepType-accum.nc` | ssrd | Accumulated (sum over the preceding hour) |

### Variables

| Variable | Unit | Description | Approx. range (CZ) |
|---|---|---|---|
| `u100` | m/s | U-component (eastward) of wind at 100 m above ground | −15 to +15 m/s |
| `v100` | m/s | V-component (northward) of wind at 100 m above ground | −15 to +15 m/s |
| `t2m` | K (Kelvin) | Air temperature at 2 m above ground. Subtract 273.15 for °C | ~260–310 K (−13 to +37 °C) |
| `ssrd` | J/m² | Surface solar radiation downwards, accumulated over 1 hour. Divide by 3600 for W/m² | 0 to ~1,400,000 J/m² (i.e. 0–389 W/m²) |
| `wind_speed_100m` *(derived)* | m/s | Horizontal wind speed at 100 m: √(u100² + v100²). Added during CSV conversion | 0 to ~22 m/s |

### Derived CSV files

After running `era5_nc_to_csv()`, one CSV per year is created:

| File | Description |
|---|---|
| `data/era5/era5_cz_{YYYY}.csv` | Spatial mean over all 493 CZ grid points, all 4 variables + `wind_speed_100m` |

**Notes:**
- 100 m wind components are used (not 10 m) because wind turbines operate at hub height (~80–120 m).
- `ssrd` is a forecast accumulated from the analysis time; divide by 3,600 to convert J/m² → W/m² (average power over the hour).
- ERA5 timestamps are in **UTC**; CET = UTC+1, CEST = UTC+2.
- The spatial mean over 493 grid points gives a representative national average.

---

## 8. ENTSO-E — Transparency Platform *(pending API key)*

| Property | Value |
|---|---|
| **Files** | `data/entsoe/` (not yet downloaded) |
| **Source** | ENTSO-E Transparency Platform |
| **URL** | https://transparency.entsoe.eu |
| **Access** | Free account required; Web API Security Token in `.env` as `ENTSOE_API_KEY` |

### Planned datasets

| File | Description | Unit |
|---|---|---|
| `cz_da_prices_entsoe.csv` | Day-ahead prices — cross-check against OTE | EUR/MWh |
| `cz_load_entsoe.csv` | Actual total load | MW |
| `cz_gen_per_type_entsoe.csv` | Actual generation per production type | MW |
| `cz_net_transfer_capacity.csv` | Net Transfer Capacities on CZ borders | MW |
| `cz_scheduled_exchanges.csv` | Scheduled commercial exchanges | MW |

**How to enable:**
1. Register at https://transparency.entsoe.eu (free)
2. Email transparency@entsoe.eu: subject `Restful API access`, body = your registered email
3. After approval (~3 working days): My Account Settings → Web API Security Token → Generate
4. Add to `.env`:  `ENTSOE_API_KEY=your_token_here`
5. Re-run `collect_data.py` — ENTSO-E data will be downloaded automatically

---

## Summary Table

| # | File | Source | Resolution | Rows | Period | Key use |
|---|---|---|---|---|---|---|
| 1 | `ote/cz_dam_ote.csv` | OTE | Hourly | 43,843 | 2020–2024 | DAM price signal for arbitrage |
| 2 | `ceps/cz_imbalance_price.csv` | ČEPS | 15-min | 57,059 | 2020–2024 | Balancing market revenue |
| 3 | `ceps/cz_crossborder_flows.csv` | ČEPS | Hourly | 43,844 | 2020–2024 | Grid congestion indicators |
| 4 | `ceps/cz_load.csv` | ČEPS | Hourly | 43,844 | 2020–2024 | Demand feature for price forecasting |
| 5 | `ceps/cz_generation_mix.csv` | ČEPS | Hourly | 43,844 | 2020–2024 | Supply composition features |
| 6 | `ceps/cz_renewable_generation.csv` | ČEPS | Hourly | 43,844 | 2020–2024 | RES variability features |
| 7 | `era5/era5_cz_*.nc` | Copernicus/ECMWF | Hourly, 0.25° | 60 files | 2020–2024 | Weather inputs for RES forecasting |
| 8 | `entsoe/` *(pending)* | ENTSO-E | Hourly | — | 2020–2024 | Cross-validation & additional features |

---

*Generated: 2026-07-02 | collect_data.py*
