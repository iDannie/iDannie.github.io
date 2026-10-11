-- Source has no trip ID: retain repeated rows, and describe counts as records.
CREATE OR REPLACE TABLE trips AS
SELECT *, (epoch(tpep_dropoff_datetime)-epoch(tpep_pickup_datetime))/60.0 AS duration_minutes,
 date_trunc('hour',tpep_pickup_datetime) AS pickup_hour
FROM source_trips;
-- Paid pickup records, January local NYC wall time, identifiable physical pickup zones.
CREATE OR REPLACE TABLE demand AS
SELECT t.*,z.Zone AS pickup_zone,z.Borough AS pickup_borough
FROM trips t JOIN zones z ON t.PULocationID=z.LocationID
WHERE tpep_pickup_datetime>=TIMESTAMP '2024-01-01'
 AND tpep_pickup_datetime<TIMESTAMP '2024-02-01'
 AND t.PULocationID BETWEEN 1 AND 263 AND fare_amount>0;
-- Separate stricter scope for trip-duration / monetary comparisons.
CREATE OR REPLACE TABLE operations AS
SELECT * FROM demand WHERE duration_minutes BETWEEN 1 AND 180
 AND trip_distance>0 AND trip_distance<=100 AND total_amount>0;
