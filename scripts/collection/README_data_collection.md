# Battery Storage Arbitrage — Data Collection & Panel

## Contents

| File | Description |
|---|---|
| `collect_data.py` | Data collection script (ENTSO-E, OTE, ČEPS, ERA5) |
| `build_panel.py` | Merges all sources into a single hourly panel CSV |
| `requirements.txt` | Python dependencies |
| `.env.example` | Template for API keys |
| `data/ote/` | OTE Czech day-ahead market prices (hourly, 2020–2024) |
| `data/entsoe/` | ENTSO-E: CZ/DE day-ahead prices, load, generation, imbalance |
| `data/ceps/` | ČEPS: imbalance prices, crossborder flows, load, generation, RES |
| `data/era5/` | ERA5 reanalysis: wind speed, temperature, solar radiation (CZ) |
| `data/topic1_panel.csv` | **Merged hourly panel — 43,848 rows × 51 columns** |
| `data/DATA_LEGEND.md` | Full documentation of all variables, units, sources |

## Replication of data collection

```bash
pip install -r requirements.txt
cp .env.example .env        # fill in ENTSOE_API_KEY and CDS_API_KEY
python collect_data.py      # downloads all data (~30 min first run)
python build_panel.py       # builds the merged panel CSV
```

## API Keys Required

| Service | Purpose | How to obtain |
|---|---|---|
| ENTSO-E Transparency Platform | CZ/DE electricity market data | Register at transparency.entsoe.eu, email transparency@entsoe.eu |
| Copernicus CDS | ERA5 reanalysis weather data | Register at cds.climate.copernicus.eu |

## Panel Variables (51 columns)

- **Prices:** OTE CZ DA price, ENTSO-E CZ/DE DA prices, ČEPS imbalance price
- **Load & flows:** ČEPS system load, 6 cross-border flow pairs (CZ↔DE, AT, PL, SK)
- **Generation mix:** ENTSO-E + ČEPS breakdown by technology (nuclear, coal, gas, solar, wind…)
- **Weather:** ERA5 100m wind speed, 2m temperature, surface solar radiation, pressure
