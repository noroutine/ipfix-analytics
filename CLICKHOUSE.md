# ClickHouse Space Management Guide

## 🔍 Diagnosing Space Usage

### Check space by table
```sql
SELECT
    database,
    table,
    formatReadableSize(sum(bytes)) AS size,
    sum(rows) AS rows,
    count() AS parts
FROM system.parts
WHERE active
GROUP BY database, table
ORDER BY sum(bytes) DESC;
```

### Check specific table details
```sql
SELECT
    partition,
    formatReadableSize(sum(bytes)) AS size,
    sum(rows) AS rows,
    count() AS parts,
    min(modification_time) AS oldest_part,
    max(modification_time) AS newest_part
FROM system.parts
WHERE database = 'your_db' 
  AND table = 'your_table'
  AND active
GROUP BY partition
ORDER BY partition;
```

### Check disk usage
```sql
SELECT
    name,
    path,
    formatReadableSize(free_space) AS free,
    formatReadableSize(total_space) AS total
FROM system.disks;
```

### View individual parts (detailed)
```sql
SELECT
    partition,
    name,
    formatReadableSize(bytes_on_disk) AS size,
    rows,
    modification_time,
    marks
FROM system.parts
WHERE database = 'your_db' 
  AND table = 'your_table'
  AND active
ORDER BY modification_time DESC
LIMIT 50;
```

---

## 🧹 Cleaning Up Space

### For regular data tables
```sql
-- Force merge and remove deleted rows
OPTIMIZE TABLE your_table FINAL;

-- Drop old partitions
ALTER TABLE your_table DROP PARTITION 'partition_id';
```

### For system logs (immediate cleanup)
```sql
-- Truncate bloated system tables
TRUNCATE TABLE system.trace_log;
TRUNCATE TABLE system.trace_log_0;
TRUNCATE TABLE system.trace_log_1;
TRUNCATE TABLE system.trace_log_2;
TRUNCATE TABLE system.trace_log_3;
TRUNCATE TABLE system.trace_log_4;
TRUNCATE TABLE system.text_log;
TRUNCATE TABLE system.asynchronous_metric_log;
TRUNCATE TABLE system.metric_log;
TRUNCATE TABLE system.metric_log_0;
TRUNCATE TABLE system.metric_log_1;
TRUNCATE TABLE system.metric_log_2;
TRUNCATE TABLE system.metric_log_3;
TRUNCATE TABLE system.query_log;
TRUNCATE TABLE system.part_log;
TRUNCATE TABLE system.processors_profile_log;
```

### Verify cleanup
```sql
SELECT formatReadableSize(sum(bytes)) AS total_size
FROM system.parts
WHERE active AND database = 'system';
```

---

## ⚙️ Preventing Future Bloat

### Configure TTL for system logs

Edit `/etc/clickhouse-server/config.xml` or create a new file in `/etc/clickhouse-server/config.d/log-ttl.xml`:

```xml
<clickhouse>
    <query_log>
        <ttl>event_date + INTERVAL 7 DAY</ttl>
    </query_log>
    
    <trace_log>
        <!-- Disable trace_log entirely (recommended unless debugging) -->
        <enabled>false</enabled>
        <!-- OR set a short TTL -->
        <!-- <ttl>event_date + INTERVAL 1 DAY</ttl> -->
    </trace_log>
    
    <text_log>
        <ttl>event_date + INTERVAL 3 DAY</ttl>
    </text_log>
    
    <metric_log>
        <ttl>event_date + INTERVAL 7 DAY</ttl>
    </metric_log>
    
    <asynchronous_metric_log>
        <ttl>event_date + INTERVAL 7 DAY</ttl>
    </asynchronous_metric_log>
    
    <part_log>
        <ttl>event_date + INTERVAL 7 DAY</ttl>
    </part_log>
    
    <processors_profile_log>
        <!-- Disable if not needed -->
        <enabled>false</enabled>
    </processors_profile_log>
</clickhouse>
```

### Apply configuration
```bash
sudo systemctl restart clickhouse-server
```

**Important:** TTL settings only affect new data. Existing logs must be manually truncated.

---

## 📊 Common Space Issues

### Issue: Database is huge with little actual data
**Cause:** System logs (especially `trace_log`) consuming gigabytes

**Solution:** 
1. Truncate system tables immediately
2. Configure TTL or disable unnecessary logs
3. Restart ClickHouse

### Issue: Many small parts not merging
**Cause:** High insert frequency with small batches

**Solution:**
```sql
-- Force merge
OPTIMIZE TABLE your_table FINAL;

-- Adjust merge settings (per table)
ALTER TABLE your_table MODIFY SETTING 
    min_bytes_for_wide_part = 0,
    min_rows_for_wide_part = 0;
```

### Issue: Deleted rows still taking space
**Cause:** ClickHouse uses soft deletes (marks rows as deleted until merge)

**Solution:**
```sql
-- Force merge to physically remove deleted rows
OPTIMIZE TABLE your_table FINAL;
```

### Issue: Old partitions not dropping
**Cause:** Manual partition management required

**Solution:**
```sql
-- List partitions
SELECT DISTINCT partition 
FROM system.parts 
WHERE table = 'your_table' AND active;

-- Drop old partitions
ALTER TABLE your_table DROP PARTITION '20240101';
```

---

## 🎯 Best Practices for IPFIX/Flow Data

For high-velocity data that's regularly deleted (like IPFIX):

1. **Use partitioning by day/hour:**
   ```sql
   ENGINE = MergeTree()
   PARTITION BY toYYYYMMDD(timestamp)
   ORDER BY (timestamp, src_ip, dst_ip);
   ```

2. **Set TTL on the table:**
   ```sql
   ALTER TABLE ipfix_raw_data 
   MODIFY TTL timestamp + INTERVAL 7 DAY;
   ```

3. **Drop old partitions instead of DELETE:**
   ```sql
   -- Much faster than DELETE
   ALTER TABLE ipfix_raw_data DROP PARTITION '20241120';
   ```

4. **Batch inserts:** Insert in batches of 10k-100k rows rather than row-by-row

5. **Monitor system logs:** They grow fast with high insert rates

---

## 🚀 Quick Reference Commands

```bash
# Check ClickHouse status
sudo systemctl status clickhouse-server

# View logs
sudo journalctl -u clickhouse-server -f

# Restart ClickHouse
sudo systemctl restart clickhouse-server

# Connect to ClickHouse
clickhouse-client
```

```sql
-- Quick space check
SELECT database, formatReadableSize(sum(bytes)) AS size
FROM system.parts WHERE active
GROUP BY database;

-- Force all system logs to flush
SYSTEM FLUSH LOGS;

-- Stop merges (emergency)
SYSTEM STOP MERGES;

-- Resume merges
SYSTEM START MERGES;
```

---

## 📝 Notes

- **trace_log** is the biggest space consumer - disable it unless actively debugging
- TTL deletions happen during background merges, not immediately
- `OPTIMIZE TABLE ... FINAL` can be resource-intensive on large tables
- System logs grow proportionally to query and insert frequency
- ClickHouse is optimized for immutable data - frequent deletes/updates are expensive