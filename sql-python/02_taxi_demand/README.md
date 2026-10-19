# NYC taxi demand and forecast comparison

The previous-week baseline produced lower forecast error than the calendar-based regression model.

[Read the full findings report](https://idannie.github.io/sql-python/02_taxi_demand/outputs/report.html)

## Executive summary

The analysis retained 2,914,490 qualifying pickup records from January 2024. Across ten busy pickup zones, the previous-week forecast achieved 14.62% weighted absolute percentage error, compared with 16.93% for a weekday-hour average and 24.58% for Poisson regression. The more complex model did not improve accuracy in the final seven-day test period.

## Business objective

The project examined where taxi pickups were concentrated and compared hourly forecasting methods to support dispatch and staffing planning. Evaluation focused on forecast accuracy, rather than claiming a change in fleet performance.

## Finding 1 · A simple weekly baseline performed best

Using the same zone and hour from the previous week produced a mean absolute error of 23.3 pickup records per zone-hour, versus 39.2 for Poisson regression. Its weighted percentage error was approximately 40.5% lower than the regression model’s. This result favors retaining a transparent baseline when added model complexity does not deliver better forecasts.

## Finding 2 · High-volume zones included airports and central Manhattan

JFK Airport led the training-period ranking with 113,476 qualifying pickups, followed by Midtown Center with 106,922 and Upper East Side South with 106,007. The ten forecast zones were selected using January 1–24 only, keeping the final week independent of zone selection.

## Finding 3 · Busy local routes had variable travel times

The highest-volume route in the operational comparison ran from Upper East Side South to Upper East Side North: 21,615 records, a median duration of 6.8 minutes and a 90th-percentile duration of 12.0 minutes. Planning around average or typical travel time alone would miss the longer trips represented in this upper tail.

## Analysis and source code

SQL queries are in `sql/`; Python analysis is in `run.py` and `analysis.ipynb`. Saved results and charts are in `outputs/`.

[Technical documentation and reproduction steps](TECHNICAL.md) · [Data definitions](DATA_DICTIONARY.md)
