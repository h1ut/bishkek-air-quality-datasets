# Data dictionary

| column | source | unit | aggregation | caveat |
|---|---|---|---|---|
| aerosol_optical_depth | CAMS | unitless | daily mean | model; column property |
| aerosol_optical_depth_max | CAMS | unitless | daily max | model; column property |
| boundary_layer_height | ERA5 | m | daily mean | reanalysis; key for winter inversions |
| boundary_layer_height_max | ERA5 | m | daily max | reanalysis; key for winter inversions |
| carbon_monoxide | OpenAQ or CAMS | µg/m³ (CAMS); OpenAQ CO may be mg/m³ or ppm depending on provider — check per station | daily mean | check unit per source; CAMS is µg/m³ |
| carbon_monoxide_max | OpenAQ or CAMS | µg/m³ (CAMS); OpenAQ CO may be mg/m³ or ppm depending on provider — check per station | daily max | check unit per source; CAMS is µg/m³ |
| carbon_monoxide_source | derived | text | which source supplied `carbon_monoxide` for this row | provenance |
| cell_id | derived | id | grid cell key `<lat:.4f>_<lon:.4f>` | — |
| city | OpenAQ | name | source city label | — |
| dangerous_day | derived | bool | pm2_5 > 55.4 | EPA Unhealthy daily; <NA> where pm2_5 is missing (not the same as False) |
| date | derived | date | UTC calendar day | — |
| dust | CAMS | µg/m³ | daily mean | model surface dust estimate |
| dust_max | CAMS | µg/m³ | daily max | model surface dust estimate |
| exceeds_kg_limit | derived | bool | pm2_5 > 35 | Kyrgyz national daily limit; <NA> where pm2_5 is missing (not the same as False) |
| lat | grid/station | degrees | point coordinate | — |
| lon | grid/station | degrees | point coordinate | — |
| n_hours_aerosol_optical_depth | derived | count | hours present that day | <18 ⇒ day flagged |
| n_hours_boundary_layer_height | derived | count | hours present that day | <18 ⇒ day flagged |
| n_hours_carbon_monoxide | derived | count | hours present that day | <18 ⇒ day flagged |
| n_hours_dust | derived | count | hours present that day | <18 ⇒ day flagged |
| n_hours_nitrogen_dioxide | derived | count | hours present that day | <18 ⇒ day flagged |
| n_hours_ozone | derived | count | hours present that day | <18 ⇒ day flagged |
| n_hours_pm10 | derived | count | hours present that day | <18 ⇒ day flagged |
| n_hours_pm2_5 | derived | count | hours present that day | <18 ⇒ day flagged |
| n_hours_relative_humidity_2m | derived | count | hours present that day | <18 ⇒ day flagged |
| n_hours_sulphur_dioxide | derived | count | hours present that day | <18 ⇒ day flagged |
| n_hours_surface_pressure | derived | count | hours present that day | <18 ⇒ day flagged |
| n_hours_temperature_2m | derived | count | hours present that day | <18 ⇒ day flagged |
| n_hours_wind_direction_10m | derived | count | hours present that day | <18 ⇒ day flagged |
| n_hours_wind_speed_10m | derived | count | hours present that day | <18 ⇒ day flagged |
| nitrogen_dioxide | OpenAQ or CAMS | µg/m³ | daily mean | as pm2_5 |
| nitrogen_dioxide_max | OpenAQ or CAMS | µg/m³ | daily max | as pm2_5 |
| nitrogen_dioxide_source | derived | text | which source supplied `nitrogen_dioxide` for this row | provenance |
| ozone | OpenAQ or CAMS | µg/m³ | daily mean | as pm2_5 |
| ozone_max | OpenAQ or CAMS | µg/m³ | daily max | as pm2_5 |
| ozone_source | derived | text | which source supplied `ozone` for this row | provenance |
| pm10 | OpenAQ or CAMS | µg/m³ | daily mean | as pm2_5 |
| pm10_max | OpenAQ or CAMS | µg/m³ | daily max | as pm2_5 |
| pm10_source | derived | text | which source supplied `pm10` for this row | provenance |
| pm2_5 | OpenAQ/AirNow or CAMS | µg/m³ | hourly→daily mean; _max kept | ground = measured; grid = model, needs validation |
| pm2_5_max | OpenAQ/AirNow or CAMS | µg/m³ | daily max | ground = measured; grid = model, needs validation |
| pm2_5_source | derived | text | which source supplied `pm2_5` for this row | provenance |
| relative_humidity | OpenAQ | % | hourly→daily mean | ground station co-located met; sensor-dependent |
| relative_humidity_2m | ERA5 | % | daily mean | reanalysis |
| relative_humidity_2m_max | ERA5 | % | daily max | reanalysis |
| sparse | derived | bool | any source had <18 h that day | flag, not a value |
| station_key | derived | id | station/city identifier | — |
| sulphur_dioxide | OpenAQ or CAMS | µg/m³ | daily mean | as pm2_5 |
| sulphur_dioxide_max | OpenAQ or CAMS | µg/m³ | daily max | as pm2_5 |
| sulphur_dioxide_source | derived | text | which source supplied `sulphur_dioxide` for this row | provenance |
| surface_pressure | ERA5 | hPa | daily mean | reanalysis |
| surface_pressure_max | ERA5 | hPa | daily max | reanalysis |
| temperature | OpenAQ | °C | hourly→daily mean; _max kept | ground station co-located met; sensor-dependent |
| temperature_2m | ERA5 | °C | daily mean; _max kept | reanalysis |
| temperature_2m_max | ERA5 | °C | daily max | reanalysis |
| wind_direction_10m | ERA5 | ° from N | daily vector mean | reanalysis |
| wind_speed_10m | ERA5 | m/s | daily mean | reanalysis |
| wind_speed_10m_max | ERA5 | m/s | daily max | reanalysis |
