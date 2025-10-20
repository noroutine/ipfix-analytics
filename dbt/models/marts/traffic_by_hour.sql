-- models/marts/traffic_by_hour.sql
{{
  config(
    materialized='table'
  )
}}

SELECT 
    received_hour as hour,
    sum(gb) as total_gb,
    count(*) as flow_count,
    avg(bytes) as avg_bytes_per_flow,
    count(distinct src_addr) as unique_sources,
    count(distinct dst_addr) as unique_destinations
FROM {{ ref('stg_ipfix_flows') }}
GROUP BY received_hour
ORDER BY received_hour