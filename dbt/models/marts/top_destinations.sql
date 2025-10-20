-- models/marts/top_destinations.sql
{{
  config(
    materialized='table'
  )
}}

SELECT
    dst_addr,
    sum(bytes) / 1024 / 1024 as mb,
    count(*) as flows,
    count(DISTINCT src_addr) as unique_sources
FROM {{ ref('stg_ipfix_flows') }}
GROUP BY dst_addr
ORDER BY mb DESC
LIMIT 100
