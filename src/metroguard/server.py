"""FastAPI Backend Server for MetroGuard AI.

Provides:
- MJPEG Real-Time Stream with HUD overlays (Skeletal landmarks, Danger polygon, Crowd Heatmap).
- Dynamic telemetry & status endpoints (CBTC Train ETA, FPS, Tracked Persons, Interlock State).
- Public Address (PA) TTS triggering & audio streaming.
- Incident archive retrieval (snapshots, pose overlay, telemetry JSON, reports).
- Copilot chat endpoint powered by gpt-4o-mini with offline fallback.
- Configuration update endpoints (danger polygon interactive calibration).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from metroguard.crowd_threat import compute_threat_score, draw_crowd_heatmap
from metroguard.copilot import copilot_query_chat, generate_incident_report
from metroguard.pa_agent import compose_announcement_text, generate_speech_sync
from metroguard.analysis import torso_angle_degrees, _foot_point

app = FastAPI(title="MetroGuard AI Tactical Server", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CONFIG_PATH = ROOT / "config" / "cameras.yaml"
OUTPUT_EVENTS = ROOT / "output" / "events"
OUTPUT_EVENTS.mkdir(parents=True, exist_ok=True)
SAMPLE_VIDEO = ROOT / "sample_videos" / "fall_test.mp4"
MODEL_PATH = ROOT / "yolov8n-pose.pt"


class SystemState:
    def __init__(self):
        self.lock = threading.Lock()
        self.running = False
        self.paused = False
        self.current_frame_bytes: bytes | None = None
        self.current_frame_index = 0
        self.fps = 0.0
        self.people_count = 0
        self.train_eta_seconds = 120.0
        self.train_speed_kmh = 58.0
        self.train_id = "METRO-104 (Outbound)"
        self.signal_interlock = "NORMAL"  # "NORMAL", "HOLD_REQUESTED", "EMERGENCY_HOLD"
        self.threat_score = 0
        self.threat_tier = "nominal"  # "nominal", "caution", "warning", "critical"
        self.active_breach_detected = False
        self.active_alert_message = ""
        self.latest_event: dict[str, Any] | None = None
        self.events_log: list[dict[str, Any]] = []
        
        # Display settings
        self.show_danger_zone = True
        self.show_skeleton = True
        self.show_heatmap = False
        self.danger_zone: list[list[float]] = [
            [0.05, 0.70],
            [0.95, 0.70],
            [0.99, 0.99],
            [0.01, 0.99],
        ]
        self.fall_torso_angle = 60.0
        self.dwell_threshold = 12
        self.openai_api_key = os.environ.get("OPENAI_API_KEY", "")

    def to_dict(self):
        with self.lock:
            has_brain = bool(self.openai_api_key and len(self.openai_api_key) > 8)
            return {
                "running": self.running,
                "paused": self.paused,
                "fps": round(self.fps, 1),
                "people_count": self.people_count,
                "train_eta_seconds": max(0, int(self.train_eta_seconds)),
                "train_speed_kmh": round(self.train_speed_kmh, 1),
                "train_id": self.train_id,
                "signal_interlock": self.signal_interlock,
                "threat_score": self.threat_score,
                "threat_tier": self.threat_tier,
                "active_breach": self.active_breach_detected,
                "active_alert_message": self.active_alert_message,
                "current_frame": self.current_frame_index,
                "danger_zone": self.danger_zone,
                "show_danger_zone": self.show_danger_zone,
                "show_skeleton": self.show_skeleton,
                "show_heatmap": self.show_heatmap,
                "has_brain": has_brain,
                "brain_model": "gpt-4o-mini (Reasoning Engine)",
                "vision_engine": "YOLOv8-Pose Nano (Visual Eyes)",
            }




state = SystemState()


def load_initial_config():
    if CONFIG_PATH.is_file():
        with CONFIG_PATH.open(encoding="utf-8") as f:
            cfg = yaml.safe_load(f).get("default_camera", {})
            state.danger_zone = cfg.get("danger_zone", state.danger_zone)
            state.fall_torso_angle = float(cfg.get("fall_torso_angle_degrees", 60.0))
            state.dwell_threshold = int(cfg.get("intrusion_dwell_frames", 12))
            state.train_eta_seconds = float(cfg.get("train_eta_seconds", 120.0))


load_initial_config()


def video_worker_loop():
    """Background loop that executes YOLOv8-pose inference on CCTV stream."""
    from ultralytics import YOLO
    
    video_source = str(SAMPLE_VIDEO)
    if not Path(video_source).is_file():
        return
        
    model = YOLO(str(MODEL_PATH))
    cap = cv2.VideoCapture(video_source)
    
    inside_frames = {}
    event_cooldown = {}
    fps_history = []
    
    state.running = True
    
    while state.running:
        if state.paused:
            time.sleep(0.05)
            continue
            
        loop_start = time.perf_counter()
        ok, frame = cap.read()
        if not ok:
            # Loop video seamlessly for continuous tactical demo
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            inside_frames.clear()
            continue
            
        state.current_frame_index += 1
        h, w = frame.shape[:2]
        
        # Scale train ETA dynamically based on passage of time
        with state.lock:
            if state.signal_interlock != "EMERGENCY_HOLD":
                state.train_eta_seconds = max(5.0, state.train_eta_seconds - 0.04)
            else:
                state.train_speed_kmh = max(0.0, state.train_speed_kmh - 2.5)

        # Polygon conversion
        zone_arr = (np.array(state.danger_zone) * np.array([w, h])).astype(np.int32)
        
        # Run YOLO Pose with ByteTrack
        results = model.track(frame, persist=True, tracker="bytetrack.yaml", verbose=False)[0]
        
        canvas = frame.copy()
        
        # Heatmap overlay if enabled
        if state.show_heatmap and results.boxes is not None:
            boxes_xyxy = results.boxes.xyxy.cpu().numpy()
            canvas = draw_crowd_heatmap(canvas, boxes_xyxy, alpha=0.45)
            
        # Danger zone polygon rendering
        if state.show_danger_zone:
            # Color based on threat tier
            zone_color = (0, 0, 255) if state.threat_tier == "critical" else (
                (0, 165, 255) if state.threat_tier == "warning" else (
                    (0, 220, 255) if state.threat_tier == "caution" else (30, 220, 100)
                )
            )
            cv2.polylines(canvas, [zone_arr], True, zone_color, 2)
            poly_overlay = canvas.copy()
            cv2.fillPoly(poly_overlay, [zone_arr], zone_color)
            canvas = cv2.addWeighted(poly_overlay, 0.18, canvas, 0.82, 0)

        boxes = results.boxes
        max_threat = 0
        tier_candidate = "nominal"
        active_intruders = 0
        
        if boxes is not None and results.keypoints is not None:
            xyxy = boxes.xyxy.cpu().numpy()
            ids = boxes.id.cpu().numpy().astype(int) if boxes.id is not None else np.arange(len(xyxy))
            points = results.keypoints.xy.cpu().numpy()
            confs = results.keypoints.conf.cpu().numpy() if results.keypoints.conf is not None else np.ones(points.shape[:2])
            
            with state.lock:
                state.people_count = len(xyxy)

            # Draw skeletons if enabled
            if state.show_skeleton:
                # Use Ultralytics built-in skeleton plotter onto a layer
                pose_layer = results.plot(boxes=False, labels=False)
                canvas = cv2.addWeighted(pose_layer, 0.5, canvas, 0.5, 0)
                
            for box, track_id, keypts, conf in zip(xyxy, ids, points, confs):
                foot = _foot_point(box, keypts, conf)
                inside = cv2.pointPolygonTest(zone_arr, foot, False) >= 0
                if inside:
                    inside_frames[track_id] = inside_frames.get(track_id, 0) + 1
                    active_intruders += 1
                else:
                    inside_frames[track_id] = 0
                    
                angle = torso_angle_degrees(keypts, conf)
                is_fallen = inside and angle is not None and angle >= state.fall_torso_angle
                
                score, sev = compute_threat_score(is_fallen, inside_frames[track_id], inside, state.train_eta_seconds)
                if score > max_threat:
                    max_threat = score
                    tier_candidate = sev
                    
                box_color = (0, 0, 255) if sev == "critical" else (
                    (0, 165, 255) if sev == "warning" else (
                        (0, 220, 255) if sev == "caution" else (50, 220, 80)
                    )
                )
                cv2.rectangle(canvas, (int(box[0]), int(box[1])), (int(box[2]), int(box[3])), box_color, 2)
                cv2.circle(canvas, foot, 5, box_color, -1)
                
                label = f"ID #{track_id} [{sev.upper()}]"
                if angle is not None:
                    label += f" {angle:.0f}°"
                cv2.putText(canvas, label, (int(box[0]), max(22, int(box[1]) - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, box_color, 2)

                # Event trigger & evidence archiving
                if sev in ("warning", "critical"):
                    now_ts = time.time()
                    last_time = event_cooldown.get((track_id, sev), 0)
                    if now_ts - last_time > 15.0:  # 15s debounce
                        event_cooldown[(track_id, sev)] = now_ts
                        event_kind = "track_fall" if is_fallen else "persistent_intrusion"
                        event_id = f"EVT-{datetime.now(timezone.utc).strftime('%H%M%S')}-{track_id}"
                        event_dir = OUTPUT_EVENTS / event_id
                        event_dir.mkdir(parents=True, exist_ok=True)
                        
                        cv2.imwrite(str(event_dir / "evidence.jpg"), canvas)
                        cv2.imwrite(str(event_dir / "pose_overlay.jpg"), results.plot())
                        
                        event_data = {
                            "event_id": event_id,
                            "event_type": event_kind,
                            "severity": sev,
                            "threat_score": score,
                            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                            "camera_id": "Platform 2 - North Edge",
                            "track_id": int(track_id),
                            "frame_index": state.current_frame_index,
                            "dwell_frames": inside_frames[track_id],
                            "torso_tilt_degrees": angle,
                            "train_eta_seconds": int(state.train_eta_seconds),
                            "train_hold_asserted": (sev == "critical"),
                        }
                        
                        # Generate PA Script & Speech Audio
                        pa_script = compose_announcement_text(
                            event_type=event_kind,
                            track_id=int(track_id),
                            platform="Platform 2",
                            train_id="Metro 104",
                            train_eta_seconds=int(state.train_eta_seconds),
                        )
                        event_data["announcement_script"] = pa_script
                        generate_speech_sync(pa_script, event_dir / "announcement.mp3")
                        event_data["announcement_audio"] = f"/api/events/{event_id}/announcement.mp3"
                        
                        # Generate Copilot SOP Report (OpenAI GPT-4o-mini Brain with Offline Fallback)
                        report_md = generate_incident_report(event_data, api_key=state.openai_api_key)
                        (event_dir / "report.md").write_text(report_md, encoding="utf-8")
                        event_data["report_markdown"] = report_md
                        
                        (event_dir / "event.json").write_text(json.dumps(event_data, indent=2), encoding="utf-8")
                        
                        with state.lock:
                            state.latest_event = event_data
                            state.events_log.insert(0, event_data)
                            if len(state.events_log) > 50:
                                state.events_log.pop()
                            if sev == "critical":
                                state.signal_interlock = "EMERGENCY_HOLD"
                                state.active_alert_message = f"CRITICAL: Track fall on Platform 2. Interlock engaged."
                            else:
                                state.active_alert_message = f"WARNING: Passenger boundary loiter #{track_id}."
        
        with state.lock:
            state.threat_score = max_threat
            state.threat_tier = tier_candidate
            state.active_breach_detected = (max_threat >= 50)
            
        # Draw tactical HUD banner at top of canvas
        hud_bar_color = (0, 0, 180) if state.threat_tier == "critical" else (
            (0, 140, 220) if state.threat_tier == "warning" else (20, 25, 30)
        )
        cv2.rectangle(canvas, (0, 0), (w, 36), hud_bar_color, -1)
        hud_text = f"METROGUARD AI | {state.threat_tier.upper()} ({state.threat_score}%) | TRAIN ETA: {int(state.train_eta_seconds)}s | INTERLOCK: {state.signal_interlock}"
        cv2.putText(canvas, hud_text, (14, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

        # Encode JPEG for live MJPEG stream
        ret, buffer = cv2.imencode(".jpg", canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if ret:
            with state.lock:
                state.current_frame_bytes = buffer.tobytes()
                
        dur = max(time.perf_counter() - loop_start, 1e-4)
        fps_history.append(1.0 / dur)
        if len(fps_history) > 15:
            fps_history.pop(0)
        with state.lock:
            state.fps = sum(fps_history) / len(fps_history)
            
        # Cap demo loop at ~25 FPS
        time.sleep(max(0.0, 0.04 - dur))

    cap.release()


# Launch video processing worker thread on startup
worker_thread = threading.Thread(target=video_worker_loop, daemon=True)
worker_thread.start()


@app.get("/api/status")
def get_status():
    """Return live system telemetry and CBTC status."""
    return state.to_dict()


@app.get("/api/events")
def get_events():
    """Return list of recent safety incident events."""
    with state.lock:
        return {"events": state.events_log}


@app.get("/api/events/{event_id}/evidence.jpg")
def get_event_evidence(event_id: str):
    file_path = OUTPUT_EVENTS / event_id / "evidence.jpg"
    if file_path.is_file():
        return FileResponse(file_path, media_type="image/jpeg")
    raise HTTPException(status_code=404, detail="Evidence frame not found")


@app.get("/api/events/{event_id}/pose_overlay.jpg")
def get_event_pose(event_id: str):
    file_path = OUTPUT_EVENTS / event_id / "pose_overlay.jpg"
    if file_path.is_file():
        return FileResponse(file_path, media_type="image/jpeg")
    raise HTTPException(status_code=404, detail="Pose overlay frame not found")


@app.get("/api/events/{event_id}/announcement.mp3")
def get_event_audio(event_id: str):
    file_path = OUTPUT_EVENTS / event_id / "announcement.mp3"
    if file_path.is_file():
        return FileResponse(file_path, media_type="audio/mpeg")
    raise HTTPException(status_code=404, detail="Audio announcement file not found")


@app.get("/api/stream")
def mjpeg_stream():
    """Provide real-time MJPEG live stream of CCTV with tactical overlays."""
    def generate():
        while True:
            frame_bytes = state.current_frame_bytes
            if frame_bytes is not None:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
                )
            time.sleep(0.04)

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


class TogglesModel(BaseModel):
    show_danger_zone: bool | None = None
    show_skeleton: bool | None = None
    show_heatmap: bool | None = None
    danger_zone: list[list[float]] | None = None


@app.post("/api/settings")
def update_settings(payload: TogglesModel):
    with state.lock:
        if payload.show_danger_zone is not None:
            state.show_danger_zone = payload.show_danger_zone
        if payload.show_skeleton is not None:
            state.show_skeleton = payload.show_skeleton
        if payload.show_heatmap is not None:
            state.show_heatmap = payload.show_heatmap
        if payload.danger_zone is not None:
            state.danger_zone = payload.danger_zone
    return {"status": "ok", "settings": state.to_dict()}


class InterlockAction(BaseModel):
    action: str  # "ACKNOWLEDGE", "RESET", "EMERGENCY_HOLD"


@app.post("/api/interlock")
def handle_interlock(payload: InterlockAction):
    with state.lock:
        if payload.action == "EMERGENCY_HOLD":
            state.signal_interlock = "EMERGENCY_HOLD"
            state.threat_tier = "critical"
            state.threat_score = 99
        elif payload.action in ("ACKNOWLEDGE", "RESET"):
            state.signal_interlock = "NORMAL"
            state.threat_tier = "nominal"
            state.train_speed_kmh = 58.0
            state.active_alert_message = ""
    return {"status": "ok", "signal_interlock": state.signal_interlock}


class OpenAIConfigModel(BaseModel):
    api_key: str


@app.post("/api/config/openai")
def configure_openai(payload: OpenAIConfigModel):
    key = payload.api_key.strip()
    with state.lock:
        state.openai_api_key = key
        os.environ["OPENAI_API_KEY"] = key
    return {
        "status": "ok",
        "has_brain": bool(key),
        "message": "OpenAI Neural Reasoning Brain connected securely on backend." if key else "Operating in offline rule-based mode."
    }



@app.post("/api/copilot/chat")
def chat_copilot(req: CopilotChatRequest):
    """Interactive incident copilot Q&A endpoint."""
    with state.lock:
        recent = list(state.events_log[:5])
        key = state.openai_api_key
    answer = copilot_query_chat(req.query, recent, api_key=key)
    return {"reply": answer}



class TriggerPAModel(BaseModel):
    message: str | None = None


@app.post("/api/pa/broadcast")
def trigger_pa(payload: TriggerPAModel):
    """Trigger on-demand PA broadcast announcement."""
    msg = payload.message or "Attention Platform 2 passengers: Please stand clear of the platform edge."
    audio_path = OUTPUT_EVENTS / "manual_broadcast.mp3"
    generate_speech_sync(msg, audio_path)
    return {
        "status": "broadcast_sent",
        "message": msg,
        "audio_url": "/api/events/manual/broadcast.mp3" if audio_path.is_file() else None,
    }


from fastapi.staticfiles import StaticFiles

WEB_DIST = ROOT / "web" / "dist"
if WEB_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(WEB_DIST), html=True), name="static_web")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("metroguard.server:app", host="0.0.0.0", port=8000, reload=False)

