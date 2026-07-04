# Regime dynamics of low/negative Czech electricity prices and flexible Direct Air Capture

This repository contains the **data, code, and results** for an empirical study of
when and why Czech day-ahead electricity prices fall to low or negative levels, and
what that implies for the economics and capacity factor of a **flexibly operated
Direct Air Capture (DAC)** plant that runs preferentially in cheap hours.

The work combines three layers:

1. **Econometrics** — identifying and modelling price regimes (a logit baseline for
   "surplus" hours and Markov-switching models with time-varying transition
   probabilities driven by residual load).
2. **Operations** — an optimal dispatch model (dynamic programming with
   minimum up/down constraints) that turns a price path into a DAC operating schedule
   and an endogenous capacity factor.
3. **Economics** — levelized cost of carbon (LCOC), break-even removal-credit prices,
   and the utilization vs. net-removal trade-off under hourly carbon accounting.

> **Source of truth.** The full methodology, derivations, assumptions, and
> interpretation of results live in the accompanying written draft, which is the
> authoritative reference for this work. That draft is **not** included in this
> repository; this repo holds only the reproducible data-and-code artifacts and the
> generated tables and figures it references.

## Repository layout

```
.
├── data/
│   ├── cz_power_panel.csv        # merged hourly panel, 43,848 × 51, UTC, 2020–2024
│   └── DATA_LEGEND.md            # full variable-level data dictionary
├── scripts/
│   ├── collection/              # download raw sources + build the panel
│   │   ├── collect_data.py
│   │   ├── build_panel.py
│   │   └── README_data_collection.md
│   ├── analysis/                # the analysis pipeline s0–s6
│   │   ├── config.py            # all paths & parameters (single source of settings)
│   │   ├── s0_data_prep.py … s6_economics.py
│   │   ├── run_all.py           # orchestrator
│   │   └── README_analysis.md
│   └── inspect_panel.py         # quick descriptive check of the panel
├── figures/                     # generated figures (PNG) used by the write-up
├── tables/                      # generated result tables (CSV)
├── requirements.txt
└── .env.example                 # template for ENTSO-E and Copernicus CDS API keys
```

## Data

A single merged hourly panel (`data/cz_power_panel.csv`) covering the Czech power
market and associated weather for 2020–2024, built from four public sources — **OTE**
(day-ahead prices), **ENTSO-E** (prices, load, generation per type, imbalance),
**ČEPS** (load, generation mix, cross-border flows, imbalance), and **ERA5** weather
reanalysis. Every column, unit, range, and caveat is documented in
[`data/DATA_LEGEND.md`](data/DATA_LEGEND.md).

## Analysis pipeline

The pipeline in `scripts/analysis/` runs in dependency order (`s0` → `s6`); see
[`scripts/analysis/README_analysis.md`](scripts/analysis/README_analysis.md) for the
per-script detail.

| Script | What it produces |
|---|---|
| `s0_data_prep.py` | residual load, surplus indicator, per-subperiod deseasonalisation, hourly grid CO₂ intensity |
| `s1_descriptives.py` | descriptive tables & figures (price trends, negative-hour patterns, duration curves) |
| `s2_logit_baseline.py` | logit model of surplus hours + marginal effects + out-of-sample scores |
| `s3_markov_switching.py` | homogeneous and TVTP Markov-switching models (Hamilton filter, Kim smoother) |
| `s4_simulation.py` | simulated price paths under PV build-out scenarios |
| `s5_dac_dispatch.py` | DAC dispatch policies and endogenous capacity-factor distributions |
| `s6_economics.py` | LCOC, break-even credit price, utilization vs. net-removal trade-off |

## Reproducing everything

```powershell
pip install -r requirements.txt          # pandas, numpy, scipy, statsmodels, matplotlib, numba

# 1) (optional) rebuild the panel from raw sources — needs API keys in .env
python scripts/collection/collect_data.py
python scripts/collection/build_panel.py

# 2) run the full analysis on the shipped panel (~2 min, deterministic)
python scripts/analysis/run_all.py
```

Step 2 alone reproduces every table in `tables/` and figure in `figures/` from the
shipped `data/cz_power_panel.csv`; step 1 is only needed to regenerate the panel
itself. All randomness is seeded (see `scripts/analysis/config.py`).

## Requirements & keys

- Python 3.12; dependencies in `requirements.txt`.
- API keys (only needed for the data-collection step) go in a local `.env`; see
  `.env.example` and the collection README for how to obtain the ENTSO-E and
  Copernicus CDS tokens. OTE and ČEPS need no key.

## Notes & open items

- DAC techno-economic parameters (`config.py`) are a working set; CAPEX/WACC
  sensitivity and literature anchoring are tracked in the written draft.
- The Markov-switching estimation window defaults to the post-crisis subperiod so the
  surplus regime is not conflated with the 2022 energy-crisis level shift.
- Scenario projections are conditional statements, not forecasts — see the draft's
  limitations for the extrapolation and carbon-accounting caveats.
