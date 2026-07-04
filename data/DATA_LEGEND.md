# Data Legend — Czech Electricity Market Hourly Panel

Variable-level documentation for the merged dataset of the Czech power market and
associated weather, covering **2020-01-01 → 2024-12-31** at **hourly resolution**.

The repository ships a single compiled artifact:

| File | Rows | Columns | Index |
|---|---|---|---|
| `cz_power_panel.csv` | 43,848 | 51 | `datetime` — **naive UTC**, hourly, continuous (no gaps) |

The raw per-source files (`ote/`, `entsoe/`, `ceps/`, `era5/`) are *not* shipped;
they are re-created locally by `scripts/collection/collect_data.py` and merged into
the panel by `scripts/collection/build_panel.py`. Sections 1–5 below document the
compiled panel column by column; Section 6 documents the upstream sources and how
they are integrated; Section 7 documents the processing pipeline; Section 8 collects
conventions, caveats and known issues.

---

## Conventions

| Aspect | Convention |
|---|---|
| **Time index** | Naive `datetime` interpreted as **UTC**. Local Czech time is CET (UTC+1) / CEST (UTC+2). |
| **Resolution** | Hourly. Sources delivered at 15-minute resolution are aggregated to hourly means (see §7). |
| **Coverage** | 2020-01-01 00:00 → 2024-12-31 23:00 UTC, a continuous 43,848-hour index. |
| **Currency** | Prices in EUR/MWh, except the ČEPS imbalance price which is native CZK/MWh. |
| **Power units** | MW (average power over the hour). |
| **Cross-border sign** | **Positive = export from CZ**, negative = import to CZ. |
| **Missing values** | Empty cells. Missing shares per column are listed in the tables below; all are < 1 %. |
| **Column names** | `source_category_detail` in snake_case; original Czech generation labels are kept as suffixes (e.g. `_fve_mw`) and translated in the notes. |

---

## 1. Prices

| Column | Unit | Source | Missing | Min | Max | Mean | Description |
|---|---|---|---|---|---|---|---|
| `ote_price_eur_mwh` | EUR/MWh | OTE | 0.04 % | −138.75 | 871.00 | 113.48 | Czech day-ahead market (DAM) clearing price. |
| `volume_mwh` | MWh | OTE | 0.04 % | 762.60 | 5,447.80 | 2,798.62 | Total traded volume on the Czech DAM in that hour. |
| `entsoe_cz_da_eur_mwh` | EUR/MWh | ENTSO-E | 0.00 % | −138.75 | 871.00 | 113.46 | Czech day-ahead price from ENTSO-E — an independent cross-check of the OTE series. |
| `entsoe_de_da_eur_mwh` | EUR/MWh | ENTSO-E | 0.00 % | −500.00 | 936.28 | 107.23 | German (DE-LU) day-ahead price — the dominant price-coupling driver for CZ. |
| `ceps_imbalance_odhadovaná_cena_kč_mwh` | CZK/MWh | ČEPS | 0.08 % | −664,968 | 213,623 | 2,084.23 | Estimated imbalance settlement price (positive = system short, negative = system long). |

**Notes**
- The OTE and ENTSO-E Czech day-ahead series are near-identical (same underlying market coupling); the tiny difference in missing share reflects OTE's few DST/report gaps that ENTSO-E fills. Keep both for validation, use one for modelling.
- Negative day-ahead prices occur in hours of high renewable infeed and low demand; the 871 EUR/MWh maximum is the 2021–2022 energy-crisis peak.
- The imbalance price is extremely heavy-tailed; the ±100,000+ CZK/MWh extremes are genuine scarcity/surplus settlement events, not parsing errors. Divide by the EUR/CZK rate (~25) for a rough EUR conversion.

---

## 2. Load

| Column | Unit | Source | Missing | Min | Max | Mean | Description |
|---|---|---|---|---|---|---|---|
| `entsoe_load_Actual Load` | MW | ENTSO-E | 0.00 % | 3,849.61 | 11,281.13 | 7,234.23 | Actual total Czech system load (ENTSO-E metered). |
| `ceps_load_zatížení_s_čerpáním_mw` | MW | ČEPS | 0.02 % | 4,224.17 | 12,132.82 | 8,014.62 | Total system load **including** pumped-storage pumping consumption. |
| `ceps_load_zatížení_mw` | MW | ČEPS | 0.02 % | 4,224.17 | 12,132.82 | 7,854.57 | Net system load **excluding** pumped-storage pumping. |

**Notes**
- The column name `entsoe_load_Actual Load` retains ENTSO-E's original label (note the space and capitals); it is kept verbatim so the panel matches the raw download.
- The two ČEPS load columns differ only by pumped-storage pumping; their gap is a proxy for pump-mode activity.
- The ENTSO-E and ČEPS load levels differ by definition and metering boundary (ENTSO-E "Actual Load" vs ČEPS "Zatížení"); both are provided rather than reconciled.

---

## 3. Generation

Two independent breakdowns of Czech generation are provided: the ENTSO-E
production-type series (international, harmonised labels) and the ČEPS technology
series (national operator, Czech labels). They cover the same physical fleet with
minor definitional differences.

### 3a. ENTSO-E generation per production type (MW, 0.00 % missing)

| Column | Min | Max | Mean | Description |
|---|---|---|---|---|
| `entsoe_gen_nuclear` | 1,106.94 | 3,988.59 | 3,272.28 | Nuclear (Dukovany + Temelín) — near-baseload. |
| `entsoe_gen_fossil_brown_coal_lignite` | 446.48 | 5,403.88 | 3,031.18 | Lignite/brown-coal thermal — the largest fossil block. |
| `entsoe_gen_fossil_hard_coal` | 0.00 | 917.40 | 213.09 | Hard-coal thermal. |
| `entsoe_gen_fossil_gas` | 70.31 | 1,515.25 | 535.74 | Natural-gas generation. |
| `entsoe_gen_fossil_coal-derived_gas` | 0.00 | 389.71 | 107.78 | Coal-derived gas (blast-furnace/coke-oven gas). |
| `entsoe_gen_fossil_oil` | 0.00 | 67.41 | 5.90 | Oil-fired generation (marginal). |
| `entsoe_gen_solar` | 0.00 | 2,680.32 | 305.59 | Solar PV. |
| `entsoe_gen_wind_onshore` | 1.26 | 295.55 | 76.23 | Onshore wind. |
| `entsoe_gen_hydro_run-of-river_and_poundage` | 0.00 | 288.20 | 121.93 | Run-of-river hydro. |
| `entsoe_gen_hydro_water_reservoir` | 0.00 | 784.32 | 139.92 | Reservoir hydro. |
| `entsoe_gen_hydro_pumped_storage` | 0.00 | 1,089.83 | 123.69 | Pumped-storage generation (turbining only). |
| `entsoe_gen_biomass` | 57.10 | 373.58 | 266.77 | Biomass. |
| `entsoe_gen_waste` | 6.56 | 37.74 | 22.73 | Waste incineration. |
| `entsoe_gen_other_renewable` | 211.43 | 309.44 | 270.28 | Other renewable. |
| `entsoe_gen_other` | 0.00 | 138.17 | 54.95 | Other/unclassified generation. |

### 3b. ČEPS generation mix (MW, 0.02 % missing)

| Column | Czech term | Min | Max | Mean | Description |
|---|---|---|---|---|---|
| `ceps_gen_je_mw` | jaderná elektrárna | 1,170.70 | 4,221.10 | 3,461.90 | Nuclear. |
| `ceps_gen_pe_mw` | parní elektrárna | 733.80 | 7,164.60 | 4,009.18 | Thermal (coal/gas/oil steam plants). |
| `ceps_gen_ppe_mw` | paroplynová/průmyslová | −0.10 | 1,452.70 | 459.16 | Combined-cycle / industrial co-generation. |
| `ceps_gen_ve_mw` | vodní elektrárna | −19.80 | 800.10 | 225.12 | Run-of-river hydro. |
| `ceps_gen_pve_mw` | přečerpávací VE | −51.60 | 1,067.90 | 128.55 | Pumped-storage (positive = generating, negative = pumping). |
| `ceps_gen_ae_mw` | alternativní | 156.00 | 386.00 | 242.50 | Alternative/auxiliary generation. |
| `ceps_gen_ze_mw` | — | 0.00 | 0.00 | 0.00 | Reserved column — zero throughout the sample. |
| `ceps_gen_vte_mw` | větrná turbína | 0.00 | 295.00 | 73.97 | Wind. |
| `ceps_gen_fve_mw` | fotovoltaická el. | 0.00 | 3,181.80 | 308.25 | Solar PV. |

### 3c. ČEPS renewable-only series (MW, 0.02 % missing)

| Column | Min | Max | Mean | Description |
|---|---|---|---|---|
| `ceps_res_vte_mw` | 0.00 | 295.00 | 73.97 | Wind — standalone RES feed (duplicates `ceps_gen_vte_mw`). |
| `ceps_res_fve_mw` | 0.00 | 3,181.80 | 308.29 | Solar PV — standalone RES feed (duplicates `ceps_gen_fve_mw`). |

**Notes**
- `ceps_res_*` columns are the same physical quantities as the corresponding `ceps_gen_*` columns, delivered by ČEPS as a separate renewable-only dataset; kept for traceability. Use one to avoid double counting.
- Small negative minima in ČEPS hydro columns are genuine (auxiliary consumption / metering), not errors.
- `ceps_gen_ze_mw` is identically zero over 2020–2024; kept to preserve the raw schema.
- ENTSO-E and ČEPS solar peaks differ (~2,680 vs ~3,182 MW) because of differing metering scope and estimation methods for distributed PV — this is an expected source discrepancy, not an inconsistency.

---

## 4. Cross-border physical flows (ČEPS)

All in MW, sign convention **positive = export from CZ**. Two variants per border:
`skutečnost` = actual metered flow, `plán` = scheduled/planned flow.

| Column | Counterpart TSO | Missing | Min | Max | Mean |
|---|---|---|---|---|---|
| `ceps_xborder_pse_skutečnost_mw` | PSE (Poland) | 0.02 % | −1,519.08 | 2,326.07 | 644.33 |
| `ceps_xborder_pse_plán_mw` | PSE (Poland) | 0.62 % | −1,714.00 | 1,572.00 | −94.27 |
| `ceps_xborder_seps_skutečnost_mw` | SEPS (Slovakia) | 0.02 % | −2,814.84 | 1,955.25 | −973.33 |
| `ceps_xborder_seps_plán_mw` | SEPS (Slovakia) | 0.62 % | −2,200.10 | 1,316.60 | −787.26 |
| `ceps_xborder_apg_skutečnost_mw` | APG (Austria) | 0.02 % | −3,069.08 | 1,025.17 | −1,032.54 |
| `ceps_xborder_apg_plán_mw` | APG (Austria) | 0.62 % | −2,920.80 | 1,563.50 | −474.44 |
| `ceps_xborder_tennet_skutečnost_mw` | TenneT (DE) | 0.02 % | −2,251.55 | 1,513.92 | −491.12 |
| `ceps_xborder_tennet_plán_mw` | TenneT (DE) | 0.62 % | −1,750.00 | 1,750.00 | 119.69 |
| `ceps_xborder_50hzt_skutečnost_mw` | 50Hertz (DE) | 0.02 % | −1,994.11 | 2,199.46 | 687.81 |
| `ceps_xborder_50hzt_plán_mw` | 50Hertz (DE) | 0.62 % | −2,502.80 | 2,093.00 | 70.14 |
| `ceps_xborder_ceps_skutečnost_mw` | ČEPS total | 0.02 % | −4,818.13 | 3,293.74 | −1,164.85 |
| `ceps_xborder_ceps_plán_mw` | ČEPS total | 0.62 % | −4,843.60 | 3,115.70 | −1,166.18 |

**Notes**
- Germany is split across its two bordering control zones (TenneT and 50Hertz); sum them for a total CZ↔DE flow.
- The `ceps_xborder_ceps_*` columns are the net cross-border balance of the Czech grid and equal the sum of the individual borders. Interpret the sign strictly per the documented convention (positive = export from CZ) rather than against external expectations, since the metered physical-flow balance can differ from the commercial trade balance.
- `plán` (scheduled) columns have a slightly higher missing share (0.62 %) than `skutečnost` (actual, 0.02 %) because schedules are occasionally not published.

---

## 5. Weather (ERA5 reanalysis)

Spatial mean over the Czech bounding box (48–52°N, 12–19°E; 493 grid points at
0.25°). All 0.00 % missing.

| Column | Unit | Min | Max | Mean | Description |
|---|---|---|---|---|---|
| `era5_u100` | m/s | −8.46 | 15.62 | 1.52 | Eastward wind component at 100 m. |
| `era5_v100` | m/s | −10.61 | 11.84 | 0.49 | Northward wind component at 100 m. |
| `era5_wind_speed_100m` | m/s | 0.02 | 15.81 | 4.58 | Derived horizontal wind speed at 100 m: √(u100² + v100²). |
| `era5_t2m` | K | 260.51 | 307.13 | 283.34 | Air temperature at 2 m (subtract 273.15 for °C: ≈ −12.6 to +34.0 °C). |
| `era5_ssrd` | J/m² | 0.00 | 3,139,383.50 | 482,593.96 | Surface solar radiation downwards, accumulated over the hour (÷3,600 for W/m²). |

**Notes**
- 100 m (not 10 m) wind is used because turbine hub heights are ~80–120 m.
- `ssrd` is an hourly accumulation; divide by 3,600 to obtain average W/m² over the hour (mean ≈ 134 W/m², peak ≈ 872 W/m²).
- ERA5 timestamps are natively UTC, so no timezone conversion is applied to these columns.

---

## 6. Upstream sources & access

| # | Source | Provider | Access | Native resolution | Feeds panel columns |
|---|---|---|---|---|---|
| 1 | Day-ahead prices & volume | **OTE, a.s.** (CZ market operator) | Public daily XLS reports (`ote-cr.cz`) | Hourly | `ote_price_eur_mwh`, `volume_mwh` |
| 2 | Prices, load, generation, imbalance | **ENTSO-E Transparency Platform** | REST API (free token; `ENTSOE_API_KEY`) | Hourly / 15-min | all `entsoe_*` columns |
| 3 | Imbalance, cross-border flows, load, generation, RES | **ČEPS, a.s.** (CZ TSO) | Public data portal (`ceps.cz/en/all-data`) | Hourly / 15-min | all `ceps_*` columns |
| 4 | Weather reanalysis | **Copernicus CDS / ECMWF (ERA5)** | CDS API (free token; `CDS_API_KEY`) | Hourly, 0.25° | all `era5_*` columns |

**ENTSO-E integration status:** fully integrated. The ENTSO-E datasets (Czech and
German day-ahead prices, actual load, actual generation per production type, and
imbalance) are downloaded via the REST API and merged into the panel — the 18
`entsoe_*` columns above are all populated with 0 % missing over 2020–2024. The
German day-ahead price and the ENTSO-E generation-per-type breakdown come
exclusively from this source.

**Obtaining the ENTSO-E token:** register at `transparency.entsoe.eu`, then email
`transparency@entsoe.eu` (subject "Restful API access", body = your registered
email); after approval, generate the token under *My Account → Web API Security
Token* and set `ENTSOE_API_KEY` in `.env`.

---

## 7. Processing pipeline (`build_panel.py`)

1. **Load** each raw source with an auto-detecting CSV reader.
2. **Timezone harmonisation.** OTE and ČEPS timestamps are naive **local** (Europe/Prague); they are localized to Europe/Prague and converted to UTC. DST spring-forward hours (non-existent) and fall-back duplicate hours (ambiguous) are dropped. ENTSO-E and ERA5 timestamps are already timezone-aware/UTC and converted directly. The final index is **naive UTC**.
3. **Temporal aggregation.** Sources delivered at 15-minute resolution (ČEPS imbalance, cross-border, load, generation; ENTSO-E load/generation where applicable) are aggregated to hourly means.
4. **Outer join** of all sources on the hourly UTC index, then **sort**.
5. **Trim** to the common window 2020-01-01 → 2024-12-31 and drop all-NaN rows.
6. **Reindex** to a continuous hourly index so the panel has no time gaps (43,848 rows); residual per-column gaps remain as missing values (all < 1 %).

**Timezone validation.** After harmonisation, the OTE and ENTSO-E Czech day-ahead
series line up at lag 0 with near-unit correlation and the solar-driven midday
price dip aligns across sources — confirming correct local→UTC alignment.

---

## 8. Caveats & known issues

- **Duplicated information is intentional.** Several quantities appear twice by design (OTE vs ENTSO-E CZ price; ČEPS `gen` vs `res` renewables; ENTSO-E vs ČEPS load and generation). This supports cross-validation; pick a single series per quantity before modelling to avoid double counting.
- **Source discrepancies are expected.** ENTSO-E and ČEPS differ in metering scope, estimation of distributed PV, and load definitions, so their levels do not match exactly. Neither is "corrected" against the other.
- **Heavy tails.** The imbalance price and, to a lesser extent, the day-ahead prices contain genuine extreme values from crisis/scarcity events. Treat outliers as real unless documented otherwise.
- **Missing data.** All columns are < 1 % missing. Scheduled (`plán`) cross-border series and the imbalance price carry the largest gaps; prices and weather are essentially complete.
- **DST handling.** A handful of hours per year are dropped or duplicated at DST transitions before reindexing; this is why raw OTE/ČEPS files have slightly irregular row counts while the merged panel is a clean continuous index.
- **Units to watch.** Imbalance price is CZK/MWh (not EUR); `t2m` is Kelvin; `ssrd` is J/m² accumulated per hour. Convert as noted before comparing across columns.

---

## Summary

| Group | Columns | Source(s) | Notes |
|---|---|---|---|
| Prices | 5 | OTE, ENTSO-E, ČEPS | CZ/DE day-ahead + volume + imbalance |
| Load | 3 | ENTSO-E, ČEPS | actual load + ČEPS load with/without pumping |
| Generation (ENTSO-E) | 15 | ENTSO-E | per production type |
| Generation (ČEPS) | 9 | ČEPS | technology mix (Czech labels) |
| Renewables (ČEPS) | 2 | ČEPS | wind & solar standalone feed |
| Cross-border flows | 12 | ČEPS | 5 borders + total, actual & planned |
| Weather | 5 | ERA5 | 100 m wind, 2 m temperature, solar radiation |
| **Total** | **51** | | 43,848 hourly rows, UTC, 2020–2024 |
