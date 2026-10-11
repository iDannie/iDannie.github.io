-- Minimum volume prevents single-trip routes dominating rankings.
WITH routes AS (
 SELECT o.pickup_zone,z.Zone AS dropoff_zone,count(*) AS records,
 median(duration_minutes) AS median_minutes,quantile_cont(duration_minutes,.9) AS p90_minutes,
 median(trip_distance) AS median_miles
 FROM operations o JOIN zones z ON o.DOLocationID=z.LocationID
 WHERE o.DOLocationID BETWEEN 1 AND 263 GROUP BY 1,2 HAVING count(*)>=100
)
SELECT *,dense_rank() OVER(ORDER BY records DESC) AS volume_rank FROM routes ORDER BY records DESC LIMIT 30;
