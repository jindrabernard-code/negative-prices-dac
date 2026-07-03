# Analysis pipeline — Regime dynamics of low/negative CZ prices × flexible DAC

Implements the calculations from the thesis methodology chapter (`thesis_draft.md`, ch. 4) plus the descriptive analysis (ch. 3.4). Input is the merged hourly panel `topic1_battery_arbitrage/data/topic1_panel.csv` (UTC, 2020–2024).

## Structure

| Script | Thesis section | What it does |
|---|---|---|
| `config.py` | — | all paths and parameters (DAC techno-economics, scenarios, thresholds); values marked `VERIFY` need sourcing in the text |
| `s0_data_prep.py` | §3.2–3.3 | residual load, surplus indicator, per-subperiod deseasonalisation, hourly grid CO₂ intensity |
| `s1_descriptives.py` | §3.4 | annual price/negative-hour tables, month×hour heatmap, duration curves, price–residual-load relation, block-length persistence |
| `s2_logit_baseline.py` | §4.1.1 | logit of surplus hours on residual load, clustered SEs, marginal effects, out-of-sample AUC/Brier |
| `s3_markov_switching.py` | §4.1.2 | homogeneous MS (statsmodels) + custom TVTP: Hamilton filter, L-BFGS MLE, Kim smoother, regime diagnostics, OOS validation |
| `s4_simulation.py` | §4.1.3, §4.2.3 | price paths simulated from the TVTP model; NECP solar scenarios shift residual load → RQ2 projection |
| `s5_dac_dispatch.py` | §4.2 | threshold policy, exact DP dispatch with min-up/down (≡ MILP), baseload; endogenous CF distributions |
| `s6_economics.py` | §4.3 | LCOC per path, break-even credit fixed point, LCOC × net-removal trade-off curve, hourly carbon accounting |
| `run_all.py` | — | orchestrator; `python run_all.py` or `python run_all.py s1 s4` |

## Run

```powershell
cd analysis
..\python_env\python312\python.exe run_all.py
```

Outputs go to `analysis/output/` (`tables/*.csv`, `figures/*.png`, `models/*.npz`). Everything is deterministic (seeds in `config.py`).

Dependencies: `pandas`, `numpy`, `scipy`, `statsmodels`, `matplotlib` (see repo `requirements.txt`).

## Methodological notes

- The **estimation window is the post-crisis subperiod** by default (`config.ESTIMATION_PERIOD`), so the surplus regime is not conflated with the 2022 crisis (structural risk §5.3 of the project instructions). Change to run subperiod robustness.
- TVTP is implemented manually because `statsmodels` does not support it; the homogeneous MS model serves as the verified anchor and initialiser.
- The dispatch DP is exactly equivalent to the MILP in §4.2.2 (deterministic, min-up/min-down) but requires no solver.
- Layer-C economics uses the threshold policy (optimal without min-run constraints); the min-run gap is quantified separately in `s5`.
- Scenario projections are **conditional statements, not forecasts** — the historical grid-intensity profile and the estimated TVTP link are held fixed outside the observed support (extrapolation risk §5.1, discussed in the thesis limits).
