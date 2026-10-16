"""CPU-only image captioning with Prometheus instrumentation.
Run:  streamlit run app.py      (UI on :8501, metrics on :8000/metrics)"""
import hashlib
import time

import pandas as pd
import streamlit as st

import metrics as m
from captioner import build_captioner
from pipeline import MAX_ZIP_IMAGES, process_single, process_zip

st.set_page_config(page_title="Image Captioning (CPU)", page_icon="🖼️", layout="wide")
m.start_metrics_server()


@st.cache_resource(show_spinner="Loading captioning model (first run downloads weights)...")
def get_captioner():
    t0 = time.perf_counter()
    cap = build_captioner()
    m.MODEL_LOAD_SECONDS.set(time.perf_counter() - t0)
    m.MODEL_PARAMS_BYTES.set(cap.weights_bytes)
    m.APP_INFO.labels(cap.name, cap.device).set(1)
    m.MODEL_LOADED.set(1)
    return cap


def client_info():
    """Best-effort client IP + short session id for metric labels."""
    ip = "unknown"
    try:
        headers = st.context.headers
        fwd = headers.get("X-Forwarded-For", "")
        ip = fwd.split(",")[0].strip() or getattr(st.context, "ip_address", None) or "local"
    except Exception:
        pass
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        ctx = get_script_run_ctx()
        sid = hashlib.sha1(ctx.session_id.encode()).hexdigest()[:8] if ctx else "na"
    except Exception:
        sid = "na"
    return ip, sid


captioner = get_captioner()
ip, sid = client_info()

st.title("🖼️ Image Captioning on CPU")
st.caption(f"Model: `{captioner.name}` · session `{sid}` · metrics at `:{m.METRICS_PORT}/metrics`")

tab_single, tab_bulk = st.tabs(["Single image", "Bulk (ZIP)"])

with tab_single:
    f = st.file_uploader("Upload an image", type=["jpg", "jpeg", "png", "bmp", "webp"], key="single")
    if f is not None:
        data = f.getvalue()
        st.image(data, width=360)
        if st.button("Generate caption", type="primary"):
            with st.spinner("Captioning..."):
                text, err = process_single(captioner, data, ip, sid)
            st.error(err) if err else st.success(text)

with tab_bulk:
    z = st.file_uploader("Upload a ZIP of images", type=["zip"], key="bulk")
    st.caption(f"Up to {MAX_ZIP_IMAGES} images per ZIP; non-image files are skipped.")
    if z is not None and st.button("Caption all images", type="primary"):
        bar = st.progress(0.0, text="Starting...")

        def on_progress(i, n, name):
            bar.progress(i / n, text=f"{i}/{n} · {name}")

        rows, err = process_zip(captioner, z.getvalue(), ip, sid, on_progress)
        if err:
            st.error(err)
        else:
            df = pd.DataFrame(rows)
            ok = int((df["error"] == "").sum())
            st.success(f"Done: {ok}/{len(df)} images captioned")
            st.dataframe(df, use_container_width=True)
            st.download_button("Download CSV", df.to_csv(index=False), "captions.csv", "text/csv")
