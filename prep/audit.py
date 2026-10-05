"""Reproducible evidence for DATA_AUDIT_REPORT.md (read-only: never changes data).

    python -m prep.audit      # -> data/prepared/audit/audit_stats.json + *.csv evidence tables
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import pandas as pd
import yaml

from prep import pm
from prep.sources import isd, openmeteo_s3
from prep.sources.openaq_archive import US_EMBASSY, US_EMBASSY_DUP, DISCOVERY_CSV

OUT = Path("data/prepared/audit")


def haversine_km(lat1, lon1, lat2, lon2):
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 12742 * math.asin(math.sqrt(a))


def monthly_profile(raw: pd.DataFrame) -> pd.DataFrame:
    r = raw.copy()
    r["month"] = r["local_date"].dt.to_period("M").astype(str)
    valid = r[r["value"] != -999]
    g = r.groupby("month")
    out = pd.DataFrame({
        "rows": g.size(),
        "sentinel_minus999": g["value"].apply(lambda s: int((s == -999).sum())),
    })
    gv = valid.groupby("month")["value"]
    out["mean_excl_sentinel"] = gv.mean().round(2)
    out["median_excl_sentinel"] = gv.median().round(2)
    out["frac_non_integer"] = gv.apply(lambda s: round(float((s % 1 != 0).mean()), 3))
    out["frac_negative"] = gv.apply(lambda s: round(float((s < 0).mean()), 3))
    return out


def best_shift(a: pd.Series, b: pd.Series, months) -> list[dict]:
    res = []
    for m in months:
        t0 = m.start_time.tz_localize("UTC"); t1 = (m + 1).start_time.tz_localize("UTC")
        aa = a[(a.index >= t0) & (a.index < t1)]
        best = None
        for k in (-2, -1, 0, 1, 2):
            bb = b[(b.index >= t0 - pd.Timedelta(hours=3)) & (b.index < t1 + pd.Timedelta(hours=3))].copy()
            bb.index = bb.index + pd.Timedelta(hours=k)
            j = pd.concat([aa.rename("a"), bb.rename("b")], axis=1, join="inner")
            if len(j) < 24:
                continue
            f = float((j["a"] == j["b"]).mean())
            if best is None or f > best["identical_frac"]:
                best = {"month": str(m), "shift_h": k, "identical_frac": round(f, 3), "n": len(j)}
        if best:
            res.append(best)
    return res


def main():
    cfg = yaml.safe_load(Path("prep/config.yaml").read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    S: dict = {}

    a_raw = pm.load_raw(US_EMBASSY)
    b_raw = pm.load_raw(US_EMBASSY_DUP)
    S["raw_rows"] = {"8225": len(a_raw), "8827": len(b_raw)}
    S["raw_span_local"] = {k: [str(r["time_start_local"].min()), str(r["time_start_local"].max())]
                           for k, r in (("8225", a_raw), ("8827", b_raw))}
    S["units"] = sorted(set(a_raw["units"]) | set(b_raw["units"]))
    S["utc_offsets"] = sorted(set(a_raw["utc_offset"]) | set(b_raw["utc_offset"]))
    S["coords_8225"] = a_raw[["lat", "lon"]].drop_duplicates().values.tolist()
    S["sensors"] = {"8225": a_raw["sensors_id"].unique().tolist(), "8827": b_raw["sensors_id"].unique().tolist()}
    # timestamps convention: first/last hour inside one day-file
    f = a_raw[a_raw["source_file"] == "location-8225-20200110.csv.gz"]["datetime"]
    S["file_20200110_first_last"] = [f.min(), f.max()]

    mp = monthly_profile(a_raw)
    mp.to_csv(OUT / "embassy_8225_monthly_profile.csv")
    S["sentinel_rows"] = {k: int((r["value"] == -999).sum()) for k, r in (("8225", a_raw), ("8827", b_raw))}

    # A1 contamination evidence
    v = a_raw[a_raw["value"] != -999].copy()
    v["dec"] = v["value"] % 1 != 0
    S["decimal_first_last_local"] = [str(v.loc[v.dec, "time_start_local"].min()),
                                     str(v.loc[v.dec, "time_start_local"].max())]
    S["decimal_hours_before_2023_03"] = int(v.loc[v["local_date"] < "2023-03-01", "dec"].sum())
    w0, w1 = cfg["us_embassy_contaminated_window"]
    win = v[v["local_date"].between(w0, w1)]
    S["window_hours"] = int(len(win)); S["window_decimal_frac"] = round(float(win["dec"].mean()), 3)
    S["window_decimal_stats"] = win.loc[win.dec, "value"].describe().round(2).to_dict()
    S["window_integer_stats"] = win.loc[~win.dec, "value"].describe().round(2).to_dict()
    s = v.set_index("time_start_utc")["value"].sort_index()
    s = s[~s.index.duplicated()]
    full = s.reindex(pd.date_range(s.index.min(), s.index.max(), freq="h"))
    dec = (full % 1 != 0) & full.notna()
    interp = full.where(~dec).interpolate(limit=3, limit_area="inside")
    m = pd.DataFrame({"dec": full[dec], "ref": interp[dec]}).dropna()
    S["decimal_vs_interpolated_integer_r"] = round(float(m["dec"].corr(m["ref"])), 3)
    S["decimal_vs_interpolated_integer_n"] = int(len(m))
    S["same_month_mean_integer_stream"] = (
        v[~v.dec].assign(y=v["local_date"].dt.year, mo=v["local_date"].dt.month)
        .groupby(["mo", "y"])["value"].mean().round(1).unstack().to_dict())

    # A1b independent check with the 2024-25 low-cost network (median of sensors)
    ids = []
    with DISCOVERY_CSV.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["location_id"].startswith(("2812", "3291")):
                ids.append(int(r["location_id"]))
    D = {}
    for lid in ids:
        r = pm.load_raw(lid)
        if r.empty:
            continue
        r["ld"] = pd.to_datetime(r["datetime"], utc=True).dt.tz_convert("Asia/Bishkek").dt.tz_localize(None).dt.normalize()
        g = r.groupby("ld")["value"].agg(["mean", "count"])
        D[lid] = g[g["count"] >= 40]["mean"]
    net = pd.DataFrame(D)
    vv = v[v["value"] > -10]
    ed = vv.groupby("local_date")["value"].agg(["mean", "count"])
    ei = vv[~vv.dec].groupby("local_date")["value"].agg(["mean", "count"])
    j = pd.DataFrame({"network_median": net.median(axis=1), "n_sensors": net.notna().sum(axis=1),
                      "embassy_all_hours": ed[ed["count"] >= 18]["mean"],
                      "embassy_integer_hours": ei[ei["count"] >= 12]["mean"]})
    j.to_csv(OUT / "embassy_vs_lowcost_network_daily.csv")
    cmp = {}
    for name, (x0, x1) in {"contaminated_2024-05_2025-01-16": ("2024-05-01", "2025-01-16"),
                           "clean_2025-01-17_2025-03-04": ("2025-01-17", "2025-03-04")}.items():
        x = j.loc[x0:x1]
        for c in ("embassy_all_hours", "embassy_integer_hours"):
            y = x[["network_median", c]].dropna()
            cmp[f"{name}:{c}"] = {"n_days": int(len(y)), "r": round(float(y.iloc[:, 0].corr(y.iloc[:, 1])), 2),
                                  "median_ratio_embassy_to_network": round(float((y[c] / y["network_median"]).median()), 2)}
    S["embassy_vs_network"] = cmp
    S["lowcost_network_sensors"] = int(net.shape[1])

    # A3 duplicate feed alignment
    aa = a_raw[a_raw["value"] != -999].set_index("time_start_utc")["value"]
    bb = b_raw[b_raw["value"] != -999].set_index("time_start_utc")["value"]
    aa = aa[~aa.index.duplicated()]; bb = bb[~bb.index.duplicated()]
    j0 = pd.concat([aa.rename("a"), bb.rename("b")], axis=1, join="inner")
    S["dup_identical_same_timestamp"] = round(float((j0["a"] == j0["b"]).mean()), 3)
    shifts = best_shift(aa, bb, pd.period_range("2019-10", "2025-03", freq="M"))
    pd.DataFrame(shifts).to_csv(OUT / "dup_feed_monthly_shift.csv", index=False)

    # A4 day definition: UTC vs local
    qc = cfg["qc_pm25_hourly"]
    h, _ = pm.qc_hourly(a_raw, qc, "2019-09-01", "2025-03-05")
    h["utc_date"] = h["time_start_utc"].dt.tz_localize(None).dt.normalize()
    S["hours_on_different_day_utc_vs_local"] = round(float((h["utc_date"] != h["local_date"]).mean()), 4)
    loc = h.groupby("local_date")["pm2_5_qc"].agg(["mean", "count"])
    utc = h.groupby("utc_date")["pm2_5_qc"].agg(["mean", "count"])
    jj = pd.concat([loc.add_prefix("loc_"), utc.add_prefix("utc_")], axis=1).dropna()
    jj = jj[(jj["loc_count"] >= 18) & (jj["utc_count"] >= 18)]
    jj = jj[(jj.index < w0) | (jj.index > w1)]
    t = cfg["thresholds"]["dangerous_pm25_24h"]
    S["utc_vs_local_daily"] = {
        "n_days": int(len(jj)),
        "mean_abs_diff": round(float((jj["loc_mean"] - jj["utc_mean"]).abs().mean()), 2),
        "p95_abs_diff": round(float((jj["loc_mean"] - jj["utc_mean"]).abs().quantile(.95)), 2),
        "dangerous_label_flips": int(((jj["loc_mean"].map(pm.trunc1) >= t) != (jj["utc_mean"].map(pm.trunc1) >= t)).sum()),
    }
    # sensitivity to a +-1 h timestamp error (A3 uncertainty)
    sens = {}
    for k in (-1, 1):
        hh = h.copy(); hh["d2"] = (hh["time_start_local"] + pd.Timedelta(hours=k)).dt.tz_localize(None).dt.normalize()
        d2 = hh.groupby("d2")["pm2_5_qc"].agg(["mean", "count"])
        z = pd.concat([loc["mean"].rename("a"), d2["mean"].rename("b"), loc["count"].rename("na"), d2["count"].rename("nb")], axis=1).dropna()
        z = z[(z.na >= 18) & (z.nb >= 18)]
        z = z[(z.index < w0) | (z.index > w1)]
        sens[f"shift_{k:+d}h"] = {"mean_abs_diff": round(float((z.a - z.b).abs().mean()), 2),
                                   "dangerous_flips": int(((z.a.map(pm.trunc1) >= t) != (z.b.map(pm.trunc1) >= t)).sum()),
                                   "n_days": int(len(z))}
    S["timestamp_shift_sensitivity"] = sens

    # A5/A7 QC flags over the clean part (whole record, rules fixed on train)
    S["qc_flag_counts_8225_all"] = h["qc_flag"].value_counts().to_dict()
    S["qc_flag_counts_8225_train"] = h[h["local_date"] < "2021-07-01"]["qc_flag"].value_counts().to_dict()
    sp = h[h["qc_flag"] == "spike"]
    S["spikes"] = [{"time_local": str(r.time_start_local), "value": r.pm2_5_raw} for r in sp.itertuples()]
    # what dropping spikes changes for daily labels
    hh = h.copy(); hh["keep_spike"] = hh["pm2_5_qc"].where(hh["qc_flag"] != "spike", hh["pm2_5_raw"])
    g1 = hh.groupby("local_date")["pm2_5_qc"].agg(["mean", "count"])
    g2 = hh.groupby("local_date")["keep_spike"].agg(["mean", "count"])
    z = pd.concat([g1.add_prefix("a_"), g2.add_prefix("b_")], axis=1)
    z = z[(z.a_count >= 18)]
    S["spike_dangerous_label_flips"] = int(((z.a_mean.map(pm.trunc1) >= t) != (z.b_mean.map(pm.trunc1) >= t)).sum())

    # gaps (8225 only, sentinel excluded)
    tt = aa.sort_index().index.to_series()
    gaps = tt.diff().dt.total_seconds().div(3600)
    big = gaps[gaps > 72].sort_values(ascending=False)
    S["gaps_over_72h_8225"] = [{"resumes_utc": str(i), "gap_h": float(g)} for i, g in big.items()]

    # A8 catalogue coordinates
    cat = (42.9006, 74.5936)
    S["catalog_vs_archive_km"] = round(haversine_km(cat[0], cat[1], 42.8273, 74.5833), 2)

    # ERA5 / CAMS coverage
    cov = {}
    for dom, (_, vars_) in openmeteo_s3.DOMAINS.items():
        for var in vars_:
            p = openmeteo_s3.raw_path(dom, var)
            if p.exists():
                d = pd.read_csv(p)
                d["time_utc"] = pd.to_datetime(d["time_utc"], utc=True)
                nn = d.dropna()
                cov[f"{dom}/{var}"] = {"first": str(nn["time_utc"].min()), "last": str(nn["time_utc"].max()),
                                       "hours": int(len(d)), "non_null": int(len(nn))}
                if var == "boundary_layer_height":
                    idx = pd.date_range(nn["time_utc"].min(), nn["time_utc"].max(), freq="h")
                    miss = idx.difference(pd.DatetimeIndex(nn["time_utc"]))
                    if len(miss):
                        ser = pd.Series(miss)
                        brk = ser.diff() != pd.Timedelta(hours=1)
                        runs = ser.groupby(brk.cumsum()).agg(["min", "max", "size"])
                        cov["blh_missing_runs_over_24h"] = [
                            {"from": str(r["min"]), "to": str(r["max"]), "hours": int(r["size"])}
                            for _, r in runs[runs["size"] > 24].iterrows()]
    S["openmeteo_s3_coverage"] = cov
    S["era5_cell_elevations_m"] = {"42.75N_74.50E(nearest)": 1636, "43.00N_74.50E(used)": 748,
                                   "source": "copernicus_era5/static/HSURF.om rows 531-532, col 1018"}

    # ISD coverage
    for name, st in cfg["sources"]["isd_stations"].items():
        d = isd.parse_station(st, range(2019, 2026))
        S[f"isd_{name}"] = {"rows": int(len(d)), "first": str(d["time_utc"].min()), "last": str(d["time_utc"].max())}

    (OUT / "audit_stats.json").write_text(json.dumps(S, indent=1, default=str, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: S[k] for k in ("raw_rows", "sentinel_rows", "window_decimal_frac",
                                        "decimal_vs_interpolated_integer_r", "embassy_vs_network",
                                        "utc_vs_local_daily", "timestamp_shift_sensitivity",
                                        "catalog_vs_archive_km", "spike_dangerous_label_flips")}, indent=1))


if __name__ == "__main__":
    main()
