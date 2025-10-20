-- models/marts/protocol_breakdown.sql
{{
  config(
    materialized='table'
  )
}}

SELECT
    proto,
    CASE proto
        WHEN 0 THEN 'HOPOPT'
        WHEN 1 THEN 'ICMP'
        WHEN 2 THEN 'IGMP'
        WHEN 6 THEN 'TCP'
        WHEN 17 THEN 'UDP'
        WHEN 41 THEN 'IPv6'
        WHEN 47 THEN 'GRE'
        WHEN 50 THEN 'ESP'
        WHEN 51 THEN 'AH'
        WHEN 58 THEN 'ICMPv6'
        WHEN 89 THEN 'OSPF'
        WHEN 103 THEN 'PIM'
        WHEN 112 THEN 'VRRP'
        WHEN 132 THEN 'SCTP'
        ELSE CONCAT('PROTO-', CAST(proto AS VARCHAR))
    END as protocol_name,
    count(*) as flows,
    sum(gb) as gb
FROM {{ ref('stg_ipfix_flows') }}
GROUP BY proto
ORDER BY flows DESC
