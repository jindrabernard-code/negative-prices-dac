"""
s5_dac_dispatch.py — operational model of flexible DAC dispatch (draft §4.2).

Policies evaluated on the simulated price paths from s4:

  * threshold  : u_t = 1{p_t < p̄_DAC}, the exactly-optimal policy absent
                 min-run constraints (§4.2.2);
  * optimal    : profit-maximising dispatch WITH minimum up/down times, solved
                 exactly by backward dynamic programming over the state
                 (on/off, hours in state) — equivalent to the MILP of §4.2.2
                 but faster and solver-free; since day-ahead prices are known
                 when committing, this coincides with perfect foresight;
  * baseload   : u_t = 1 always.

The willingness-to-pay threshold (bridge to layer C):
    p̄_DAC = (π − c_v)/e − (h/e)·p_heat

Outputs:
  tables/dispatch_benchmarks.csv   CF / profit / mean electricity price paid,
                                   by scenario × policy (at reference π)
  figures/fig_cf_distribution.png  capacity-factor distributions
  figures/fig_dispatch_week.png    dispatch decisions in a sample week

Run:  python analysis/s5_dac_dispatch.py
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config as C

# Reference credit for the benchmark table/figures. Chosen so that the implied
# willingness-to-pay threshold lies INSIDE the price distribution (with the
# config working set: (100-20)/0.5 - (1.7/0.5)*30 = 58 EUR/MWh) — otherwise
# the dispatch degenerates to baseload and the benchmark comparison is empty.
# The full credit grid is scanned in s6.
REFERENCE_CREDIT = 100.0    # EUR/tCO2


def wtp_threshold(credit_price: float) -> float:
    D = C.DAC
    return ((credit_price - D["var_opex_eur_per_t"]) / D["el_mwh_per_t"]
            - (D["heat_mwh_per_t"] / D["el_mwh_per_t"]) * D["heat_price_eur_mwh"])


def dispatch_threshold(prices: np.ndarray, p_bar: float) -> np.ndarray:
    """u (paths × T), no min-run constraints."""
    return (prices < p_bar).astype(np.int8)


def dispatch_dp(prices: np.ndarray, p_bar: float,
                tau_on: int, tau_off: int) -> np.ndarray:
    """Exact optimal dispatch with min-up/min-down via backward DP,
    vectorised across paths. Hourly reward when on: P·(p̄ − p_t)."""
    P_mw = C.DAC["power_mw"]
    reward = P_mw * (p_bar - prices)                       # (n, T)
    n, T = prices.shape
    # states: 0..tau_on-1 = on for (k+1) hours (k<tau_on-1 forced on),
    #         tau_on..tau_on+tau_off-1 = off for (k+1) hours
    S = tau_on + tau_off
    NEG = -1e18
    V = np.zeros((S, n))
    choice = np.zeros((T, S, n), dtype=np.int8)            # 1 = be ON next
    for t in range(T - 1, -1, -1):
        Vn = np.full((S, n), NEG)
        ch = np.zeros((S, n), dtype=np.int8)
        for s in range(S):
            if s < tau_on:                                  # currently ON
                stay = reward[:, t] * 0 + V[min(s + 1, tau_on - 1)]
                on_val = reward[:, t] + V[min(s + 1, tau_on - 1)]
                if s < tau_on - 1:                          # forced on
                    Vn[s], ch[s] = on_val, 1
                else:                                       # free: stay on or switch off
                    off_val = V[tau_on]                     # first off state
                    go_on = on_val >= off_val
                    Vn[s] = np.where(go_on, on_val, off_val)
                    ch[s] = go_on.astype(np.int8)
            else:                                           # currently OFF
                k = s - tau_on
                off_val = V[min(s + 1, S - 1)]
                if k < tau_off - 1:                         # forced off
                    Vn[s], ch[s] = off_val, 0
                else:                                       # free: stay off or start
                    on_val = reward[:, t] + V[0]
                    go_on = on_val > off_val
                    Vn[s] = np.where(go_on, on_val, off_val)
                    ch[s] = go_on.astype(np.int8)
        V = Vn
        choice[t] = ch

    # forward pass to recover u
    u = np.zeros((n, T), dtype=np.int8)
    state = np.full(n, S - 1)                               # start OFF and free
    for t in range(T):
        on = choice[t][state, np.arange(n)] == 1
        u[:, t] = on
        was_on = state < tau_on
        state = np.where(
            on, np.where(was_on, np.minimum(state + 1, tau_on - 1), 0),
            np.where(was_on, tau_on, np.minimum(state + 1, S - 1)))
    return u


def evaluate(u: np.ndarray, prices: np.ndarray, p_bar: float) -> dict:
    P_mw = C.DAC["power_mw"]
    cf = u.mean(axis=1)
    el_cost = (u * prices).sum(axis=1) * P_mw               # EUR per path-year
    mwh = u.sum(axis=1) * P_mw
    profit = (P_mw * (p_bar - prices) * u).sum(axis=1)
    return {
        "CF_mean": cf.mean(), "CF_p05": np.quantile(cf, 0.05),
        "CF_p95": np.quantile(cf, 0.95),
        "mean_el_price_paid": np.nansum(el_cost) / np.nansum(mwh),
        "profit_mean_keur": profit.mean() / 1e3,
    }


def main():
    p_bar = wtp_threshold(REFERENCE_CREDIT)
    D = C.DAC
    print(f"reference credit {REFERENCE_CREDIT} EUR/t -> "
          f"willingness to pay p̄_DAC = {p_bar:.1f} EUR/MWh")

    rows = []
    cf_dists = {}
    for name in C.SOLAR_SCENARIOS:
        f = np.load(C.MOD_DIR / f"sim_paths_{name}.npz")
        prices = f["prices"].astype(np.float64)

        u_thr = dispatch_threshold(prices, p_bar)
        u_opt = dispatch_dp(prices, p_bar, D["min_up_hours"], D["min_down_hours"])
        u_base = np.ones_like(u_thr)

        for policy, u in [("threshold", u_thr), ("optimal_minrun", u_opt),
                          ("baseload", u_base)]:
            r = {"scenario": name, "policy": policy, **evaluate(u, prices, p_bar)}
            rows.append(r)
        cf_dists[name] = u_opt.mean(axis=1)
        print(f"  {name:22s} CF(threshold)={u_thr.mean():.3f} "
              f"CF(optimal)={u_opt.mean():.3f}")

    tab = pd.DataFrame(rows).set_index(["scenario", "policy"]).round(4)
    tab.to_csv(C.TAB_DIR / "dispatch_benchmarks.csv")
    print("\n== dispatch benchmarks (π = 500 EUR/t) ==\n", tab)

    # ── figures ───────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for name, cf in cf_dists.items():
        ax.hist(cf, bins=30, alpha=0.5, label=name, density=True)
    ax.set_xlabel("capacity factor (optimal policy)")
    ax.set_ylabel("density")
    ax.set_title(f"Endogenous capacity-factor distribution (π = {REFERENCE_CREDIT:.0f} EUR/t)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(C.FIG_DIR / "fig_cf_distribution.png", dpi=150)
    plt.close(fig)

    # sample dispatch week (first path, today scenario)
    f = np.load(C.MOD_DIR / "sim_paths_today.npz")
    prices = f["prices"][0].astype(np.float64)
    wk = slice(24 * 120, 24 * 127)
    u = dispatch_dp(prices[None, :], p_bar, D["min_up_hours"], D["min_down_hours"])[0]
    fig, ax = plt.subplots(figsize=(12, 4))
    t = np.arange(len(prices))[wk]
    ax.plot(t, prices[wk], "k-", lw=1, label="price")
    ax.axhline(p_bar, color="tab:blue", ls="--", lw=1, label="p̄_DAC")
    on = u[wk].astype(bool)
    ax.fill_between(t, prices[wk].min() - 10, prices[wk].max() + 10, where=on,
                    color="tab:green", alpha=0.2, label="DAC running")
    ax.set_xlabel("hour of year")
    ax.set_ylabel("EUR/MWh")
    ax.set_title("Dispatch in a sample simulated week (May, 'today' scenario)")
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    fig.savefig(C.FIG_DIR / "fig_dispatch_week.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
