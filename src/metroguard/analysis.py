"""Local YOLO pose analysis and event evidence packaging."""

from __future__ import annotations

import json
import math
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np
from ultralytics import YOLO


def torso_angle_degrees(keypoints: np.ndarray, confidence: np.ndarray) -> float | None:
    """Return torso tilt away from vertical using COCO shoulder and hip points."""
    # COCO indices: left/right shoulder 5/6, left/right hip 11/12.
    if len(keypoints) < 13 or np.any(confidence[[5, 6, 11, 12]] < 0.25):
        return None
    shoulder = keypoints[[5, 6]].mean(axis=0)
    hip = keypoints[[11, 12]].mean(axis=0)
    dx, dy = shoulder - hip
    return math.degrees(math.atan2(abs(float(dx)), abs(float(dy)) + 1e-6))


def _foot_point(box: np.ndarray, keypoints: np.ndarray, confidence: np.ndarray) -> tuple[int, int]:
    # COCO ankle indices 15/16. Fall back to bounding-box bottom center.
    ankles = [i for i in (15, 16) if i < len(keypoints) and confidence[i] >= 0.25]
    if ankles:
        point = keypoints[ankles].mean(axis=0)
        return int(point[0]), int(point[1])
    return int((box[0] + box[2]) / 2), int(box[3])


def analyze_video(
    video_path: str | Path,
    model_path: str | Path,
    camera: dict[str, Any],
    output_dir: str | Path,
    progress: Callable[[int, int, np.ndarray, dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Analyze a video, save event snapshots/JSON, and return a compact summary."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError("Could not open this video. Check that it is a readable MP4 with a supported codec.")

    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    zone = np.array(camera["danger_zone"], dtype=np.float32)
    if zone.ndim != 2 or zone.shape[0] < 3 or zone.shape[1] != 2 or not np.isfinite(zone).all():
        cap.release()
        raise ValueError("Danger zone must contain at least three normalized [x, y] points.")
    if np.any(zone < 0) or np.any(zone > 1):
        cap.release()
        raise ValueError("Danger zone points must be between 0.0 and 1.0.")
    zone_px = (zone * np.array([width, height])).astype(np.int32)

    model = YOLO(str(model_path))
    inside_frames: dict[int, int] = defaultdict(int)
    events: list[dict[str, Any]] = []
    event_tracks: set[tuple[int, str]] = set()
    frame_index = 0
    started = time.perf_counter()
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frame_index += 1
            result = model.track(frame, persist=True, tracker="bytetrack.yaml", verbose=False)[0]
            canvas = frame.copy()
            cv2.polylines(canvas, [zone_px], True, (30, 190, 255), 2)
            overlay = canvas.copy()
            cv2.fillPoly(overlay, [zone_px], (20, 130, 30))
            canvas = cv2.addWeighted(overlay, 0.15, canvas, 0.85, 0)

            boxes = result.boxes
            if boxes is not None and result.keypoints is not None:
                xyxy = boxes.xyxy.cpu().numpy()
                ids = boxes.id.cpu().numpy().astype(int) if boxes.id is not None else np.arange(len(xyxy))
                points = result.keypoints.xy.cpu().numpy()
                confs = result.keypoints.conf.cpu().numpy() if result.keypoints.conf is not None else np.ones(points.shape[:2])
                for box, track_id, keypoints, confidence in zip(xyxy, ids, points, confs):
                    foot = _foot_point(box, keypoints, confidence)
                    inside = cv2.pointPolygonTest(zone_px, foot, False) >= 0
                    inside_frames[track_id] = inside_frames[track_id] + 1 if inside else 0
                    angle = torso_angle_degrees(keypoints, confidence)
                    fallen = inside and angle is not None and angle >= float(camera.get("fall_torso_angle_degrees", 60))
                    
                    train_eta = camera.get("train_eta_seconds", 120)
                    from metroguard.crowd_threat import compute_threat_score
                    threat_score, severity = compute_threat_score(fallen, inside_frames[track_id], inside, train_eta)
                    
                    color = (0, 0, 255) if severity == "critical" else (0, 165, 255) if severity == "warning" else (0, 220, 255) if severity == "caution" else (50, 200, 50)
                    cv2.rectangle(canvas, (int(box[0]), int(box[1])), (int(box[2]), int(box[3])), color, 2)
                    cv2.circle(canvas, foot, 5, color, -1)
                    label = f"ID {track_id} | {severity.upper()} ({threat_score}%)"
                    if angle is not None:
                        label += f" | tilt {angle:.0f}°"
                    cv2.putText(canvas, label, (int(box[0]), max(20, int(box[1]) - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                    
                    if severity in ("warning", "critical"):
                        kind = "track_fall" if fallen else "persistent_intrusion"
                        key = (track_id, kind)
                        if key not in event_tracks:
                            event_tracks.add(key)
                            event_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
                            event_dir = output_root / event_id
                            event_dir.mkdir(parents=True, exist_ok=True)
                            
                            # Save evidence frame
                            cv2.imwrite(str(event_dir / "evidence.jpg"), canvas)
                            
                            # Save skeletal pose overlay frame
                            pose_canvas = result.plot()
                            cv2.imwrite(str(event_dir / "pose_overlay.jpg"), pose_canvas)
                            
                            event = {
                                "event_id": event_id,
                                "event_type": kind,
                                "severity": severity,
                                "threat_score": threat_score,
                                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                                "camera_id": camera.get("camera_id", "local-video"),
                                "track_id": int(track_id),
                                "frame_index": frame_index,
                                "video_time_seconds": frame_index / fps if fps > 0 else None,
                                "dwell_frames": inside_frames[track_id],
                                "torso_tilt_degrees": angle,
                                "train_eta_seconds": train_eta,
                                "response_mode": "simulated",
                                "evidence_image": "evidence.jpg",
                                "pose_overlay_image": "pose_overlay.jpg",
                                "train_hold_asserted": (severity == "critical"),
                            }
                            
                            # Generate PA speech audio file
                            from metroguard.pa_agent import compose_announcement_text, generate_speech_sync
                            script = compose_announcement_text(
                                event_type=kind,
                                track_id=int(track_id),
                                platform=camera.get("camera_id", "Platform 2"),
                                train_id="Train 104",
                                train_eta_seconds=train_eta,
                            )
                            event["announcement_script"] = script
                            audio_path = event_dir / "announcement.mp3"
                            if generate_speech_sync(script, audio_path):
                                event["announcement_audio"] = "announcement.mp3"
                                
                            # Generate Copilot 3-bullet SOP incident report
                            from metroguard.copilot import generate_incident_report
                            report_md = generate_incident_report(event)
                            (event_dir / "report.md").write_text(report_md, encoding="utf-8")
                            event["report_markdown"] = report_md
                            
                            (event_dir / "event.json").write_text(json.dumps(event, indent=2), encoding="utf-8")
                            events.append(event)


            elapsed = max(time.perf_counter() - started, 1e-6)
            stats = {"fps": frame_index / elapsed, "people": int(len(boxes)) if boxes is not None else 0, "frame": frame_index}
            if progress:
                progress(frame_index, total, canvas, stats)
    finally:
        cap.release()

    elapsed = max(time.perf_counter() - started, 1e-6)
    return {"frames": frame_index, "source_fps": fps, "resolution": [width, height], "processing_fps": frame_index / elapsed, "events": events}

