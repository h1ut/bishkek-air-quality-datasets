"""Chronological split assignment (by TARGET date) and train-only preprocessing."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd


def _windows(spec):
    return [spec] if isinstance(spec[0], str) else spec


def assign(X: pd.DataFrame, splits: dict, embargo_days: int) -> pd.Series:
    """Split label per row, decided by the row's TARGET date (issue date + horizon).

    Splits are chronological (train < validation < test). Because every feature of a row is
    computed from days <= its issue date, a train row can never see validation/test days.
    The gap between the last target of one split and the first target of the next must be
    >= ``embargo_days`` (asserted); rows whose target falls in a gap are labelled 'embargo'
    and are not used, which damps the optimism caused by day-to-day autocorrelation.
    """
    lab = pd.Series("embargo", index=X.index, dtype=object)
    order = ["train", "validation", "test"]
    prev_end = None
    for name in order:
        ws = _windows(splits[name])
        first = min(pd.Timestamp(a) for a, _ in ws)
        if prev_end is not None:
            gap = (first - prev_end).days - 1
            assert gap >= embargo_days, f"{name}: gap {gap} d < embargo {embargo_days} d"
        span = X["target_date"].between(first, max(pd.Timestamp(b) for _, b in ws))
        lab[span] = "excluded_window"       # between two windows of the same split (no usable target)
        for a, b in ws:
            lab[X["target_date"].between(pd.Timestamp(a), pd.Timestamp(b))] = name
        prev_end = max(pd.Timestamp(b) for _, b in ws)
    lab[X["target_date"] < min(pd.Timestamp(a) for a, _ in _windows(splits["train"]))] = "unused"
    lab[X["target_date"] > prev_end] = "unused"
    return lab


class TrainOnlyPreprocessor:
    """Median imputation + standardisation, parameters estimated on TRAIN rows only.

    Missing-indicator columns are added for features with any missing value in train, so a
    model can tell an imputed value from a measured one. The target is never touched.
    """

    def __init__(self, columns: list[str]):
        self.columns = list(columns)
        self.median_: dict = {}
        self.mean_: dict = {}
        self.std_: dict = {}
        self.indicators_: list[str] = []

    def fit(self, train: pd.DataFrame) -> "TrainOnlyPreprocessor":
        for c in self.columns:
            s = pd.to_numeric(train[c], errors="coerce").astype(float)
            med = float(s.median()) if s.notna().any() else 0.0
            filled = s.fillna(med)
            self.median_[c] = med
            self.mean_[c] = float(filled.mean())
            sd = float(filled.std(ddof=0))
            self.std_[c] = sd if sd > 0 else 1.0
            if s.isna().any():
                self.indicators_.append(c)
        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        cols = {}
        for c in self.columns:
            s = pd.to_numeric(df[c], errors="coerce").astype(float)
            cols[c] = (s.fillna(self.median_[c]) - self.mean_[c]) / self.std_[c]
        for c in self.indicators_:
            cols[f"{c}__missing"] = df[c].isna().astype(np.int8)
        return pd.DataFrame(cols, index=df.index)

    def to_json(self) -> str:
        return json.dumps({"fitted_on": "train", "columns": self.columns, "median": self.median_,
                           "mean_after_impute": self.mean_, "std_after_impute": self.std_,
                           "missing_indicators": self.indicators_}, indent=1)
