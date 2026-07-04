"""
s0_data_prep.py — data preparation (draft §3.2–3.3).

Loads the merged hourly panel, constructs the variables used by all later
layers, and writes a single prepared dataset:

  * residual load  R_t = load − solar − wind          (§3.3)
  * surplus-hour indicator  y_t = 1{p_t < threshold}  (§3.3)
  * deseasonalised price  p̃_t = p_t − f̂_t            (§3.3)
      f̂_t : hour-of-day × day-type dummies + annual Fourier terms,
      fitted separately per crisis subperiod so the 2022 level shock
      does not contaminate the seasonal profile
  * hourly grid emission intensity (generation-weighted average)
  * subperiod labels, calendar features

Run:  python analysis/s0_data_prep.py
"""
import numpy as np
import pandas as pd

import config as C


# ── helpers ───────────────────────────────────────────────────────────────────

def czech_holidays(years) -> set:
    """Fixed-date Czech public holidays + Easter Monday / Good Friday."""
    fixed = [(1, 1), (5, 1), (5, 8), (7, 5), (7, 6), (9, 28),
             (10, 28), (11, 17), (12, 24), (12, 25), (12, 26)]

    def easter_sunday(y):  # Anonymous Gregorian algorithm
        a, b, c = y % 19, y // 100, y % 100
        d, e = b // 4, b % 4
        f = (b + 8) // 25
        g = (b - f + 1) // 3
        h = (19 * a + b - d - g + 15) % 30
        i, k = c // 4, c % 4
        l = (32 + 2 * e + 2 * i - h - k) % 7
        m = (a + 11 * h + 22 * l) // 451
        month = (h + l - 7 * m + 114) // 31
        day = ((h + l - 7 * m + 114) % 31) + 1
        return pd.Timestamp(y, month, day)

    out = set()
    for y in years:
        for m, d in fixed:
            out.add(pd.Timestamp(y, m, d).date())
        es = easter_sunday(y)
        out.add((es + pd.Timedelta(days=1)).date())   # Easter Monday
        out.add((es - pd.Timedelta(days=2)).date())   # Good Friday
    return out


def add_calendar(df: pd.DataFrame) -> pd.DataFrame:
    idx = df.index
    df["hour"] = idx.hour
    df["month"] = idx.month
    df["year"] = idx.year
    df["doy"] = idx.dayofyear
    hol = czech_holidays(sorted(idx.year.unique()))
    is_hol = pd.Series(idx.date, index=idx).isin(hol)
    df["daytype"] = np.where(is_hol | (idx.dayofweek >= 5), "weekend_holiday", "workday")
    return df


def label_subperiods(df: pd.DataFrame) -> pd.DataFrame:
    df["subperiod"] = pd.NA
    for name, (a, b) in C.SUBPERIODS.items():
        df.loc[a:b, "subperiod"] = name
    return df


def fit_seasonal_component(df: pd.DataFrame, price_col: str) -> pd.Series:
    """OLS seasonal profile: hour×daytype dummies + annual Fourier terms,
    fitted separately within each subperiod (crisis break, §3.3)."""
    fhat = pd.Series(np.nan, index=df.index)
    for sp, g in df.groupby("subperiod", observed=True):
        y = g[price_col]
        ok = y.notna()
        X_parts = [pd.get_dummies(g["hour"].astype(str) + "_" + g["daytype"], dtype=float)]
        for k in range(1, C.N_FOURIER_ANNUAL + 1):
            X_parts.append(pd.DataFrame({
                f"sin{k}": np.sin(2 * np.pi * k * g["doy"] / 365.25),
                f"cos{k}": np.cos(2 * np.pi * k * g["doy"] / 365.25),
            }, index=g.index))
        X = pd.concat(X_parts, axis=1)
        beta, *_ = np.linalg.lstsq(X[ok].values, y[ok].values, rcond=None)
        fhat.loc[g.index] = X.values @ beta
    return fhat


def grid_emission_intensity(df: pd.DataFrame) -> pd.Series:
    """Generation-weighted average CO2 intensity of CZ generation [tCO2/MWh]."""
    cols = [c for c in C.EMISSION_FACTORS if c in df.columns]
    gen = df[cols].clip(lower=0)
    emis = sum(gen[c] * C.EMISSION_FACTORS[c] for c in cols)
    total = gen.sum(axis=1)
    return (emis / total.replace(0, np.nan)).rename("grid_intensity_t_per_mwh")


# ── main ─────────────────────────────────────────────────────────────────────

def prepare() -> pd.DataFrame:
    df = pd.read_csv(C.PANEL_CSV, index_col=0, parse_dates=True)
    df = df.loc[C.SAMPLE_START:C.SAMPLE_END]

    df = add_calendar(df)
    df = label_subperiods(df)

    # residual load (ČEPS series; ENTSO-E variant for robustness)
    df["residual_load_mw"] = (df["ceps_load_zatížení_mw"]
                              - df["ceps_res_fve_mw"] - df["ceps_res_vte_mw"])
    df["residual_load_entsoe_mw"] = (df["entsoe_load_Actual Load"]
                                     - df["entsoe_gen_solar"] - df["entsoe_gen_wind_onshore"])
    df["solar_mw"] = df["ceps_res_fve_mw"]

    # surplus indicators
    p = df["ote_price_eur_mwh"]
    df["surplus"] = (p < C.SURPLUS_THRESHOLD_EUR).astype(int)
    for thr in C.SURPLUS_THRESHOLD_VARIANTS:
        df[f"surplus_lt{int(thr)}"] = (p < thr).astype(int)

    # deseasonalised price
    df["price_seasonal"] = fit_seasonal_component(df, "ote_price_eur_mwh")
    df["price_deseason"] = p - df["price_seasonal"]

    # hourly grid emission intensity
    df["grid_intensity_t_per_mwh"] = grid_emission_intensity(df)

    df.to_csv(C.PREPARED_CSV)
    print(f"prepared dataset: {df.shape[0]:,} rows x {df.shape[1]} cols -> {C.PREPARED_CSV}")
    print(df[["ote_price_eur_mwh", "residual_load_mw", "surplus",
              "price_deseason", "grid_intensity_t_per_mwh"]].describe().round(2))
    return df


def load_prepared() -> pd.DataFrame:
    """Used by downstream sub-scripts; rebuilds the dataset if missing."""
    if not C.PREPARED_CSV.exists():
        return prepare()
    return pd.read_csv(C.PREPARED_CSV, index_col=0, parse_dates=True)


if __name__ == "__main__":
    prepare()
