"""Telemetry and crowd analysis helpers for MetroGuard AI.

Calculates:
- Multi-person crowd density heatmap overlay
- Dynamic Threat Score (0 - 100) combining posture, zone dwell, and CBTC train ETA
- Platform surge bottleneck warning
"""

from __future__ import annotations

import cv2
import numpy as np


def compute_threat_score(
    is_fallen: bool,
    dwell_frames: int,
    inside_zone: bool,
    train_eta_seconds: float | None = 120.0,
) -> tuple[int, str]:
    """Compute composite dynamic threat score (0-100) and severity classification.
    
    Tiers:
    - Tier 1 (Caution): Brief edge crossing, Train ETA > 90s.
    - Tier 2 (Warning): Persistent dwell > 15-30 frames, Train ETA 45s - 90s.
    - Tier 3 (Critical): Track Fall OR zone intrusion with Train ETA < 45s.
    """
    eta = train_eta_seconds if train_eta_seconds is not None else 120.0
    
    if is_fallen:
        # Fallen person is an immediate Tier 3 emergency
        score = 98 if eta < 45 else 90
        return score, "critical"
        
    if not inside_zone:
        return 0, "nominal"
        
    score = 25  # baseline caution for being inside danger zone
    
    # Scale with dwell time
    if dwell_frames > 15:
        score += min(35, (dwell_frames - 15) * 2)
        
    # Scale with train proximity
    if eta <= 30:
        score += 45
    elif eta <= 60:
        score += 30
    elif eta <= 90:
        score += 15
        
    score = min(score, 100)
    
    if score >= 80 or (dwell_frames > 25 and eta < 45):
        return score, "critical"
    elif score >= 50 or dwell_frames >= 12:
        return score, "warning"
    else:
        return score, "caution"


def draw_crowd_heatmap(canvas: np.ndarray, detections_xyxy: np.ndarray, alpha: float = 0.4) -> np.ndarray:
    """Generate subtle Gaussian crowd density heatmap on the video canvas."""
    if len(detections_xyxy) == 0:
        return canvas
        
    h, w = canvas.shape[:2]
    density_map = np.zeros((h // 4, w // 4), dtype=np.float32)
    
    for box in detections_xyxy:
        cx = int((box[0] + box[2]) / 8)
        cy = int((box[1] + box[3]) / 8)
        if 0 <= cx < density_map.shape[1] and 0 <= cy < density_map.shape[0]:
            cv2.circle(density_map, (cx, cy), 18, 1.0, -1)
            
    if density_map.max() > 0:
        density_map = cv2.GaussianBlur(density_map, (25, 25), 0)
        density_map = density_map / (density_map.max() + 1e-6)
        heatmap = cv2.applyColorMap((density_map * 255).astype(np.uint8), cv2.COLORMAP_JET)
        heatmap = cv2.resize(heatmap, (w, h))
        
        # Blend only where there is significant density
        mask = cv2.resize(density_map, (w, h)) > 0.1
        canvas[mask] = cv2.addWeighted(canvas, 1 - alpha, heatmap, alpha, 0)[mask]
        
    return canvas
