"""
s6_economics.py — economic evaluation: LCOC, break-even credit price and the
LCOC × net-removal trade-off curve (draft §4.3).

  LCOC = (CAPEX·CRF + FOM + C_el + C_heat) / Q,   Q = CF·T·P/e  (endogenous)
  CRF  = r(1+r)^n / ((1+r)^n − 1)

  Break-even: π* solves LCOC(π*) = π* — a fixed point, because the dispatch
  threshold p̄_DAC(π) determines CF, C_el and Q. Solved by scanning the credit
  grid and interpolating the crossing.

  Time-resolved carbon accounting (§4.3.3):
  Q_net = Q − Σ_t u_t (P·ε_t^grid + (P·h/e)·ε_heat),
  ε_t^grid = hourly generation-weighted CZ intensity of the base year.
  (Scenario limitation: historical intensity profile is retained across PV
  scenarios; flagged in the draft limitations.)

Uses the threshold policy (exactly optimal without min-run constraints; s5
quantifies the min-run gap separately).

Outputs:
  tables/lcoc_by_credit_price.csv
  tables/breakeven_by_scenario.csv
  tables/tradeoff_curve.csv
  figures/fig_lcoc_fixed_point.png
  figures/fig_tradeoff_curve.png

Run:  python analysis/s6_economics.py
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config as C
from s0_data_prep import load_prepared
from s5_dac_dispatch import wtp_threshold, dispatch_threshold

D = C.DAC


def capital_costs() -> tuple[float, float]:
    """(annualised CAPEX, fixed O&M) in EUR/year."""
    nameplate_tpy = D["power_mw"] / D["el_mwh_per_t"] * 8760
    capex_total = D["capex_eur_per_tpy"] * nameplate_tpy
    r, n = D["wacc"], D["lifetime_years"]
    crf = r * (1 + r) ** n / ((1 + r) ** n - 1)
    return capex_total * crf, capex_total * D["fom_share_of_capex"]


def lcoc_paths(prices: np.ndarray, u: np.ndarray) -> np.ndarray:
    """LCOC per simulated path [EUR/tCO2]; inf when the plant never runs."""
    capex_ann, fom = capital_costs()
    P_mw = D["power_mw"]
    q = u.sum(axis=1) * P_mw / D["el_mwh_per_t"]            # tCO2 per path
    c_el = (u * prices).sum(axis=1) * P_mw
    c_heat = q * D["heat_mwh_per_t"] * D["heat_price_eur_mwh"]
    c_var = q * D["var_opex_eur_per_t"]
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(q > 0, (capex_ann + fom + c_el + c_heat + c_var) / q, np.inf)


def net_removals(u: np.ndarray, eps_grid: np.ndarray) -> np.ndarray:
    """Q_net per path [tCO2/yr], hourly grid intensity + heat footprint."""
    P_mw = D["power_mw"]
    q = u.sum(axis=1) * P_mw / D["el_mwh_per_t"]
    el_emis = (u * eps_grid[None, :]).sum(axis=1) * P_mw
    heat_emis = q * D["heat_mwh_per_t"] * C.HEAT_EMISSION_FACTOR
    return q - el_emis - heat_emis


def main():
    df = load_prepared()

    rows, be_rows = [], []
    for name in C.SOLAR_SCENARIOS:
        f = np.load(C.MOD_DIR / f"sim_paths_{name}.npz")
        prices = f["prices"].astype(np.float64)
        idx = pd.to_datetime(f["index"].astype("int64"))
        eps_grid = (df.loc[idx, "grid_intensity_t_per_mwh"]
                    .ffill().fillna(0.0).values)

        med_lcoc = {}
        for credit in C.CREDIT_PRICE_GRID:
            p_bar = wtp_threshold(credit)
            u = dispatch_threshold(prices, p_bar)
            lc = lcoc_paths(prices, u)
            qn = net_removals(u, eps_grid)
            finite = np.isfinite(lc)
            med = np.median(lc[finite]) if finite.any() else np.inf
            med_lcoc[credit] = med
            rows.append({
                "scenario": name, "credit_eur_t": credit, "p_bar_eur_mwh": p_bar,
                "CF_mean": u.mean(),
                "LCOC_median": med,
                "LCOC_p05": np.quantile(lc[finite], 0.05) if finite.any() else np.inf,
                "LCOC_p95": np.quantile(lc[finite], 0.95) if finite.any() else np.inf,
                "net_removals_mean_t": qn.mean(),
                "net_share_of_gross": (qn.mean()
                                       / max((u.sum(axis=1).mean()
                                              * D["power_mw"] / D["el_mwh_per_t"]), 1e-9)),
            })

        # break-even: crossing of LCOC(π) with the 45° line
        grid = np.array(C.CREDIT_PRICE_GRID, dtype=float)
        lcs = np.array([med_lcoc[c] for c in grid])
        diff = lcs - grid
        be = np.nan
        for i in range(len(grid) - 1):
            if np.isfinite(diff[i]) and np.isfinite(diff[i + 1]) \
                    and diff[i] > 0 >= diff[i + 1]:
                be = grid[i] + (grid[i + 1] - grid[i]) * diff[i] / (diff[i] - diff[i + 1])
                break
        be_rows.append({"scenario": name, "breakeven_credit_eur_t": be})
        print(f"  {name:22s} break-even ≈ "
              f"{be:.0f} EUR/t" if np.isfinite(be) else
              f"  {name:22s} break-even outside grid {grid[0]:.0f}–{grid[-1]:.0f}")

    tab = pd.DataFrame(rows).round(3)
    tab.to_csv(C.TAB_DIR / "lcoc_by_credit_price.csv", index=False)
    pd.DataFrame(be_rows).round(1).to_csv(
        C.TAB_DIR / "breakeven_by_scenario.csv", index=False)

    # ── trade-off curve: LCOC and net removals vs operating threshold ────────
    f = np.load(C.MOD_DIR / "sim_paths_today.npz")
    prices = f["prices"].astype(np.float64)
    idx = pd.to_datetime(f["index"].astype("int64"))
    eps_grid = df.loc[idx, "grid_intensity_t_per_mwh"].ffill().fillna(0.0).values
    thr_grid = np.arange(-20, 261, 10.0)
    to_rows = []
    for p_bar in thr_grid:
        u = dispatch_threshold(prices, p_bar)
        lc = lcoc_paths(prices, u)
        qn = net_removals(u, eps_grid)
        finite = np.isfinite(lc)
        to_rows.append({
            "p_bar_eur_mwh": p_bar,
            "CF_mean": u.mean(),
            "LCOC_median": np.median(lc[finite]) if finite.any() else np.inf,
            "net_removals_mean_t": qn.mean(),
            "cost_per_net_t": (np.median(lc[finite]) * u.sum(axis=1).mean()
                               * D["power_mw"] / D["el_mwh_per_t"] / max(qn.mean(), 1e-9))
            if finite.any() else np.inf,
        })
    to = pd.DataFrame(to_rows).round(3)
    to.to_csv(C.TAB_DIR / "tradeoff_curve.csv", index=False)

    # ── figures ───────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(7.5, 5))
    for name, g in tab.groupby("scenario"):
        ax.plot(g["credit_eur_t"], g["LCOC_median"], "o-", ms=3, label=name)
    lim = [0, max(C.CREDIT_PRICE_GRID)]
    ax.plot(lim, lim, "k--", lw=1, label="45° (break-even)")
    ax.set_xlabel("removal-credit price π [EUR/tCO₂]")
    ax.set_ylabel("median LCOC [EUR/tCO₂]")
    ax.set_ylim(0, 3000)
    ax.set_title("LCOC(π) and the break-even fixed point")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(C.FIG_DIR / "fig_lcoc_fixed_point.png", dpi=150)
    plt.close(fig)

    fig, ax1 = plt.subplots(figsize=(7.5, 5))
    ax1.plot(to["p_bar_eur_mwh"], to["LCOC_median"], "o-", ms=3,
             color="tab:blue", label="median LCOC")
    ax1.set_xlabel("operating threshold p̄ [EUR/MWh]")
    ax1.set_ylabel("median LCOC [EUR/tCO₂]", color="tab:blue")
    ax1.set_ylim(0, 3000)
    ax2 = ax1.twinx()
    ax2.plot(to["p_bar_eur_mwh"], to["net_removals_mean_t"], "s-", ms=3,
             color="tab:green", label="net removals")
    ax2.set_ylabel("net removals [tCO₂/yr]", color="tab:green")
    ax1.set_title("Trade-off: LCOC vs net removals as the operating threshold rises\n"
                  "('today' scenario)")
    fig.tight_layout()
    fig.savefig(C.FIG_DIR / "fig_tradeoff_curve.png", dpi=150)
    plt.close(fig)

    print(f"\ntables  -> {C.TAB_DIR}\nfigures -> {C.FIG_DIR}")


if __name__ == "__main__":
    main()
