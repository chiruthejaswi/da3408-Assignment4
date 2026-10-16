"""Prometheus instrumentation for the image-captioning app.

Importing this module defines every metric exactly once per Python process
(Streamlit re-runs app.py on every interaction, but imported modules are cached).
Call start_metrics_server() once to expose /metrics on a separate port.
"""
import os
import threading
import time

import psutil
from prometheus_client import Counter, Gauge, Histogram, Summary, start_http_server

METRICS_PORT = int(os.getenv("METRICS_PORT", "8000"))

# ---------------------------------------------------------------- Counters
# Total images processed. Labels: Single vs Bulk, outcome, and client IP.
IMAGES_PROCESSED = Counter(
    "caption_images_processed",  # exposed as caption_images_processed_total
    "Images processed by the captioning pipeline",
    ["mode", "status", "client_ip"],
)
# One increment per user action (a bulk ZIP = 1 request, N images).
REQUESTS = Counter(
    "caption_requests",  # -> caption_requests_total
    "User requests (a single upload or a whole ZIP)",
    ["mode", "status", "client_ip"],
)
# Per-session activity (session_id is a short hash of the Streamlit session).
SESSION_REQUESTS = Counter(
    "caption_session_requests",  # -> caption_session_requests_total
    "Requests per Streamlit browser session",
    ["session_id", "mode"],
)
ERRORS = Counter(
    "caption_errors",  # -> caption_errors_total
    "Errors by type",
    ["mode", "error_type"],
)
SKIPPED_FILES = Counter(
    "caption_zip_skipped_files",  # -> caption_zip_skipped_files_total
    "Files inside a ZIP that were skipped",
    ["reason"],
)
# "_total" companions for the Summaries below (Summary itself only has _sum/_count).
INFERENCE_SECONDS_TOTAL = Counter(
    "caption_inference_busy_seconds",  # -> caption_inference_busy_seconds_total
    "Cumulative wall-clock seconds spent in model inference",
    ["mode"],
)
CAPTION_CHARS_TOTAL = Counter(
    "caption_output_chars",  # -> caption_output_chars_total
    "Cumulative characters generated",
    ["mode"],
)
UPLOAD_BYTES_TOTAL = Counter(
    "caption_upload_bytes",  # -> caption_upload_bytes_total
    "Cumulative bytes uploaded by users",
    ["mode"],
)

# ------------------------------------------------------------------ Gauges
ACTIVE_REQUESTS = Gauge(
    "caption_active_requests", "Requests currently being processed", ["mode"]
)
BULK_PROGRESS = Gauge(
    "caption_bulk_progress_ratio",
    "Progress (0-1) of the bulk job currently running",
)
BULK_QUEUE_IMAGES = Gauge(
    "caption_bulk_images_remaining", "Images still to process in the running bulk job"
)
MODEL_LOADED = Gauge("caption_model_loaded", "1 if the model is loaded in memory")
MODEL_PARAMS_BYTES = Gauge(
    "caption_model_weights_bytes", "Memory taken by model weights (parameters)"
)
MODEL_LOAD_SECONDS = Gauge("caption_model_load_seconds", "Time taken to load the model")
LAST_INFERENCE_TS = Gauge(
    "caption_last_inference_timestamp_seconds", "Unix time of last successful inference"
)
APP_START_TS = Gauge("caption_app_start_timestamp_seconds", "Unix time the app started")
APP_START_TS.set(time.time())
APP_INFO = Gauge(
    "caption_app_info", "Static app metadata (value is always 1)", ["model", "device"]
)

_proc = psutil.Process()
PROCESS_RSS = Gauge("caption_process_memory_bytes", "Resident memory (RSS) of the app process")
PROCESS_RSS.set_function(lambda: _proc.memory_info().rss)
PROCESS_CPU = Gauge(
    "caption_process_cpu_percent", "CPU percent used by the app process (100 = one core)"
)
PROCESS_CPU.set_function(lambda: _proc.cpu_percent(interval=None))
PROCESS_THREADS = Gauge("caption_process_threads", "Thread count of the app process")
PROCESS_THREADS.set_function(lambda: _proc.num_threads())

# -------------------------------------------------------------- Histograms
INFERENCE_LATENCY = Histogram(
    "caption_inference_duration_seconds",
    "Model inference time per image",
    ["mode"],
    buckets=(0.1, 0.25, 0.5, 1, 2, 3, 5, 8, 12, 20, 30, 60),
)
REQUEST_LATENCY = Histogram(
    "caption_request_duration_seconds",
    "End-to-end time for one request (a whole ZIP counts as one)",
    ["mode"],
    buckets=(0.5, 1, 2, 5, 10, 20, 30, 60, 120, 300, 600),
)
IMAGE_BYTES = Histogram(
    "caption_image_size_bytes",
    "Size of each uploaded image",
    ["mode"],
    buckets=(1e4, 5e4, 1e5, 5e5, 1e6, 2e6, 5e6, 1e7),
)
BULK_BATCH_SIZE = Histogram(
    "caption_bulk_batch_size_images",
    "Number of images per ZIP upload",
    buckets=(1, 5, 10, 20, 50, 100, 200),
)

# --------------------------------------------------------------- Summaries
# A Summary exports <name>_sum and <name>_count; rate(_sum)/rate(_count) = mean.
INFERENCE_SUMMARY = Summary(
    "caption_inference_summary_seconds", "Inference time per image (summary)", ["mode"]
)
CAPTION_LENGTH_SUMMARY = Summary(
    "caption_length_chars", "Characters per generated caption", ["mode"]
)
IMAGE_PIXELS_SUMMARY = Summary(
    "caption_image_pixels", "Pixels (width x height) per uploaded image", ["mode"]
)
ZIP_BYTES_SUMMARY = Summary("caption_zip_upload_bytes", "Size of uploaded ZIP archives")

_server_lock = threading.Lock()
_server_started = False


def start_metrics_server() -> None:
    """Expose /metrics on METRICS_PORT (idempotent, safe under Streamlit reruns)."""
    global _server_started
    with _server_lock:
        if not _server_started:
            _proc.cpu_percent(interval=None)  # prime the CPU counter
            start_http_server(METRICS_PORT)
            _server_started = True
