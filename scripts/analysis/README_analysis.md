# Analysis pipeline — Regime dynamics of low/negative CZ prices × flexible DAC

Implements the calculations plus the descriptive analysis. Input is the merged hourly panel `topic1_battery_arbitrage/data/topic1_panel.csv`.

## Structure

| Script | What it does |
|---|---|
| `config.py` | all paths and parameters (DAC techno-economics, scenarios, thresholds); values marked `VERIFY` need sourcing in the text |
| `s0_data_prep.py` | residual load, surplus indicator, per-subperiod deseasonalisation, hourly grid CO₂ intensity |
| `s1_descriptives.py` | annual price/negative-hour tables, month×hour heatmap, duration curves, price–residual-load relation, block-length persistence |
| `s2_logit_baseline.py` | logit of surplus hours on residual load, clustered SEs, marginal effects, out-of-sample AUC/Brier |
| `s3_markov_switching.py` | homogeneous MS (statsmodels) + custom TVTP: Hamilton filter, L-BFGS MLE, Kim smoother, regime diagnostics, OOS validation |
| `s4_simulation.py` | price paths simulated from the TVTP model; NECP solar scenarios shift residual load → RQ2 projection |
| `s5_dac_dispatch.py` | threshold policy, exact DP dispatch with min-up/down (≡ MILP), baseload; endogenous CF distributions |
| `s6_economics.py` | LCOC per path, break-even credit fixed point, LCOC × net-removal trade-off curve, hourly carbon accounting |
| `run_all.py` | orchestrator; `python run_all.py` or `python run_all.py s1 s4` |

## Run

```powershell
cd analysis
..\python_env\python312\python.exe run_all.py
```

Outputs go to `analysis/output/` (`tables/*.csv`, `figures/*.png`, `models/*.npz`). Everything is deterministic (seeds in `config.py`).


