#!/usr/bin/env python3
"""
collect_data.py
===============
Data collection script for the Czech electricity market dataset.
Downloads and stores the raw sources that feed the merged hourly panel.

Data sources
------------
  1. ENTSO-E Transparency Platform   entsoe-py client   (free API key required)
  2. OTE (Czech market operator)     public XML / Excel downloads
  3. ČEPS (Czech TSO)                public data portal
  4. ERA5 reanalysis weather         Copernicus CDS API  (free API key required)

Quick start
-----------
  pip install -r requirements.txt
  cp .env.example .env          # fill in your API keys
  python collect_data.py

All output is written to ./data/{source}/*.csv  (and .nc for ERA5).
A log file collect_data.log is created in the working directory.
"""

import os
import sys
import time
import logging
import requests
import pandas as pd
import xml.etree.ElementTree as ET
from io import BytesIO
from datetime import date, timedelta
from pathlib import Path
from dotenv import load_dotenv

# ─── Logging ──────────────────────────────────────────────────────────────────
_stream_handler = logging.StreamHandler(sys.stdout)
_stream_handler.stream = open(sys.stdout.fileno(), mode="w", encoding="utf-8", closefd=False, buffering=1)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        _stream_handler,
        logging.FileHandler("collect_data.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# ─── Configuration ─────────────────────────────────────────────────────────────
load_dotenv()

# --- API keys (set in .env file) ---
ENTSOE_API_KEY: str = os.getenv("ENTSOE_API_KEY", "")
CDS_API_KEY: str    = os.getenv("CDS_API_KEY", "")   # Personal Access Token (new CDS API, 2024+)
CDS_API_URL: str    = os.getenv("CDS_API_URL", "https://cds.climate.copernicus.eu/api")

# --- Date range ---
START_DATE = pd.Timestamp("2020-01-01", tz="UTC")
END_DATE   = pd.Timestamp("2025-01-01", tz="UTC")

# --- Output directory ---
DATA_DIR = Path("data")

# --- ENTSO-E bidding zone / area codes ---
CZ_AREA = "10YCZ-CEPS-----N"   # Czech Republic
DE_AREA = "10Y1001A1001A82H"   # Germany–Luxembourg (price coupling driver)

# --- Czech Republic bounding box for ERA5 (N, W, S, E) ---
CZ_BBOX = [52, 12, 48, 19]

# ─── Shared utilities ──────────────────────────────────────────────────────────

def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_csv(df: pd.DataFrame, path: Path) -> None:
    """Save a DataFrame to CSV and log the result."""
    df.to_csv(path)
    log.info(f"    Saved {len(df):,} rows → {path.relative_to(DATA_DIR.parent)}")


def http_get(url: str, params: dict | None = None, **kwargs) -> requests.Response:
    """GET request with exponential-back-off retry (3 attempts)."""
    for attempt in range(1, 4):
        try:
            r = requests.get(url, params=params, timeout=60, **kwargs)
            r.raise_for_status()
            return r
        except requests.RequestException as exc:
            log.warning(f"    [{attempt}/3] {url} — {exc}")
            if attempt < 3:
                time.sleep(5 * attempt)
    raise RuntimeError(f"Failed after 3 attempts: {url}")


# ─── MODULE 1: ENTSO-E Transparency Platform ──────────────────────────────────

def collect_entsoe(out_dir: Path) -> None:
    """
    Download electricity market data from ENTSO-E using the entsoe-py library.

    Datasets collected
    ------------------
    cz_da_prices.csv      Hourly day-ahead clearing prices for Czech Republic (€/MWh)
    de_da_prices.csv      Hourly day-ahead clearing prices for Germany–Luxembourg (€/MWh)
    cz_load.csv           Actual total electricity load in CZ (MW)
    cz_generation.csv     Actual generation split by technology (nuclear, wind, solar …)
    cz_imbalance.csv      Czech imbalance/settlement prices

    Prerequisites
    -------------
    1. Register (free) at https://transparency.entsoe.eu
    2. Send an email to transparency@entsoe.eu with subject "Restful API access"
       and your registered email address in the body (approval takes ~3 working days)
    3. After approval: log in → My Account Settings → Web API Security Token → Generate
    4. Copy your token to .env:  ENTSOE_API_KEY=your_token_here
    """
    log.info("━━━ ENTSO-E ━━━")
    ensure_dir(out_dir)

    if not ENTSOE_API_KEY:
        log.warning(
            "ENTSOE_API_KEY is not set → skipping ENTSO-E.\n"
            "  1. Register (free) at https://transparency.entsoe.eu\n"
            "  2. Email transparency@entsoe.eu, subject: 'Restful API access',\n"
            "     body: your registered email address (approval ~3 working days)\n"
            "  3. After approval: My Account Settings → Web API Security Token → Generate\n"
            "  4. Add:  ENTSOE_API_KEY=your_token  to your .env file."
        )
        return

    try:
        from entsoe import EntsoePandasClient
    except ImportError:
        log.error("entsoe-py is not installed.  Run:  pip install entsoe-py")
        return

    client = EntsoePandasClient(api_key=ENTSOE_API_KEY)

    def query_in_yearly_chunks(fn, *args, **kwargs):
        """
        Split a multi-year query into yearly chunks to stay within the API's
        page-size limit and to allow partial recovery on errors.
        """
        frames = []
        for year in range(START_DATE.year, END_DATE.year):
            s = pd.Timestamp(f"{year}-01-01", tz="UTC")
            e = pd.Timestamp(f"{year + 1}-01-01", tz="UTC")
            log.info(f"    year {year} …")
            try:
                chunk = fn(*args, start=s, end=e, **kwargs)
                frames.append(chunk)
            except Exception as exc:
                log.warning(f"    year {year} failed: {exc}")
            time.sleep(1)   # respect the API rate limit
        return pd.concat(frames) if frames else pd.DataFrame()

    # 1. Czech day-ahead prices
    log.info("  [1/5] CZ day-ahead prices")
    cz_da = query_in_yearly_chunks(client.query_day_ahead_prices, CZ_AREA)
    if not cz_da.empty:
        save_csv(cz_da.rename("price_eur_mwh").to_frame(), out_dir / "cz_da_prices.csv")

    # 2. German / DE-LU day-ahead prices  (price coupling driver)
    log.info("  [2/5] DE-LU day-ahead prices")
    de_da = query_in_yearly_chunks(client.query_day_ahead_prices, DE_AREA)
    if not de_da.empty:
        save_csv(de_da.rename("price_eur_mwh").to_frame(), out_dir / "de_da_prices.csv")

    # 3. CZ actual load
    log.info("  [3/5] CZ actual load")
    cz_load = query_in_yearly_chunks(client.query_load, CZ_AREA)
    if not cz_load.empty:
        save_csv(cz_load, out_dir / "cz_load.csv")

    # 4. CZ generation mix (nuclear, wind, solar, hydro, …)
    log.info("  [4/5] CZ generation by technology")
    cz_gen = query_in_yearly_chunks(client.query_generation, CZ_AREA)
    if not cz_gen.empty:
        save_csv(cz_gen, out_dir / "cz_generation.csv")

    # 5. CZ imbalance prices (needed for the recourse / settlement stage)
    log.info("  [5/5] CZ imbalance prices")
    try:
        cz_imb = query_in_yearly_chunks(client.query_imbalance_prices, CZ_AREA)
        if not cz_imb.empty:
            save_csv(cz_imb, out_dir / "cz_imbalance.csv")
    except Exception as exc:
        log.warning(
            f"  Imbalance prices query failed: {exc}\n"
            "  This dataset may not be available for CZ via the API.\n"
            "  Download manually from: https://transparency.entsoe.eu → Balancing → Imbalance Prices"
        )

    log.info("  ENTSO-E collection complete.")


# ─── MODULE 2: OTE — Czech Electricity Market Operator ────────────────────────

def collect_ote(out_dir: Path) -> None:
    """
    Download market data from OTE (Operátor trhu s energiemi, a.s.).
    Website: https://www.ote-cr.cz

    OTE publishes daily XML reports with hourly clearing prices and volumes
    for the Czech day-ahead market. This module iterates over each day in the
    target period, fetches the XML report, and assembles a tidy CSV.

    Important notes
    ---------------
    - The download is polite (0.5 s between requests) but covers ~1,825 days,
      so expect it to take roughly 15–20 minutes.
    - If the XML endpoint has changed or returns errors, OTE also publishes
      yearly Excel reports (see warning at the end of this function).
    - OTE intraday (continuous) market data is less structured; manual download
      from the statistics section is the safest option.

    Manual fallback
    ---------------
    https://www.ote-cr.cz/en/statistics/electricity/market-prices
    → download yearly Excel files → place them in data/ote/
    """
    log.info("━━━ OTE ━━━")
    ensure_dir(out_dir)

    import io
    OTE_BASE = "https://www.ote-cr.cz"
    # OTE publishes daily XLS reports at a predictable URL:
    # /pubweb/attachments/01/{year}/month{MM}/day{DD}/DT_{DD}_{MM}_{YYYY}_CZ.xls
    def _ote_xls_url(d) -> str:
        return (
            f"{OTE_BASE}/pubweb/attachments/01/{d.year}"
            f"/month{d.month:02d}/day{d.day:02d}"
            f"/DT_{d.day:02d}_{d.month:02d}_{d.year}_CZ.xls"
        )

    out_csv = out_dir / "cz_dam_ote.csv"
    if out_csv.exists():
        log.info(f"  OTE: {out_csv.name} already exists — skipping download.")
        log.info("  OTE collection complete.")
        return

    records = []
    current  = START_DATE.date()
    end_date = END_DATE.date()
    total_days = (end_date - current).days
    ok_count, err_count = 0, 0

    log.info(f"  OTE: fetching {total_days} daily XLS reports …")

    while current < end_date:
        date_str = current.strftime("%Y-%m-%d")
        try:
            r = requests.get(_ote_xls_url(current), timeout=30)
            if r.status_code == 200 and r.content:
                df_day = pd.read_excel(io.BytesIO(r.content), header=None)
                # Data rows start at index 6; columns: hour, price_eur_mwh, volume_mwh, ...
                # Find the "Hodina" header row dynamically — OTE restructured
                # the XLS in mid-2024, moving the hourly table further down.
                hodina_row = None
                for i, row in df_day.iterrows():
                    if str(row.iloc[0]).strip() == "Hodina":
                        hodina_row = i
                        break
                if hodina_row is None:
                    err_count += 1
                    current += timedelta(days=1)
                    time.sleep(0.3)
                    continue
                data_rows = df_day.iloc[hodina_row + 2 : hodina_row + 27].copy()
                data_rows.columns = range(len(data_rows.columns))
                for _, row in data_rows.iterrows():
                    try:
                        hour = int(float(row[0]))
                        if not (1 <= hour <= 25):
                            continue
                        records.append({
                            "date":          date_str,
                            "hour":          hour,
                            "price_eur_mwh": float(row[1]),
                            "volume_mwh":    float(row[2]),
                        })
                    except (ValueError, TypeError):
                        continue
                ok_count += 1
            else:
                err_count += 1
        except Exception:
            err_count += 1

        current += timedelta(days=1)
        time.sleep(0.3)

        processed = ok_count + err_count
        if processed % 200 == 0:
            log.info(f"    {processed}/{total_days} days  (ok={ok_count}, err={err_count})")

    if records:
        df = pd.DataFrame(records)
        df["datetime"] = pd.to_datetime(df["date"]) + pd.to_timedelta(
            (df["hour"].astype(float) - 1).mul(3600).astype("int64"), unit="s"
        )
        df = df.drop(columns=["date", "hour"]).set_index("datetime").sort_index()
        save_csv(df, out_dir / "cz_dam_ote.csv")
        log.info(f"  OTE: {ok_count}/{total_days} days collected successfully.")
    else:
        log.warning(
            "  OTE: no data collected.\n"
            "  Manual fallback: https://www.ote-cr.cz/en/statistics/electricity/market-prices\n"
            "  Download yearly Excel files and place them in data/ote/"
        )

    log.info("  OTE collection complete.")


# ─── MODULE 3: ČEPS — Czech Electricity Transmission System Operator ──────────

def collect_ceps(out_dir: Path) -> None:
    """
    Download data from ČEPS (ČEPS, a.s. — Czech TSO).
    Website: https://www.ceps.cz/en/all-data

    ČEPS provides the following datasets used in the panel:

    Dataset                     Description
    ─────────────────────────── ─────────────────────────────────────────────
    Imbalance settlement        Negative/positive imbalance prices (CZK/MWh)
    FCR capacity prices         Frequency containment reserve auction results
    aFRR capacity & energy      Automatic frequency restoration reserve
    Cross-border nominations    Physical flows CZ ↔ AT/SK/PL/DE

    Programmatic access
    -------------------
    ČEPS exposes some datasets via a JSON/XML API used internally by their
    chart widgets. This module attempts those endpoints; if they fail (the
    API may not be officially documented), clear manual instructions are shown.

    Manual fallback
    ---------------
    https://www.ceps.cz/en/all-data
    → "Balancing" tab → Settlement of imbalances → Export to Excel
    → "System services" tab → FCR / aFRR auction results → Export
    → Save files to: data/ceps/
    """
    log.info("━━━ ČEPS ━━━")
    ensure_dir(out_dir)

    import io as _io

    CEPS_BASE = "https://www.ceps.cz"
    DOWNLOAD_URL = CEPS_BASE + "/downloads/graph"
    HEADERS = {"Referer": CEPS_BASE + "/en/all-data"}

    # Datasets available via the ČEPS /downloads/graph endpoint.
    # CSV format: semicolon-separated, Czech date format.
    # Tuple: (ČEPS method name, aggregation).
    # OdhadovanaCenaOdchylky is published at 15-min (QH) resolution.
    CEPS_DATASETS = {
        "cz_imbalance_price":     ("OdhadovanaCenaOdchylky",  "QH"),  # Imbalance price CZK/MWh (15-min)
        "cz_crossborder_flows":   ("CrossborderPowerFlows",   "HR"),  # Physical flows CZ↔PL/SK/AT/DE (MW)
        "cz_load":                ("Load",                    "HR"),  # System load (MW)
        "cz_generation_mix":      ("Generation",              "HR"),  # Generation by source (MW)
        "cz_renewable_generation":("GenerationRES",           "HR"),  # Renewables breakdown (MW)
    }

    any_success = False

    def _ceps_fetch(method: str, dfrom: str, dto: str, agregation: str = "HR") -> "pd.DataFrame | None":
        """Fetch one ČEPS dataset, return parsed DataFrame or None on failure."""
        params = {
            "method": method, "format": "csv",
            "date_from": dfrom, "date_to": dto, "agregation": agregation,
        }
        r = requests.get(DOWNLOAD_URL, params=params, timeout=120, headers=HEADERS)
        if r.status_code != 200 or len(r.content) < 500:
            return None
        raw = r.content.decode("utf-8-sig", errors="replace")
        lines = raw.splitlines()
        # Keep ALL column slots (including empty) to preserve semicolon alignment.
        # Use numeric column indices; rename after index is set.
        all_cols = [c.strip() for c in lines[2].split(";")]
        df = pd.read_csv(
            _io.StringIO("\n".join(lines[3:])),
            sep=";", header=None, on_bad_lines="skip",
        )
        df.columns = range(len(df.columns))
        if df.empty:
            return None
        sample = str(df.iloc[0, 0]).strip()
        if " " in sample and len(sample) >= 13:
            # Hourly: "DD.MM.YYYY HH:MM" in column 0
            df[0] = pd.to_datetime(df[0], format="%d.%m.%Y %H:%M", errors="coerce")
            df = df.dropna(subset=[0]).set_index(0)
            df.index.name = "datetime"
            data_cols = [c for c in all_cols[1:] if c]
        else:
            # 15-min: "DD.MM.YYYY" in col 0, "HH:MM-HH:MM" in col 1
            df["datetime"] = pd.to_datetime(df[0], format="%d.%m.%Y", errors="coerce") + \
                             df[1].str[:5].apply(
                                 lambda x: pd.Timedelta(hours=int(x[:2]), minutes=int(x[3:5]))
                                           if isinstance(x, str) and len(x) >= 5 else pd.NaT
                             )
            df = df.dropna(subset=["datetime"]).set_index("datetime")
            df = df.drop(columns=[0, 1], errors="ignore")
            data_cols = [c for c in all_cols[2:] if c]
        rename_map = {old: new for old, new in zip(df.columns, data_cols)}
        df = df.rename(columns=rename_map)
        df = df[[c for c in df.columns if isinstance(c, str) and c.strip()]]
        df = df.dropna(how="all").sort_index()
        return df if not df.empty else None

    date_from = START_DATE.strftime("%Y-%m-%dT%H:%M")
    date_to   = END_DATE.strftime("%Y-%m-%dT%H:%M")

    for filename, (method, agg) in CEPS_DATASETS.items():
        out_file = out_dir / f"{filename}.csv"
        if out_file.exists():
            log.info(f"  ČEPS {method}: {out_file.name} already exists — skipping.")
            any_success = True
            continue
        try:
            df = _ceps_fetch(method, date_from, date_to, agregation=agg)
            if df is None:
                # Server returns 500 for large ranges — fall back to yearly chunks
                log.info(f"  ČEPS {method}: full-range failed, trying yearly chunks …")
                chunks = []
                for yr in range(START_DATE.year, END_DATE.year):
                    try:
                        chunk = _ceps_fetch(method, f"{yr}-01-01T00:00", f"{yr+1}-01-01T00:00", agregation=agg)
                    except Exception:
                        chunk = None
                    if chunk is not None:
                        chunks.append(chunk)
                    time.sleep(0.5)
                df = pd.concat(chunks).sort_index() if chunks else None

            if df is not None:
                save_csv(df, out_file)
                log.info(f"  ČEPS {method}: {len(df)} rows → {out_file.name}")
                any_success = True
            else:
                log.warning(f"  ČEPS {method}: download failed (HTTP error or empty response)")
        except Exception as exc:
            log.warning(f"  ČEPS {method}: {exc}")

    if not any_success:
        log.warning(
            "  ČEPS: all downloads failed.\n"
            "  Manual fallback: https://www.ceps.cz/en/all-data\n"
            "  Use the Export button on each graph and save CSVs to data/ceps/"
        )

    log.info("  ČEPS collection complete.")


# ─── MODULE 4: ERA5 Reanalysis Weather Data ───────────────────────────────────

def collect_era5(out_dir: Path) -> None:
    """
    Download ERA5 hourly reanalysis data for the Czech Republic via the
    Copernicus Climate Data Store (CDS) API.

    Variables downloaded
    --------------------
    100m_u_component_of_wind          )  → derive 100 m wind speed
    100m_v_component_of_wind          )    (proxy for wind power generation)
    surface_solar_radiation_downwards      proxy for PV generation (W/m²·s)
    2m_temperature                         demand proxy (°C)

    Files are saved as monthly NetCDF files:  data/era5/era5_cz_{year}_{mm}.nc
    To convert to CSV, run the helper function era5_nc_to_csv() below.
    One month ≈ 4 variables × 24 h × ~30 days × ~16 grid points ≈ 5–10 MB.

    Prerequisites
    -------------
    1. Register (free) at https://cds.climate.copernicus.eu
    2. Accept the ERA5 licence on the dataset page:
       https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels
    3. Go to https://cds.climate.copernicus.eu/profile → copy your
       Personal Access Token (a UUID like 12345678-abcd-...)
    4. Add to .env:  CDS_API_KEY=your_personal_access_token
    5. pip install "cdsapi>=0.7.2"

    Documentation: https://cds.climate.copernicus.eu/how-to-api
    """
    log.info("━━━ ERA5 ━━━")
    ensure_dir(out_dir)

    if not CDS_API_KEY:
        log.warning(
            "CDS_API_KEY is not set → skipping ERA5 download.\n"
            "  Register (free) at https://cds.climate.copernicus.eu\n"
            "  Profile page → copy your Personal Access Token\n"
            "  Then add:  CDS_API_KEY=your_token  to your .env file."
        )
        return

    try:
        import cdsapi
    except ImportError:
        log.error("cdsapi is not installed.  Run:  pip install cdsapi")
        return

    # The new CDS API (2024+) enforces per-request size limits; a full year of
    # 4 variables × 24 h × 365 days exceeds the limit.  Requesting one month
    # at a time stays well within the quota and allows resumable downloads.
    c = cdsapi.Client(url=CDS_API_URL, key=CDS_API_KEY, quiet=True)

    import calendar as _cal
    months_total = (END_DATE.year - START_DATE.year) * 12 + END_DATE.month - START_DATE.month
    done, errors = 0, 0

    for year in range(START_DATE.year, END_DATE.year + 1):
        for month in range(1, 13):
            # Skip months outside [START_DATE, END_DATE)
            if year == START_DATE.year and month < START_DATE.month:
                continue
            if year == END_DATE.year and month >= END_DATE.month:
                continue

            out_file = out_dir / f"era5_cz_{year}_{month:02d}.nc"
            if out_file.exists():
                log.info(f"  ERA5 {year}-{month:02d}: already exists, skipping.")
                done += 1
                continue

            last_day = _cal.monthrange(year, month)[1]
            log.info(f"  ERA5 {year}-{month:02d}: submitting request ({done+1}/{months_total}) …")
            try:
                c.retrieve(
                    "reanalysis-era5-single-levels",
                    {
                        "product_type": "reanalysis",
                        "variable": [
                            "100m_u_component_of_wind",
                            "100m_v_component_of_wind",
                            "surface_solar_radiation_downwards",
                            "2m_temperature",
                        ],
                        "year":  str(year),
                        "month": f"{month:02d}",
                        "day":   [f"{d:02d}" for d in range(1, last_day + 1)],
                        "time":  [f"{h:02d}:00" for h in range(0, 24)],
                        "area":  CZ_BBOX,   # N / W / S / E
                        "format": "netcdf",
                    },
                    str(out_file),
                )
                log.info(f"  ERA5 {year}-{month:02d}: saved → {out_file.name}")
                done += 1
            except Exception as exc:
                log.error(f"  ERA5 {year}-{month:02d}: failed — {exc}")
                errors += 1

    log.info(f"  ERA5 collection complete. ({done} months saved, {errors} errors)")


def era5_nc_to_csv(era5_dir: Path, out_dir: Path) -> None:
    """
    Convert downloaded ERA5 files (monthly ZIP archives containing NetCDF files)
    to a single CSV per year, spatially averaged over the CZ bounding box.

    The CDS API (2024+) returns a ZIP with two inner NetCDF files:
      - data_stream-oper_stepType-instant.nc  → u100, v100, t2m
      - data_stream-oper_stepType-accum.nc    → ssrd

    Resulting files: data/era5/era5_cz_{year}.csv
    Columns: valid_time, u100 [m/s], v100 [m/s], t2m [K],
             ssrd [J/m²], wind_speed_100m [m/s]
    """
    try:
        import netCDF4 as _nc4
        import numpy as np
        import zipfile
    except ImportError:
        log.error("netCDF4 not installed. Run:  pip install netCDF4")
        return

    ensure_dir(out_dir)

    from itertools import groupby

    def _year_key(p):
        parts = p.stem.split("_")
        return parts[2]  # era5 / cz / YYYY / [MM]

    def _read_nc_from_zip(zip_path: Path, nc_name: str) -> "pd.DataFrame":
        """Read one inner NetCDF from a ZIP, return spatially-averaged DataFrame."""
        with zipfile.ZipFile(zip_path) as z:
            raw = z.read(nc_name)
        ds = _nc4.Dataset(nc_name, memory=raw)
        times = _nc4.num2date(
            ds.variables["valid_time"][:],
            units=ds.variables["valid_time"].units,
        )
        times_dt = pd.DatetimeIndex(
            [pd.Timestamp(str(t)) for t in times], name="valid_time"
        )
        data_vars = {
            v: ds.variables[v][:].mean(axis=(1, 2))  # avg over lat/lon
            for v in ds.variables
            if ds.variables[v].ndim == 3
        }
        ds.close()
        return pd.DataFrame(data_vars, index=times_dt)

    nc_files = sorted(era5_dir.glob("era5_cz_*.nc"))

    for year, group in groupby(nc_files, key=_year_key):
        csv_file = out_dir / f"era5_cz_{year}.csv"
        if csv_file.exists():
            log.info(f"  ERA5→CSV {year}: already exists, skipping.")
            continue
        files = list(group)
        log.info(f"  ERA5→CSV {year}: converting {len(files)} month(s) …")
        chunks = []
        for f in files:
            try:
                with zipfile.ZipFile(f) as z:
                    inner_names = z.namelist()
                dfs = []
                for name in inner_names:
                    if name.endswith(".nc"):
                        dfs.append(_read_nc_from_zip(f, name))
                if dfs:
                    merged = pd.concat(dfs, axis=1)
                    chunks.append(merged)
            except Exception as exc:
                log.warning(f"  ERA5→CSV {year}: error reading {f.name} — {exc}")

        if not chunks:
            log.warning(f"  ERA5→CSV {year}: no data, skipping.")
            continue

        df = pd.concat(chunks).sort_index()
        df = df[~df.index.duplicated(keep="first")]
        if "u100" in df.columns and "v100" in df.columns:
            df["wind_speed_100m"] = np.sqrt(df["u100"] ** 2 + df["v100"] ** 2)
        save_csv(df, csv_file)
        log.info(f"  ERA5→CSV {year}: {len(df)} rows → {csv_file.name}")


# ─── MAIN ──────────────────────────────────────────────────────────────────────

def main() -> None:
    sep = "═" * 60
    log.info(sep)
    log.info("Czech electricity market — data collection")
    log.info(f"Period  : {START_DATE.date()}  →  {END_DATE.date()}")
    log.info(f"Output  : {DATA_DIR.resolve()}")
    log.info(sep)

    collect_entsoe(DATA_DIR / "entsoe")
    collect_ote(DATA_DIR / "ote")
    collect_ceps(DATA_DIR / "ceps")
    collect_era5(DATA_DIR / "era5")

    # Convert ERA5 NetCDF to CSV (optional, comment out if not needed)
    era5_nc_to_csv(DATA_DIR / "era5", DATA_DIR / "era5")

    log.info(sep)
    log.info("Collection finished. Review warnings above for any manual steps.")
    log.info(f"Log saved to: collect_data.log")
    log.info(sep)


if __name__ == "__main__":
    main()
