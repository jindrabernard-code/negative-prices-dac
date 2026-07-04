"""
config.py — central configuration for the analysis pipeline.

All tunable parameters live here so that individual sub-scripts stay free of
magic numbers. Values marked VERIFY are working assumptions that are
justified (and possibly updated) in the accompanying draft.
"""
from pathlib import Path

# ── paths ─────────────────────────────────────────────────────────────────────
# ROOT is the repository root (the folder that contains data/, scripts/, ...).
ROOT = Path(__file__).resolve().parents[2]
PANEL_CSV = ROOT / "data" / "cz_power_panel.csv"

OUT_DIR = Path(__file__).resolve().parent / "output"
TAB_DIR = OUT_DIR / "tables"
FIG_DIR = OUT_DIR / "figures"
MOD_DIR = OUT_DIR / "models"
for d in (TAB_DIR, FIG_DIR, MOD_DIR):
    d.mkdir(parents=True, exist_ok=True)

PREPARED_CSV = OUT_DIR / "prepared_dataset.csv"

# ── sample definition ─────────────────────────────────────────────────────────
SAMPLE_START = "2020-01-01"
SAMPLE_END = "2024-12-31"

# Structural-break subperiods (energy crisis 2021–2023). VERIFY exact dating
# in the text; robustness section should vary these boundaries.
SUBPERIODS = {
    "pre_crisis": ("2020-01-01", "2021-06-30"),
    "crisis": ("2021-07-01", "2023-03-31"),
    "post_crisis": ("2023-04-01", "2024-12-31"),
}

# Estimation sample for the regime models: post-crisis by default, so that the
# surplus regime is not conflated with the crisis level shift (§5 risk 3).
ESTIMATION_PERIOD = "post_crisis"

# Out-of-sample holdout (within the estimation period) for validation.
HOLDOUT_START = "2024-07-01"

# ── surplus-hour definition ───────────────────────────────────────────────────
SURPLUS_THRESHOLD_EUR = 0.0          # headline: negative price
SURPLUS_THRESHOLD_VARIANTS = [5.0, 20.0]

# ── deseasonalisation ─────────────────────────────────────────────────────────
N_FOURIER_ANNUAL = 3                 # pairs of sin/cos terms for the annual cycle

# ── Markov-switching model ────────────────────────────────────────────────────
MS_N_REGIMES = 3                     # surplus / normal / spike
MS_MAX_ITER = 500
MS_SEED = 42

# ── simulation (layer B input) ────────────────────────────────────────────────
N_SIM_PATHS = 200                    # price paths per scenario
SIM_SEED = 123

# PV build-out scenarios: multiplicative scaling of the hourly solar infeed
# profile relative to the estimation sample. VERIFY against NECP (~10 GW PV by
# 2030 vs ~4.7 GW installed in 2026 → central 2030 factor ≈ 2.0–2.2 relative
# to 2024 infeed; 2035 extrapolated). Framed strictly as scenarios.
SOLAR_SCENARIOS = {
    "today": 1.0,
    "necp_2030_low": 1.6,
    "necp_2030_central": 2.1,
    "necp_2030_high": 2.6,
    "necp_2035_central": 3.0,
}

# ── DAC techno-economics (layer B/C). All VERIFY — solid-sorbent working set. ─
DAC = {
    "power_mw": 10.0,                # rated electrical power P
    "el_mwh_per_t": 0.5,             # e: specific electricity use   [MWh_el/tCO2]
    "heat_mwh_per_t": 1.7,           # h: specific heat demand       [MWh_th/tCO2]
    "heat_price_eur_mwh": 30.0,      # p_heat (parameter, no heat-market model)
    "capex_eur_per_tpy": 1500.0,     # specific CAPEX per t/yr nameplate capacity
    "fom_share_of_capex": 0.04,      # fixed O&M as share of CAPEX per year
    "var_opex_eur_per_t": 20.0,      # c_v: non-energy variable cost [EUR/tCO2]
    "lifetime_years": 20,
    "wacc": 0.07,
    "min_up_hours": 3,               # sorbent-cycle inertia
    "min_down_hours": 2,
}

# Removal-credit price grid for the break-even search [EUR/tCO2].
CREDIT_PRICE_GRID = [100, 200, 300, 400, 500, 600, 800, 1000, 1200, 1500]

# ── hourly grid emission intensity (layer C) ─────────────────────────────────
# Operational (combustion) emission factors, tCO2 per MWh electricity.
# VERIFY against literature (e.g. IPCC/EEA factors + plant efficiencies).
EMISSION_FACTORS = {
    "entsoe_gen_fossil_brown_coal_lignite": 1.06,
    "entsoe_gen_fossil_hard_coal": 0.87,
    "entsoe_gen_fossil_gas": 0.36,
    "entsoe_gen_fossil_coal-derived_gas": 1.40,
    "entsoe_gen_fossil_oil": 0.65,
    "entsoe_gen_waste": 0.26,
    "entsoe_gen_biomass": 0.0,       # biogenic, treated as neutral (discuss in limits)
    "entsoe_gen_nuclear": 0.0,
    "entsoe_gen_solar": 0.0,
    "entsoe_gen_wind_onshore": 0.0,
    "entsoe_gen_hydro_pumped_storage": 0.0,
    "entsoe_gen_hydro_run-of-river_and_poundage": 0.0,
    "entsoe_gen_hydro_water_reservoir": 0.0,
    "entsoe_gen_other": 0.30,
    "entsoe_gen_other_renewable": 0.0,
}
HEAT_EMISSION_FACTOR = 0.20          # tCO2/MWh_th for the heat source. VERIFY.
