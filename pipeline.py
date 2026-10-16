"""Streamlit-independent processing logic with all instrumentation.
Keeping it separate lets us unit-test the metrics without a browser."""
import io
import os
import time
import zipfile
from typing import Callable, Optional

from PIL import Image, UnidentifiedImageError

import metrics as m
from captioner import prepare_image

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
MAX_ZIP_IMAGES = int(os.getenv("MAX_ZIP_IMAGES", "100"))
MAX_ZIP_UNCOMPRESSED = int(os.getenv("MAX_ZIP_UNCOMPRESSED_MB", "200")) * 1024 * 1024


def _caption_one(captioner, data: bytes, mode: str, ip: str, sid: str):
    """Caption one image, recording per-image metrics. Returns (caption|None, error|None)."""
    m.IMAGE_BYTES.labels(mode).observe(len(data))
    m.UPLOAD_BYTES_TOTAL.labels(mode).inc(len(data))
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
        m.IMAGE_PIXELS_SUMMARY.labels(mode).observe(img.width * img.height)
        img = prepare_image(img)
    except (UnidentifiedImageError, OSError, ValueError):
        m.ERRORS.labels(mode, "bad_image").inc()
        m.IMAGES_PROCESSED.labels(mode, "error", ip).inc()
        return None, "not a valid image"

    t0 = time.perf_counter()
    try:
        text = captioner.caption(img)
    except Exception as exc:  # model failure
        m.ERRORS.labels(mode, "inference").inc()
        m.IMAGES_PROCESSED.labels(mode, "error", ip).inc()
        return None, f"inference failed: {exc}"
    dt = time.perf_counter() - t0

    m.INFERENCE_LATENCY.labels(mode).observe(dt)
    m.INFERENCE_SUMMARY.labels(mode).observe(dt)
    m.INFERENCE_SECONDS_TOTAL.labels(mode).inc(dt)
    m.CAPTION_LENGTH_SUMMARY.labels(mode).observe(len(text))
    m.CAPTION_CHARS_TOTAL.labels(mode).inc(len(text))
    m.IMAGES_PROCESSED.labels(mode, "success", ip).inc()
    m.LAST_INFERENCE_TS.set_to_current_time()
    return text, None


def process_single(captioner, data: bytes, ip: str, sid: str):
    mode = "single"
    m.SESSION_REQUESTS.labels(sid, mode).inc()
    m.ACTIVE_REQUESTS.labels(mode).inc()
    t0 = time.perf_counter()
    try:
        text, err = _caption_one(captioner, data, mode, ip, sid)
        m.REQUESTS.labels(mode, "success" if err is None else "error", ip).inc()
        return text, err
    finally:
        m.REQUEST_LATENCY.labels(mode).observe(time.perf_counter() - t0)
        m.ACTIVE_REQUESTS.labels(mode).dec()


def process_zip(
    captioner,
    zip_bytes: bytes,
    ip: str,
    sid: str,
    progress: Optional[Callable[[int, int, str], None]] = None,
):
    """Returns (rows, error). rows = [{'file','caption','error'}]."""
    mode = "bulk"
    m.SESSION_REQUESTS.labels(sid, mode).inc()
    m.ZIP_BYTES_SUMMARY.observe(len(zip_bytes))
    m.ACTIVE_REQUESTS.labels(mode).inc()
    t0 = time.perf_counter()
    status = "success"
    try:
        try:
            zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
        except zipfile.BadZipFile:
            status = "error"
            m.ERRORS.labels(mode, "bad_zip").inc()
            return [], "Not a valid ZIP file"

        names = []
        total = 0
        for info in zf.infolist():
            low = info.filename.lower()
            if info.is_dir() or "__macosx" in low or os.path.basename(low).startswith("."):
                continue
            if not low.endswith(IMAGE_EXTS):
                m.SKIPPED_FILES.labels("not_image").inc()
                continue
            total += info.file_size
            if total > MAX_ZIP_UNCOMPRESSED:  # zip-bomb guard
                m.SKIPPED_FILES.labels("too_large").inc()
                status = "error"
                m.ERRORS.labels(mode, "zip_too_large").inc()
                return [], f"ZIP expands beyond {MAX_ZIP_UNCOMPRESSED // 2**20} MB limit"
            names.append(info)
        if len(names) > MAX_ZIP_IMAGES:
            m.SKIPPED_FILES.labels("over_limit").inc(len(names) - MAX_ZIP_IMAGES)
            names = names[:MAX_ZIP_IMAGES]
        if not names:
            status = "error"
            m.ERRORS.labels(mode, "empty_zip").inc()
            return [], "No images found in the ZIP"

        m.BULK_BATCH_SIZE.observe(len(names))
        rows, n = [], len(names)
        m.BULK_QUEUE_IMAGES.set(n)
        m.BULK_PROGRESS.set(0)
        for i, info in enumerate(names, 1):
            text, err = _caption_one(captioner, zf.read(info), mode, ip, sid)
            rows.append({"file": info.filename, "caption": text or "", "error": err or ""})
            m.BULK_PROGRESS.set(i / n)
            m.BULK_QUEUE_IMAGES.set(n - i)
            if progress:
                progress(i, n, info.filename)
        if any(r["error"] for r in rows):
            status = "partial"
        return rows, None
    finally:
        m.BULK_PROGRESS.set(0)
        m.BULK_QUEUE_IMAGES.set(0)
        m.REQUESTS.labels(mode, status, ip).inc()
        m.REQUEST_LATENCY.labels(mode).observe(time.perf_counter() - t0)
        m.ACTIVE_REQUESTS.labels(mode).dec()
