"""
s4_simulation.py — price-path simulation from the estimated TVTP model
(draft §4.2.3) and scenario projection of the surplus regime (§4.1.3, RQ2).

Design:
  * base year = last full calendar year of the estimation sample (2024):
    its hourly load, wind and seasonal price component are reused so the
    diurnal/seasonal structure of the conditioning variable is preserved;
  * scenarios scale the hourly solar infeed by the NECP-derived factors in
    config.SOLAR_SCENARIOS, shift the residual-load distribution, and hence
    the TVTP transition probabilities — framed strictly as "if the trajectory
    materialises and the estimated relationship remains stable";
  * for each scenario, N_SIM_PATHS regime paths are drawn from the TVTP chain,
    prices from the regime-conditional Gaussians, and the deterministic
    seasonal component is re-added.

Outputs:
  models/sim_paths_<scenario>.npz      simulated price matrices (paths × hours)
  tables/sim_scenario_summary.csv      implied surplus-regime and negative-hour
                                       frequencies per scenario (RQ2 answer)
  figures/fig_sim_price_sample.png
  figures/fig_scenario_surplus_freq.png

Run:  python analysis/s4_simulation.py
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config as C
from s0_data_prep import load_prepared
from s3_markov_switching import transition_matrices

BASE_YEAR = 2024


def load_model():
    f = np.load(C.MOD_DIR / "tvtp_params.npz")
    return (f["mu"], f["sigma"], f["gamma0"], f["gamma1"],
            float(f["z_mean"]), float(f["z_std"]), int(f["K"]))


def scenario_residual_load(base: pd.DataFrame, solar_factor: float) -> np.ndarray:
    return (base["ceps_load_zatížení_mw"]
            - solar_factor * base["ceps_res_fve_mw"]
            - base["ceps_res_vte_mw"]).values


def simulate_paths(z_std_series, mu, sigma, g0, g1, K, n_paths, seed):
    """Draw regime and price paths given the (scenario) conditioning series."""
    rng = np.random.default_rng(seed)
    T = len(z_std_series)
    P = transition_matrices(g0, g1, z_std_series)          # (T, K, K)
    cumP = P.cumsum(axis=2)

    regimes = np.empty((n_paths, T), dtype=np.int8)
    s = rng.integers(0, K, size=n_paths)
    u = rng.random((n_paths, T))
    for t in range(T):
        s = (u[:, t, None] > cumP[t][s]).sum(axis=1)       # inverse-CDF draw
        regimes[:, t] = s

    eps = rng.standard_normal((n_paths, T))
    prices_deseason = mu[regimes] + sigma[regimes] * eps
    return regimes, prices_deseason


def main():
    df = load_prepared()
    mu, sigma, g0, g1, z_mean, z_std, K = load_model()

    base = df[df["year"] == BASE_YEAR].dropna(
        subset=["ceps_load_zatížení_mw", "ceps_res_fve_mw", "ceps_res_vte_mw",
                "price_seasonal"])
    seasonal = base["price_seasonal"].values
    T = len(base)
    print(f"base year {BASE_YEAR}: {T:,} hours, "
          f"{C.N_SIM_PATHS} paths x {len(C.SOLAR_SCENARIOS)} scenarios")

    summary = []
    sample_paths = {}
    for i, (name, factor) in enumerate(C.SOLAR_SCENARIOS.items()):
        R = scenario_residual_load(base, factor)
        z = np.roll((R - z_mean) / z_std, 1); z[0] = z[1]

        regimes, p_des = simulate_paths(z, mu, sigma, g0, g1, K,
                                        C.N_SIM_PATHS, C.SIM_SEED + i)
        prices = (p_des + seasonal[None, :]).astype(np.float32)

        np.savez_compressed(C.MOD_DIR / f"sim_paths_{name}.npz",
                            prices=prices, regimes=regimes,
                            index=base.index.values.astype("datetime64[ns]").astype("int64"))
        surplus_share = (regimes == 0).mean()
        neg_share = (prices < 0).mean()
        summary.append({
            "scenario": name, "solar_factor": factor,
            "mean_residual_load_mw": R.mean(),
            "share_hours_resload_lt_min": (R < R.min() if factor == 1.0
                                           else R < scenario_residual_load(base, 1.0).min()).mean(),
            "surplus_regime_share": surplus_share,
            "expected_surplus_hours_per_year": surplus_share * T,
            "negative_price_share": neg_share,
            "expected_negative_hours_per_year": neg_share * T,
            "mean_price": float(prices.mean()),
        })
        sample_paths[name] = prices[0]
        print(f"  {name:22s} factor={factor:.1f}  surplus regime "
              f"{surplus_share:6.2%}  negative prices {neg_share:6.2%}")

    tab = pd.DataFrame(summary).set_index("scenario").round(4)
    tab.to_csv(C.TAB_DIR / "sim_scenario_summary.csv")
    print("\n== scenario summary (RQ2) ==\n",
          tab[["surplus_regime_share", "expected_negative_hours_per_year",
               "mean_price"]])

    # ── figures ───────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(12, 4))
    wk = slice(24 * 120, 24 * 127)                          # a week in May
    ax.plot(base.index[wk], base["ote_price_eur_mwh"].values[wk],
            "k-", lw=1.5, label=f"observed {BASE_YEAR}")
    for name in ["today", "necp_2030_central"]:
        ax.plot(base.index[wk], sample_paths[name][wk], lw=0.9, alpha=0.8,
                label=f"simulated ({name})")
    ax.axhline(0, color="grey", lw=0.7)
    ax.set_ylabel("EUR/MWh")
    ax.set_title("Observed vs simulated price paths — sample week in May")
    ax.legend()
    fig.tight_layout()
    fig.savefig(C.FIG_DIR / "fig_sim_price_sample.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(tab.index, tab["expected_negative_hours_per_year"], color="crimson", alpha=0.8)
    ax.set_ylabel("expected negative-price hours / year")
    ax.set_title("Projected negative-price hours by PV scenario (conditional, not a forecast)")
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    fig.savefig(C.FIG_DIR / "fig_scenario_surplus_freq.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
