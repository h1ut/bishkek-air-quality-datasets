from __future__ import annotations
import argparse
import glob
import shutil
import subprocess
from pathlib import Path

import pandas as pd

_EXTRACTORS = ["7z", "7za", "unrar", "bsdtar"]


def find_extractor() -> str | None:
    for e in _EXTRACTORS:
        if shutil.which(e):
            return e
    return None


def extract_archives(raw_dir="data/raw/zenodo_12720883") -> list[str]:
    exe = find_extractor()
    if not exe:
        print("[zenodo] no rar extractor (7z/unrar/bsdtar) on PATH; skipping .rar")
        return []
    done = []
    for rar in glob.glob(f"{raw_dir}/*.rar"):
        dest = Path(rar).with_suffix("")
        dest.mkdir(exist_ok=True)
        if exe in ("7z", "7za"):
            cmd = [exe, "x", "-y", f"-o{dest}", rar]
        elif exe == "unrar":
            cmd = [exe, "x", "-o+", rar, f"{dest}/"]
        else:
            cmd = [exe, "-x", "-f", rar, "-C", str(dest)]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            done.append(str(dest))
        except subprocess.CalledProcessError as e:  # noqa: PERF203
            print(f"[zenodo] extract failed for {rar}: {e}")
    return done


def _to_daily_pm(df, time_col, pm_col):
    d = df[[time_col, pm_col]].copy()
    d[time_col] = pd.to_datetime(d[time_col], errors="coerce")
    d = d.dropna(subset=[time_col])
    d["date"] = d[time_col].dt.floor("D")
    g = d.groupby("date")[pm_col]
    out = g.mean().reset_index().rename(columns={pm_col: "pm2_5"})
    out["n_hours_pm2_5"] = g.count().values
    return out.sort_values("date").reset_index(drop=True)


def _find_files(raw_dir, *needles):
    hits = []
    for fp in glob.glob(f"{raw_dir}/**/*", recursive=True):
        low = fp.lower()
        if any(n in low for n in needles) and low.endswith((".csv", ".xlsx", ".xls")):
            hits.append(fp)
    return hits


def _read_any(fp):
    if fp.lower().endswith(".csv"):
        return pd.read_csv(fp)
    return pd.read_excel(fp)  # needs openpyxl (already a pandas extra in the env)


def _pick_cols(df):
    tcol = next((c for c in df.columns if str(c).lower() in
                 ("datetime", "date", "timestamp", "time", "date_time")), None)
    pcol = next((c for c in df.columns if "2.5" in str(c) or
                 str(c).lower() in ("pm25", "pm2_5", "value")), None)
    return tcol, pcol


def parse_us_embassy(raw_dir="data/raw/zenodo_12720883") -> pd.DataFrame:
    for fp in _find_files(raw_dir, "embassy", "us.embassy", "us_embassy"):
        try:
            df = _read_any(fp)
            t, p = _pick_cols(df)
            if t and p:
                return _to_daily_pm(df, t, p)
        except Exception as e:  # noqa: BLE001
            print(f"[zenodo] could not parse {fp}: {e}")
    return pd.DataFrame(columns=["date", "pm2_5", "n_hours_pm2_5"])


def parse_clarity(raw_dir="data/raw/zenodo_12720883") -> pd.DataFrame:
    for fp in _find_files(raw_dir, "clarity"):
        try:
            df = _read_any(fp)
            t, p = _pick_cols(df)
            if t and p:
                return _to_daily_pm(df, t, p)
        except Exception as e:  # noqa: BLE001
            print(f"[zenodo] could not parse {fp}: {e}")
    return pd.DataFrame(columns=["date", "pm2_5", "n_hours_pm2_5"])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default="data/raw/zenodo_12720883")
    args = ap.parse_args(argv)
    extract_archives(args.raw_dir)
    Path("data/processed").mkdir(parents=True, exist_ok=True)
    emb = parse_us_embassy(args.raw_dir)
    if not emb.empty:
        emb.to_csv("data/processed/zenodo_bishkek_us_embassy_daily.csv", index=False)
    cl = parse_clarity(args.raw_dir)
    if not cl.empty:
        cl.to_csv("data/processed/zenodo_clarity_bishkek_daily.csv", index=False)
    print(f"[zenodo] us_embassy: {len(emb)} days; clarity: {len(cl)} days")


if __name__ == "__main__":
    main()
