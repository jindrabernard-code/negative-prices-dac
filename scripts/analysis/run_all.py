"""
run_all.py — orchestrator for the thesis analysis pipeline.

Runs the sub-scripts in dependency order:

  s0_data_prep         panel -> prepared dataset (residual load, surplus flag,
                       deseasonalised price, grid intensity)
  s1_descriptives      tables + figures for thesis §3.4
  s2_logit_baseline    logit safety net (§4.1.1)
  s3_markov_switching  homogeneous MS + TVTP estimation (§4.1.2)   [slowest]
  s4_simulation        price-path simulation + RQ2 scenarios (§4.1.3, §4.2.3)
  s5_dac_dispatch      dispatch policies + benchmarks (§4.2)
  s6_economics         LCOC, break-even, trade-off curve (§4.3)

Usage:
  python analysis/run_all.py            # full pipeline
  python analysis/run_all.py s1 s4 s6   # selected steps only
"""
import importlib
import sys
import time
from pathlib import Path

# ensure the analysis directory is on sys.path so sub-modules resolve
_here = Path(__file__).resolve().parent
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))

STEPS = {
    "s0": "s0_data_prep",
    "s1": "s1_descriptives",
    "s2": "s2_logit_baseline",
    "s3": "s3_markov_switching",
    "s4": "s4_simulation",
    "s5": "s5_dac_dispatch",
    "s6": "s6_economics",
}


def main():
    selected = sys.argv[1:] or list(STEPS)
    for key in selected:
        if key not in STEPS:
            raise SystemExit(f"unknown step '{key}'; choose from {list(STEPS)}")
        mod_name = STEPS[key]
        print(f"\n{'=' * 70}\n{key}: {mod_name}\n{'=' * 70}")
        t0 = time.time()
        mod = importlib.import_module(mod_name)
        if key == "s0":
            mod.prepare()
        else:
            mod.main()
        print(f"[{key} done in {time.time() - t0:.1f}s]")


if __name__ == "__main__":
    main()
