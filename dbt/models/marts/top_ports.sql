-- models/marts/top_ports.sql
{{
  config(
    materialized='table'
  )
}}

SELECT
    dst_port,
    CASE dst_port
        WHEN 20 THEN 'FTP-DATA'
        WHEN 21 THEN 'FTP'
        WHEN 22 THEN 'SSH'
        WHEN 23 THEN 'TELNET'
        WHEN 25 THEN 'SMTP'
        WHEN 53 THEN 'DNS'
        WHEN 67 THEN 'DHCP-SERVER'
        WHEN 68 THEN 'DHCP-CLIENT'
        WHEN 69 THEN 'TFTP'
        WHEN 80 THEN 'HTTP'
        WHEN 110 THEN 'POP3'
        WHEN 123 THEN 'NTP'
        WHEN 143 THEN 'IMAP'
        WHEN 161 THEN 'SNMP'
        WHEN 162 THEN 'SNMP-TRAP'
        WHEN 389 THEN 'LDAP'
        WHEN 443 THEN 'HTTPS'
        WHEN 445 THEN 'SMB'
        WHEN 465 THEN 'SMTPS'
        WHEN 514 THEN 'SYSLOG'
        WHEN 587 THEN 'SMTP-SUBMISSION'
        WHEN 636 THEN 'LDAPS'
        WHEN 993 THEN 'IMAPS'
        WHEN 995 THEN 'POP3S'
        WHEN 1433 THEN 'MSSQL'
        WHEN 1521 THEN 'ORACLE'
        WHEN 3306 THEN 'MYSQL'
        WHEN 3389 THEN 'RDP'
        WHEN 5432 THEN 'POSTGRESQL'
        WHEN 5900 THEN 'VNC'
        WHEN 6379 THEN 'REDIS'
        WHEN 8080 THEN 'HTTP-ALT'
        WHEN 8443 THEN 'HTTPS-ALT'
        WHEN 9200 THEN 'ELASTICSEARCH'
        WHEN 27017 THEN 'MONGODB'
        ELSE CAST(dst_port AS VARCHAR)
    END as service,
    count(*) as connections,
    sum(bytes) / 1024 / 1024 as mb
FROM {{ ref('stg_ipfix_flows') }}
GROUP BY dst_port
ORDER BY connections DESC
LIMIT 50
