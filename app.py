from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import cv2
import streamlit as st
import yaml

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from metroguard.analysis import analyze_video  # noqa: E402

st.set_page_config(page_title="MetroGuard | Station Operations", page_icon="🚇", layout="wide")
st.markdown("""
<style>
.stApp { background: #090d12; color: #e7edf4; }
[data-testid="stMetric"] { background: #111922; padding: 14px; border: 1px solid #243342; border-radius: 8px; }
div[data-testid="stAlert"] { border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

st.title("METROGUARD AI")
st.caption("LOCAL VIDEO SAFETY REVIEW · OPERATOR DECISION SUPPORT · SIMULATED RESPONSE ACTIONS")

config_path = ROOT / "config" / "cameras.yaml"
with config_path.open(encoding="utf-8") as stream:
    camera = yaml.safe_load(stream)["default_camera"]

left, right = st.columns([1, 2.2], gap="large")
with left:
    st.subheader("Video source")
    sample_files = sorted((ROOT / "sample_videos").glob("*.mp4")) if (ROOT / "sample_videos").exists() else []
    source_mode = st.radio("Select source", ["Project sample", "Upload local MP4"], horizontal=True)
    uploaded = None
    selected_sample = None
    if source_mode == "Project sample":
        if sample_files:
            selected_sample = st.selectbox("Available clips", sample_files, format_func=lambda p: p.name)
        else:
            st.info("No sample clip is in this checkout. Upload a local MP4 to continue.")
    else:
        uploaded = st.file_uploader("Choose a local MP4", type=["mp4", "mov", "avi"])

    st.subheader("Camera calibration")
    st.caption(f"Camera profile: {camera.get('camera_id')} · {camera.get('use_case')}")
    zone_text = st.text_area("Danger zone points (normalized [x, y])", json.dumps(camera["danger_zone"], indent=2), height=150)
    dwell = st.number_input("Intrusion alert dwell (frames)", min_value=1, max_value=1000, value=int(camera["intrusion_dwell_frames"]))
    fall_angle = st.slider("Fall torso tilt threshold (degrees from vertical)", min_value=30, max_value=90, value=int(camera["fall_torso_angle_degrees"]))
    eta = st.number_input("Simulated train ETA (seconds)", min_value=0, max_value=900, value=int(camera["train_eta_seconds"]))
    start = st.button("▶  Analyze video", type="primary", use_container_width=True)

with right:
    st.subheader("Live review")
    feed = st.empty()
    metrics = st.empty()
    status = st.empty()

if start:
    try:
        zone_points = json.loads(zone_text)
        run_camera = {**camera, "danger_zone": zone_points, "intrusion_dwell_frames": dwell,
                      "fall_torso_angle_degrees": fall_angle, "train_eta_seconds": eta}
        model_path = Path(os.environ.get("METROGUARD_MODEL", ROOT / "yolov8n-pose.pt"))
        if not model_path.is_file():
            st.error(f"YOLO pose weights were not found at {model_path}. Place the supplied weights there or set METROGUARD_MODEL.")
            st.stop()
        if selected_sample is not None:
            video_path = selected_sample
        elif uploaded is not None:
            upload_dir = ROOT / "output" / "uploads"
            upload_dir.mkdir(parents=True, exist_ok=True)
            video_path = upload_dir / Path(uploaded.name).name
            video_path.write_bytes(uploaded.getbuffer())
        else:
            st.error("Select a sample clip or upload a video first.")
            st.stop()

        progress = st.progress(0.0, text="Loading local model and video…")
        def update_frame(frame_index: int, total: int, frame, stats: dict):
            if total:
                progress.progress(min(frame_index / total, 1.0), text=f"Analyzing frame {frame_index:,} / {total:,}")
            feed.image(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), channels="RGB", use_container_width=True)
            metrics.metric("Inference speed", f"{stats['fps']:.1f} FPS", f"{stats['people']} people in current frame")

        summary = analyze_video(video_path, model_path, run_camera, ROOT / "output" / "events", update_frame)
        progress.progress(1.0, text="Analysis complete")
        status.success(f"Processed {summary['frames']:,} frames at {summary['processing_fps']:.1f} FPS. {len(summary['events'])} event(s) saved locally.")
        st.session_state["metroguard_summary"] = summary
    except (ValueError, json.JSONDecodeError, OSError) as exc:
        st.error(str(exc))

summary = st.session_state.get("metroguard_summary")
if summary:
    st.divider()
    st.subheader("Incident log")
    if summary["events"]:
        for event in reversed(summary["events"]):
            label = f"{event['severity'].upper()} · {event['event_type'].replace('_', ' ').title()} · track {event['track_id']} · frame {event['frame_index']}"
            with st.expander(label):
                event_dir = ROOT / "output" / "events" / event["event_id"]
                col_img1, col_img2 = st.columns(2)
                with col_img1:
                    if (event_dir / "evidence.jpg").is_file():
                        st.image(str(event_dir / "evidence.jpg"), caption="1. CCTV Evidence Frame")
                with col_img2:
                    if (event_dir / "pose_overlay.jpg").is_file():
                        st.image(str(event_dir / "pose_overlay.jpg"), caption="2. Skeletal Keypoint Diagnostic")
                        
                if (event_dir / "announcement.mp3").is_file():
                    st.caption("🔊 Autonomous PA Voice Broadcast:")
                    st.audio(str(event_dir / "announcement.mp3"))
                    
                if (event_dir / "report.md").is_file():
                    st.caption("🤖 OpenAI Incident Copilot SOP Report:")
                    st.markdown((event_dir / "report.md").read_text(encoding="utf-8"))
                    
                st.caption("Telemetry Record:")
                st.json(event)
                if event.get("severity") == "critical":
                    st.error("🚨 CRITICAL ALERT: TRAIN HOLD & EMERGENCY MARSHAL DISPATCH TRIGGERED (SIMULATED).")

    else:
        st.info("No persistent intrusion or fall event was detected in this clip.")

st.caption("Prototype only. Camera zones and thresholds need per-view calibration. Alerts require human verification; no signaling or PA system is connected.")

