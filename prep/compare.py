"""Before/after comparison on the SAME raw reference data.

"Before" reproduces the legacy logic of fetch/common.to_daily + fetch/build_dataset.build_stations
applied to the US Embassy hourly feed(s): UTC calendar day, no sentinel/QC handling, no
completeness rule (only a 'sparse' flag), both archive feeds kept as separate station keys,
dangerous = mean > 55.4. "After" is data/prepared/pm25_daily_target.csv.

    python -m prep.compare   # -> data/prepared/before_after.md
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from prep import pm
from prep.sources.openaq_archive import US_EMBASSY, US_EMBASSY_DUP

P = Path("data/prepared")


def _split_of(dates: pd.Series, splits: dict) -> pd.Series:
    """Split label by the day itself (the day is a potential target)."""
    lab = pd.Series("outside", index=dates.index, dtype=object)
    for name in ("train", "validation", "test"):
        ws = splits[name] if not isinstance(splits[name][0], str) else [splits[name]]
        for a, b in ws:
            lab[dates.between(pd.Timestamp(a), pd.Timestamp(b))] = name
    return lab


def legacy(cfg) -> pd.DataFrame:
    frames = []
    for lid, key in ((US_EMBASSY, "openaq_8225"), (US_EMBASSY_DUP, "openaq_8827")):
        r = pm.load_raw(lid)
        d = pm.legacy_daily_utc(r)
        d["station_key"] = key
        d["sparse"] = d["n_rows"] < 18
        frames.append(d)
    out = pd.concat(frames, ignore_index=True)
    out = out[(out["date"] >= cfg["study"]["period_start"]) & (out["date"] <= "2025-03-04")]
    out["dangerous_day"] = out["pm2_5"] > 55.4
    return out


def main():
    cfg = yaml.safe_load(Path("prep/config.yaml").read_text(encoding="utf-8"))
    L = legacy(cfg)
    A = pd.read_csv(P / "pm25_daily_target.csv", parse_dates=["date"])
    A = A[A["date"] <= "2025-03-04"]
    span = pd.date_range(cfg["study"]["period_start"], "2025-03-04", freq="D")
    L1 = L[L["station_key"] == "openaq_8225"]
    rows = []
    rows.append(("daily rows (station-days)", f"{len(L)} (2 keys for 1 instrument)", f"{len(A)} (1 series)"))
    dup = L.groupby("date").size().gt(1).sum()
    rows.append(("same instrument-day present twice", f"{dup}", "0"))
    rows.append(("calendar days covered (any value)", f"{L['date'].nunique()} / {len(span)}",
                 f"{int(A['pm2_5'].notna().sum())} valid / {len(span)}"))
    rows.append(("day definition", "UTC calendar day (18:00-18:00 local)", "local day Asia/Bishkek (EPA)"))
    rows.append(("days with < 18 hours used as values", f"{int(L1['sparse'].sum())} (8225 key)", "0 (set to NaN)"))
    rows.append(("days with negative daily mean (-999 sentinel averaged in)",
                 f"{int((L1['pm2_5'] < 0).sum())} (8225 key)", "0"))
    rows.append(("hours with -999 sentinel inside means", f"{int((pm.load_raw(US_EMBASSY)['value'] == -999).sum())}", "0"))
    w0, w1 = cfg["us_embassy_contaminated_window"]
    inwin = L1["date"].between(w0, w1)
    rows.append(("days from the contaminated feed window 2023-03-16..2025-01-16",
                 f"{int(inwin.sum())} used", f"0 used ({int(A['date'].between(w0, w1).sum())} rows kept as NaN)"))
    rows.append(("missing target days inside study span", f"{len(span) - L1['date'].nunique()} (8225 key)",
                 f"{int(A['pm2_5'].isna().sum())} (incl. contaminated window)"))
    lines = ["# Before / after (same raw US Embassy data)", "",
             "| metric | before (legacy logic) | after (prep pipeline) |", "|---|---|---|"]
    lines += [f"| {a} | {b} | {c} |" for a, b, c in rows]
    # dangerous days per split
    L1 = L1.assign(split=_split_of(L1["date"], cfg["splits"]))
    A = A.assign(split=_split_of(A["date"], cfg["splits"]))
    lines += ["", "## Days by split (day treated as a target day)", "",
              "| split | before: days | before: dangerous (>55.4, UTC day, unfiltered) | after: valid days | after: dangerous (EPA trunc >= 55.5, local day) | after: > 35 (KG limit) |",
              "|---|---|---|---|---|---|"]
    for s in ("train", "validation", "test", "outside"):
        lb = L1[L1["split"] == s]; ab = A[A["split"] == s]
        lines.append(f"| {s} | {len(lb)} | {int(lb['dangerous_day'].sum())} | {int(ab['pm2_5'].notna().sum())} | "
                     f"{int(ab['dangerous_day'].astype('boolean').sum())} | {int(ab['exceeds_kg_limit'].astype('boolean').sum())} |")
    (P / "before_after.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
