# Master Thesis — Regime Dynamics of Low/Negative CZ Electricity Prices × Flexible DAC

Self-contained thesis folder. Everything needed to reproduce and extend the analysis lives here; originals remain in their source locations (`topic1_battery_arbitrage/`, `analysis/`, workspace root) — files here are copies.

## Main documents

| File | Description |
|---|---|
| `thesis_draft_full.md` / `.docx` | **The current complete draft (ch. 1–9)** — merged from the ch. 1–4 text and the results chapters, with embedded figures. **Not published to the public GitHub repository** (excluded via `.gitignore`); it stays local only. |
| `instrukce_projekt_rezimy_dac_lcoc.md` | Project charter / truth source (topic, RQs, methodology, scope control) |

Earlier partial/superseded draft versions (`thesis_draft_ch1-4.*`, `archive/thesis_draft.*`) have been removed; this is the only draft kept going forward.

## Results

| Folder | Contents |
|---|---|
| `figures/` | All 15 generated figures (PNG) referenced by the draft |
| `tables/` | All result tables (CSV): descriptives, logit, Markov-switching, scenarios, dispatch benchmarks, LCOC/break-even, trade-off curve |

## Reproducibility

| Item | Contents |
|---|---|
| `data/topic1_panel.csv` | Merged hourly panel 2020–2024 (43,848 h × 51 vars, UTC) — the single input of the analysis |
| `data/DATA_LEGEND.md` | Full variable-level documentation of all data sources |
| `scripts/collection/` | `collect_data.py` (OTE, ENTSO-E, ČEPS, ERA5 downloads), `build_panel.py` (timezone-harmonised panel builder) |
| `scripts/analysis/` | The full analysis pipeline `s0`–`s6` + `config.py` + `run_all.py` (see `README_analysis.md`) |
| `scripts/inspect_panel.py` | Quick descriptive check of the panel |
| `requirements.txt`, `.env.example` | Python dependencies and API-key template (ENTSO-E, Copernicus CDS) |

### Rebuilding everything from scratch

```powershell
pip install -r requirements.txt        # + statsmodels, matplotlib, numba
python scripts/collection/collect_data.py   # downloads raw data (~30 min, needs API keys)
python scripts/collection/build_panel.py    # builds the hourly panel
python scripts/analysis/run_all.py          # runs the full analysis (~2 min)
```

Note: the analysis scripts read the panel from the original repository path (`topic1_battery_arbitrage/data/topic1_panel.csv`, see `scripts/analysis/config.py`); the copy in `data/` here is for archival completeness.

## Status / open items for the final version

- Anchor the DAC techno-economic parameter set (Table 7.1) in literature; add CAPEX/WACC sensitivity.
- Re-estimate the MS model with seasonality in regime-dependent means (level-based regimes) — see §5.3 caveat.
- Marginal (not average) emission-intensity variant of the carbon accounting; low-carbon heat variant.
- Extend the sample through 2025; finalise press-release citations per ESF MU template.
