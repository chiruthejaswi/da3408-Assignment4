# Image Captioning Observability (DA3408 A4)

Streamlit + BLIP (CPU) image-captioning app instrumented with `prometheus_client`, scraped by Prometheus
together with `node_exporter`, alerts via Alertmanager, and a colour-blind-safe Grafana dashboard.

```
Streamlit :8501 --(metrics :8000)--> Prometheus :9090 --> Grafana :3000
node_exporter :9100 ----------------^        |
                                             +--> Alertmanager :9093 --> alert_receiver.py :5001
```

## Prerequisites
Python 3.10+, Docker Desktop / Docker Engine with Compose, ~2 GB free disk (model weights ~1 GB).

## Step 1: Python environment
```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# CPU-only torch (smaller download), optional:
# pip install torch --index-url https://download.pytorch.org/whl/cpu
```

## Step 2: Make test data
```bash
python make_test_data.py           # creates test_data/images and bulk_5/20/50.zip
```

## Step 3: Start the monitoring stack
```bash
docker compose up -d
docker compose ps                  # 4 containers should be Up
```
Check http://localhost:9090/targets: `node` and `prometheus` should be UP (`captioning_app` is DOWN until step 4).


## Step 4: Run the app
```bash
streamlit run app.py
```
- UI: http://localhost:8501 (first run downloads the model, so wait)
- Metrics: http://localhost:8000/metrics (open it and search for `caption_`)

Check http://localhost:9090/targets: all three jobs should now be UP.

## Step 5: Alert receiver (optional but shows the pipeline works)
```bash
python alert_receiver.py
```
Test an alert: stop Streamlit for ~20 s; `CaptioningAppDown` fires and appears in this terminal and at
http://localhost:9090/alerts and http://localhost:9093.

## Step 6: Open Grafana
http://localhost:3000 (admin / admin). The datasource and dashboard are auto-provisioned:
**Dashboards -> Image Captioning, Application & System Observability** (refresh 5 s).




## Metric inventory (python side)
| Type | Metric | Labels |
|---|---|---|
| Counter | `caption_images_processed_total` | mode, status, client_ip |
| Counter | `caption_requests_total` | mode, status, client_ip |
| Counter | `caption_session_requests_total` | session_id, mode |
| Counter | `caption_errors_total`, `caption_zip_skipped_files_total` | mode/error_type, reason |
| Counter | `caption_inference_busy_seconds_total`, `caption_output_chars_total`, `caption_upload_bytes_total` | mode |
| Gauge | `caption_active_requests` | mode |
| Gauge | `caption_bulk_progress_ratio`, `caption_bulk_images_remaining` | none |
| Gauge | `caption_process_memory_bytes`, `caption_process_cpu_percent`, `caption_process_threads` | none (live callbacks) |
| Gauge | `caption_model_loaded`, `caption_model_weights_bytes`, `caption_model_load_seconds`, `caption_last_inference_timestamp_seconds`, `caption_app_info` | model, device on app_info |
| Histogram | `caption_inference_duration_seconds`, `caption_request_duration_seconds`, `caption_image_size_bytes` | mode |
| Histogram | `caption_bulk_batch_size_images` | none |
| Summary | `caption_inference_summary_seconds`, `caption_length_chars`, `caption_image_pixels` (`_sum`, `_count`) | mode |
| Summary | `caption_zip_upload_bytes` | none |

## Notes
- See `docs/promql_notes.md` for each key query
