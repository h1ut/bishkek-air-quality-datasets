# Baseline sanity check

Trained on `train` only; no tuning; `test` evaluated once. Dangerous = trunc1(PM2.5) >= 55.5 µg/m³.

## validation

| model | n | MAE | RMSE | bias | MAE dangerous | MAE other | n dangerous | recall | precision | CSI |
|---|---|---|---|---|---|---|---|---|---|---|
| persistence (D -> D+1) | 267 | 12.5 | 22.7 | -0.1 | 29.4 | 9.8 | 36 | 0.56 | 0.57 | 0.39 |
| train monthly climatology | 267 | 22.4 | 35.5 | +12.9 | 34.1 | 20.6 | 36 | 0.81 | 0.34 | 0.31 |
| ridge (log1p, train-fit impute+scale) | 267 | 11.8 | 19.5 | -0.8 | 30.3 | 8.9 | 36 | 0.50 | 0.62 | 0.38 |
| hist gradient boosting (log1p, defaults) | 267 | 10.4 | 18.2 | -1.2 | 28.7 | 7.5 | 36 | 0.53 | 0.76 | 0.45 |

## test

| model | n | MAE | RMSE | bias | MAE dangerous | MAE other | n dangerous | recall | precision | CSI |
|---|---|---|---|---|---|---|---|---|---|---|
| persistence (D -> D+1) | 190 | 29.7 | 50.6 | +0.4 | 53.0 | 15.5 | 72 | 0.72 | 0.70 | 0.55 |
| train monthly climatology | 190 | 39.6 | 64.5 | -1.9 | 58.6 | 27.9 | 72 | 0.71 | 0.50 | 0.41 |
| ridge (log1p, train-fit impute+scale) | 190 | 35.6 | 96.8 | +14.1 | 71.5 | 13.7 | 72 | 0.75 | 0.73 | 0.59 |
| hist gradient boosting (log1p, defaults) | 190 | 24.7 | 45.0 | -9.0 | 47.4 | 10.8 | 72 | 0.71 | 0.75 | 0.57 |
