-- models/marts/top_talkers_by_bytes.sql
{{
  config(
    materialized='table'
  )
}}

SELECT
    src_addr,
    sum(bytes) / 1024 / 1024 as mb,
    sum(packets) as packets,
    count(*) as flows,
    count(DISTINCT dst_addr) as unique_dsts
FROM {{ ref('stg_ipfix_flows') }}
GROUP BY src_addr
ORDER BY mb DESC
LIMIT 100
