# Data dictionary

| column | source | unit | aggregation | caveat |
|---|---|---|---|---|
| cell_id | TODO-REVIEW | TODO-REVIEW | TODO-REVIEW | TODO-REVIEW |
| lat | TODO-REVIEW | TODO-REVIEW | TODO-REVIEW | TODO-REVIEW |
| lon | TODO-REVIEW | TODO-REVIEW | TODO-REVIEW | TODO-REVIEW |
| date | TODO-REVIEW | TODO-REVIEW | TODO-REVIEW | TODO-REVIEW |
| n_hours_pm2_5 | derived | count | hours present that day | <18 ⇒ day flagged |
| pm2_5 | OpenAQ/AirNow or CAMS | µg/m³ | hourly→daily mean; _max kept | ground = measured; grid = model, needs validation |
| pm2_5_max | OpenAQ/AirNow or CAMS | µg/m³ | daily max | ground = measured; grid = model, needs validation |
| n_hours_pm10 | derived | count | hours present that day | <18 ⇒ day flagged |
| pm10 | OpenAQ or CAMS | µg/m³ | daily mean | as pm2_5 |
| pm10_max | OpenAQ or CAMS | µg/m³ | daily max | as pm2_5 |
| n_hours_carbon_monoxide | derived | count | hours present that day | <18 ⇒ day flagged |
| carbon_monoxide | OpenAQ or CAMS | µg/m³ (OpenAQ) / µg/m³ (CAMS) | daily mean | check unit per source; CAMS is µg/m³ |
| carbon_monoxide_max | OpenAQ or CAMS | µg/m³ (OpenAQ) / µg/m³ (CAMS) | daily max | check unit per source; CAMS is µg/m³ |
| n_hours_nitrogen_dioxide | derived | count | hours present that day | <18 ⇒ day flagged |
| nitrogen_dioxide | OpenAQ or CAMS | µg/m³ | daily mean | as pm2_5 |
| nitrogen_dioxide_max | OpenAQ or CAMS | µg/m³ | daily max | as pm2_5 |
| n_hours_sulphur_dioxide | derived | count | hours present that day | <18 ⇒ day flagged |
| sulphur_dioxide | OpenAQ or CAMS | µg/m³ | daily mean | as pm2_5 |
| sulphur_dioxide_max | OpenAQ or CAMS | µg/m³ | daily max | as pm2_5 |
| n_hours_ozone | derived | count | hours present that day | <18 ⇒ day flagged |
| ozone | OpenAQ or CAMS | µg/m³ | daily mean | as pm2_5 |
| ozone_max | OpenAQ or CAMS | µg/m³ | daily max | as pm2_5 |
| n_hours_aerosol_optical_depth | derived | count | hours present that day | <18 ⇒ day flagged |
| aerosol_optical_depth | CAMS | unitless | daily mean | model; column property |
| aerosol_optical_depth_max | CAMS | unitless | daily max | model; column property |
| n_hours_dust | derived | count | hours present that day | <18 ⇒ day flagged |
| dust | CAMS | µg/m³ | daily mean | model surface dust estimate |
| dust_max | CAMS | µg/m³ | daily max | model surface dust estimate |
| n_hours_temperature_2m | derived | count | hours present that day | <18 ⇒ day flagged |
| temperature_2m | ERA5 | °C | daily mean; _max kept | reanalysis |
| temperature_2m_max | ERA5 | °C | daily max | reanalysis |
| n_hours_relative_humidity_2m | derived | count | hours present that day | <18 ⇒ day flagged |
| relative_humidity_2m | ERA5 | % | daily mean | reanalysis |
| relative_humidity_2m_max | ERA5 | % | daily max | reanalysis |
| n_hours_wind_speed_10m | derived | count | hours present that day | <18 ⇒ day flagged |
| wind_speed_10m | ERA5 | m/s | daily mean | reanalysis |
| wind_speed_10m_max | ERA5 | m/s | daily max | reanalysis |
| n_hours_wind_direction_10m | derived | count | hours present that day | <18 ⇒ day flagged |
| wind_direction_10m | ERA5 | ° from N | daily vector mean | reanalysis |
| n_hours_surface_pressure | derived | count | hours present that day | <18 ⇒ day flagged |
| surface_pressure | ERA5 | hPa | daily mean | reanalysis |
| surface_pressure_max | ERA5 | hPa | daily max | reanalysis |
| n_hours_boundary_layer_height | derived | count | hours present that day | <18 ⇒ day flagged |
| boundary_layer_height | ERA5 | m | daily mean | reanalysis; key for winter inversions |
| boundary_layer_height_max | ERA5 | m | daily max | reanalysis; key for winter inversions |
| sparse | TODO-REVIEW | TODO-REVIEW | TODO-REVIEW | TODO-REVIEW |
| dangerous_day | derived | bool | pm2_5 > 55.4 | EPA Unhealthy daily |
| exceeds_kg_limit | derived | bool | pm2_5 > 35 | Kyrgyz national daily limit |