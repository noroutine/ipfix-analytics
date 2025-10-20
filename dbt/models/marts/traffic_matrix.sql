-- models/marts/traffic_matrix.sql
{{
  config(
    materialized='table'
  )
}}

SELECT
    src_addr,
    dst_addr,
    sum(bytes) / 1024 / 1024 as mb,
    count(*) as flows
FROM {{ ref('stg_ipfix_flows') }}
GROUP BY src_addr, dst_addr
ORDER BY mb DESC
LIMIT 500
