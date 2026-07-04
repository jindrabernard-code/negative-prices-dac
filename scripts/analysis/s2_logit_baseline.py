"""
s2_logit_baseline.py — baseline binary response model (draft §4.1.1).

Logit of the surplus-hour indicator on residual load + calendar controls:

    Pr(y_t = 1 | x_t) = Λ(x_t'β)

Serves as the robust, interpretable safety net for the regime model.
Standard errors are clustered on days (serial dependence of hourly data).
Includes out-of-sample evaluation on the holdout window.

Outputs:
  tables/logit_coefficients.csv
  tables/logit_marginal_effects.csv
  tables/logit_oos_evaluation.csv
  figures/fig_logit_prob_vs_resload.png

Run:  python analysis/s2_logit_baseline.py
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

import config as CFG
from s0_data_prep import load_prepared

FORMULA = ("surplus ~ resload_gw + C(hour) + C(daytype) + C(month)")


def prepare_frame(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["resload_gw"] = d["residual_load_mw"] / 1000.0
    d["date"] = d.index.date
    return d.dropna(subset=["surplus", "resload_gw"])


def fit(d: pd.DataFrame):
    model = smf.logit(FORMULA, data=d)
    # cluster-robust (by day) covariance
    res = model.fit(disp=False, maxiter=200)
    res_cl = model.fit(disp=False, maxiter=200,
                       cov_type="cluster", cov_kwds={"groups": d["date"]})
    return res_cl if res_cl.mle_retvals.get("converged", True) else res


def oos_evaluation(res, d_test: pd.DataFrame) -> pd.DataFrame:
    p = res.predict(d_test)
    y = d_test["surplus"].values
    # Brier score, log loss, hit rates at 0.5 threshold, calibration of frequency
    eps = 1e-12
    rows = {
        "n_obs": len(y),
        "actual_surplus_share": y.mean(),
        "predicted_surplus_share": p.mean(),
        "brier_score": np.mean((p - y) ** 2),
        "log_loss": -np.mean(y * np.log(p + eps) + (1 - y) * np.log(1 - p + eps)),
        "auc": _auc(y, p.values),
    }
    return pd.Series(rows, name="value").to_frame()


def _auc(y, p):
    """Mann–Whitney AUC without sklearn dependency."""
    order = np.argsort(p)
    ranks = np.empty(len(p))
    ranks[order] = np.arange(1, len(p) + 1)
    n1 = y.sum()
    n0 = len(y) - n1
    if n1 == 0 or n0 == 0:
        return np.nan
    return (ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n0 * n1)


def main():
    df = load_prepared()
    a, b = CFG.SUBPERIODS[CFG.ESTIMATION_PERIOD]
    d = prepare_frame(df.loc[a:b])
    d_train = d.loc[: CFG.HOLDOUT_START]
    d_test = d.loc[CFG.HOLDOUT_START:]
    print(f"train {d_train.index.min().date()} – {d_train.index.max().date()} "
          f"({len(d_train):,}), test from {CFG.HOLDOUT_START} ({len(d_test):,})")

    res = fit(d_train)
    print(res.summary())

    coefs = pd.DataFrame({"coef": res.params, "se": res.bse, "pvalue": res.pvalues})
    coefs.to_csv(CFG.TAB_DIR / "logit_coefficients.csv")

    # average marginal effect of residual load (GW)
    ame = res.get_margeff(at="overall")
    ame_tab = ame.summary_frame()
    ame_tab.to_csv(CFG.TAB_DIR / "logit_marginal_effects.csv")
    print("\n== average marginal effects ==\n", ame_tab.head(3))

    ev = oos_evaluation(res, d_test)
    ev.to_csv(CFG.TAB_DIR / "logit_oos_evaluation.csv")
    print("\n== out-of-sample evaluation ==\n", ev.round(4))

    # predicted probability vs residual load at midday, workday, June
    grid = pd.DataFrame({
        "resload_gw": np.linspace(d["resload_gw"].min(), d["resload_gw"].max(), 100),
        "hour": 11, "daytype": "workday", "month": 6,
    })
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(grid["resload_gw"], res.predict(grid), lw=2)
    ax.set_xlabel("residual load [GW]")
    ax.set_ylabel("Pr(surplus hour)")
    ax.set_title("Logit: surplus probability vs residual load (June workday, 11:00 UTC)")
    fig.tight_layout()
    fig.savefig(CFG.FIG_DIR / "fig_logit_prob_vs_resload.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
