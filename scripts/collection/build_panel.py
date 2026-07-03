"""
build_panel.py  —  Topic 1: Battery Storage Arbitrage
======================================================
Merges all collected data sources into a single wide-format hourly panel CSV.

Output
------
  data/topic1_panel.csv
  Index : datetime (UTC, hourly)
  Columns (see DATA_LEGEND.md for full descriptions):

  PRICES (EUR/MWh unless noted)
    ote_price_eur_mwh       OTE Czech day-ahead clearing price
    entsoe_cz_da_eur_mwh    ENTSO-E Czech day-ahead price (cross-check)
    entsoe_de_da_eur_mwh    ENTSO-E German day-ahead price (price-coupling driver)
    ceps_imbalance_czk_mwh  ČEPS imbalance / settlement price (CZK/MWh, 15-min → hourly avg)

  LOAD & SYSTEM (MW)
    ceps_load_mw            ČEPS Czech system load
    ceps_crossborder_*_mw   ČEPS cross-border flows (CZ↔DE, AT, PL, SK)

  GENERATION MIX (MW)
    ceps_gen_nuclear_mw, _coal_mw, _gas_mw, _hydro_mw, _solar_mw, _wind_mw, ...

  RENEWABLES (MW)
    ceps_res_solar_mw, ceps_res_wind_mw, ...

  WEATHER (ERA5 spatial average over CZ bounding box)
    era5_wind_speed_100m        Derived 100m wind speed (m/s) = sqrt(u100²+v100²)
    era5_t2m                    2m air temperature (K)
    era5_ssrd                   Surface solar radiation downwards (J/m²)
    era5_sp                     Surface pressure (Pa)

Usage
-----
  python build_panel.py
"""

import sys
import logging
import pandas as pd
import numpy as np
from pathlib import Path

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)-8s  %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger(__name__)

DATA_DIR  = Path(__file__).parent / "data"
OUT_FILE  = DATA_DIR / "topic1_panel.csv"

# ─── helpers ──────────────────────────────────────────────────────────────────

def read_csv_auto(path: Path, skip_rows: int = 0, source_tz: str | None = None) -> pd.DataFrame:
    """Read a CSV with a datetime index; handle tz-aware strings and bad rows.

    source_tz: timezone of naive timestamps in the file (e.g. "Europe/Prague"
    for OTE and ČEPS exports). Tz-aware timestamps are converted directly.
    If None, naive timestamps are assumed to already be UTC (ERA5, ENTSO-E).
    The returned index is always naive UTC.
    """
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, index_col=0, skiprows=range(1, skip_rows + 1) if skip_rows else None)
    # Drop rows where index can't be parsed as a datetime (e.g. extra header rows)
    try:
        idx = pd.to_datetime(df.index, errors="coerce")
    except ValueError:
        # tz-aware strings with mixed offsets (+01:00 CET / +02:00 CEST)
        idx = pd.to_datetime(df.index, errors="coerce", utc=True)
    df = df[idx.notna()].copy()
    idx = idx[idx.notna()]
    if idx.tz is None and source_tz:
        # Naive local time: DST spring-forward hours don't exist (NaT),
        # the fall-back duplicated hour is ambiguous (NaT) — both dropped
        # and documented in DATA_LEGEND.md.
        idx = idx.tz_localize(source_tz, ambiguous="NaT", nonexistent="NaT")
        df = df[idx.notna()]
        idx = idx[idx.notna()]
    elif idx.tz is None:
        idx = idx.tz_localize("UTC")
    df.index = idx.tz_convert("UTC").tz_localize(None)
    df = df.apply(pd.to_numeric, errors="coerce")
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="first")]
    return df


def resample_to_hourly(df: pd.DataFrame, method: str = "mean") -> pd.DataFrame:
    if df.empty:
        return df
    if method == "mean":
        return df.resample("h").mean()
    if method == "sum":
        return df.resample("h").sum()
    return df.resample("h").first()


# ─── 1. OTE day-ahead prices ──────────────────────────────────────────────────
def load_ote() -> pd.DataFrame:
    log.info("Loading OTE day-ahead prices...")
    path = DATA_DIR / "ote" / "cz_dam_ote.csv"
    if not path.exists():
        log.warning(f"  Not found: {path}")
        return pd.DataFrame()
    # OTE XLS exports carry naive CET/CEST local timestamps → convert to UTC
    df = read_csv_auto(path, source_tz="Europe/Prague")
    df = df.rename(columns={"price_eur_mwh": "ote_price_eur_mwh"})
    df = df.resample("h").mean()   # ensure hourly (already is, but handle duplicates)
    log.info(f"  OTE: {len(df):,} rows  {df.index.min().date()} → {df.index.max().date()}")
    return df


# ─── 2. ENTSO-E prices & load ─────────────────────────────────────────────────
def load_entsoe() -> pd.DataFrame:
    log.info("Loading ENTSO-E data...")
    frames = {}

    # CZ day-ahead prices
    p = DATA_DIR / "entsoe" / "cz_da_prices.csv"
    if p.exists():
        df = read_csv_auto(p)
        if not df.empty:
            df.columns = ["entsoe_cz_da_eur_mwh"]
            frames["cz_da"] = df

    # DE day-ahead prices
    p = DATA_DIR / "entsoe" / "de_da_prices.csv"
    if p.exists():
        df = read_csv_auto(p)
        if not df.empty:
            df.columns = ["entsoe_de_da_eur_mwh"]
            frames["de_da"] = df

    # CZ actual load
    p = DATA_DIR / "entsoe" / "cz_load.csv"
    if p.exists():
        df = read_csv_auto(p)
        if not df.empty:
            df.columns = [f"entsoe_load_{c}" for c in df.columns]
            frames["cz_load"] = df

    # CZ generation by technology (entsoe-py writes a double-header; skip row 1)
    p = DATA_DIR / "entsoe" / "cz_generation.csv"
    if p.exists():
        df = read_csv_auto(p, skip_rows=1)   # skip "Actual Aggregated" row
        if not df.empty:
            # Drop duplicate pump-storage column (entsoe-py names it .1)
            df = df.loc[:, ~df.columns.str.endswith(".1")]
            df.columns = [
                f"entsoe_gen_{c.lower().replace(' ', '_').replace('/', '_')}"
                for c in df.columns
            ]
            frames["cz_gen"] = resample_to_hourly(df)

    if not frames:
        log.warning("  No ENTSO-E data found (not yet downloaded or API key was missing).")
        return pd.DataFrame()

    result = pd.concat(list(frames.values()), axis=1)
    result = resample_to_hourly(result)
    log.info(f"  ENTSO-E: {len(result):,} rows, {len(result.columns)} columns")
    return result


# ─── 3. ČEPS datasets ─────────────────────────────────────────────────────────
def load_ceps() -> pd.DataFrame:
    log.info("Loading ČEPS data...")
    ceps_dir = DATA_DIR / "ceps"
    frames = {}

    FILE_MAP = {
        "cz_imbalance_price.csv":     "ceps_imbalance",
        "cz_crossborder_flows.csv":   "ceps_xborder",
        "cz_load.csv":                "ceps_load",
        "cz_generation_mix.csv":      "ceps_gen",
        "cz_renewable_generation.csv": "ceps_res",
    }

    for fname, prefix in FILE_MAP.items():
        p = ceps_dir / fname
        if not p.exists():
            log.warning(f"  Missing: {p.name}")
            continue
        # ČEPS exports carry naive CET/CEST local timestamps → convert to UTC
        df = read_csv_auto(p, source_tz="Europe/Prague")
        if df.empty:
            continue
        # Rename all columns with prefix
        df.columns = [f"{prefix}_{c.lower().replace(' ', '_').replace('/', '_').replace('(', '').replace(')', '').replace('[', '').replace(']', '').rstrip('_')}"
                      for c in df.columns]
        # Resample to hourly (imbalance is 15-min)
        df = resample_to_hourly(df, "mean")
        frames[prefix] = df
        log.info(f"  {fname}: {len(df):,} rows")

    if not frames:
        return pd.DataFrame()
    result = pd.concat(list(frames.values()), axis=1)
    log.info(f"  ČEPS combined: {len(result):,} rows, {len(result.columns)} columns")
    return result


# ─── 4. ERA5 weather ──────────────────────────────────────────────────────────
def load_era5() -> pd.DataFrame:
    log.info("Loading ERA5 weather data...")
    era5_dir = DATA_DIR / "era5"
    csv_files = sorted(era5_dir.glob("era5_cz_????.csv"))   # yearly CSVs, not monthly .nc
    if not csv_files:
        log.warning("  No ERA5 CSVs found.")
        return pd.DataFrame()

    frames = []
    for f in csv_files:
        df = read_csv_auto(f)
        if not df.empty:
            frames.append(df)

    if not frames:
        return pd.DataFrame()

    era5 = pd.concat(frames).sort_index()
    era5 = era5[~era5.index.duplicated(keep="first")]
    # Prefix columns
    era5.columns = [f"era5_{c}" if not c.startswith("era5_") else c for c in era5.columns]
    # Resample to hourly (ERA5 is already hourly but may have 3h gaps)
    era5 = era5.resample("h").mean()
    log.info(f"  ERA5: {len(era5):,} rows, columns: {list(era5.columns)}")
    return era5


# ─── 5. Build panel ───────────────────────────────────────────────────────────
def build_panel() -> None:
    sep = "═" * 60
    log.info(sep)
    log.info("Topic 1 — Building Hourly Panel Dataset")
    log.info(sep)

    ote    = load_ote()
    entsoe = load_entsoe()
    ceps   = load_ceps()
    era5   = load_era5()

    # Merge all on hourly UTC datetime index
    pieces = [df for df in [ote, entsoe, ceps, era5] if not df.empty]
    if not pieces:
        log.error("No data loaded — nothing to merge.")
        return

    panel = pieces[0]
    for df in pieces[1:]:
        panel = panel.join(df, how="outer")

    panel = panel.sort_index()

    # Trim to 2020-01-01 – 2024-12-31 (Topic 1 scope)
    panel = panel.loc["2020-01-01":"2024-12-31"]

    # Drop rows that are entirely NaN
    panel = panel.dropna(how="all")

    log.info(sep)
    log.info(f"Panel: {len(panel):,} rows × {len(panel.columns)} columns")
    log.info(f"Date range: {panel.index.min()} → {panel.index.max()}")
    log.info(f"Columns: {list(panel.columns)}")
    missing_pct = panel.isnull().mean().sort_values(ascending=False)
    log.info(f"Missing data (top 10):\n{missing_pct.head(10).to_string()}")

    panel.to_csv(OUT_FILE)
    log.info(f"Saved → {OUT_FILE}  ({OUT_FILE.stat().st_size / 1024:.0f} KB)")
    log.info(sep)


if __name__ == "__main__":
    build_panel()
