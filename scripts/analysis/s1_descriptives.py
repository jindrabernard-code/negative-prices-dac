"""
s1_descriptives.py — descriptive analysis (draft §3.4).

Produces the tables and figures that document the two motivating facts:
(i) the 2021–2023 crisis structural break, (ii) the acceleration of
negative-price hours in lockstep with solar build-out.

Outputs (analysis/output/):
  tables/desc_price_by_year.csv        annual price stats + negative hours + max FVE
  tables/desc_neg_by_month_hour.csv    negative-hour counts month × hour
  tables/desc_neg_block_lengths.csv    run-length distribution of negative blocks
  tables/desc_correlations.csv         CZ–DE price corr, price–residual load corr
  figures/fig_price_timeseries.png     price with negative hours highlighted
  figures/fig_neg_heatmap.png          month × hour heatmap of negative hours
  figures/fig_duration_curves.png      annual price-duration curves
  figures/fig_solar_vs_neg.png         solar infeed growth vs negative hours
  figures/fig_price_vs_resload.png     price vs residual load (binned)
  figures/fig_diurnal_profiles.png     mean diurnal price + solar profile per year

Run:  python analysis/s1_descriptives.py
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config as C
from s0_data_prep import load_prepared

PRICE = "ote_price_eur_mwh"


def table_price_by_year(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("year")
    tab = pd.DataFrame({
        "mean": g[PRICE].mean(),
        "std": g[PRICE].std(),
        "min": g[PRICE].min(),
        "p25": g[PRICE].quantile(0.25),
        "median": g[PRICE].median(),
        "p75": g[PRICE].quantile(0.75),
        "max": g[PRICE].max(),
        "neg_hours": g["surplus"].sum(),
        "neg_share_pct": 100 * g["surplus"].mean(),
        "lt20_hours": g["surplus_lt20"].sum(),
        "max_solar_mw": g["solar_mw"].max(),
        "mean_resload_mw": g["residual_load_mw"].mean(),
    }).round(2)
    tab.to_csv(C.TAB_DIR / "desc_price_by_year.csv")
    return tab


def table_neg_month_hour(df: pd.DataFrame) -> pd.DataFrame:
    pivot = df.pivot_table(index="month", columns="hour", values="surplus", aggfunc="sum")
    pivot.to_csv(C.TAB_DIR / "desc_neg_by_month_hour.csv")
    return pivot


def table_block_lengths(df: pd.DataFrame) -> pd.DataFrame:
    """Run lengths of consecutive negative-price hours (persistence, H1)."""
    s = df["surplus"].fillna(0).astype(int).values
    runs = []
    n = 0
    for v in s:
        if v:
            n += 1
        elif n:
            runs.append(n)
            n = 0
    if n:
        runs.append(n)
    runs = pd.Series(runs, name="block_length")
    tab = runs.value_counts().sort_index().rename("count").to_frame()
    tab["share_pct"] = (100 * tab["count"] / tab["count"].sum()).round(1)
    tab.to_csv(C.TAB_DIR / "desc_neg_block_lengths.csv")
    print(f"negative blocks: {len(runs)} blocks, mean length {runs.mean():.2f} h, "
          f"max {runs.max()} h")
    return tab


def table_correlations(df: pd.DataFrame) -> pd.DataFrame:
    rows = {}
    both = df[[PRICE, "entsoe_de_da_eur_mwh"]].dropna()
    rows["corr_cz_de_price"] = both.corr().iloc[0, 1]
    for sp in list(C.SUBPERIODS) + [None]:
        d = df if sp is None else df[df["subperiod"] == sp]
        rows[f"corr_price_resload_{sp or 'full'}"] = (
            d[[PRICE, "residual_load_mw"]].dropna().corr().iloc[0, 1])
    tab = pd.Series(rows, name="value").round(4).to_frame()
    tab.to_csv(C.TAB_DIR / "desc_correlations.csv")
    return tab


# ── figures ──────────────────────────────────────────────────────────────────

def fig_price_timeseries(df):
    fig, ax = plt.subplots(figsize=(12, 4.5))
    ax.plot(df.index, df[PRICE], lw=0.25, color="steelblue")
    neg = df[df["surplus"] == 1]
    ax.scatter(neg.index, neg[PRICE], s=2, color="crimson", zorder=3,
               label=f"negative hours (n={len(neg)})")
    for name, (a, b) in C.SUBPERIODS.items():
        ax.axvline(pd.Timestamp(a), color="grey", ls="--", lw=0.7)
    ax.set_ylabel("EUR/MWh")
    ax.set_title("Czech day-ahead price 2020–2024 (OTE), negative hours highlighted")
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(C.FIG_DIR / "fig_price_timeseries.png", dpi=150)
    plt.close(fig)


def fig_neg_heatmap(pivot):
    fig, ax = plt.subplots(figsize=(10, 5))
    im = ax.imshow(pivot.values, aspect="auto", cmap="Reds")
    ax.set_xticks(range(24), pivot.columns)
    ax.set_yticks(range(12), pivot.index)
    ax.set_xlabel("hour (UTC)")
    ax.set_ylabel("month")
    ax.set_title("Negative-price hours by month × hour, 2020–2024")
    fig.colorbar(im, label="hours")
    fig.tight_layout()
    fig.savefig(C.FIG_DIR / "fig_neg_heatmap.png", dpi=150)
    plt.close(fig)


def fig_duration_curves(df):
    fig, ax = plt.subplots(figsize=(8, 5))
    for y, g in df.groupby("year"):
        p = g[PRICE].dropna().sort_values(ascending=False).values
        ax.plot(np.linspace(0, 100, len(p)), p, lw=1.2, label=str(y))
    ax.axhline(0, color="k", lw=0.7)
    ax.set_xlabel("% of hours")
    ax.set_ylabel("EUR/MWh")
    ax.set_ylim(-150, 500)
    ax.set_title("Price-duration curves by year")
    ax.legend()
    fig.tight_layout()
    fig.savefig(C.FIG_DIR / "fig_duration_curves.png", dpi=150)
    plt.close(fig)


def fig_solar_vs_neg(tab_year):
    fig, ax1 = plt.subplots(figsize=(7, 4.5))
    ax1.bar(tab_year.index, tab_year["neg_hours"], color="crimson", alpha=0.7)
    ax1.set_ylabel("negative hours / year", color="crimson")
    ax2 = ax1.twinx()
    ax2.plot(tab_year.index, tab_year["max_solar_mw"], "o-", color="darkorange")
    ax2.set_ylabel("max hourly solar infeed [MW]", color="darkorange")
    ax1.set_title("Negative-price hours vs peak solar infeed")
    fig.tight_layout()
    fig.savefig(C.FIG_DIR / "fig_solar_vs_neg.png", dpi=150)
    plt.close(fig)


def fig_price_vs_resload(df):
    d = df[[PRICE, "residual_load_mw", "subperiod"]].dropna()
    fig, ax = plt.subplots(figsize=(8, 5))
    colors = {"pre_crisis": "tab:blue", "crisis": "tab:red", "post_crisis": "tab:green"}
    for sp, g in d.groupby("subperiod", observed=True):
        bins = pd.qcut(g["residual_load_mw"], 30)
        m = g.groupby(bins, observed=True).agg(
            rl=("residual_load_mw", "mean"), p=(PRICE, "mean"))
        ax.plot(m["rl"], m["p"], "o-", ms=3, color=colors.get(sp, "grey"), label=sp)
    ax.axhline(0, color="k", lw=0.7)
    ax.set_xlabel("residual load [MW]")
    ax.set_ylabel("mean price [EUR/MWh]")
    ax.set_title("Price vs residual load (30 quantile bins, by subperiod)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(C.FIG_DIR / "fig_price_vs_resload.png", dpi=150)
    plt.close(fig)


def fig_diurnal(df):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharex=True)
    for y, g in df.groupby("year"):
        axes[0].plot(g.groupby("hour")[PRICE].mean(), label=str(y))
        axes[1].plot(g.groupby("hour")["solar_mw"].mean(), label=str(y))
    axes[0].set_title("mean diurnal price profile")
    axes[0].set_ylabel("EUR/MWh")
    axes[1].set_title("mean diurnal solar infeed")
    axes[1].set_ylabel("MW")
    for ax in axes:
        ax.set_xlabel("hour (UTC)")
        ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(C.FIG_DIR / "fig_diurnal_profiles.png", dpi=150)
    plt.close(fig)


def main():
    df = load_prepared()
    tab_year = table_price_by_year(df)
    print("\n== price by year ==\n", tab_year)
    pivot = table_neg_month_hour(df)
    table_block_lengths(df)
    print("\n== correlations ==\n", table_correlations(df))
    fig_price_timeseries(df)
    fig_neg_heatmap(pivot)
    fig_duration_curves(df)
    fig_solar_vs_neg(tab_year)
    fig_price_vs_resload(df)
    fig_diurnal(df)
    print(f"\nfigures -> {C.FIG_DIR}\ntables  -> {C.TAB_DIR}")


if __name__ == "__main__":
    main()
