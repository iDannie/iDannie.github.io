# Data dictionary

| Field | Meaning / handling |
|---|---|
| tpep_pickup_datetime / tpep_dropoff_datetime | Reported trip timestamps, treated as NYC local wall time. |
| PULocationID / DOLocationID | TLC zone identifiers joined to LocationID in the lookup. |
| fare_amount | Metered fare amount; positive value required for demand scope. |
| total_amount | Total recorded passenger charge, not driver profit. |
| trip_distance | Reported distance in miles. |
| duration_minutes | Difference between reported timestamps in minutes. |
| payment_type | 1 = credit card; 2 = cash. Credit tips only used for tip-to-fare summaries. |
| tip_amount | Recorded tips, excluding cash tips. |
| records | Count of source records in a selected pickup zone and hour. |
| last_week | Corresponding observed count 168 hours before test hour. |
| weekday_hour_mean | Training mean for zone × weekday × hour. |
| poisson | Calendar model expected count; fractional values are valid expectations. |

Demand: January pickups, known physical pickup zone 1–263 and positive base fare. Operations add 1–180 minutes, distance >0 and ≤100 miles, positive total charge. Selected zones: top 10 by training records only. Grid: 10 × 744 hours. Prediction origin: 2024-01-25 00:00. Holdout: next 168 hours. No duplicate removal without a unique trip ID.
