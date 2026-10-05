"""Generate data/prepared/FEATURE_DICTIONARY.md from the built tables (every column documented).

    python -m prep.dictionary
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

P = Path("data/prepared")

SRC = {
    "pm": ("US Embassy BAM-1020 via OpenAQ archive (loc. 8225, gaps from 8827)", "µg/m³"),
    "isd_manas": ("NOAA ISD 38353199999 Manas airport METAR (measured)", None),
    "isd_bishkek": ("NOAA ISD 38353099999 Bishkek SYNOP (measured)", None),
    "era5": ("ECMWF ERA5 0.25° cell 43.00N 74.50E (elev. 748 m) via Open-Meteo S3", None),
    "cams": ("CAMS global forecast archive 0.4° cell 42.8N 74.4E via Open-Meteo S3 (from 2022-08-04)", "µg/m³"),
    "cal": ("calendar of the TARGET day", "-"),
}
UNITS = [
    (r"temp|t2m|dewpoint", "°C"), (r"rh", "%"), (r"slp|mslp", "hPa"), (r"wind_speed|ws10|_u_|_v_|u10|v10|wind_u|wind_v", "m/s"),
    (r"visibility", "m"), (r"frac", "fraction 0-1"), (r"blh", "m"), (r"ventilation", "m²/s"),
    (r"precip", "mm/day"), (r"cloud", "%"), (r"swrad", "W/m²"), (r"aerosol_optical_depth", "unitless"),
    (r"carbon_monoxide|nitrogen_dioxide|sulphur_dioxide|ozone|pm10|pm2_5|dust", "µg/m³"),
]
AGG = [
    (r"_mean", "local-day mean"), (r"_min", "local-day min"), (r"_max", "local-day max"),
    (r"_range", "local-day max - min"), (r"_sum", "local-day sum"), (r"_frac", "share of reports that day"),
]
FIXED = {
    "issue_date": ("key", "date", "forecast issue day D (local); all predictors use data <= end of D", "-"),
    "target_date": ("key", "date", "D + horizon (1 day)", "-"),
    "split": ("derived", "label", "train / validation / test / embargo / excluded_window / unused (by target_date)", "-"),
    "y_pm2_5": ("target", "µg/m³", "24-h mean PM2.5 of target_date over the LOCAL day; NaN if < 18 valid hours; never imputed", "no"),
    "y_valid": ("target", "bool", "target present (>= 18 valid hours)", "no"),
    "y_n_hours": ("target", "count", "valid hours in the target day", "no"),
    "y_dangerous": ("target", "bool", "EPA AQI 'Unhealthy': trunc(y_pm2_5, 0.1) >= 55.5", "no"),
    "y_exceeds_kg": ("target", "bool", "Kyrgyz daily limit: y_pm2_5 > 35", "no"),
    "y_source": ("target", "text", "archive feed(s) that supplied the target day's hours", "no"),
    "pm_lag1": ("pm", "µg/m³", "PM2.5 local-day mean of day D (lag 1 = issue day)", "yes"),
    "pm_lag2": ("pm", "µg/m³", "day D-1", "yes"), "pm_lag3": ("pm", "µg/m³", "day D-2", "yes"),
    "pm_lag7": ("pm", "µg/m³", "day D-6", "yes"),
    "pm_max_lag1": ("pm", "µg/m³", "max hourly value of day D", "yes"),
    "pm_n_hours_lag1": ("pm", "count", "valid hours of day D", "yes"),
    "pm_lag1_minus_lag2": ("pm", "µg/m³", "day-to-day change D vs D-1", "yes"),
    "pm_roll7_max": ("pm", "µg/m³", "max daily mean over D-6..D (>= 4 days)", "yes"),
    "pm_dangerous_days_last7": ("pm", "count", "dangerous days in D-6..D (>= 4 valid days)", "yes"),
    "pm_evening_mean_lag1": ("pm", "µg/m³", "mean of hours 18-23 local of day D (>= 3 hours)", "yes"),
    "pm_hour23_lag1": ("pm", "µg/m³", "hour 23:00-24:00 local of day D (reported at issue time)", "yes"),
    "cal_doy_sin": ("cal", "-", "sin(2π·doy/365.25) of target day", "yes (calendar)"),
    "cal_doy_cos": ("cal", "-", "cos(2π·doy/365.25) of target day", "yes (calendar)"),
    "cal_month": ("cal", "1-12", "month of target day", "yes (calendar)"),
    "cal_dow": ("cal", "0=Mon", "weekday of target day", "yes (calendar)"),
    "cal_weekend": ("cal", "0/1", "Saturday/Sunday", "yes (calendar)"),
    "cal_heating_season_nominal": ("cal", "0/1", "15 Oct - 15 Apr (Bishkek nominal heating season)", "yes (calendar)"),
}


def describe(col: str) -> tuple[str, str, str, str, str]:
    if col in FIXED:
        s, u, a, avail = FIXED[col]
        return SRC.get(s, (s, u))[0] if s in SRC else s, u, a, avail, ""
    m = re.match(r"pm_roll(\d+)_(mean|n)$", col)
    if m:
        w, kind = m.groups()
        return (SRC["pm"][0], "µg/m³" if kind == "mean" else "count",
                f"{'mean' if kind == 'mean' else 'number of valid days'} of daily PM2.5 over D-{int(w)-1}..D", "yes", "")
    pref = next(p for p in ("isd_manas", "isd_bishkek", "era5", "cams") if col.startswith(p))
    base = col[len(pref) + 1:]
    lagtxt = "day D" if base.endswith("_lag1") else "change D minus D-1" if base.endswith("_d1") else ""
    base = re.sub(r"_(lag1|d1)$", "", base)
    unit = next((u for pat, u in UNITS if re.search(pat, base)), "-")
    agg = next((a for pat, a in AGG if re.search(pat, base)), "local-day value")
    if base.endswith("_d1") or col.endswith("_d1"):
        agg = f"{agg}; difference day D minus day D-1"
    avail = {"isd_manas": "yes (GTS real time)", "isd_bishkek": "yes (GTS real time)",
             "era5": "proxy: ERA5 has ~5 d latency - stands in for an operational analysis",
             "cams": "yes (CAMS forecasts are issued daily); NaN before 2022-08-04"}[pref]
    note = ""
    if "visibility" in base and pref == "isd_manas":
        note = "METAR caps visibility at 9999 m"
    if "blh" in base or "ventilation" in base:
        note = "upstream gap 2024-01-01..2024-06-30 (NaN)"
    return SRC[pref][0], unit, f"{agg} ({lagtxt})", avail, note


def main():
    X = pd.read_parquet(P / "features_all.parquet")
    pre = json.loads((P / "preprocessing_train_fit.json").read_text(encoding="utf-8"))
    log = json.loads((P / "processing_log.json").read_text(encoding="utf-8"))
    dropped = set(log.get("model_columns_dropped_lt50pct_train_coverage", []))
    tr = X[(X["split"] == "train") & X["y_valid"]]
    L = ["# Feature dictionary - Bishkek next-day PM2.5 dataset", "",
         "Generated by `python -m prep.dictionary` from `data/prepared/features_all.parquet`.", "",
         "Row = forecast issue day D (local, Asia/Bishkek UTC+6). Target = 24-h local-day mean PM2.5 of D+1.",
         "Every predictor uses only data time-stamped within or before local day D (tested by "
         "`prep.checks` → `leakage.features_use_only_past`).", "",
         "Columns marked *model: no* are kept in `*_raw.parquet` / `features_all.parquet` but excluded from "
         "`*_model.parquet` because < 50 % of TRAIN rows have them (e.g. CAMS starts 2022-08-04).", "",
         "| column | source | unit | definition / aggregation | available at issue time | train coverage | model | note |",
         "|---|---|---|---|---|---|---|---|"]
    for c in X.columns:
        if c in ("issue_date", "target_date", "split") or c.startswith("y_") or c.startswith(("pm_", "isd_", "era5_", "cams_", "cal_")):
            s, u, a, av, note = describe(c)
            cov = f"{tr[c].notna().mean():.0%}" if c in tr and not c.startswith(("y_",)) and c not in ("issue_date", "target_date", "split") else "-"
            inmodel = "-" if c.startswith("y_") or c in ("issue_date", "target_date", "split") else ("no" if c in dropped else "yes")
            L.append(f"| `{c}` | {s} | {u} | {a} | {av} | {cov} | {inmodel} | {note} |")
    L += ["", "## Hourly table `pm25_hourly_qc.parquet`", "",
          "| column | meaning |", "|---|---|",
          "| `time_start_utc` | start of the averaging hour, UTC (archive `datetime` is hour END, local offset +06:00) |",
          "| `time_start_local` / `local_date` / `local_hour` | same hour in Asia/Bishkek; `local_date` defines the 24-h day |",
          "| `pm2_5_raw` | value exactly as in the raw archive file (8225; 8827 for filled hours) |",
          "| `pm2_5_qc` | value after QC (NaN when the flag voids it) |",
          "| `qc_flag` | ok, neg_small (kept), missing, missing_sentinel (-999), duplicate_conflict, error_code (985/990/995/999), bam_floor (-15), below_min (< -10), flatline (>= 6 identical h > 2 µg/m³), spike (isolated 1-h > 6x both neighbours and > 300), filled_from_8827, feed_contaminated |",
          "| `source` | openaq:8225 or openaq:8827 (time-aligned) |",
          "", "## Daily table `pm25_daily_target.csv`", "", "| column | meaning |", "|---|---|",
          "| `date` | local calendar day |", "| `pm2_5_n_hours` | valid QC'd hours |",
          "| `pm2_5_mean_all` | mean of whatever valid hours exist (diagnostic only; NOT the target) |",
          "| `pm2_5` | target value: mean if >= 18 valid hours, else NaN |", "| `pm2_5_max` | max valid hour (valid days only) |",
          "| `pm2_5_n_spike`, `pm2_5_n_flatline`, `pm2_5_n_error` | QC counts that day |",
          "| `pm2_5_valid_day` | >= 18 valid hours |", "| `dangerous_day` | trunc1(pm2_5) >= 55.5 (EPA AQI Unhealthy, 24-h) |",
          "| `exceeds_kg_limit` | pm2_5 > 35 (ПДК с.с., ПП КР №201/2016) |", "| `pm2_5_source` | feeds used |",
          "", "## Model matrices `*_model.parquet`", "",
          f"{len(pre['columns'])} predictors, median-imputed and standardised with TRAIN statistics "
          f"(`preprocessing_train_fit.json`), plus {len(pre['missing_indicators'])} `<col>__missing` 0/1 indicators."]
    (P / "FEATURE_DICTIONARY.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"documented {sum(1 for l in L if l.startswith('| `'))} columns")


if __name__ == "__main__":
    main()
