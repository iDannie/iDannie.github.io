-- Zone selection uses training data only. Full grid retains true zero-count cells.
CREATE OR REPLACE TABLE selected_zones AS
SELECT PULocationID,pickup_zone,count(*) AS training_records
FROM demand WHERE tpep_pickup_datetime<TIMESTAMP '2024-01-25'
GROUP BY 1,2 ORDER BY training_records DESC,PULocationID LIMIT 10;
CREATE OR REPLACE TABLE hourly_panel AS
WITH hours AS (SELECT unnest(generate_series(TIMESTAMP '2024-01-01',TIMESTAMP '2024-01-31 23:00:00',INTERVAL '1 hour')) AS hour),
counts AS (SELECT PULocationID,pickup_hour,count(*) AS records FROM demand GROUP BY 1,2)
SELECT h.hour,z.PULocationID,z.pickup_zone,coalesce(c.records,0) AS records
FROM hours h CROSS JOIN selected_zones z
LEFT JOIN counts c ON c.PULocationID=z.PULocationID AND c.pickup_hour=h.hour
ORDER BY z.PULocationID,h.hour;
SELECT * FROM hourly_panel ORDER BY PULocationID,hour;
