"""Generates grafana/dashboards/captioning_dashboard.json.
Run: python gen_dashboard.py
Palette = Okabe-Ito (colour-blind safe). Every multi-series panel also gets a distinct
line dash so series stay distinguishable in greyscale print / PDF.
"""
import json

DS = {"type": "prometheus", "uid": "prometheus"}
BLUE, ORANGE, GREEN, SKY, VERM, PURPLE, YELLOW = (
    "#0072B2", "#E69F00", "#009E73", "#56B4E9", "#D55E00", "#CC79A7", "#F0E442",
)
PALETTE = [BLUE, ORANGE, GREEN, VERM, SKY, PURPLE]
DASHES = [None, [10, 10], [2, 6], [10, 6, 2, 6], [14, 4], [4, 4]]  # solid, dash, dot, dash-dot...
RI = "$__rate_interval"
CPU_BUSY = f'100 * (1 - avg(rate(node_cpu_seconds_total{{mode="idle"}}[{RI}])))'
CORES = 'count(count by (cpu) (node_cpu_seconds_total{mode="idle"}))'

panels, _id, _x, _y, _rowh = [], [0], [0], [0], [0]


def nid():
    _id[0] += 1
    return _id[0]


def place(w, h):
    if _x[0] + w > 24:
        _x[0], _y[0], _rowh[0] = 0, _y[0] + _rowh[0], 0
    pos = {"x": _x[0], "y": _y[0], "w": w, "h": h}
    _x[0] += w
    _rowh[0] = max(_rowh[0], h)
    return pos


def newline():
    _y[0] += _rowh[0]
    _x[0], _rowh[0] = 0, 0


def row(title):
    newline()
    panels.append({"type": "row", "title": title, "collapsed": False, "id": nid(),
                   "gridPos": {"x": 0, "y": _y[0], "w": 24, "h": 1}, "panels": []})
    _y[0] += 1


def targets(items, instant=False, fmt=None):
    out = []
    for i, (expr, legend) in enumerate(items):
        t = {"refId": chr(65 + i), "datasource": DS, "expr": expr, "legendFormat": legend}
        if instant:
            t["instant"], t["range"] = True, False
        if fmt:
            t["format"] = fmt
        out.append(t)
    return out


def style_overrides(legends, right=None):
    """Colour + dash per series (matched by display name). right = {legend: (label, unit, min, max)}."""
    ov = []
    for i, name in enumerate(legends):
        props = [{"id": "color", "value": {"mode": "fixed", "fixedColor": PALETTE[i % len(PALETTE)]}}]
        d = DASHES[i % len(DASHES)]
        props.append({"id": "custom.lineStyle",
                      "value": {"fill": "dash", "dash": d} if d else {"fill": "solid"}})
        if right and name in right:
            label, unit, mn, mx = right[name]
            props += [{"id": "custom.axisPlacement", "value": "right"},
                      {"id": "custom.axisLabel", "value": label},
                      {"id": "unit", "value": unit}]
            if mn is not None:
                props.append({"id": "min", "value": mn})
            if mx is not None:
                props.append({"id": "max", "value": mx})
        ov.append({"matcher": {"id": "byName", "options": name}, "properties": props})
    return ov


def ts(title, sub, story, items, unit, ylabel, w=8, h=8, log=False, ymin=None, ymax=None,
       stack=False, right=None, xlabel="Time (local)"):
    legends = [l for _, l in items]
    custom = {
        "drawStyle": "line", "lineWidth": 2, "fillOpacity": 12 if stack else 0, "showPoints": "auto",
        "pointSize": 5, "spanNulls": True, "axisLabel": ylabel, "axisPlacement": "auto",
        "scaleDistribution": {"type": "log", "log": 10} if log else {"type": "linear"},
        "stacking": {"mode": "normal" if stack else "none", "group": "A"},
    }
    defaults = {"unit": unit, "custom": custom, "color": {"mode": "palette-classic"}}
    if ymin is not None:
        defaults["min"] = ymin
    if ymax is not None:
        defaults["max"] = ymax
    scale = "log10" if log else "linear"
    panels.append({
        "type": "timeseries", "id": nid(), "datasource": DS,
        "title": f"{title} — {sub} [y: {scale}]",
        "description": f"{story}\nX-axis: {xlabel}. Y-axis: {ylabel}, {scale} scale.",
        "gridPos": place(w, h), "targets": targets(items),
        "fieldConfig": {"defaults": defaults, "overrides": style_overrides(legends, right)},
        "options": {"legend": {"showLegend": len(items) > 1, "displayMode": "table" if len(items) > 1 else "list",
                               "placement": "bottom", "calcs": ["lastNotNull"]},
                    "tooltip": {"mode": "multi", "sort": "desc"}},
    })


def stat(title, sub, story, expr, unit, thresholds=None, w=3, h=4, mappings=None, decimals=None,
         reduce="lastNotNull", color_mode="background", legend=""):
    steps = thresholds or [(None, BLUE)]
    defaults = {"unit": unit, "color": {"mode": "thresholds"},
                "thresholds": {"mode": "absolute",
                               "steps": [{"color": c, "value": v} for v, c in steps]}}
    if mappings:
        defaults["mappings"] = mappings
    if decimals is not None:
        defaults["decimals"] = decimals
    panels.append({
        "type": "stat", "id": nid(), "datasource": DS, "title": f"{title} — {sub}",
        "description": story, "gridPos": place(w, h),
        "targets": targets([(expr, legend)]),
        "fieldConfig": {"defaults": defaults, "overrides": []},
        "options": {"reduceOptions": {"calcs": [reduce], "fields": "", "values": False},
                    "colorMode": color_mode, "graphMode": "area", "textMode": "value_and_name" if legend else "auto"},
    })


def gauge(title, sub, story, expr, unit, mn, mx, thresholds, w=6, h=7):
    panels.append({
        "type": "gauge", "id": nid(), "datasource": DS, "title": f"{title} — {sub}",
        "description": story, "gridPos": place(w, h), "targets": targets([(expr, "")]),
        "fieldConfig": {"defaults": {"unit": unit, "min": mn, "max": mx, "color": {"mode": "thresholds"},
                                     "thresholds": {"mode": "absolute",
                                                    "steps": [{"color": c, "value": v} for v, c in thresholds]}},
                        "overrides": []},
        "options": {"reduceOptions": {"calcs": ["lastNotNull"]}, "showThresholdMarkers": True,
                    "showThresholdLabels": False},
    })


UP_MAP = [{"type": "value", "options": {"0": {"text": "DOWN", "color": VERM},
                                          "1": {"text": "UP", "color": BLUE}}}]

# =================================================================== layout
panels.append({
    "type": "text", "id": nid(), "title": "How to read this dashboard", "gridPos": place(24, 3),
    "options": {"mode": "markdown", "content": (
        "**Story:** top → bottom goes from *is it alive?* to *how fast / how much?* to *which hardware resource "
        "is paying for it?* and finally *who is using it?*. Row 5 overlays application load on system metrics so "
        "a bulk-ZIP upload can be traced straight to its CPU / RAM footprint.  \n"
        "**Colours:** Okabe-Ito colour-blind-safe palette; series also differ by line dash, so print/PDF stays readable. "
        "Blue = healthy, orange = warning, vermillion = critical. Refresh: 5 s.")},
})

row("1 · Health at a glance")
stat("App status", "Prometheus scrape of the Streamlit app", "UP when Prometheus can scrape the app's /metrics endpoint; DOWN otherwise.",
     'up{job="captioning_app"}', "none", [(None, VERM), (1, BLUE)], mappings=UP_MAP)
stat("node_exporter", "system-metrics scrape", "UP when node_exporter (CPU/RAM/disk metrics) is reachable.",
     'up{job="node"}', "none", [(None, VERM), (1, BLUE)], mappings=UP_MAP)
stat("Alerts firing", "count of active Prometheus alerts", "Number of alerts currently in the firing state (see alert_rules.yml).",
     'count(ALERTS{alertstate="firing"}) or vector(0)', "none", [(None, BLUE), (1, VERM)])
stat("In-flight requests", "being processed right now", "Requests currently executing; on a CPU-only host more than ~3 means queuing.",
     "sum(caption_active_requests)", "none", [(None, BLUE), (3, ORANGE), (6, VERM)])
stat("Images captioned", "successful, over the selected time range", "Successful captions in the dashboard's time range, single + bulk.",
     'sum(increase(caption_images_processed_total{status="success"}[$__range]))', "short",
     [(None, BLUE)], decimals=0, reduce="lastNotNull")
stat("p95 inference latency", "per image, last 5 min", "95% of images finish faster than this. Orange > 3 s, red > 8 s (CPU model).",
     "histogram_quantile(0.95, sum by (le) (rate(caption_inference_duration_seconds_bucket[5m])))", "s",
     [(None, BLUE), (3, ORANGE), (8, VERM)], decimals=2)
stat("Error ratio", "failed ÷ all images, last 5 min", "Share of images that errored (bad file, corrupt ZIP member, model failure).",
     '100 * sum(rate(caption_images_processed_total{status="error"}[5m])) / sum(rate(caption_images_processed_total[5m])) or vector(0)',
     "percent", [(None, BLUE), (2, ORANGE), (10, VERM)], decimals=1)
stat("System CPU", "all cores, last 1 min", "Whole-machine CPU busy percentage from node_exporter.",
     CPU_BUSY.replace(RI, "1m"), "percent", [(None, BLUE), (70, ORANGE), (85, VERM)], decimals=0)

row("2 · Throughput and latency")
ts("Throughput", "images captioned per minute, by mode",
   "How fast the app turns images into captions. Bulk jobs show as plateaus; single uploads as small blips.",
   [(f'sum by (mode) (rate(caption_images_processed_total{{status="success"}}[{RI}])) * 60', "{{mode}}")],
   "suffix: img/min", "Images per minute", ymin=0)
ts("Inference latency percentiles", "p50 / p95 / p99 per image",
   "Spread of per-image model time. A widening gap between p50 and p99 means some images are much slower, typically under CPU contention.",
   [(f"histogram_quantile({q}, sum by (le) (rate(caption_inference_duration_seconds_bucket[{RI}])))", f"p{int(q*100)}")
    for q in (0.5, 0.95, 0.99)], "s", "Seconds per image", ymin=0)
ts("Mean inference time", "from Summary _sum ÷ _count, by mode",
   "Average model time per image, derived from the Summary's _sum and _count series (rate of sum over rate of count).",
   [(f"sum by (mode) (rate(caption_inference_summary_seconds_sum[{RI}])) / sum by (mode) (rate(caption_inference_summary_seconds_count[{RI}]))", "{{mode}}")],
   "s", "Seconds per image", ymin=0)
ts("Request duration p95", "end-to-end, single vs bulk",
   "Bulk requests take orders of magnitude longer than single ones (a ZIP is one request), so a log axis keeps both readable.",
   [(f"histogram_quantile(0.95, sum by (le, mode) (rate(caption_request_duration_seconds_bucket[{RI}])))", "{{mode}}")],
   "s", "Seconds per request", log=True)
ts("Requests per minute", "by mode and outcome",
   "User actions per minute (a ZIP counts once). 'partial' = ZIP with at least one failed image.",
   [(f"sum by (mode, status) (rate(caption_requests_total[{RI}])) * 60", "{{mode}} / {{status}}")],
   "suffix: req/min", "Requests per minute", ymin=0)
panels.append({
    "type": "heatmap", "id": nid(), "datasource": DS,
    "title": "Inference time distribution — histogram buckets over time [y: bucket upper bound, s]",
    "description": "Each column is a moment in time; brighter cells mean more images landed in that latency bucket. "
                   "Shows the full shape of latency, not just percentiles.\nX-axis: Time (local). Y-axis: Seconds per image, bucket boundaries.",
    "gridPos": place(8, 8),
    "targets": targets([("sum by (le) (increase(caption_inference_duration_seconds_bucket[$__interval]))", "{{le}}")], fmt="heatmap"),
    "fieldConfig": {"defaults": {"custom": {"scaleDistribution": {"type": "linear"}}}, "overrides": []},
    "options": {"calculate": False, "color": {"mode": "scheme", "scheme": "Viridis", "fill": "dark-orange",
                                              "scale": "exponential", "exponent": 0.5, "steps": 32},
                "yAxis": {"axisLabel": "Seconds per image (bucket upper bound)", "unit": "s"},
                "legend": {"show": True}, "tooltip": {"show": True, "yHistogram": False}, "cellGap": 1,
                "rowsFrame": {"layout": "auto"}},
})

row("3 · Application internals")
ts("In-flight requests", "active requests by mode",
   "Concurrency inside the app. Climbing values while throughput is flat indicate a backlog.",
   [("caption_active_requests", "{{mode}}")], "none", "Active requests", ymin=0)
gauge("Bulk job progress", "current ZIP, 0–100%", "Completion of the bulk ZIP being processed right now; 0 when idle.",
      "caption_bulk_progress_ratio", "percentunit", 0, 1, [(None, BLUE), (0.5, BLUE), (1, GREEN)], w=4)
ts("Bulk images remaining", "queue depth of running ZIP",
   "Images left in the active ZIP; falls linearly if inference time is steady.",
   [("caption_bulk_images_remaining", "remaining")], "suffix: img", "Images remaining", w=4, ymin=0)
ts("Errors", "per minute, by mode and type",
   "Which failures happen and where: bad_image, bad_zip, inference, zip_too_large, empty_zip.",
   [(f"sum by (mode, error_type) (rate(caption_errors_total[{RI}])) * 60", "{{mode}} / {{error_type}}")],
   "suffix: err/min", "Errors per minute", ymin=0, w=8)
ts("Upload volume", "bytes received per second, by mode",
   "Incoming image data. Large ZIPs raise memory and decode work even before inference starts.",
   [(f"sum by (mode) (rate(caption_upload_bytes_total[{RI}]))", "{{mode}}")], "Bps", "Bytes per second", ymin=0)
ts("Mean caption length", "characters, from Summary _sum ÷ _count",
   "Average generated caption length; sudden changes can reveal model or input drift.",
   [(f"sum by (mode) (rate(caption_length_chars_sum[{RI}])) / sum by (mode) (rate(caption_length_chars_count[{RI}]))", "{{mode}}")],
   "suffix: chars", "Characters per caption", ymin=0)
ts("App memory", "process RSS vs model weights",
   "Resident memory of the app process against the memory taken by model weights alone; the gap is runtime, images and buffers.",
   [("caption_process_memory_bytes", "App RSS"), ("caption_model_weights_bytes", "Model weights")],
   "bytes", "Memory (bytes)", ymin=0)

row("4 · System resources (node_exporter)")
ts("CPU utilisation by mode", "stacked share of all cores",
   "Where the CPU time goes. Inference should show up as 'user'; 'iowait' means disk is the bottleneck.",
   [(f'100 * avg by (mode) (rate(node_cpu_seconds_total{{mode=~"user|system|iowait"}}[{RI}]))', "{{mode}}")],
   "percent", "CPU time (% of all cores)", stack=True, ymin=0, ymax=100)
ts("Memory", "used vs total",
   "System RAM in use (total minus available) against installed RAM.",
   [("node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes", "Used"), ("node_memory_MemTotal_bytes", "Total")],
   "bytes", "Memory (bytes)", ymin=0)
gauge("Disk usage", "root filesystem", "Percentage of the root filesystem in use.",
      '100 * (1 - max(node_filesystem_avail_bytes{mountpoint="/",fstype!="tmpfs"} / node_filesystem_size_bytes{mountpoint="/",fstype!="tmpfs"}))',
      "percent", 0, 100, [(None, BLUE), (70, ORANGE), (90, VERM)], w=4)
ts("Disk I/O", "read vs write throughput",
   "Bytes per second hitting disk; spikes on first run reflect model-weight loading.",
   [(f"sum(rate(node_disk_read_bytes_total[{RI}]))", "read"), (f"sum(rate(node_disk_written_bytes_total[{RI}]))", "write")],
   "Bps", "Bytes per second", w=6, ymin=0)
ts("Network", "receive vs transmit",
   "Network traffic excluding loopback and container bridges.",
   [(f'sum(rate(node_network_receive_bytes_total{{device!~"lo|veth.*|docker.*|br-.*"}}[{RI}]))', "receive"),
    (f'sum(rate(node_network_transmit_bytes_total{{device!~"lo|veth.*|docker.*|br-.*"}}[{RI}]))', "transmit")],
   "Bps", "Bytes per second", w=6, ymin=0)
ts("Load average", "1-minute load vs core count",
   "Runnable processes against available cores; load above the core line means work is queuing for CPU.",
   [("node_load1", "load1"), (CORES, "CPU cores")], "none", "Load / cores", ymin=0)

row("5 · Correlation: application load vs hardware")
ts("Bulk load vs system CPU", "img/min (left) and CPU % (right)",
   "Story: when a bulk ZIP starts, throughput rises and system CPU climbs with it, showing inference is CPU-bound.",
   [(f'sum(rate(caption_images_processed_total{{mode="bulk"}}[{RI}])) * 60', "Bulk throughput (img/min)"),
    (CPU_BUSY, "System CPU (%)")],
   "suffix: img/min", "Images per minute", w=12, h=9, ymin=0,
   right={"System CPU (%)": ("System CPU (%)", "percent", 0, 100)})
ts("p95 latency vs system CPU", "seconds (left) and CPU % (right)",
   "Story: per-image latency rises as CPU saturates, typically when single uploads overlap a running bulk job.",
   [("histogram_quantile(0.95, sum by (le) (rate(caption_inference_duration_seconds_bucket[" + RI + "])))", "p95 latency (s)"),
    (CPU_BUSY, "System CPU (%)")],
   "s", "Seconds per image", w=12, h=9, ymin=0,
   right={"System CPU (%)": ("System CPU (%)", "percent", 0, 100)})
ts("In-flight requests vs system CPU", "requests (left) and CPU % (right)",
   "Story: concurrency drives CPU. Each extra in-flight request adds a step to CPU utilisation.",
   [("sum(caption_active_requests)", "Active requests"), (CPU_BUSY, "System CPU (%)")],
   "none", "Active requests", w=8, h=8, ymin=0,
   right={"System CPU (%)": ("System CPU (%)", "percent", 0, 100)})
ts("App share of CPU vs whole system", "percent of all cores",
   "Story: how much of the machine's CPU belongs to the app. Equal lines mean the app is the cause; a gap means other processes compete.",
   [(f"caption_process_cpu_percent / scalar({CORES})", "App process (%)"), (CPU_BUSY, "Whole system (%)")],
   "percent", "CPU (% of all cores)", w=8, h=8, ymin=0, ymax=100)
ts("App memory vs system memory", "bytes",
   "Story: the app's resident memory (steps up at model load, grows during bulk) against total system RAM in use.",
   [("caption_process_memory_bytes", "App RSS"),
    ("node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes", "System used")],
   "bytes", "Memory (bytes)", w=8, h=8, ymin=0)

row("6 · Clients")
panels.append({
    "type": "table", "id": nid(), "datasource": DS,
    "title": "Top clients — images processed per source IP [range total]",
    "description": "Which source IPs generated the most work in the selected time range, split by success/error.",
    "gridPos": place(8, 8),
    "targets": targets([('topk(10, sum by (client_ip, status) (increase(caption_images_processed_total[$__range])))', "")],
                       instant=True, fmt="table"),
    "transformations": [{"id": "organize", "options": {
        "excludeByName": {"Time": True},
        "renameByName": {"client_ip": "Client IP", "status": "Outcome", "Value": "Images"}}}],
    "fieldConfig": {"defaults": {"decimals": 0}, "overrides": []},
    "options": {"showHeader": True, "sortBy": [{"displayName": "Images", "desc": True}]},
})
panels.append({
    "type": "bargauge", "id": nid(), "datasource": DS,
    "title": "Requests per browser session — top 8 [range total]",
    "description": "Sessions (short hash of the Streamlit session id) ranked by number of requests in the selected range.",
    "gridPos": place(8, 8),
    "targets": targets([('topk(8, sum by (session_id) (increase(caption_session_requests_total[$__range])))', "{{session_id}}")], instant=True),
    "fieldConfig": {"defaults": {"unit": "suffix: req", "decimals": 0, "min": 0,
                                 "color": {"mode": "fixed", "fixedColor": BLUE}}, "overrides": []},
    "options": {"orientation": "horizontal", "displayMode": "basic", "showUnfilled": True,
                "reduceOptions": {"calcs": ["lastNotNull"]}},
})
ts("Requests by client IP", "top 5, per minute",
   "Traffic per source IP over time; reveals a single client dominating the box.",
   [(f"topk(5, sum by (client_ip) (rate(caption_requests_total[{RI}]))) * 60", "{{client_ip}}")],
   "suffix: req/min", "Requests per minute", ymin=0)

dashboard = {
    "uid": "captioning-obs", "title": "Image Captioning — Application & System Observability",
    "tags": ["captioning", "prometheus", "node_exporter"], "timezone": "browser", "editable": True,
    "refresh": "5s", "time": {"from": "now-15m", "to": "now"}, "schemaVersion": 39, "version": 1,
    "graphTooltip": 1, "panels": panels, "templating": {"list": []}, "annotations": {"list": []},
    "timepicker": {"refresh_intervals": ["5s", "10s", "30s", "1m"]},
}
out = "grafana/dashboards/captioning_dashboard.json"
json.dump(dashboard, open(out, "w"), indent=2, ensure_ascii=False)
print(f"wrote {out}: {len(panels)} panels")
