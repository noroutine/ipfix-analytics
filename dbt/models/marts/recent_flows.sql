-- models/marts/recent_flows.sql
{{
  config(
    materialized='table'
  )
}}

SELECT
    received_at,
    src_addr,
    dst_addr,
    src_port,
    dst_port,
    proto,
    bytes,
    packets
FROM {{ ref('stg_ipfix_flows') }}
ORDER BY received_at DESC
LIMIT 50000
