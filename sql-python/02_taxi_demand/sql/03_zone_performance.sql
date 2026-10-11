SELECT PULocationID,pickup_zone,pickup_borough,count(*) AS eligible_records,
 median(duration_minutes) AS median_duration_minutes,
 median(trip_distance) AS median_distance_miles,
 sum(fare_amount) AS recorded_base_fare_usd,
 sum(total_amount) AS recorded_total_amount_usd,
 avg(CASE WHEN payment_type=1 AND fare_amount>0 THEN tip_amount/fare_amount END) AS credit_tip_to_fare_ratio
FROM operations GROUP BY 1,2,3 ORDER BY eligible_records DESC;
