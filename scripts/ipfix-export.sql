SET send_progress_in_http_headers = 1;
-- SET send_logs_level = 'trace';  -- Everything (too noisy for cron jobs)
-- SET send_logs_level = 'information';  -- Errors, warnings, and basic info
SET send_logs_level = 'warning';
SET log_queries = 1;

-- Step 1: Mark everything for export
SELECT concat('Rows to export: ', toString(count())) FROM playground.ipfix_raw_data WHERE exported = 0;

ALTER TABLE playground.ipfix_raw_data
UPDATE exported = 1
WHERE exported = 0
SETTINGS mutations_sync = 1; -- wait for mutation

SELECT 'Step 1 complete: Marked rows for export' AS status;
SELECT concat('Rows marked: ', toString(count())) FROM playground.ipfix_raw_data WHERE exported = 1;

-- Step 2: Export what is marked
INSERT INTO FUNCTION s3(
    concat('https://{{ s3_endpoint }}/{{ s3_bucket }}/ipfix_decoded_', formatDateTime(now(), '%Y%m%d_%H%i%S'), '.parquet'),
    '{{ s3_access_key }}',
    '{{ s3_secret_key }}',
    'Parquet'
)
SELECT
    -- Format MAC addresses
    CASE
        WHEN src_mac = 0 THEN NULL
        ELSE concat(
            lpad(hex(bitShiftRight(src_mac, 40)), 2, '0'), ':',
            lpad(hex(bitAnd(bitShiftRight(src_mac, 32), 255)), 2, '0'), ':',
            lpad(hex(bitAnd(bitShiftRight(src_mac, 24), 255)), 2, '0'), ':',
            lpad(hex(bitAnd(bitShiftRight(src_mac, 16), 255)), 2, '0'), ':',
            lpad(hex(bitAnd(bitShiftRight(src_mac, 8), 255)), 2, '0'), ':',
            lpad(hex(bitAnd(src_mac, 255)), 2, '0')
        )
    END AS src_mac,

    CASE
        WHEN dst_mac = 0 THEN NULL
        ELSE concat(
            lpad(hex(bitShiftRight(dst_mac, 40)), 2, '0'), ':',
            lpad(hex(bitAnd(bitShiftRight(dst_mac, 32), 255)), 2, '0'), ':',
            lpad(hex(bitAnd(bitShiftRight(dst_mac, 24), 255)), 2, '0'), ':',
            lpad(hex(bitAnd(bitShiftRight(dst_mac, 16), 255)), 2, '0'), ':',
            lpad(hex(bitAnd(bitShiftRight(dst_mac, 8), 255)), 2, '0'), ':',
            lpad(hex(bitAnd(dst_mac, 255)), 2, '0')
        )
    END AS dst_mac,

    tcp_flags,
    time_received_ns,
    time_flow_start_ns,
    time_flow_end_ns,

    -- Sampler address
    IPv4NumToString(byteSwap(reinterpretAsUInt32(sampler_address))) AS sampler_address,

    -- Source and destination IPs
    CASE
        WHEN etype = 2048 THEN IPv4NumToString(byteSwap(reinterpretAsUInt32(src_addr)))
        WHEN etype = 34525 THEN IPv6NumToString(src_addr)
        ELSE 'unknown'
    END AS src_addr,

    CASE
        WHEN etype = 2048 THEN IPv4NumToString(byteSwap(reinterpretAsUInt32(dst_addr)))
        WHEN etype = 34525 THEN IPv6NumToString(dst_addr)
        ELSE 'unknown'
    END AS dst_addr,

    in_if,
    out_if,
    ingress_vrf_id,
    dot1q_vlan,
    post_dot1q_vlan,
    dot1q_cvlan,
    post_dot1q_cvlan,
    etype,
    proto,
    src_port,
    dst_port,
    bytes,
    packets,
    custom_integer_1,
    custom_integer_2
FROM playground.ipfix_raw_data
WHERE exported = 1
SETTINGS output_format_parquet_compression_method='zstd';

SELECT 'Step 2 complete: Exported to S3' AS status;


-- Step 3: Delete exported records
ALTER TABLE playground.ipfix_raw_data
DELETE WHERE exported = 1;

SELECT 'Step 3 complete: Deleted exported rows' AS status;