# PromQL notes

## 1. Throughput (images per minute)
```promql
sum by (mode) (rate(caption_images_processed_total{status="success"}[$__rate_interval])) * 60
```
Prompt used: "PromQL for images per minute grouped by mode from counter caption_images_processed_total with a status label"

- `rate()` = (last sample - first sample) / seconds in the window, handling counter resets.
- `* 60` converts per-second to per-minute.
- counter is 10 at t=0 s and 16 at t=30 s, so rate = 6/30 = 0.2 img/s, times 60 = **12 img/min**.

## 2. Latency percentiles from a histogram
```promql
histogram_quantile(0.95, sum by (le) (rate(caption_inference_duration_seconds_bucket[$__rate_interval])))
```
Prompt used: "PromQL p95 latency from histogram caption_inference_duration_seconds_bucket"

- Buckets are cumulative counts (`le` = "less than or equal"). Prometheus finds the bucket where the
  95th-percentile rank falls and **linearly interpolates** inside it.
- **By hand:** bucket rates for 100 images: le=1 -> 40, le=2 -> 80, le=3 -> 100.
  Rank = 0.95 x 100 = 95. It lies in (2, 3]. Between 80 and 100 there are 20 images; we need 15 of them.
  p95 = 2 + (3-2) x (95-80)/(100-80) = 2 + 0.75 = **2.75 s**.
- `sum by (le)` is required so bucket series from different `mode` labels are merged before the quantile.

## 3. Mean latency from a Summary
```promql
sum by (mode) (rate(caption_inference_summary_seconds_sum[$__rate_interval]))
  / sum by (mode) (rate(caption_inference_summary_seconds_count[$__rate_interval]))
```
- `_sum` = total seconds spent, `_count` = number of observations. Ratio of their rates = mean per image.
- **By hand:** over 60 s, `_sum` grows 30 and `_count` grows 12, so mean = 30/12 = **2.5 s/image**.
- Note: `prometheus_client`'s Python Summary exports only `_sum` and `_count` (no quantiles). The `_total`
  companions are the counters `caption_inference_busy_seconds_total`, `caption_output_chars_total`, `caption_upload_bytes_total`.

## 4. Error ratio
```promql
100 * sum(rate(caption_images_processed_total{status="error"}[5m]))
    / sum(rate(caption_images_processed_total[5m])) or vector(0)
```
- Numerator: error rate. Denominator: all images. `or vector(0)` shows 0 instead of "No data" when idle.
- **By hand:** 3 errors out of 60 images in the window = 3/60 x 100 = **5 %**.

## 5. CPU utilisation from node_exporter
```promql
100 * (1 - avg(rate(node_cpu_seconds_total{mode="idle"}[$__rate_interval])))
```
Prompt used: "PromQL overall CPU utilisation percent from node_cpu_seconds_total across all cores"

- `node_cpu_seconds_total{mode="idle"}` counts seconds each core spent idle. `rate` gives idle fraction per core
  (0-1); `avg` over cores gives machine-wide idle fraction; `1 - idle` = busy.
- **By hand:** 4 cores, idle fractions 0.9, 0.5, 0.3, 0.3 -> avg 0.5 -> busy = 100 x (1-0.5) = **50 %**.

## 6. Memory used
```promql
node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes
```
`MemAvailable` estimates memory usable without swapping (includes reclaimable cache), so subtracting it from the
total gives memory genuinely in use.

## 7. App share of total CPU (correlation panel)
```promql
caption_process_cpu_percent / scalar(count(count by (cpu) (node_cpu_seconds_total{mode="idle"})))
```
- `caption_process_cpu_percent` is psutil's per-process value where 100 = one full core (can reach 400 on 4 cores).
- `count by (cpu)(...)` creates one series per core; outer `count()` counts them = number of cores; `scalar()` turns it into a number.
- **By hand:** app at 200 on a 4-core machine -> 200/4 = **50 %** of whole-machine capacity.

## 8. Regexes used (all simple, documented per the attribution rule)
| Regex | Where | Meaning |
|---|---|---|
| `mode=~"user\|system\|iowait"` | CPU-by-mode panel | keep only these three CPU modes |
| `device!~"lo\|veth.*\|docker.*\|br-.*"` | Network panels | exclude loopback and container virtual NICs |
Prompt used: "PromQL regex to exclude loopback, docker and veth network interfaces"
