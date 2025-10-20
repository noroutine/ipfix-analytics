-- sources/hourly_traffic.sql
SELECT * FROM traffic_by_hour
WHERE hour >= current_date - interval '7 days'
ORDER BY hour