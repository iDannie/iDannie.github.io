# NYC taxi operations — SQL

## Results

2,914,490 paid January pickup records qualify for demand analysis; 2,848,985 pass the additional trip-quality filters. Midtown Center is the largest pickup zone with 141,721 records. A previous-week daily baseline for January 25–31 has 3.6% WAPE and 3,544 records/day MAE.

## Recommended next step

Use zone and hourly profiles to guide staffing review. Treat the previous-week forecast as a benchmark and test additional months before operational use. Compare routes and payment types within the stricter operations scope.

## Scope and limits

NYC TLC yellow taxi records, January 2024, local wall-clock timestamps. Counts measure recorded served demand, not unmet demand or unique customers. Demand requires a positive fare and a mapped pickup zone 1–263. Operational comparisons also require 1–180 minutes, 0–100 miles (exclusive of zero) and positive total amount. Repeated rows are retained because there is no trip ID. Total charges are not driver profit. Electronic tip recording differs from cash. One week of evaluation does not establish year-round accuracy.

## Sources

- NYC TLC trip records and source limitations: https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page
- Yellow taxi data dictionary: https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_yellow.pdf
