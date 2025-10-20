-- models/marts/overview_stats.sql
{{
  config(
    materialized='table'
  )
}}

SELECT
    count(*) as total_flows,
    sum(gb) as total_gb,
    count(DISTINCT src_addr) as unique_sources,
    count(DISTINCT dst_addr) as unique_destinations,
    min(received_at) as start_time,
    max(received_at) as end_time
FROM {{ ref('stg_ipfix_flows') }}
