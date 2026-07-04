# Data collection & panel construction

Scripts that download the raw public data sources for the Czech electricity market and merge them into a single hourly panel. See `../../data/DATA_LEGEND.md` for the full variable-level documentation.

## Contents

| File / Folder | Description |
|---|---|
| `collect_data.py` | Downloads all raw sources (ENTSO-E, OTE, ČEPS, ERA5) into `data/` |
| `build_panel.py` | Merges all sources into a single timezone-harmonised hourly panel CSV |
| `data/ote/` | OTE Czech day-ahead market prices (hourly) |
| `data/entsoe/` | ENTSO-E: CZ/DE day-ahead prices, actual load, generation per type, imbalance |
| `data/ceps/` | ČEPS: imbalance price, cross-border flows, system load, generation mix, RES |
| `data/era5/` | ERA5 reanalysis: 100 m wind, 2 m temperature, surface solar radiation (CZ) |
| `data/cz_power_panel.csv` | **Merged hourly panel — 43,848 rows × 51 columns, UTC, 2020–2024** |

> Note: only the merged panel (`data/cz_power_panel.csv`) is shipped in the repository. The raw per-source subfolders are recreated locally when you run `collect_data.py`.

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env        # fill in ENTSOE_API_KEY and CDS_API_KEY
python collect_data.py      # downloads all raw data (~30 min on first run)
python build_panel.py       # builds the merged panel CSV
```

## API keys required

| Service | Purpose | How to obtain |
|---|---|---|
| ENTSO-E Transparency Platform | CZ/DE prices, load, generation, imbalance | Register at transparency.entsoe.eu, then email transparency@entsoe.eu to request REST API access |
| Copernicus CDS | ERA5 reanalysis weather data | Register at cds.climate.copernicus.eu and copy the personal access token |

OTE and ČEPS data are downloaded from public endpoints and need no key.

## Panel variables (51 columns)

- **Prices:** OTE CZ day-ahead price, ENTSO-E CZ/DE day-ahead prices, ČEPS imbalance price
- **Load & flows:** ENTSO-E actual load, ČEPS system load, six cross-border flow pairs (CZ↔DE via TenneT & 50Hertz, CZ↔AT, CZ↔PL, CZ↔SK)
- **Generation mix:** ENTSO-E generation per production type and ČEPS technology breakdown (nuclear, lignite, hard coal, gas, solar, wind, hydro, …)
- **Weather:** ERA5 100 m wind components and speed, 2 m temperature, surface solar radiation
