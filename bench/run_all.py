"""
Run the mock-stack KPI suite end to end (KPI 1, 2, 3, 4, 6, 7) and emit all
CSVs + PNGs into bench/results/.

KPI 5 (mock vs Next Door) is intentionally separate: run kpi5_mock_vs_ndks.py
once here (mock) and once under the ndks profile to build the comparison.

Prereq: the mock stack must be up (`docker compose up -d --build`).
"""
from __future__ import annotations

import importlib
import sys
import time

import common as c
import httpx

MODULES = [
    "kpi1_stage_latency",
    "kpi2_hops_latency",
    "kpi3_cost_hops_scenario",
    "kpi4_throughput_sigma",
    "kpi6_success_rate",
    "kpi7_pool_rho",
    "kpi5_mock_vs_ndks",   # records current backend (mock here)
]


def _wait_stack(timeout: float = 60.0) -> bool:
    print("Checking the stack is up...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            g = httpx.get(f"{c.GATEWAY_URL}/health", timeout=3).status_code
            a = httpx.get(f"{c.AUDIT_URL}/health", timeout=3).status_code
            t = httpx.get(f"{c.TOPOLOGY_URL}/health", timeout=3).status_code
            if g == a == t == 200:
                print("  stack is healthy.\n")
                return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(2)
    return False


def main() -> int:
    if not _wait_stack():
        print("ERROR: stack not reachable. Run `docker compose up -d --build` "
              "first.", file=sys.stderr)
        return 1
    for name in MODULES:
        print(f"\n=== {name} ===")
        mod = importlib.import_module(name)
        try:
            if name == "kpi5_mock_vs_ndks":
                backend, rows = mod.run()
                if rows:
                    c.write_csv(f"kpi5_{backend}.csv", rows,
                                ["backend", "e2e_ms", "kom_ms", "http_ms"])
                mod.plot()
            else:
                rows = mod.run()
                # each module knows its own CSV columns via its __main__; reuse:
                mod.plot(rows) if hasattr(mod, "plot") else None
                _persist(name, mod, rows)
        except Exception as exc:  # noqa: BLE001
            print(f"  !! {name} failed: {exc}")
    print(f"\nDone. Charts + CSVs in {c.RESULTS_DIR}")
    return 0


def _persist(name: str, mod, rows) -> None:
    # Re-run the module's own CSV writer by invoking its __main__ block logic is
    # awkward; instead each module writes its CSV in __main__. For run_all we
    # call the module's documented columns through a tiny convention:
    writers = {
        "kpi1_stage_latency": ("kpi1_stage_latency.csv",
                               ["scenario", "reps", "e2e_mean_ms", *c.STAGE_LABELS]),
        "kpi2_hops_latency": ("kpi2_hops_latency.csv",
                              ["src", "dst", "hops", "e2e_ms", "http_ms", "cost"]),
        "kpi3_cost_hops_scenario": ("kpi3_cost_hops_scenario.csv",
                                    ["scenario", "hops_nominal", "cost_nominal",
                                     "path_nominal", "hops_fault", "cost_fault",
                                     "path_fault", "d_hops"]),
        "kpi4_throughput_sigma": ("kpi4_throughput_sigma.csv",
                                  ["n", "throughput", "sigma", "ok", "total",
                                   "elapsed_s"]),
        "kpi6_success_rate": ("kpi6_success_rate.csv",
                              ["scenario", "ok_200", "err_503", "success_rate"]),
        "kpi7_pool_rho": ("kpi7_pool_rho.csv",
                          ["t", "rho", "stored", "prefetching", "threshold"]),
    }
    if name in writers:
        fname, cols = writers[name]
        c.write_csv(fname, rows, cols)


if __name__ == "__main__":
    raise SystemExit(main())
