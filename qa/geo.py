from __future__ import annotations
import pandas as pd

BISHKEK_LAT = 42.8746
BISHKEK_LON = 74.5698


def nearest_cell_id(grid_df: pd.DataFrame, lat: float = BISHKEK_LAT,
                    lon: float = BISHKEK_LON) -> str:
    if grid_df is None or len(grid_df) == 0:
        raise ValueError("grid_df is empty; cannot pick a nearest cell")
    d = (grid_df["lat"] - lat) ** 2 + (grid_df["lon"] - lon) ** 2
    return str(grid_df.loc[d.idxmin(), "cell_id"])
