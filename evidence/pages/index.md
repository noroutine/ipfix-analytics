---
title: Network Traffic Dashboard
---
<!-- pages/dashboard.md -->

## Summary Statistics
```sql stats
SELECT * FROM overview_stats
```

<BigValue 
  data={stats} 
  value=total_flows 
  title="Total Flows"
  fmt='#,##0'
/>

<BigValue 
  data={stats} 
  value=total_gb 
  title="Total Traffic (GB)"
  fmt='#,##0.00'
/>

<BigValue 
  data={stats} 
  value=unique_sources 
  title="Unique Sources"
  fmt='#,##0'
/>

<BigValue 
  data={stats} 
  value=unique_destinations 
  title="Unique Destinations"
  fmt='#,##0'
/>

---

## Traffic Over Time
```sql traffic_chart
SELECT * FROM hourly_traffic
```

<LineChart
  data={traffic_chart}
  x=hour
  y=total_gb
  xFmt="UTC"
  yAxisTitle="Gigabytes"
  title="Hourly Traffic Volume"
/>

---

## Top Talkers

```sql top_talkers_by_bytes
SELECT * FROM top_talkers_by_bytes
```

<DataTable data={top_talkers_by_bytes} rows=20>
  <Column id=src_addr/>
  <Column id=mb fmt='#,##0.00'/>
  <Column id=packets fmt='#,##0'/>
  <Column id=flows fmt='#,##0'/>
  <Column id=unique_dsts fmt='#,##0'/>
</DataTable>

<BarChart 
  data={top_talkers_by_bytes}
  x=src_addr
  y=mb
  swapXY=true
  title="Top 20 Sources by Traffic"
  limit=20
/>

---

## Protocol Distribution

```sql protocol_breakdown
SELECT * FROM protocol_breakdown
```

<BarChart 
  data={protocol_breakdown}
  x=protocol_name
  y=gb
  title="Traffic by Protocol"
/>

<DataTable data={protocol_breakdown}/>

---

## Top Services (by Port)

```sql top_ports
SELECT * FROM top_ports
```

<BarChart 
  data={top_ports}
  x=service
  y=mb
  title="Top Services by Traffic"
  limit=20
  swapXY=true
/>

---

## Top Destinations

```sql top_destinations
SELECT * FROM top_destinations
```

<DataTable data={top_destinations} rows=20>
  <Column id=dst_addr/>
  <Column id=mb fmt='#,##0.00'/>
  <Column id=flows fmt='#,##0'/>
  <Column id=unique_sources fmt='#,##0'/>
</DataTable>

<BarChart
  data={top_destinations}
  x=dst_addr
  y=mb
  swapXY=true
  title="Top 20 Destinations by Traffic"
  limit=20
/>

---

## Top Conversations
```sql top_convos
SELECT * FROM traffic_matrix LIMIT 20
```

<DataTable data={top_convos}>
  <Column id=src_addr/>
  <Column id=dst_addr/>
  <Column id=mb fmt='#,##0.00'/>
  <Column id=flows fmt='#,##0'/>
</DataTable>

---

## Recent Flows

```sql recent_flows
SELECT * FROM recent_flows LIMIT 100
```

<DataTable data={recent_flows}>
  <Column id=received_at/>
  <Column id=src_addr/>
  <Column id=dst_addr/>
  <Column id=src_port fmt='###0'/>
  <Column id=dst_port fmt='###0'/>
  <Column id=proto/>
  <Column id=bytes fmt='#,##0'/>
  <Column id=packets fmt='#,##0'/>
</DataTable>