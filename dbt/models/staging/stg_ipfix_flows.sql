-- models/staging/stg_ipfix_flows.sql
{{
  config(
    materialized='table'
  )
}}

SELECT
    to_timestamp(time_received_ns / 1000000000) as received_at,
    date_trunc('hour', to_timestamp(time_received_ns / 1000000000)) as received_hour,
    date_trunc('day', to_timestamp(time_received_ns / 1000000000)) as received_date,
    bytes,
    bytes / 1024.0 / 1024.0 / 1024.0 as gb,
    packets,
    src_addr,
    dst_addr,
    src_port,
    dst_port,
    proto
FROM read_parquet('s3://ipfix/ipfix_*.parquet')