-- DuckDB SQL. Inputs: source_data (trip records), source_zones (one row per LocationID).
CREATE OR REPLACE TEMP TABLE demand AS
SELECT s.*, z.Zone AS zone, date_trunc('day',tpep_pickup_datetime) AS day,
       hour(tpep_pickup_datetime) AS hour,
       (epoch(tpep_dropoff_datetime)-epoch(tpep_pickup_datetime))/60.0 AS minutes
FROM source_data s JOIN source_zones z ON s.PULocationID=z.LocationID
WHERE tpep_pickup_datetime >= DATE '2024-01-01' AND tpep_pickup_datetime < DATE '2024-02-01'
  AND s.PULocationID BETWEEN 1 AND 263 AND fare_amount>0;

CREATE OR REPLACE TEMP TABLE operations AS
SELECT * FROM demand WHERE minutes BETWEEN 1 AND 180
  AND trip_distance>0 AND trip_distance<=100 AND total_amount>0;

CREATE OR REPLACE TABLE daily AS
WITH calendar AS (
    SELECT day FROM generate_series(TIMESTAMP '2024-01-01',TIMESTAMP '2024-01-31',INTERVAL '1 day') t(day)
), counts AS (SELECT day,count(*) AS records FROM demand GROUP BY day), filled AS (
    SELECT c.day,coalesce(n.records,0) AS records FROM calendar c LEFT JOIN counts n USING(day)
)
SELECT *,CASE WHEN count(*) OVER w=7 THEN avg(records) OVER w END AS rolling_seven_day_mean
FROM filled WINDOW w AS(ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) ORDER BY day;

CREATE OR REPLACE TABLE hourly AS
SELECT h.hour,count(d.hour) AS records FROM range(24) h(hour)
LEFT JOIN demand d USING(hour) GROUP BY h.hour ORDER BY h.hour;

CREATE OR REPLACE TABLE zones AS
WITH counts AS (SELECT PULocationID,zone,count(*) AS records FROM demand GROUP BY 1,2)
SELECT *,records::DOUBLE/sum(records) OVER() AS workload_share,
       sum(records) OVER(ORDER BY records DESC,PULocationID ROWS UNBOUNDED PRECEDING)::DOUBLE
         /sum(records) OVER() AS cumulative_share
FROM counts ORDER BY records DESC,PULocationID;

CREATE OR REPLACE TABLE routes AS
SELECT PULocationID,DOLocationID,count(*) AS records,median(minutes) AS median_minutes,
       avg(total_amount) AS mean_charge
FROM operations GROUP BY 1,2 HAVING count(*)>=100
ORDER BY records DESC,PULocationID,DOLocationID;

CREATE OR REPLACE TABLE payments AS
SELECT payment_type,count(*) AS records,avg(total_amount) AS mean_charge,avg(tip_amount) AS mean_recorded_tip
FROM operations GROUP BY payment_type ORDER BY payment_type;

-- Calendar spine ensures LAG(7) means seven days, including any zero-count days.
-- Form lags before selecting the holdout; Jan 25-31 predictions use Jan 18-24 only.
CREATE OR REPLACE TABLE forecast AS
WITH predictions AS(SELECT day,records,lag(records,7) OVER(ORDER BY day) AS prediction FROM daily)
SELECT *,prediction-records AS error FROM predictions WHERE day>=DATE '2024-01-25' ORDER BY day;
CREATE OR REPLACE TABLE forecast_metrics AS
SELECT avg(abs(error)) AS mae,sum(abs(error))::DOUBLE/nullif(sum(records),0) AS wape,
       sum(error)::DOUBLE/nullif(sum(records),0) AS bias_share FROM forecast;

CREATE OR REPLACE TABLE quality AS
SELECT (SELECT count(*) FROM source_data) AS source_rows,
       (SELECT count(*) FROM demand) AS demand_records,
       (SELECT count(*) FROM operations) AS operations_records,
       (SELECT count(*) FROM source_data)-(SELECT count(*) FROM demand) AS excluded_demand_records;
CREATE OR REPLACE TABLE validation AS
SELECT 'unique_zone_lookup' AS check_name,count(*)=count(DISTINCT LocationID) AS passed FROM source_zones
UNION ALL SELECT 'daily_reconciles',(SELECT sum(records) FROM daily)=(SELECT count(*) FROM demand)
UNION ALL SELECT 'zones_reconcile',(SELECT sum(records) FROM zones)=(SELECT count(*) FROM demand)
UNION ALL SELECT 'hourly_reconcile',(SELECT sum(records) FROM hourly)=(SELECT count(*) FROM demand)
UNION ALL SELECT 'seven_predictions',count(*)=7 AND count(prediction)=7 FROM forecast
UNION ALL SELECT 'operations_subset',(SELECT count(*) FROM operations)<=(SELECT count(*) FROM demand);
