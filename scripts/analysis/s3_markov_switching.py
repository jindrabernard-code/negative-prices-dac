"""
s3_markov_switching.py — Markov-switching models of the deseasonalised price
(draft §4.1.2).

Two estimators:

  1. Homogeneous MS (constant transition matrix), regime-dependent mean and
     variance, via statsmodels MarkovRegression. Used for initial values,
     model comparison, and as the software-verified anchor.

  2. TVTP-MS (Filardo 1994): custom implementation. Transition probabilities
     are multinomial-logit functions of the lagged standardised residual load

         p_ij,t = exp(γ0_ij + γ1_ij z_{t-1}) / Σ_l exp(γ0_il + γ1_il z_{t-1}),

     likelihood evaluated by the Hamilton filter, maximised numerically
     (L-BFGS-B), smoothed probabilities by the Kim (1994) backward recursion.
     statsmodels does not implement TVTP — this is the known technical risk
     flagged in the project instructions, addressed here directly.

Regimes are relabelled by their means: 0 = surplus (lowest), ..., K-1 = spike.

Outputs:
  tables/ms_homogeneous_params.csv     regime params + transition matrix
  tables/ms_tvtp_params.csv            regime params + γ coefficients
  tables/ms_model_comparison.csv       loglik / AIC / BIC
  tables/ms_regime_diagnostics.csv     surplus-regime share by hour/month (sense check)
  tables/ms_oos_validation.csv         holdout: surplus prob vs realised negative hours
  models/tvtp_params.npz               parameters for the simulation layer (s4)
  figures/fig_ms_smoothed_probs.png
  figures/fig_tvtp_transition_curves.png

Run:  python analysis/s3_markov_switching.py
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import logsumexp
import statsmodels.api as sm

import config as C
from s0_data_prep import load_prepared

try:
    from numba import njit
except ImportError:      # pragma: no cover - numba is expected to be installed
    def njit(*a, **k):
        def deco(f):
            return f
        return deco(a[0]) if a and callable(a[0]) else deco

K = C.MS_N_REGIMES


# ── TVTP machinery ────────────────────────────────────────────────────────────

def unpack(theta, K):
    """theta -> (mu[K], sigma[K], gamma0[K,K-1], gamma1[K,K-1])."""
    i = 0
    mu = theta[i:i + K]; i += K
    sigma = np.exp(theta[i:i + K]); i += K
    g0 = theta[i:i + K * (K - 1)].reshape(K, K - 1); i += K * (K - 1)
    g1 = theta[i:i + K * (K - 1)].reshape(K, K - 1)
    return mu, sigma, g0, g1


def transition_matrices(g0, g1, z):
    """P[t, i, j] for all t; last destination category normalised to 0."""
    T = len(z)
    K = g0.shape[0]
    logits = np.zeros((T, K, K))
    logits[:, :, :-1] = g0[None, :, :] + g1[None, :, :] * z[:, None, None]
    logits -= logsumexp(logits, axis=2, keepdims=True)
    return np.exp(logits)


@njit(cache=True)
def _filter_core(dens, P):
    """JIT-compiled scaled Hamilton filter recursion."""
    T, K = dens.shape
    xi_filt = np.empty((T, K))
    xi_pred = np.empty((T, K))
    loglik = 0.0
    xi = np.full(K, 1.0 / K)
    for t in range(T):
        xp = xi @ P[t]                                     # predicted
        num = xp * dens[t]
        s = num.sum()
        loglik += np.log(s)
        xi = num / s
        xi_pred[t] = xp
        xi_filt[t] = xi
    return loglik, xi_filt, xi_pred


def hamilton_filter(y, z, theta, K):
    """Scaled Hamilton filter. Returns loglik, filtered and predicted probs."""
    mu, sigma, g0, g1 = unpack(theta, K)
    P = transition_matrices(g0, g1, z)                     # (T, K, K)
    dens = np.exp(-0.5 * ((y[:, None] - mu[None, :]) / sigma[None, :]) ** 2) \
        / (np.sqrt(2 * np.pi) * sigma[None, :])            # (T, K)
    dens = np.maximum(dens, 1e-300)
    loglik, xi_filt, xi_pred = _filter_core(dens, np.ascontiguousarray(P))
    return loglik, xi_filt, xi_pred, P


def kim_smoother(xi_filt, xi_pred, P):
    T, K = xi_filt.shape
    xi_smooth = np.empty((T, K))
    xi_smooth[-1] = xi_filt[-1]
    for t in range(T - 2, -1, -1):
        ratio = xi_smooth[t + 1] / np.maximum(xi_pred[t + 1], 1e-300)
        xi_smooth[t] = xi_filt[t] * (P[t + 1] @ ratio)
    return xi_smooth


def fit_tvtp(y, z, theta0, K):
    def nll(theta):
        try:
            ll, *_ = hamilton_filter(y, z, theta, K)
            return -ll
        except FloatingPointError:
            return 1e12

    with np.errstate(over="ignore", under="ignore"):
        res = minimize(nll, theta0, method="L-BFGS-B",
                       options={"maxiter": C.MS_MAX_ITER, "maxfun": 20000})
    return res


def relabel_by_mean(mu):
    """Permutation that orders regimes surplus < normal < spike."""
    return np.argsort(mu)


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    np.random.seed(C.MS_SEED)
    df = load_prepared()
    a, b = C.SUBPERIODS[C.ESTIMATION_PERIOD]
    d = df.loc[a:b].dropna(subset=["price_deseason", "residual_load_mw"])
    d_train = d.loc[: C.HOLDOUT_START]
    d_test = d.loc[C.HOLDOUT_START:]

    y = d_train["price_deseason"].values
    z_raw = d_train["residual_load_mw"].values
    z_mean, z_std = z_raw.mean(), z_raw.std()
    z = np.roll((z_raw - z_mean) / z_std, 1)               # z_{t-1}
    z[0] = z[1]

    print(f"estimation: {C.ESTIMATION_PERIOD} "
          f"{d_train.index.min()} – {d_train.index.max()}  (n={len(y):,})")

    # ── 1. homogeneous MS (statsmodels) ──────────────────────────────────────
    ms = sm.tsa.MarkovRegression(y, k_regimes=K, trend="c", switching_variance=True)
    ms_res = ms.fit(search_reps=10)
    # extract by parameter NAME (layout is transition probs first, then
    # const[k], then sigma2[k] — positional access is unsafe)
    pmap = dict(zip(ms.param_names, ms_res.params))
    mu_h = np.array([pmap[f"const[{k}]"] for k in range(K)])
    sig_h = np.sqrt(np.array([pmap[f"sigma2[{k}]"] for k in range(K)]))
    # regime_transition shape (K, K, 1): [to, from, time]; transpose to [from, to]
    Ph = ms_res.regime_transition[:, :, 0].T              # (K, K) rows=from, cols=to
    order = relabel_by_mean(mu_h)
    mu_h, sig_h = mu_h[order], sig_h[order]
    Ph = Ph[np.ix_(order, order)]

    hom_tab = pd.DataFrame({"mu": mu_h, "sigma": sig_h},
                           index=[f"regime_{k}" for k in range(K)])
    for j in range(K):
        hom_tab[f"P_to_{j}"] = Ph[:, j]
    hom_tab.round(4).to_csv(C.TAB_DIR / "ms_homogeneous_params.csv")
    print("\n== homogeneous MS ==\n", hom_tab.round(3))

    # ── 2. TVTP-MS, initialised from the homogeneous fit ─────────────────────
    g0_init = np.log(np.maximum(Ph[:, :-1], 1e-4) / np.maximum(Ph[:, [-1]], 1e-4))
    theta0 = np.concatenate([mu_h, np.log(sig_h),
                             g0_init.ravel(), np.zeros(K * (K - 1))])
    res = fit_tvtp(y, z, theta0, K)
    mu, sigma, g0, g1 = unpack(res.x, K)
    order = relabel_by_mean(mu)
    # relabel: permute means/sigmas; γ rows (origin) and columns are permuted by
    # re-deriving from permuted transition matrices at z = 0 and slope structure
    perm_full = np.ix_(order, order)
    mu, sigma = mu[order], sigma[order]
    # transition params: rebuild by permuting implied matrices at reference z's
    P0 = transition_matrices(g0, g1, np.array([0.0]))[0][perm_full]
    P1 = transition_matrices(g0, g1, np.array([1.0]))[0][perm_full]
    l0 = np.log(np.maximum(P0[:, :-1], 1e-12) / np.maximum(P0[:, [-1]], 1e-12))
    l1 = np.log(np.maximum(P1[:, :-1], 1e-12) / np.maximum(P1[:, [-1]], 1e-12))
    g0, g1 = l0, l1 - l0
    theta_star = np.concatenate([mu, np.log(sigma), g0.ravel(), g1.ravel()])

    ll, xi_filt, xi_pred, P = hamilton_filter(y, z, theta_star, K)
    xi_smooth = kim_smoother(xi_filt, xi_pred, P)

    tvtp_tab = pd.DataFrame({"mu": mu, "sigma": sigma},
                            index=[f"regime_{k}" for k in range(K)])
    for j in range(K - 1):
        tvtp_tab[f"gamma0_to_{j}"] = g0[:, j]
        tvtp_tab[f"gamma1_to_{j}"] = g1[:, j]
    tvtp_tab.round(4).to_csv(C.TAB_DIR / "ms_tvtp_params.csv")
    print("\n== TVTP MS ==\n", tvtp_tab.round(3))

    # model comparison
    n_h = len(ms_res.params)
    n_t = len(theta_star)
    comp = pd.DataFrame({
        "loglik": [ms_res.llf, ll],
        "n_params": [n_h, n_t],
        "AIC": [2 * n_h - 2 * ms_res.llf, 2 * n_t - 2 * ll],
        "BIC": [n_h * np.log(len(y)) - 2 * ms_res.llf, n_t * np.log(len(y)) - 2 * ll],
    }, index=["MS_homogeneous", "MS_TVTP"])
    comp.round(1).to_csv(C.TAB_DIR / "ms_model_comparison.csv")
    print("\n== model comparison ==\n", comp.round(1))

    # ── diagnostics: does the surplus regime make physical sense? ────────────
    diag = d_train.copy()
    diag["p_surplus"] = xi_smooth[:, 0]
    diag["regime"] = xi_smooth.argmax(axis=1)
    by_hour = diag.groupby("hour")["p_surplus"].mean()
    by_month = diag.groupby("month")["p_surplus"].mean()
    by_daytype = diag.groupby("daytype")["p_surplus"].mean()
    pd.concat({"by_hour": by_hour, "by_month": by_month, "by_daytype": by_daytype}
              ).round(4).to_csv(C.TAB_DIR / "ms_regime_diagnostics.csv")
    print("\nsurplus-regime prob peaks at hour",
          by_hour.idxmax(), "and month", by_month.idxmax())

    # ── out-of-sample validation on holdout ───────────────────────────────────
    y_te = d_test["price_deseason"].values
    z_te_raw = d_test["residual_load_mw"].values
    z_te = np.roll((z_te_raw - z_mean) / z_std, 1); z_te[0] = z_te[1]
    _, xf_te, xp_te, P_te = hamilton_filter(y_te, z_te, theta_star, K)
    surplus_pred = xp_te[:, 0]                # one-step-ahead surplus prob
    actual_neg = d_test["surplus"].values
    oos = pd.Series({
        "n_obs": len(y_te),
        "actual_neg_share": actual_neg.mean(),
        "predicted_surplus_share": surplus_pred.mean(),
        "corr_pred_actual": np.corrcoef(surplus_pred, actual_neg)[0, 1],
    }, name="value").to_frame()
    oos.round(4).to_csv(C.TAB_DIR / "ms_oos_validation.csv")
    print("\n== OOS validation ==\n", oos.round(4))

    # ── persist for the simulation layer ─────────────────────────────────────
    np.savez(C.MOD_DIR / "tvtp_params.npz",
             mu=mu, sigma=sigma, gamma0=g0, gamma1=g1,
             z_mean=z_mean, z_std=z_std, K=K, loglik=ll)

    # ── figures ───────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(2, 1, figsize=(12, 6), sharex=True)
    axes[0].plot(d_train.index, d_train["ote_price_eur_mwh"], lw=0.3)
    axes[0].set_ylabel("EUR/MWh")
    axes[0].set_title("price and smoothed surplus-regime probability (training window)")
    axes[1].fill_between(d_train.index, xi_smooth[:, 0], color="crimson", alpha=0.6)
    axes[1].set_ylabel("Pr(surplus)")
    fig.tight_layout()
    fig.savefig(C.FIG_DIR / "fig_ms_smoothed_probs.png", dpi=150)
    plt.close(fig)

    zz = np.linspace(-3, 3, 200)
    Pz = transition_matrices(g0, g1, zz)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for i in range(K):
        ax.plot(zz, Pz[:, i, 0], label=f"from regime {i}")
    ax.set_xlabel("standardised residual load $z_{t-1}$")
    ax.set_ylabel("Pr(transition into surplus regime)")
    ax.set_title("TVTP: transition probabilities into the surplus regime")
    ax.legend()
    fig.tight_layout()
    fig.savefig(C.FIG_DIR / "fig_tvtp_transition_curves.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
